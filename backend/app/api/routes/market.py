from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.data.manager import data_manager
from app.core.analysis.market_info import MarketAnalyzer
from app.config import get_config
from app.utils.logger import setup_logger

config = get_config()
logger = setup_logger(__name__)
router = APIRouter()

market_analyzer = MarketAnalyzer()


@router.get("/symbols")
async def get_available_symbols(
    source: Optional[str] = Query(None, description="Data source: binance, yahoo, csv")
) -> Dict[str, Any]:
    """Get list of available symbols from data sources"""
    try:
        # Get symbols from all sources or specific source
        if source:
            if not config.is_source_available(source):
                raise HTTPException(
                    status_code=400,
                    detail=f"Source '{source}' not available in current mode"
                )
            
            # Initialize data manager if needed
            if not data_manager._initialized:
                await data_manager.initialize()
            
            if source not in data_manager.sources:
                raise HTTPException(
                    status_code=400,
                    detail=f"Source '{source}' failed to initialize"
                )
            
            symbols = await data_manager.sources[source].get_symbols()
            return {
                "source": source,
                "symbols": symbols,
                "total": len(symbols)
            }
        
        else:
            # Get from all sources
            all_symbols = await data_manager.get_available_symbols()
            
            # Format response
            total_symbols = sum(len(symbols) for symbols in all_symbols.values())
            
            return {
                "sources": all_symbols,
                "total_symbols": total_symbols,
                "available_sources": list(all_symbols.keys())
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_symbols(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum results")
) -> List[Dict[str, Any]]:
    """Search for symbols across all data sources"""
    try:
        query = query.upper()
        all_symbols = await data_manager.get_available_symbols()
        
        results = []
        
        for source, symbols in all_symbols.items():
            for symbol in symbols:
                if query in symbol:
                    results.append({
                        "symbol": symbol,
                        "source": source,
                        "type": _guess_symbol_type(symbol)
                    })
                    
                    if len(results) >= limit:
                        break
            
            if len(results) >= limit:
                break
        
        return results
        
    except Exception as e:
        logger.error(f"Error searching symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info/{symbol}")
async def get_market_info(
    symbol: str,
    source: Optional[str] = Query(None, description="Preferred data source")
) -> Dict[str, Any]:
    """Get comprehensive market information for a symbol"""
    try:
        # Fetch recent data
        df = await data_manager.fetch_ohlcv(
            symbol=symbol,
            timeframe="1h",
            limit=24*7,  # 7 days of hourly data
            source_name=source
        )
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
        
        # Analyze market
        market_info = await market_analyzer.analyze(symbol, df)
        
        # Add source information
        market_info["data_source"] = df.attrs.get('source', 'unknown')
        
        return market_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting market info for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    source: Optional[str] = Query(None, description="Preferred data source")
) -> Dict[str, Any]:
    """Get current ticker data for a symbol"""
    try:
        ticker = await data_manager.fetch_ticker(symbol, source_name=source)
        
        return {
            "symbol": symbol,
            "ticker": ticker,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting ticker for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare")
async def compare_symbols(
    symbols: str = Query(..., description="Comma-separated symbols to compare"),
    timeframe: str = Query("1d", description="Timeframe for comparison"),
    metric: str = Query("performance", description="Metric to compare: performance, volatility, volume")
) -> Dict[str, Any]:
    """Compare multiple symbols"""
    try:
        symbol_list = [s.strip() for s in symbols.split(",")]
        
        if len(symbol_list) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 symbols for comparison")
        
        comparison_data = {}
        
        for symbol in symbol_list:
            try:
                # Fetch data
                df = await data_manager.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=100
                )
                
                if not df.empty:
                    # Calculate metrics
                    if metric == "performance":
                        # Calculate returns
                        start_price = df['close'].iloc[0]
                        end_price = df['close'].iloc[-1]
                        performance = ((end_price - start_price) / start_price) * 100
                        
                        comparison_data[symbol] = {
                            "value": float(performance),
                            "start_price": float(start_price),
                            "end_price": float(end_price),
                            "label": f"{performance:.2f}%"
                        }
                        
                    elif metric == "volatility":
                        # Calculate volatility
                        returns = df['close'].pct_change().dropna()
                        volatility = returns.std() * np.sqrt(252) * 100  # Annualized
                        
                        comparison_data[symbol] = {
                            "value": float(volatility),
                            "label": f"{volatility:.2f}%"
                        }
                        
                    elif metric == "volume":
                        # Average volume
                        avg_volume = df['volume'].mean()
                        
                        comparison_data[symbol] = {
                            "value": float(avg_volume),
                            "label": f"{avg_volume:,.0f}"
                        }
                        
            except Exception as e:
                logger.warning(f"Error comparing {symbol}: {e}")
                comparison_data[symbol] = {
                    "value": 0,
                    "label": "Error",
                    "error": str(e)
                }
        
        # Sort by value
        sorted_symbols = sorted(
            comparison_data.items(),
            key=lambda x: x[1]["value"],
            reverse=True
        )
        
        return {
            "metric": metric,
            "timeframe": timeframe,
            "data": dict(sorted_symbols),
            "winner": sorted_symbols[0][0] if sorted_symbols else None,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending_symbols(
    source: str = Query("binance", description="Data source"),
    metric: str = Query("volume", description="Trending metric: volume, gainers, losers"),
    limit: int = Query(10, description="Number of results")
) -> List[Dict[str, Any]]:
    """Get trending symbols based on various metrics"""
    try:
        if not config.is_source_available(source):
            raise HTTPException(
                status_code=400,
                detail=f"Source '{source}' not available in current mode"
            )
        
        # This would typically connect to real-time data feeds
        # For now, return sample data based on available symbols
        symbols = await data_manager.get_available_symbols()
        
        if source not in symbols:
            raise HTTPException(status_code=400, detail=f"No symbols for source '{source}'")
        
        trending = []
        
        # Sample implementation - in production this would use real metrics
        sample_symbols = symbols[source][:min(limit * 2, len(symbols[source]))]
        
        for symbol in sample_symbols:
            try:
                # Fetch recent data
                df = await data_manager.fetch_ohlcv(
                    symbol=symbol,
                    timeframe="1h",
                    limit=24,
                    source_name=source
                )
                
                if not df.empty:
                    change_24h = ((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]) * 100
                    volume_24h = df['volume'].sum()
                    
                    trending.append({
                        "symbol": symbol,
                        "change_24h": float(change_24h),
                        "volume_24h": float(volume_24h),
                        "price": float(df['close'].iloc[-1])
                    })
                    
            except Exception as e:
                logger.warning(f"Error processing {symbol}: {e}")
                continue
        
        # Sort based on metric
        if metric == "gainers":
            trending.sort(key=lambda x: x["change_24h"], reverse=True)
        elif metric == "losers":
            trending.sort(key=lambda x: x["change_24h"])
        else:  # volume
            trending.sort(key=lambda x: x["volume_24h"], reverse=True)
        
        return trending[:limit]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trending symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _guess_symbol_type(symbol: str) -> str:
    """Guess the type of symbol (crypto, stock, etc.)"""
    if "/" in symbol or any(symbol.endswith(suffix) for suffix in ["USDT", "BTC", "ETH", "BNB"]):
        return "crypto"
    elif symbol.startswith("^"):
        return "index"
    elif len(symbol) <= 5 and symbol.isalpha():
        return "stock"
    else:
        return "unknown"