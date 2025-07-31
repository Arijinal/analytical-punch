import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class MarketAnalyzer:
    """Analyzes market data to provide comprehensive market information"""
    
    async def analyze(self, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze market data and return comprehensive metrics
        
        Returns:
            Dict containing price changes, volume analysis, technical summary, etc.
        """
        if df.empty:
            return self._empty_analysis(symbol)
        
        try:
            # Current price and basic info
            current_price = float(df['close'].iloc[-1])
            current_volume = float(df['volume'].iloc[-1])
            
            # Price changes
            price_changes = self._calculate_price_changes(df)
            
            # Volume analysis
            volume_analysis = self._analyze_volume(df)
            
            # Price statistics
            price_stats = self._calculate_price_statistics(df)
            
            # Volatility metrics
            volatility_metrics = self._calculate_volatility(df)
            
            # Support and resistance levels
            key_levels = self._identify_key_levels(df)
            
            # Technical summary
            technical_summary = self._generate_technical_summary(
                df, price_changes, volume_analysis, volatility_metrics
            )
            
            # Market structure
            market_structure = self._analyze_market_structure(df)
            
            return {
                "symbol": symbol,
                "current_price": current_price,
                "current_volume": current_volume,
                "price_changes": price_changes,
                "volume_analysis": volume_analysis,
                "price_statistics": price_stats,
                "volatility": volatility_metrics,
                "key_levels": key_levels,
                "technical_summary": technical_summary,
                "market_structure": market_structure,
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market for {symbol}: {e}")
            return self._empty_analysis(symbol)
    
    def _empty_analysis(self, symbol: str) -> Dict[str, Any]:
        """Return empty analysis structure"""
        return {
            "symbol": symbol,
            "current_price": 0,
            "current_volume": 0,
            "price_changes": {},
            "volume_analysis": {},
            "price_statistics": {},
            "volatility": {},
            "key_levels": {},
            "technical_summary": {
                "trend": "unknown",
                "strength": 0,
                "recommendation": "No data available"
            },
            "market_structure": {},
            "last_update": datetime.now().isoformat()
        }
    
    def _calculate_price_changes(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate price changes over various periods"""
        current_price = df['close'].iloc[-1]
        changes = {}
        
        # Define periods to check
        periods = {
            "1h": 1,
            "4h": 4,
            "24h": 24,
            "7d": 24 * 7,
            "30d": 24 * 30
        }
        
        for period_name, hours in periods.items():
            try:
                # Calculate how many candles back to look
                # This assumes we know the timeframe from the DataFrame
                candles_back = self._estimate_candles_for_period(df, hours)
                
                if candles_back < len(df):
                    past_price = df['close'].iloc[-candles_back-1]
                    change = current_price - past_price
                    change_pct = (change / past_price) * 100
                    
                    changes[f"change_{period_name}"] = float(change)
                    changes[f"change_{period_name}_pct"] = float(change_pct)
                else:
                    changes[f"change_{period_name}"] = 0
                    changes[f"change_{period_name}_pct"] = 0
                    
            except Exception as e:
                logger.warning(f"Error calculating {period_name} change: {e}")
                changes[f"change_{period_name}"] = 0
                changes[f"change_{period_name}_pct"] = 0
        
        return changes
    
    def _analyze_volume(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze volume patterns and metrics"""
        volume = df['volume']
        
        # Basic volume stats
        volume_sma_20 = volume.rolling(window=20).mean()
        current_volume = volume.iloc[-1]
        avg_volume = volume_sma_20.iloc[-1] if not pd.isna(volume_sma_20.iloc[-1]) else volume.mean()
        
        # Volume trend
        volume_trend = "neutral"
        if len(volume) > 20:
            recent_avg = volume.iloc[-5:].mean()
            older_avg = volume.iloc[-20:-5].mean()
            if recent_avg > older_avg * 1.2:
                volume_trend = "increasing"
            elif recent_avg < older_avg * 0.8:
                volume_trend = "decreasing"
        
        # Detect volume spikes
        volume_spike = current_volume > avg_volume * 2
        
        # Volume-price correlation
        if len(df) > 20:
            price_change = df['close'].pct_change()
            volume_change = volume.pct_change()
            correlation = price_change.corr(volume_change)
        else:
            correlation = 0
        
        return {
            "current_volume": float(current_volume),
            "average_volume": float(avg_volume),
            "volume_ratio": float(current_volume / avg_volume) if avg_volume > 0 else 1,
            "volume_trend": volume_trend,
            "volume_spike": volume_spike,
            "volume_price_correlation": float(correlation) if not pd.isna(correlation) else 0,
            "24h_volume": float(volume.iloc[-24:].sum()) if len(volume) >= 24 else float(volume.sum())
        }
    
    def _calculate_price_statistics(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate various price statistics"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Different period statistics
        stats = {}
        
        for period in [24, 24*7, 24*30]:  # 24h, 7d, 30d
            candles = self._estimate_candles_for_period(df, period)
            if candles < len(df):
                period_high = high.iloc[-candles:].max()
                period_low = low.iloc[-candles:].min()
                period_range = period_high - period_low
                period_avg = close.iloc[-candles:].mean()
                
                period_name = {24: "24h", 24*7: "7d", 24*30: "30d"}[period]
                
                stats[f"high_{period_name}"] = float(period_high)
                stats[f"low_{period_name}"] = float(period_low)
                stats[f"range_{period_name}"] = float(period_range)
                stats[f"average_{period_name}"] = float(period_avg)
        
        # All-time stats (from available data)
        stats["high_all"] = float(high.max())
        stats["low_all"] = float(low.min())
        stats["average_all"] = float(close.mean())
        
        # Current position in range
        current_price = close.iloc[-1]
        if len(df) > 30:
            month_high = high.iloc[-30:].max()
            month_low = low.iloc[-30:].min()
            if month_high > month_low:
                position_in_range = (current_price - month_low) / (month_high - month_low)
                stats["position_in_range"] = float(position_in_range)
            else:
                stats["position_in_range"] = 0.5
        
        return stats
    
    def _calculate_volatility(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate volatility metrics"""
        close = df['close']
        returns = close.pct_change().dropna()
        
        metrics = {}
        
        # Standard deviation (volatility)
        if len(returns) > 1:
            # Different period volatilities
            for period, name in [(24, "24h"), (24*7, "7d"), (24*30, "30d")]:
                candles = self._estimate_candles_for_period(df, period)
                if candles < len(returns):
                    period_returns = returns.iloc[-candles:]
                    vol = period_returns.std() * np.sqrt(365 * 24)  # Annualized
                    metrics[f"volatility_{name}"] = float(vol * 100)  # As percentage
            
            # Current volatility regime
            recent_vol = returns.iloc[-24:].std() if len(returns) > 24 else returns.std()
            longer_vol = returns.iloc[-24*7:].std() if len(returns) > 24*7 else returns.std()
            
            if recent_vol > longer_vol * 1.5:
                metrics["volatility_regime"] = "high"
            elif recent_vol < longer_vol * 0.7:
                metrics["volatility_regime"] = "low"
            else:
                metrics["volatility_regime"] = "normal"
            
            # Volatility percentile
            if len(returns) > 100:
                rolling_vol = returns.rolling(window=24).std()
                current_vol = rolling_vol.iloc[-1]
                percentile = (rolling_vol < current_vol).sum() / len(rolling_vol.dropna())
                metrics["volatility_percentile"] = float(percentile * 100)
        
        return metrics
    
    def _identify_key_levels(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """Identify key support and resistance levels"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        levels = {
            "support": [],
            "resistance": [],
            "pivot_points": {}
        }
        
        # Simple pivot points
        if len(df) > 1:
            # Daily pivot calculations
            yesterday_high = high.iloc[-2]
            yesterday_low = low.iloc[-2]
            yesterday_close = close.iloc[-2]
            
            pivot = (yesterday_high + yesterday_low + yesterday_close) / 3
            
            levels["pivot_points"] = {
                "pivot": float(pivot),
                "r1": float(2 * pivot - yesterday_low),
                "r2": float(pivot + yesterday_high - yesterday_low),
                "r3": float(yesterday_high + 2 * (pivot - yesterday_low)),
                "s1": float(2 * pivot - yesterday_high),
                "s2": float(pivot - yesterday_high + yesterday_low),
                "s3": float(yesterday_low - 2 * (yesterday_high - pivot))
            }
        
        # Recent highs and lows as resistance/support
        if len(df) > 20:
            # Find recent peaks and troughs
            for i in range(5, len(df) - 5):
                # Local high (resistance)
                if high.iloc[i] == high.iloc[i-5:i+5].max():
                    levels["resistance"].append(float(high.iloc[i]))
                
                # Local low (support)
                if low.iloc[i] == low.iloc[i-5:i+5].min():
                    levels["support"].append(float(low.iloc[i]))
            
            # Keep only unique levels and sort
            levels["support"] = sorted(list(set(levels["support"])))[-5:]  # Keep 5 nearest
            levels["resistance"] = sorted(list(set(levels["resistance"])))[:5]  # Keep 5 nearest
        
        return levels
    
    def _generate_technical_summary(
        self,
        df: pd.DataFrame,
        price_changes: Dict,
        volume_analysis: Dict,
        volatility_metrics: Dict
    ) -> Dict[str, Any]:
        """Generate technical analysis summary"""
        close = df['close']
        
        # Determine trend
        trend = "neutral"
        strength = 50
        
        if len(close) > 50:
            sma_20 = close.rolling(window=20).mean()
            sma_50 = close.rolling(window=50).mean()
            
            current_price = close.iloc[-1]
            
            # Trend determination
            if current_price > sma_20.iloc[-1] > sma_50.iloc[-1]:
                trend = "bullish"
                strength = 70
                
                # Stronger if price well above averages
                if current_price > sma_20.iloc[-1] * 1.02:
                    strength = 85
                    
            elif current_price < sma_20.iloc[-1] < sma_50.iloc[-1]:
                trend = "bearish"
                strength = 70
                
                # Stronger if price well below averages
                if current_price < sma_20.iloc[-1] * 0.98:
                    strength = 85
            
            # Adjust for momentum
            if price_changes.get("change_24h_pct", 0) > 5:
                strength = min(100, strength + 10)
            elif price_changes.get("change_24h_pct", 0) < -5:
                strength = min(100, strength + 10)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            trend, strength, volume_analysis, volatility_metrics
        )
        
        return {
            "trend": trend,
            "strength": strength,
            "recommendation": recommendation,
            "volume_confirmation": volume_analysis.get("volume_trend", "neutral") == trend,
            "volatility_status": volatility_metrics.get("volatility_regime", "normal")
        }
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze market structure (trending, ranging, etc.)"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        structure = {
            "type": "unknown",
            "strength": 0,
            "characteristics": []
        }
        
        if len(df) < 50:
            return structure
        
        # Calculate ADX for trend strength (simplified)
        high_low = high - low
        high_close = abs(high - close.shift(1))
        low_close = abs(low - close.shift(1))
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        
        # Price movement relative to ATR
        price_movement = abs(close.iloc[-1] - close.iloc[-20])
        relative_movement = price_movement / (atr.iloc[-1] * 20) if atr.iloc[-1] > 0 else 0
        
        # Determine structure
        if relative_movement > 1.5:
            structure["type"] = "trending"
            structure["strength"] = min(100, relative_movement * 50)
            structure["characteristics"].append("Strong directional movement")
            
        elif relative_movement < 0.5:
            structure["type"] = "ranging"
            structure["strength"] = min(100, (1 - relative_movement) * 100)
            structure["characteristics"].append("Price consolidation")
            
            # Check if it's a tight range
            recent_range = high.iloc[-20:].max() - low.iloc[-20:].min()
            avg_range = (high - low).iloc[-50:].mean()
            
            if recent_range < avg_range * 0.7:
                structure["characteristics"].append("Tight range - potential breakout")
        
        else:
            structure["type"] = "transitional"
            structure["strength"] = 50
            structure["characteristics"].append("Market in transition")
        
        # Check for specific patterns
        if close.iloc[-1] > close.iloc[-5:].mean() > close.iloc[-20:].mean():
            structure["characteristics"].append("Higher highs and higher lows")
        elif close.iloc[-1] < close.iloc[-5:].mean() < close.iloc[-20:].mean():
            structure["characteristics"].append("Lower highs and lower lows")
        
        return structure
    
    def _generate_recommendation(
        self,
        trend: str,
        strength: int,
        volume_analysis: Dict,
        volatility_metrics: Dict
    ) -> str:
        """Generate human-readable recommendation"""
        
        recommendations = []
        
        # Trend-based recommendation
        if trend == "bullish" and strength > 70:
            recommendations.append("Strong uptrend in progress")
            if volume_analysis.get("volume_trend") == "increasing":
                recommendations.append("with increasing volume support")
        elif trend == "bearish" and strength > 70:
            recommendations.append("Strong downtrend in progress")
            if volume_analysis.get("volume_trend") == "increasing":
                recommendations.append("with increasing selling pressure")
        else:
            recommendations.append("Market showing neutral/sideways action")
        
        # Volatility-based advice
        vol_regime = volatility_metrics.get("volatility_regime", "normal")
        if vol_regime == "high":
            recommendations.append("High volatility - wider stops recommended")
        elif vol_regime == "low":
            recommendations.append("Low volatility - potential breakout setup")
        
        # Volume spike alert
        if volume_analysis.get("volume_spike", False):
            recommendations.append("Volume spike detected - significant activity")
        
        return ". ".join(recommendations)
    
    def _estimate_candles_for_period(self, df: pd.DataFrame, hours: int) -> int:
        """Estimate number of candles for a given hour period"""
        # Try to detect timeframe from DataFrame index
        if len(df) > 1:
            time_diff = (df.index[1] - df.index[0]).total_seconds() / 60  # Minutes
            
            # Common timeframes
            if time_diff <= 1:
                candles_per_hour = 60
            elif time_diff <= 5:
                candles_per_hour = 12
            elif time_diff <= 15:
                candles_per_hour = 4
            elif time_diff <= 30:
                candles_per_hour = 2
            elif time_diff <= 60:
                candles_per_hour = 1
            elif time_diff <= 240:
                candles_per_hour = 0.25
            else:  # Daily or higher
                candles_per_hour = 1/24
            
            return int(hours * candles_per_hour)
        
        # Default to hourly
        return hours