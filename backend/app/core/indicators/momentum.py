import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from app.core.indicators.base import Indicator, IndicatorResult
from app.config import get_config

config = get_config()


class RSIIndicator(Indicator):
    """Relative Strength Index - Momentum oscillator with divergence detection"""
    
    def __init__(self, period: int = 14, overbought: int = 70, oversold: int = 30):
        params = {
            'period': period,
            'overbought': overbought,
            'oversold': oversold
        }
        super().__init__('rsi', params)
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate RSI with divergence detection"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        close = df['close']
        period = self.params['period']
        overbought = self.params['overbought']
        oversold = self.params['oversold']
        
        # Calculate price changes
        delta = close.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Calculate average gains and losses
        avg_gains = gains.rolling(window=period).mean()
        avg_losses = losses.rolling(window=period).mean()
        
        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        # Handle division by zero
        rsi = rsi.fillna(50)  # Neutral RSI when no losses
        
        # Generate signals based on overbought/oversold levels
        signals = pd.Series(0, index=df.index)
        
        # Basic overbought/oversold signals
        signals[rsi > overbought] = -1  # Potential sell
        signals[rsi < oversold] = 1     # Potential buy
        
        # Exit overbought/oversold signals (stronger)
        for i in range(1, len(rsi)):
            # Exit from overbought
            if rsi.iloc[i-1] > overbought and rsi.iloc[i] <= overbought:
                signals.iloc[i] = -2  # Strong sell signal
            # Exit from oversold
            elif rsi.iloc[i-1] < oversold and rsi.iloc[i] >= oversold:
                signals.iloc[i] = 2   # Strong buy signal
        
        # Detect divergences
        divergence = self._calculate_divergence(close, rsi, lookback=20)
        
        # Calculate momentum (rate of change of RSI)
        rsi_momentum = rsi.diff(5)  # 5-period momentum
        
        # Smoothed RSI for better signals
        rsi_smooth = rsi.rolling(window=3).mean()
        
        # RSI trend strength
        rsi_trend = pd.Series(0, index=df.index)
        rsi_trend[rsi > 50] = 1   # Bullish momentum
        rsi_trend[rsi < 50] = -1  # Bearish momentum
        
        # Hidden divergence detection (trend continuation)
        hidden_divergence = pd.Series(0, index=df.index)
        for i in range(20, len(close)):
            # Bullish hidden divergence
            if close.iloc[i] > close.iloc[i-10:i].mean() and rsi.iloc[i] < rsi.iloc[i-10:i].mean():
                if rsi.iloc[i] > 30:  # Not oversold
                    hidden_divergence.iloc[i] = 1
            # Bearish hidden divergence
            elif close.iloc[i] < close.iloc[i-10:i].mean() and rsi.iloc[i] > rsi.iloc[i-10:i].mean():
                if rsi.iloc[i] < 70:  # Not overbought
                    hidden_divergence.iloc[i] = -1
        
        return IndicatorResult(
            name=self.name,
            values=rsi,
            params=self.params,
            signals=signals,
            additional_series={
                'rsi_smooth': rsi_smooth,
                'divergence': divergence,
                'hidden_divergence': hidden_divergence,
                'rsi_momentum': rsi_momentum,
                'rsi_trend': rsi_trend
            },
            metadata={
                'current_rsi': float(rsi.iloc[-1]),
                'is_overbought': rsi.iloc[-1] > overbought,
                'is_oversold': rsi.iloc[-1] < oversold,
                'momentum_direction': 'bullish' if rsi_momentum.iloc[-1] > 0 else 'bearish',
                'divergence_detected': divergence.iloc[-5:].any() != 0
            }
        )


class MACDIndicator(Indicator):
    """Moving Average Convergence Divergence - Trend following momentum indicator"""
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        params = {
            'fast': fast,
            'slow': slow,
            'signal': signal
        }
        super().__init__('macd', params)
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate MACD with signal line and histogram"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        close = df['close']
        fast_period = self.params['fast']
        slow_period = self.params['slow']
        signal_period = self.params['signal']
        
        # Calculate EMAs
        ema_fast = close.ewm(span=fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=slow_period, adjust=False).mean()
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        
        # MACD histogram
        macd_histogram = macd_line - signal_line
        
        # Generate trading signals
        signals = self._detect_crossovers(macd_line, signal_line)
        
        # Zero line crossovers (additional signals)
        zero_crosses = pd.Series(0, index=df.index)
        for i in range(1, len(macd_line)):
            # MACD crosses above zero
            if macd_line.iloc[i-1] <= 0 and macd_line.iloc[i] > 0:
                zero_crosses.iloc[i] = 1
            # MACD crosses below zero
            elif macd_line.iloc[i-1] >= 0 and macd_line.iloc[i] < 0:
                zero_crosses.iloc[i] = -1
        
        # Histogram momentum (widening/narrowing)
        hist_momentum = macd_histogram.diff()
        hist_acceleration = hist_momentum.diff()
        
        # Divergence detection between price and MACD
        macd_divergence = self._calculate_divergence(close, macd_line, lookback=30)
        
        # MACD trend strength
        trend_strength = abs(macd_line) / close * 100  # MACD as percentage of price
        
        # Histogram reversal detection
        histogram_reversal = pd.Series(0, index=df.index)
        for i in range(2, len(macd_histogram)):
            # Bullish reversal (histogram stops declining)
            if (macd_histogram.iloc[i] > macd_histogram.iloc[i-1] and 
                macd_histogram.iloc[i-1] < macd_histogram.iloc[i-2] and
                macd_histogram.iloc[i] < 0):
                histogram_reversal.iloc[i] = 1
            # Bearish reversal (histogram stops rising)
            elif (macd_histogram.iloc[i] < macd_histogram.iloc[i-1] and 
                  macd_histogram.iloc[i-1] > macd_histogram.iloc[i-2] and
                  macd_histogram.iloc[i] > 0):
                histogram_reversal.iloc[i] = -1
        
        return IndicatorResult(
            name=self.name,
            values=macd_line,
            params=self.params,
            signals=signals,
            additional_series={
                'signal_line': signal_line,
                'histogram': macd_histogram,
                'zero_crosses': zero_crosses,
                'hist_momentum': hist_momentum,
                'hist_acceleration': hist_acceleration,
                'divergence': macd_divergence,
                'trend_strength': trend_strength,
                'histogram_reversal': histogram_reversal
            },
            metadata={
                'current_macd': float(macd_line.iloc[-1]),
                'current_signal': float(signal_line.iloc[-1]),
                'current_histogram': float(macd_histogram.iloc[-1]),
                'above_zero': macd_line.iloc[-1] > 0,
                'above_signal': macd_line.iloc[-1] > signal_line.iloc[-1],
                'histogram_expanding': hist_momentum.iloc[-1] > 0,
                'trend_direction': 'bullish' if macd_line.iloc[-1] > 0 else 'bearish'
            }
        )


class StochasticIndicator(Indicator):
    """Stochastic Oscillator - Momentum indicator comparing close to price range"""
    
    def __init__(self, k_period: int = 14, d_period: int = 3, smooth: int = 3):
        params = {
            'k_period': k_period,
            'd_period': d_period,
            'smooth': smooth
        }
        super().__init__('stochastic', params)
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate Stochastic %K and %D"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        k_period = self.params['k_period']
        d_period = self.params['d_period']
        smooth = self.params['smooth']
        
        # Calculate %K (fast stochastic)
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        fast_k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        
        # Smooth %K to get slow %K
        slow_k = fast_k.rolling(window=smooth).mean()
        
        # Calculate %D (signal line)
        slow_d = slow_k.rolling(window=d_period).mean()
        
        # Generate signals
        signals = self._detect_crossovers(slow_k, slow_d)
        
        # Overbought/Oversold levels
        overbought = 80
        oversold = 20
        
        # Enhanced signals based on levels
        for i in range(1, len(slow_k)):
            # Bullish signal: %K crosses %D while in oversold
            if signals.iloc[i] > 0 and slow_k.iloc[i] < oversold:
                signals.iloc[i] = 2  # Strong buy
            # Bearish signal: %K crosses %D while in overbought
            elif signals.iloc[i] < 0 and slow_k.iloc[i] > overbought:
                signals.iloc[i] = -2  # Strong sell
        
        # Divergence detection
        stoch_divergence = self._calculate_divergence(close, slow_k, lookback=20)
        
        # Bull/Bear setup detection
        setup = pd.Series(0, index=df.index)
        for i in range(2, len(slow_k)):
            # Bull setup: %K turns up from oversold
            if (slow_k.iloc[i] > slow_k.iloc[i-1] and 
                slow_k.iloc[i-1] < slow_k.iloc[i-2] and
                slow_k.iloc[i] < oversold):
                setup.iloc[i] = 1
            # Bear setup: %K turns down from overbought
            elif (slow_k.iloc[i] < slow_k.iloc[i-1] and 
                  slow_k.iloc[i-1] > slow_k.iloc[i-2] and
                  slow_k.iloc[i] > overbought):
                setup.iloc[i] = -1
        
        # %K-%D spread (momentum)
        kd_spread = slow_k - slow_d
        
        # Double stochastic (stochastic of stochastic)
        double_stoch = 100 * ((slow_k - slow_k.rolling(k_period).min()) / 
                              (slow_k.rolling(k_period).max() - slow_k.rolling(k_period).min()))
        
        return IndicatorResult(
            name=self.name,
            values=slow_k,  # %K is the primary value
            params=self.params,
            signals=signals,
            additional_series={
                'fast_k': fast_k,
                'slow_d': slow_d,
                'divergence': stoch_divergence,
                'setup': setup,
                'kd_spread': kd_spread,
                'double_stoch': double_stoch
            },
            metadata={
                'current_k': float(slow_k.iloc[-1]),
                'current_d': float(slow_d.iloc[-1]),
                'is_overbought': slow_k.iloc[-1] > overbought,
                'is_oversold': slow_k.iloc[-1] < oversold,
                'k_above_d': slow_k.iloc[-1] > slow_d.iloc[-1],
                'momentum': 'bullish' if kd_spread.iloc[-1] > 0 else 'bearish'
            }
        )