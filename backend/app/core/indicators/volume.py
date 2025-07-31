import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from app.core.indicators.base import Indicator, IndicatorResult
from app.config import get_config

config = get_config()


class OBVIndicator(Indicator):
    """On-Balance Volume - Cumulative volume flow indicator"""
    
    def __init__(self):
        super().__init__('obv', {})
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate OBV with trend analysis"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        close = df['close']
        volume = df['volume']
        
        # Calculate OBV
        obv = pd.Series(0.0, index=df.index)
        obv.iloc[0] = volume.iloc[0]
        
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]:
                # Price up, add volume
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                # Price down, subtract volume
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                # Price unchanged, OBV stays the same
                obv.iloc[i] = obv.iloc[i-1]
        
        # OBV moving averages for trend
        obv_sma_short = obv.rolling(window=10).mean()
        obv_sma_long = obv.rolling(window=20).mean()
        
        # OBV trend signals
        signals = self._detect_crossovers(obv_sma_short, obv_sma_long)
        
        # Divergence between price and OBV
        obv_divergence = self._calculate_divergence(close, obv, lookback=20)
        
        # OBV momentum (rate of change)
        obv_roc = obv.pct_change(periods=10) * 100
        
        # Volume trend strength
        obv_trend = pd.Series(0, index=df.index)
        obv_trend[obv > obv_sma_long] = 1   # Bullish volume trend
        obv_trend[obv < obv_sma_long] = -1  # Bearish volume trend
        
        # Breakout detection based on OBV
        obv_high = obv.rolling(window=20).max()
        obv_low = obv.rolling(window=20).min()
        
        obv_breakout = pd.Series(0, index=df.index)
        for i in range(20, len(obv)):
            # OBV breakout above recent highs
            if obv.iloc[i] > obv_high.iloc[i-1]:
                obv_breakout.iloc[i] = 1
            # OBV breakdown below recent lows
            elif obv.iloc[i] < obv_low.iloc[i-1]:
                obv_breakout.iloc[i] = -1
        
        # Normalized OBV (scaled to price movements)
        obv_normalized = obv / obv.rolling(window=20).mean()
        
        # Volume confirmation of price moves
        price_change = close.pct_change()
        volume_confirmation = pd.Series(0, index=df.index)
        
        for i in range(1, len(df)):
            # Strong volume on up move
            if price_change.iloc[i] > 0.01 and volume.iloc[i] > volume.rolling(window=20).mean().iloc[i] * 1.5:
                volume_confirmation.iloc[i] = 1
            # Strong volume on down move
            elif price_change.iloc[i] < -0.01 and volume.iloc[i] > volume.rolling(window=20).mean().iloc[i] * 1.5:
                volume_confirmation.iloc[i] = -1
        
        return IndicatorResult(
            name=self.name,
            values=obv,
            params=self.params,
            signals=signals,
            additional_series={
                'obv_sma_short': obv_sma_short,
                'obv_sma_long': obv_sma_long,
                'obv_divergence': obv_divergence,
                'obv_roc': obv_roc,
                'obv_trend': obv_trend,
                'obv_breakout': obv_breakout,
                'obv_normalized': obv_normalized,
                'volume_confirmation': volume_confirmation
            },
            metadata={
                'current_obv': float(obv.iloc[-1]),
                'obv_trend_direction': 'bullish' if obv_trend.iloc[-1] > 0 else 'bearish',
                'volume_momentum': 'positive' if obv_roc.iloc[-1] > 0 else 'negative',
                'divergence_present': bool(obv_divergence.iloc[-5:].any()),
                'recent_breakout': 'bullish' if obv_breakout.iloc[-5:].max() > 0 else
                                  'bearish' if obv_breakout.iloc[-5:].min() < 0 else 'none'
            }
        )


class VolumeROCIndicator(Indicator):
    """Volume Rate of Change - Measures volume momentum"""
    
    def __init__(self, period: int = 14):
        params = {'period': period}
        super().__init__('volume_roc', params)
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate Volume ROC with analysis"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        volume = df['volume']
        close = df['close']
        period = self.params['period']
        
        # Calculate Volume ROC
        volume_roc = ((volume - volume.shift(period)) / volume.shift(period)) * 100
        
        # Smooth the indicator
        volume_roc_smooth = volume_roc.rolling(window=3).mean()
        
        # Volume moving averages for context
        volume_sma = volume.rolling(window=period).mean()
        volume_ratio = volume / volume_sma
        
        # Detect volume spikes
        volume_spike_threshold = 2.0  # 200% of average
        volume_spikes = pd.Series(0, index=df.index)
        volume_spikes[volume_ratio > volume_spike_threshold] = 1
        
        # Volume trend
        volume_trend = pd.Series(0, index=df.index)
        volume_trend[volume_roc_smooth > 10] = 1   # Increasing volume
        volume_trend[volume_roc_smooth < -10] = -1  # Decreasing volume
        
        # Generate signals based on volume expansion/contraction
        signals = pd.Series(0, index=df.index)
        
        # Price movement with volume confirmation
        price_roc = close.pct_change(periods=period) * 100
        
        for i in range(period, len(df)):
            # Bullish: Price up with increasing volume
            if price_roc.iloc[i] > 0 and volume_roc.iloc[i] > 20:
                signals.iloc[i] = 1
            # Bearish: Price down with increasing volume
            elif price_roc.iloc[i] < 0 and volume_roc.iloc[i] > 20:
                signals.iloc[i] = -1
            # Weak move: Price movement with decreasing volume (potential reversal)
            elif abs(price_roc.iloc[i]) > 2 and volume_roc.iloc[i] < -20:
                signals.iloc[i] = -np.sign(price_roc.iloc[i]) * 0.5
        
        # Volume climax detection
        volume_climax = pd.Series(0, index=df.index)
        extreme_threshold = volume_roc.rolling(window=period*4).quantile(0.95)
        
        for i in range(1, len(volume_roc)):
            if volume_roc.iloc[i] > extreme_threshold.iloc[i]:
                # Check price action
                if close.iloc[i] > close.iloc[i-1]:
                    volume_climax.iloc[i] = -1  # Buying climax (potential top)
                else:
                    volume_climax.iloc[i] = 1   # Selling climax (potential bottom)
        
        # Volume dry-up detection (very low volume)
        volume_dryup = volume < volume_sma * 0.5
        
        # Accumulation/Distribution detection
        acc_dist = pd.Series(0, index=df.index)
        for i in range(period, len(df)):
            # Accumulation: Higher lows with steady/increasing volume
            if (close.iloc[i] > close.iloc[i-period] and 
                volume_roc.iloc[i] > -10):
                acc_dist.iloc[i] = 1
            # Distribution: Lower highs with steady/increasing volume
            elif (close.iloc[i] < close.iloc[i-period] and 
                  volume_roc.iloc[i] > -10):
                acc_dist.iloc[i] = -1
        
        # Volume momentum oscillator
        volume_momentum = volume_roc - volume_roc.rolling(window=period).mean()
        
        return IndicatorResult(
            name=self.name,
            values=volume_roc,
            params=self.params,
            signals=signals,
            additional_series={
                'volume_roc_smooth': volume_roc_smooth,
                'volume_ratio': volume_ratio,
                'volume_spikes': volume_spikes,
                'volume_trend': volume_trend,
                'volume_climax': volume_climax,
                'volume_dryup': volume_dryup.astype(int),
                'acc_dist': acc_dist,
                'volume_momentum': volume_momentum,
                'price_roc': price_roc
            },
            metadata={
                'current_volume_roc': float(volume_roc.iloc[-1]),
                'volume_trend_status': 'increasing' if volume_trend.iloc[-1] > 0 else
                                      'decreasing' if volume_trend.iloc[-1] < 0 else 'stable',
                'recent_spike': bool(volume_spikes.iloc[-5:].any()),
                'recent_climax': 'buying' if volume_climax.iloc[-5:].min() < 0 else
                                'selling' if volume_climax.iloc[-5:].max() > 0 else 'none',
                'accumulation_phase': 'accumulation' if acc_dist.iloc[-5:].mean() > 0.5 else
                                     'distribution' if acc_dist.iloc[-5:].mean() < -0.5 else 'neutral'
            }
        )