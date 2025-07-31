import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from app.core.indicators.base import Indicator, IndicatorResult
from app.config import get_config

config = get_config()


class ADXIndicator(Indicator):
    """Average Directional Index - Measures trend strength regardless of direction"""
    
    def __init__(self, period: int = 14):
        params = {
            'period': period
        }
        super().__init__('adx', params)
        
    def calculate(self, df: pd.DataFrame, **kwargs) -> IndicatorResult:
        """Calculate ADX with DI+ and DI-"""
        if len(df) < self.params['period'] * 2:
            return self._empty_result(df)
            
        # Calculate True Range
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range components
        high_low = high - low
        high_close_prev = abs(high - close.shift(1))
        low_close_prev = abs(low - close.shift(1))
        
        # True Range
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        
        # Directional Movement
        dm_plus = np.where(
            (high - high.shift(1) > low.shift(1) - low) & (high - high.shift(1) > 0),
            high - high.shift(1),
            0
        )
        
        dm_minus = np.where(
            (low.shift(1) - low > high - high.shift(1)) & (low.shift(1) - low > 0),
            low.shift(1) - low,
            0
        )
        
        # Smooth using Wilder's method
        atr = self._wilder_smooth(tr, self.params['period'])
        dm_plus_smooth = self._wilder_smooth(pd.Series(dm_plus, index=df.index), self.params['period'])
        dm_minus_smooth = self._wilder_smooth(pd.Series(dm_minus, index=df.index), self.params['period'])
        
        # Directional Indicators
        di_plus = 100 * dm_plus_smooth / atr
        di_minus = 100 * dm_minus_smooth / atr
        
        # DX
        di_sum = di_plus + di_minus
        di_diff = abs(di_plus - di_minus)
        dx = 100 * di_diff / di_sum.where(di_sum != 0, 1)
        
        # ADX is smoothed DX
        adx = self._wilder_smooth(dx, self.params['period'])
        
        # Generate signals
        adx_current = adx.iloc[-1] if not adx.empty else 0
        di_plus_current = di_plus.iloc[-1] if not di_plus.empty else 0
        di_minus_current = di_minus.iloc[-1] if not di_minus.empty else 0
        
        # Strong trend when ADX > 25
        signal = None
        if adx_current > 25:
            if di_plus_current > di_minus_current:
                signal = 'bullish_trend'
            else:
                signal = 'bearish_trend'
        elif adx_current < 20:
            signal = 'no_trend'
        
        # Calculate trend direction changes
        crossovers = self._find_di_crossovers(di_plus, di_minus)
        
        return IndicatorResult(
            name=self.name,
            values={
                'adx': adx,
                'di_plus': di_plus,
                'di_minus': di_minus
            },
            signal=signal,
            metadata={
                'adx_current': float(adx_current),
                'di_plus_current': float(di_plus_current),
                'di_minus_current': float(di_minus_current),
                'trend_strength': 'strong' if adx_current > 25 else 'weak' if adx_current < 20 else 'moderate',
                'trend_direction': 'bullish' if di_plus_current > di_minus_current else 'bearish',
                'crossovers': crossovers
            }
        )
    
    def _wilder_smooth(self, series: pd.Series, period: int) -> pd.Series:
        """Wilder's smoothing method (used in RSI and ADX)"""
        alpha = 1.0 / period
        return series.ewm(alpha=alpha, adjust=False).mean()
    
    def _find_di_crossovers(self, di_plus: pd.Series, di_minus: pd.Series) -> list:
        """Find DI+ and DI- crossovers for trend changes"""
        crossovers = []
        
        if len(di_plus) < 2:
            return crossovers
            
        # Look for crossovers in last 10 bars
        lookback = min(10, len(di_plus))
        
        for i in range(1, lookback):
            idx = -i
            prev_idx = idx - 1
            
            # Bullish crossover: DI+ crosses above DI-
            if (di_plus.iloc[prev_idx] <= di_minus.iloc[prev_idx] and 
                di_plus.iloc[idx] > di_minus.iloc[idx]):
                crossovers.append({
                    'type': 'bullish',
                    'bars_ago': i,
                    'di_plus': float(di_plus.iloc[idx]),
                    'di_minus': float(di_minus.iloc[idx])
                })
            
            # Bearish crossover: DI- crosses above DI+
            elif (di_minus.iloc[prev_idx] <= di_plus.iloc[prev_idx] and 
                  di_minus.iloc[idx] > di_plus.iloc[idx]):
                crossovers.append({
                    'type': 'bearish',
                    'bars_ago': i,
                    'di_plus': float(di_plus.iloc[idx]),
                    'di_minus': float(di_minus.iloc[idx])
                })
        
        return crossovers
    
    def _empty_result(self, df: pd.DataFrame) -> IndicatorResult:
        """Return empty result when not enough data"""
        empty_series = pd.Series(index=df.index, dtype=float)
        return IndicatorResult(
            name=self.name,
            values={
                'adx': empty_series,
                'di_plus': empty_series,
                'di_minus': empty_series
            },
            signal=None,
            metadata={'error': 'Not enough data'}
        )