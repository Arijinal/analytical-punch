import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any

from app.core.indicators.base import Indicator, IndicatorResult
from app.config import get_config

config = get_config()


class SMAIndicator(Indicator):
    """Simple Moving Average - Smooth price action to identify trends"""
    
    def __init__(self, periods: Optional[List[int]] = None):
        default_periods = config.INDICATOR_DEFAULTS['sma']['periods']
        periods = periods or default_periods
        super().__init__('sma', {'periods': periods})
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate SMA for multiple periods"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        close_prices = df['close']
        periods = self.params['periods']
        
        # Calculate primary SMA (first period)
        primary_period = periods[0]
        primary_sma = close_prices.rolling(window=primary_period).mean()
        
        # Calculate additional SMAs
        additional_series = {}
        for period in periods[1:]:
            additional_series[f'sma_{period}'] = close_prices.rolling(window=period).mean()
        
        # Detect trend based on multiple SMAs
        if len(periods) >= 2:
            # Trend: 1 = bullish, -1 = bearish, 0 = neutral
            fast_sma = primary_sma
            slow_sma = additional_series[f'sma_{periods[1]}']
            trend = pd.Series(0, index=df.index)
            trend[fast_sma > slow_sma] = 1
            trend[fast_sma < slow_sma] = -1
            
            signals = self._detect_crossovers(fast_sma, slow_sma)
        else:
            trend = pd.Series(0, index=df.index)
            signals = pd.Series(0, index=df.index)
        
        # Add trend strength
        if len(periods) >= 3:
            # All SMAs aligned = strong trend
            all_smas = [primary_sma] + list(additional_series.values())
            trend_strength = pd.Series(0.0, index=df.index)
            
            for i in range(len(df)):
                sma_values = [sma.iloc[i] for sma in all_smas if not pd.isna(sma.iloc[i])]
                if len(sma_values) >= 2:
                    if all(sma_values[j] > sma_values[j+1] for j in range(len(sma_values)-1)):
                        trend_strength.iloc[i] = 1.0  # Strong uptrend
                    elif all(sma_values[j] < sma_values[j+1] for j in range(len(sma_values)-1)):
                        trend_strength.iloc[i] = -1.0  # Strong downtrend
                    else:
                        trend_strength.iloc[i] = 0.5 * trend.iloc[i]  # Weak trend
            
            additional_series['trend_strength'] = trend_strength
        
        return IndicatorResult(
            name=self.name,
            values=primary_sma,
            params=self.params,
            signals=signals,
            additional_series=additional_series,
            metadata={
                'primary_period': primary_period,
                'trend': trend.iloc[-1] if len(trend) > 0 else 0
            }
        )


class EMAIndicator(Indicator):
    """Exponential Moving Average - More responsive to recent price changes"""
    
    def __init__(self, periods: Optional[List[int]] = None):
        default_periods = config.INDICATOR_DEFAULTS['ema']['periods']
        periods = periods or default_periods
        super().__init__('ema', {'periods': periods})
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate EMA for multiple periods"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        close_prices = df['close']
        periods = self.params['periods']
        
        # Calculate primary EMA
        primary_period = periods[0]
        primary_ema = close_prices.ewm(span=primary_period, adjust=False).mean()
        
        # Calculate additional EMAs
        additional_series = {}
        for period in periods[1:]:
            additional_series[f'ema_{period}'] = close_prices.ewm(span=period, adjust=False).mean()
        
        # MACD-style signal if we have 12 and 26 period EMAs
        signals = pd.Series(0, index=df.index)
        if 12 in periods and 26 in periods:
            ema_12 = primary_ema if primary_period == 12 else additional_series.get('ema_12')
            ema_26 = additional_series.get('ema_26') if primary_period != 26 else primary_ema
            
            if ema_12 is not None and ema_26 is not None:
                macd_line = ema_12 - ema_26
                signal_line = macd_line.ewm(span=9, adjust=False).mean()
                signals = self._detect_crossovers(macd_line, signal_line)
                
                additional_series['macd'] = macd_line
                additional_series['macd_signal'] = signal_line
                additional_series['macd_histogram'] = macd_line - signal_line
        
        # Price position relative to EMA
        price_position = (close_prices - primary_ema) / primary_ema * 100
        additional_series['price_position'] = price_position
        
        return IndicatorResult(
            name=self.name,
            values=primary_ema,
            params=self.params,
            signals=signals,
            additional_series=additional_series,
            metadata={
                'primary_period': primary_period,
                'price_above_ema': close_prices.iloc[-1] > primary_ema.iloc[-1]
            }
        )


class IchimokuIndicator(Indicator):
    """Ichimoku Cloud - Complete trend following system with 5 components"""
    
    def __init__(self, params: Optional[Dict[str, int]] = None):
        default_params = {
            'tenkan_period': 9,
            'kijun_period': 26,
            'senkou_b_period': 52,
            'displacement': 26
        }
        params = params or default_params
        super().__init__('ichimoku', params)
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate all Ichimoku Cloud components"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Extract parameters
        tenkan_period = self.params['tenkan_period']
        kijun_period = self.params['kijun_period']
        senkou_b_period = self.params['senkou_b_period']
        displacement = self.params['displacement']
        
        # Tenkan-sen (Conversion Line)
        tenkan_high = high.rolling(window=tenkan_period).max()
        tenkan_low = low.rolling(window=tenkan_period).min()
        tenkan_sen = (tenkan_high + tenkan_low) / 2
        
        # Kijun-sen (Base Line)
        kijun_high = high.rolling(window=kijun_period).max()
        kijun_low = low.rolling(window=kijun_period).min()
        kijun_sen = (kijun_high + kijun_low) / 2
        
        # Senkou Span A (Leading Span A)
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(displacement)
        
        # Senkou Span B (Leading Span B)
        senkou_b_high = high.rolling(window=senkou_b_period).max()
        senkou_b_low = low.rolling(window=senkou_b_period).min()
        senkou_span_b = ((senkou_b_high + senkou_b_low) / 2).shift(displacement)
        
        # Chikou Span (Lagging Span)
        chikou_span = close.shift(-displacement)
        
        # Generate signals
        signals = pd.Series(0, index=df.index)
        
        # TK Cross signals
        tk_cross = self._detect_crossovers(tenkan_sen, kijun_sen)
        
        # Price vs Cloud signals
        cloud_top = pd.DataFrame([senkou_span_a, senkou_span_b]).max()
        cloud_bottom = pd.DataFrame([senkou_span_a, senkou_span_b]).min()
        
        # Bullish: price above cloud, bearish: price below cloud
        for i in range(len(close)):
            if pd.notna(cloud_top.iloc[i]) and pd.notna(cloud_bottom.iloc[i]):
                if close.iloc[i] > cloud_top.iloc[i]:
                    if tk_cross.iloc[i] > 0:  # TK bullish cross above cloud
                        signals.iloc[i] = 2  # Strong buy
                    elif signals.iloc[i] == 0:
                        signals.iloc[i] = 1  # Buy
                elif close.iloc[i] < cloud_bottom.iloc[i]:
                    if tk_cross.iloc[i] < 0:  # TK bearish cross below cloud
                        signals.iloc[i] = -2  # Strong sell
                    elif signals.iloc[i] == 0:
                        signals.iloc[i] = -1  # Sell
        
        # Cloud thickness (volatility indicator)
        cloud_thickness = abs(senkou_span_a - senkou_span_b)
        
        # Future cloud color (bullish/bearish bias)
        future_cloud = pd.Series(0, index=df.index)
        future_cloud[senkou_span_a > senkou_span_b] = 1
        future_cloud[senkou_span_a < senkou_span_b] = -1
        
        return IndicatorResult(
            name=self.name,
            values=tenkan_sen,  # Primary line
            params=self.params,
            signals=signals,
            additional_series={
                'kijun_sen': kijun_sen,
                'senkou_span_a': senkou_span_a,
                'senkou_span_b': senkou_span_b,
                'chikou_span': chikou_span,
                'cloud_top': cloud_top,
                'cloud_bottom': cloud_bottom,
                'cloud_thickness': cloud_thickness,
                'future_cloud': future_cloud
            },
            metadata={
                'current_position': 'above_cloud' if close.iloc[-1] > cloud_top.iloc[-1] else 
                                  'below_cloud' if close.iloc[-1] < cloud_bottom.iloc[-1] else 
                                  'inside_cloud',
                'tk_position': 'bullish' if tenkan_sen.iloc[-1] > kijun_sen.iloc[-1] else 'bearish',
                'cloud_trend': 'bullish' if future_cloud.iloc[-1] > 0 else 'bearish'
            }
        )