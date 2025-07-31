from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd

from app.data.manager import data_manager
from app.core.indicators.base import IndicatorManager
from app.core.signals.generator import SignalGenerator
from app.core.analysis.market_info import MarketAnalyzer
from app.config import get_config
from app.utils.cache import cached, usage_tracker
from app.utils.logger import setup_logger

config = get_config()
logger = setup_logger(__name__)
router = APIRouter()

# Initialize components
indicator_manager = IndicatorManager()
signal_generator = SignalGenerator()
market_analyzer = MarketAnalyzer()


@router.get("/{symbol}")
async def get_chart_data(
    symbol: str,
    interval: str = Query("1h", description="Timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w"),
    indicators: Optional[str] = Query(None, description="Comma-separated indicator names"),
    limit: Optional[int] = Query(500, description="Number of candles to return"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
) -> Dict[str, Any]:
    """
    Get comprehensive chart data including OHLCV, indicators, signals, and market info.
    This is the main endpoint that provides everything needed for the chart.
    """
    try:
        # Track API usage
        await usage_tracker.track_api_call(
            f"/chart/{symbol}",
            {"interval": interval, "indicators": indicators}
        )
        
        # Parse dates if provided
        start_time = None
        end_time = None
        if start_date:
            start_time = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end_time = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Fetch OHLCV data
        ohlcv_df = await data_manager.fetch_ohlcv(
            symbol=symbol,
            timeframe=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        if ohlcv_df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
        
        # Parse requested indicators
        requested_indicators = None
        if indicators:
            requested_indicators = [ind.strip() for ind in indicators.split(",")]
            
            # Check indicator limit in non-personal mode
            if not config.PERSONAL_MODE and len(requested_indicators) > config.MAX_INDICATORS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Maximum {config.MAX_INDICATORS} indicators allowed in free tier"
                )
        
        # Calculate indicators
        indicator_results = await indicator_manager.calculate_all(
            ohlcv_df,
            indicator_names=requested_indicators
        )
        
        # Generate trading signals
        signals = await signal_generator.generate_signals(symbol, interval)
        
        # Get market information
        market_info = await market_analyzer.analyze(symbol, ohlcv_df)
        
        # Prepare response
        response = {
            "symbol": symbol,
            "interval": interval,
            "data_source": ohlcv_df.attrs.get('source', 'unknown'),
            "candles": _format_ohlcv(ohlcv_df),
            "indicators": _format_indicators(indicator_results),
            "signals": [signal.to_dict() for signal in signals],
            "market_info": market_info,
            "metadata": {
                "total_candles": len(ohlcv_df),
                "start_date": ohlcv_df.index[0].isoformat() if len(ohlcv_df) > 0 else None,
                "end_date": ohlcv_df.index[-1].isoformat() if len(ohlcv_df) > 0 else None,
                "latest_price": float(ohlcv_df['close'].iloc[-1]) if len(ohlcv_df) > 0 else None,
                "indicators_calculated": list(indicator_results.keys()),
                "signals_generated": len(signals)
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chart data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/indicators")
async def get_available_indicators(symbol: str) -> Dict[str, Any]:
    """Get list of available indicators for a symbol"""
    try:
        # Check if symbol is valid
        validation = await data_manager.validate_symbol(symbol)
        
        if not any(validation.values()):
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
        
        # Get all available indicators
        indicators = indicator_manager.list_indicators()
        
        # Filter based on mode
        if not config.PERSONAL_MODE:
            # In SaaS mode, show limited set
            allowed_indicators = ['sma', 'ema', 'rsi', 'macd', 'bollinger_bands']
            indicators = [ind for ind in indicators if ind['name'] in allowed_indicators]
        
        return {
            "symbol": symbol,
            "available_indicators": indicators,
            "max_indicators": config.MAX_INDICATORS or "unlimited",
            "mode": "personal" if config.PERSONAL_MODE else "saas"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting indicators for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/signals")
async def get_signals_only(
    symbol: str,
    timeframe: str = Query("1h", description="Primary timeframe for analysis")
) -> Dict[str, Any]:
    """Get only trading signals for a symbol"""
    try:
        # Generate signals
        signals = await signal_generator.generate_signals(symbol, timeframe)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "signals": [signal.to_dict() for signal in signals],
            "total_signals": len(signals),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating signals for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _format_ohlcv(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Format OHLCV DataFrame for API response"""
    candles = []
    
    for timestamp, row in df.iterrows():
        candles.append({
            "time": int(timestamp.timestamp()) if isinstance(timestamp, pd.Timestamp) else timestamp,
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": float(row['volume'])
        })
    
    return candles


def _format_indicators(indicator_results: Dict) -> Dict[str, Any]:
    """Format indicator results for API response"""
    formatted = {}
    
    for name, result in indicator_results.items():
        formatted[name] = result.to_dict()
    
    return formatted