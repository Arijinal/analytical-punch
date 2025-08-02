from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import json
from typing import Dict, Set
import logging

from app.config import get_config
from app.api.routes import chart, market, backtest, trading
from app.api.websocket import ConnectionManager
from app.services.realtime_updater import RealTimeUpdater
from app.utils.logger import setup_logger
from app.database.trading_db import initialize_trading_database

# Setup
config = get_config()
logger = setup_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Analytical Punch",
    description="Professional Trading Analysis Platform",
    version="1.0.0",
    docs_url="/docs" if config.DEBUG else None,
    redoc_url="/redoc" if config.DEBUG else None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
manager = ConnectionManager()

# Real-time price updater
realtime_updater = RealTimeUpdater(manager)

# Include routers
app.include_router(chart.router, prefix=f"{config.API_PREFIX}/chart", tags=["chart"])
app.include_router(market.router, prefix=f"{config.API_PREFIX}/market", tags=["market"])
app.include_router(backtest.router, prefix=f"{config.API_PREFIX}/backtest", tags=["backtest"])
app.include_router(trading.router, prefix=f"{config.API_PREFIX}/trading", tags=["trading"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info(f"Starting Analytical Punch in {'PERSONAL' if config.PERSONAL_MODE else 'SaaS'} mode")
    logger.info(f"Available data sources: {config.AVAILABLE_SOURCES}")
    logger.info(f"Max indicators: {config.MAX_INDICATORS or 'Unlimited'}")
    logger.info(f"Historical days: {config.HISTORICAL_DAYS}")
    
    # Initialize trading database
    try:
        await initialize_trading_database()
        logger.info("Trading database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize trading database: {e}")
    
    # Start real-time update subscription checker
    asyncio.create_task(realtime_updater.check_subscriptions())
    logger.info("Real-time price updater started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Analytical Punch")
    await realtime_updater.shutdown()
    await manager.disconnect_all()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Analytical Punch",
        "version": "1.0.0",
        "mode": "personal" if config.PERSONAL_MODE else "saas",
        "api_docs": "/docs" if config.DEBUG else None
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mode": "personal" if config.PERSONAL_MODE else "saas",
        "features": {
            "max_indicators": config.MAX_INDICATORS or "unlimited",
            "historical_days": config.HISTORICAL_DAYS,
            "ml_signals": config.ENABLE_ML_SIGNALS,
            "backtesting": config.ENABLE_BACKTESTING,
            "sources": config.AVAILABLE_SOURCES
        }
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "subscribe":
                symbol = message.get("symbol")
                interval = message.get("interval", "1h")
                await manager.subscribe(websocket, symbol, interval)
                
                # Send confirmation
                await websocket.send_json({
                    "type": "subscribed",
                    "symbol": symbol,
                    "interval": interval
                })
                
            elif message.get("type") == "unsubscribe":
                symbol = message.get("symbol")
                await manager.unsubscribe(websocket, symbol)
                
                # Send confirmation
                await websocket.send_json({
                    "type": "unsubscribed",
                    "symbol": symbol
                })
                
            elif message.get("type") == "ping":
                # Heartbeat
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Error handlers
@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Resource not found"}
    )


@app.exception_handler(500)
async def internal_error(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower()
    )