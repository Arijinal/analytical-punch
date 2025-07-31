import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from app.core.indicators.base import Indicator, IndicatorResult
from app.config import get_config

config = get_config()


class BollingerBandsIndicator(Indicator):
    """Bollinger Bands - Volatility bands based on standard deviation"""
    
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        params = {
            'period': period,
            'std_dev': std_dev
        }
        super().__init__('bollinger_bands', params)
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate Bollinger Bands with squeeze detection"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        close = df['close']
        high = df['high']
        low = df['low']
        
        period = self.params['period']
        std_dev = self.params['std_dev']
        
        # Calculate middle band (SMA)
        middle_band = close.rolling(window=period).mean()
        
        # Calculate standard deviation
        std = close.rolling(window=period).std()
        
        # Calculate upper and lower bands
        upper_band = middle_band + (std_dev * std)
        lower_band = middle_band - (std_dev * std)
        
        # Calculate band width
        band_width = upper_band - lower_band
        band_width_ratio = band_width / middle_band * 100  # As percentage
        
        # Calculate %B (where price is relative to bands)
        percent_b = (close - lower_band) / (upper_band - lower_band)
        
        # Generate signals
        signals = pd.Series(0, index=df.index)
        
        # Basic band touch signals
        for i in range(len(close)):
            if close.iloc[i] <= lower_band.iloc[i]:
                signals.iloc[i] = 1  # Potential buy (oversold)
            elif close.iloc[i] >= upper_band.iloc[i]:
                signals.iloc[i] = -1  # Potential sell (overbought)
        
        # Band breakout signals (stronger)
        for i in range(1, len(close)):
            # Break above upper band
            if close.iloc[i-1] <= upper_band.iloc[i-1] and close.iloc[i] > upper_band.iloc[i]:
                if signals.iloc[i] == 0:
                    signals.iloc[i] = -2  # Strong sell signal
            # Break below lower band
            elif close.iloc[i-1] >= lower_band.iloc[i-1] and close.iloc[i] < lower_band.iloc[i]:
                if signals.iloc[i] == 0:
                    signals.iloc[i] = 2  # Strong buy signal
        
        # Bollinger Band Squeeze detection
        # Using ATR for comparison
        atr = self._calculate_atr(high, low, close, period=period)
        squeeze_threshold = 2.0  # Band width should be at least 2x ATR
        squeeze = band_width < (squeeze_threshold * atr)
        
        # Squeeze release signals
        squeeze_release = pd.Series(0, index=df.index)
        for i in range(1, len(squeeze)):
            if squeeze.iloc[i-1] and not squeeze.iloc[i]:
                # Squeeze released - check direction
                if close.iloc[i] > middle_band.iloc[i]:
                    squeeze_release.iloc[i] = 1  # Bullish squeeze release
                else:
                    squeeze_release.iloc[i] = -1  # Bearish squeeze release
        
        # Band expansion/contraction
        band_momentum = band_width.diff()
        expanding_bands = band_momentum > 0
        
        # Walk along the bands pattern
        walk_pattern = pd.Series(0, index=df.index)
        walk_threshold = 3  # Number of consecutive touches
        
        # Detect upper band walk
        upper_touches = (close >= upper_band * 0.98).astype(int)  # Within 2% of upper band
        upper_walk = upper_touches.rolling(window=walk_threshold).sum() >= walk_threshold
        
        # Detect lower band walk
        lower_touches = (close <= lower_band * 1.02).astype(int)  # Within 2% of lower band
        lower_walk = lower_touches.rolling(window=walk_threshold).sum() >= walk_threshold
        
        walk_pattern[upper_walk] = 1   # Bullish walk
        walk_pattern[lower_walk] = -1  # Bearish walk
        
        return IndicatorResult(
            name=self.name,
            values=middle_band,  # Middle band as primary
            params=self.params,
            signals=signals,
            additional_series={
                'upper_band': upper_band,
                'lower_band': lower_band,
                'band_width': band_width,
                'band_width_ratio': band_width_ratio,
                'percent_b': percent_b,
                'squeeze': squeeze.astype(int),
                'squeeze_release': squeeze_release,
                'expanding_bands': expanding_bands.astype(int),
                'walk_pattern': walk_pattern
            },
            metadata={
                'current_position': 'above_upper' if close.iloc[-1] > upper_band.iloc[-1] else
                                   'below_lower' if close.iloc[-1] < lower_band.iloc[-1] else
                                   'inside_bands',
                'percent_b_value': float(percent_b.iloc[-1]),
                'in_squeeze': bool(squeeze.iloc[-1]),
                'band_trend': 'expanding' if band_momentum.iloc[-1] > 0 else 'contracting',
                'volatility_level': 'high' if band_width_ratio.iloc[-1] > 4 else
                                   'low' if band_width_ratio.iloc[-1] < 2 else 'normal'
            }
        )
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Helper method to calculate ATR"""
        high_low = high - low
        high_close = abs(high - close.shift(1))
        low_close = abs(low - close.shift(1))
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr


class ATRIndicator(Indicator):
    """Average True Range - Measures market volatility"""
    
    def __init__(self, period: int = 14):
        params = {'period': period}
        super().__init__('atr', params)
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate ATR with volatility analysis"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        high = df['high']
        low = df['low']
        close = df['close']
        period = self.params['period']
        
        # Calculate True Range components
        high_low = high - low
        high_close = abs(high - close.shift(1))
        low_close = abs(low - close.shift(1))
        
        # True Range is the maximum of the three
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # ATR is the moving average of True Range
        atr = true_range.rolling(window=period).mean()
        
        # ATR as percentage of close price
        atr_percent = (atr / close) * 100
        
        # Volatility regime detection
        atr_sma = atr.rolling(window=period * 2).mean()
        volatility_regime = pd.Series('normal', index=df.index)
        volatility_regime[atr > atr_sma * 1.5] = 'high'
        volatility_regime[atr < atr_sma * 0.7] = 'low'
        
        # ATR expansion/contraction
        atr_change = atr.pct_change(periods=5)
        expanding_volatility = atr_change > 0
        
        # Normalized ATR (0-100 scale based on recent history)
        atr_min = atr.rolling(window=period * 4).min()
        atr_max = atr.rolling(window=period * 4).max()
        atr_normalized = ((atr - atr_min) / (atr_max - atr_min)) * 100
        
        # Volatility breakout detection
        volatility_breakout = pd.Series(0, index=df.index)
        atr_threshold = atr.rolling(window=period * 2).quantile(0.75)
        
        for i in range(1, len(atr)):
            if atr.iloc[i] > atr_threshold.iloc[i] and atr.iloc[i-1] <= atr_threshold.iloc[i-1]:
                volatility_breakout.iloc[i] = 1  # Volatility expansion signal
        
        # Calculate suggested stop loss distances
        stop_loss_1x = close - atr  # Conservative
        stop_loss_2x = close - (2 * atr)  # Normal
        stop_loss_3x = close - (3 * atr)  # Aggressive
        
        # Volatility-based position sizing (inverse of ATR%)
        # Higher volatility = smaller position size
        position_size_factor = 1 / (atr_percent / 2)  # Normalized around 2% ATR
        position_size_factor = position_size_factor.clip(0.2, 5.0)  # Limit between 0.2x and 5x
        
        # No direct trading signals from ATR (it's a volatility measure)
        signals = pd.Series(0, index=df.index)
        
        return IndicatorResult(
            name=self.name,
            values=atr,
            params=self.params,
            signals=signals,
            additional_series={
                'true_range': true_range,
                'atr_percent': atr_percent,
                'atr_normalized': atr_normalized,
                'volatility_breakout': volatility_breakout,
                'stop_loss_1x': stop_loss_1x,
                'stop_loss_2x': stop_loss_2x,
                'stop_loss_3x': stop_loss_3x,
                'position_size_factor': position_size_factor
            },
            metadata={
                'current_atr': float(atr.iloc[-1]),
                'atr_as_percent': float(atr_percent.iloc[-1]),
                'volatility_regime': volatility_regime.iloc[-1],
                'volatility_expanding': bool(expanding_volatility.iloc[-1]),
                'normalized_volatility': float(atr_normalized.iloc[-1]) if not pd.isna(atr_normalized.iloc[-1]) else 50.0,
                'suggested_stop_distance': float(atr.iloc[-1] * 2)  # 2x ATR stop
            }
        )