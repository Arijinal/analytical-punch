from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.backtest.engine import BacktestEngine
from app.config import get_config
from app.utils.logger import setup_logger

config = get_config()
logger = setup_logger(__name__)
router = APIRouter()

# Initialize backtest engine
backtest_engine = BacktestEngine()


class BacktestRequest(BaseModel):
    """Request model for backtesting"""
    symbol: str
    strategy: str
    start_date: str
    end_date: str
    initial_capital: float = 10000
    position_size: float = 0.1  # 10% per trade
    stop_loss: Optional[float] = 0.02  # 2% stop loss
    take_profit: Optional[float] = 0.04  # 4% take profit
    timeframe: str = "1h"
    commission: float = 0.001  # 0.1% commission
    slippage: float = 0.0005  # 0.05% slippage
    
    class Config:
        schema_extra = {
            "example": {
                "symbol": "BTC/USDT",
                "strategy": "momentum_punch",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 10000,
                "position_size": 0.1,
                "stop_loss": 0.02,
                "take_profit": 0.04,
                "timeframe": "1h"
            }
        }


@router.post("/run")
async def run_backtest(request: BacktestRequest) -> Dict[str, Any]:
    """Run a backtest with specified parameters"""
    try:
        # Check if backtesting is enabled
        if not config.ENABLE_BACKTESTING:
            raise HTTPException(
                status_code=403,
                detail="Backtesting not available in current mode"
            )
        
        # Parse dates
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        # Validate date range
        max_days = config.MAX_BACKTEST_DAYS
        if (end_date - start_date).days > max_days:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum backtest period is {max_days} days"
            )
        
        # Run backtest
        results = await backtest_engine.run(
            symbol=request.symbol,
            strategy=request.strategy,
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.initial_capital,
            position_size=request.position_size,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            timeframe=request.timeframe,
            commission=request.commission,
            slippage=request.slippage
        )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies")
async def get_available_strategies() -> List[Dict[str, Any]]:
    """Get list of available backtest strategies"""
    strategies = [
        {
            "name": "momentum_punch",
            "description": "Trend following with momentum confirmation",
            "parameters": ["rsi_period", "macd_fast", "macd_slow", "macd_signal"],
            "risk_profile": "medium"
        },
        {
            "name": "value_punch",
            "description": "Mean reversion at extremes",
            "parameters": ["rsi_oversold", "rsi_overbought", "bollinger_period", "bollinger_std"],
            "risk_profile": "low-medium"
        },
        {
            "name": "breakout_punch",
            "description": "Volatility expansion trades",
            "parameters": ["atr_period", "breakout_threshold", "volume_threshold"],
            "risk_profile": "high"
        },
        {
            "name": "trend_punch",
            "description": "Strong directional moves with multiple confirmations",
            "parameters": ["ichimoku_settings", "sma_periods", "min_trend_strength"],
            "risk_profile": "medium-high"
        }
    ]
    
    return strategies


@router.post("/optimize")
async def optimize_strategy(
    symbol: str = Body(...),
    strategy: str = Body(...),
    start_date: str = Body(...),
    end_date: str = Body(...),
    optimization_target: str = Body("sharpe_ratio", description="Metric to optimize: sharpe_ratio, total_return, win_rate")
) -> Dict[str, Any]:
    """Optimize strategy parameters"""
    try:
        if not config.PERSONAL_MODE:
            raise HTTPException(
                status_code=403,
                detail="Strategy optimization only available in personal mode"
            )
        
        # Parse dates
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Run optimization
        optimal_params = await backtest_engine.optimize(
            symbol=symbol,
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            optimization_target=optimization_target
        )
        
        return optimal_params
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error optimizing strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{backtest_id}")
async def get_backtest_results(backtest_id: str) -> Dict[str, Any]:
    """Get detailed results of a specific backtest"""
    try:
        results = await backtest_engine.get_results(backtest_id)
        
        if not results:
            raise HTTPException(status_code=404, detail="Backtest not found")
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting backtest results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_backtest_history(
    limit: int = Query(10, description="Number of recent backtests to return")
) -> List[Dict[str, Any]]:
    """Get history of recent backtests"""
    try:
        if not config.PERSONAL_MODE:
            raise HTTPException(
                status_code=403,
                detail="Backtest history only available in personal mode"
            )
        
        history = await backtest_engine.get_history(limit=limit)
        
        return history
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting backtest history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_strategies(
    symbol: str = Body(...),
    strategies: List[str] = Body(..., description="List of strategies to compare"),
    start_date: str = Body(...),
    end_date: str = Body(...),
    initial_capital: float = Body(10000)
) -> Dict[str, Any]:
    """Compare multiple strategies on the same data"""
    try:
        if len(strategies) > 5:
            raise HTTPException(
                status_code=400,
                detail="Maximum 5 strategies for comparison"
            )
        
        # Parse dates
        start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Run backtests for each strategy
        comparison_results = {}
        
        for strategy in strategies:
            try:
                results = await backtest_engine.run(
                    symbol=symbol,
                    strategy=strategy,
                    start_date=start_date_dt,
                    end_date=end_date_dt,
                    initial_capital=initial_capital
                )
                
                comparison_results[strategy] = {
                    "total_return": results["metrics"]["total_return"],
                    "sharpe_ratio": results["metrics"]["sharpe_ratio"],
                    "max_drawdown": results["metrics"]["max_drawdown"],
                    "win_rate": results["metrics"]["win_rate"],
                    "total_trades": results["metrics"]["total_trades"]
                }
                
            except Exception as e:
                logger.warning(f"Error backtesting {strategy}: {e}")
                comparison_results[strategy] = {"error": str(e)}
        
        # Determine best strategy
        best_strategy = max(
            [s for s in comparison_results.items() if "error" not in s[1]],
            key=lambda x: x[1]["sharpe_ratio"],
            default=(None, {})
        )[0]
        
        return {
            "symbol": symbol,
            "period": f"{start_date} to {end_date}",
            "results": comparison_results,
            "best_strategy": best_strategy,
            "comparison_metrics": ["total_return", "sharpe_ratio", "max_drawdown", "win_rate"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))