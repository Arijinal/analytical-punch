import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from scipy.signal import argrelextrema

from app.core.indicators.base import Indicator, IndicatorResult
from app.config import get_config

config = get_config()


class FibonacciIndicator(Indicator):
    """Fibonacci Retracement - Identifies potential support/resistance levels"""
    
    def __init__(self, lookback: int = 100):
        params = {'lookback': lookback}
        super().__init__('fibonacci', params)
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate Fibonacci retracement levels"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        high = df['high']
        low = df['low']
        close = df['close']
        lookback = self.params['lookback']
        
        # Key Fibonacci ratios
        fib_ratios = {
            0.0: '0%',
            0.236: '23.6%',
            0.382: '38.2%',
            0.5: '50%',
            0.618: '61.8%',
            0.786: '78.6%',
            1.0: '100%',
            1.618: '161.8%',
            2.618: '261.8%'
        }
        
        # Initialize series for levels
        fib_levels = {}
        for ratio, name in fib_ratios.items():
            fib_levels[f'fib_{name}'] = pd.Series(np.nan, index=df.index)
        
        # Series to track swing points
        swing_high = pd.Series(np.nan, index=df.index)
        swing_low = pd.Series(np.nan, index=df.index)
        
        # Detect swings using local extrema
        order = 5  # Window for detecting extrema
        
        # Find local maxima and minima
        high_indices = argrelextrema(high.values, np.greater, order=order)[0]
        low_indices = argrelextrema(low.values, np.less, order=order)[0]
        
        # Mark swing points
        for idx in high_indices:
            swing_high.iloc[idx] = high.iloc[idx]
        for idx in low_indices:
            swing_low.iloc[idx] = low.iloc[idx]
        
        # Calculate Fibonacci levels for each point
        for i in range(lookback, len(df)):
            # Look back for recent swing high and low
            recent_high_idx = swing_high.iloc[i-lookback:i].idxmax()
            recent_low_idx = swing_low.iloc[i-lookback:i].idxmin()
            
            if pd.notna(recent_high_idx) and pd.notna(recent_low_idx):
                swing_high_value = high.loc[recent_high_idx]
                swing_low_value = low.loc[recent_low_idx]
                
                # Determine trend direction
                if recent_high_idx > recent_low_idx:
                    # Uptrend - calculate retracement from low to high
                    diff = swing_high_value - swing_low_value
                    for ratio, name in fib_ratios.items():
                        if ratio <= 1.0:  # Retracement levels
                            fib_levels[f'fib_{name}'].iloc[i] = swing_low_value + (diff * ratio)
                        else:  # Extension levels
                            fib_levels[f'fib_{name}'].iloc[i] = swing_high_value + (diff * (ratio - 1.0))
                else:
                    # Downtrend - calculate retracement from high to low
                    diff = swing_high_value - swing_low_value
                    for ratio, name in fib_ratios.items():
                        if ratio <= 1.0:  # Retracement levels
                            fib_levels[f'fib_{name}'].iloc[i] = swing_high_value - (diff * ratio)
                        else:  # Extension levels
                            fib_levels[f'fib_{name}'].iloc[i] = swing_low_value - (diff * (ratio - 1.0))
        
        # Forward fill Fibonacci levels
        for level_name in fib_levels:
            fib_levels[level_name] = fib_levels[level_name].fillna(method='ffill')
        
        # Generate signals based on Fibonacci levels
        signals = pd.Series(0, index=df.index)
        
        # Check for bounces off Fibonacci levels
        tolerance = 0.002  # 0.2% tolerance
        
        for i in range(1, len(close)):
            if pd.notna(fib_levels['fib_61.8%'].iloc[i]):
                # Key levels to check
                key_levels = ['fib_38.2%', 'fib_50%', 'fib_61.8%']
                
                for level_name in key_levels:
                    level_value = fib_levels[level_name].iloc[i]
                    if pd.notna(level_value):
                        # Check if price bounced off level
                        if (abs(low.iloc[i] - level_value) / level_value < tolerance and
                            close.iloc[i] > low.iloc[i]):
                            signals.iloc[i] = 1  # Bounce up from support
                        elif (abs(high.iloc[i] - level_value) / level_value < tolerance and
                              close.iloc[i] < high.iloc[i]):
                            signals.iloc[i] = -1  # Bounce down from resistance
        
        # Calculate distance to nearest Fibonacci level
        distance_to_fib = pd.Series(np.inf, index=df.index)
        nearest_fib_level = pd.Series('', index=df.index)
        
        for i in range(len(close)):
            min_distance = np.inf
            nearest_level = ''
            
            for level_name, level_series in fib_levels.items():
                if pd.notna(level_series.iloc[i]):
                    distance = abs(close.iloc[i] - level_series.iloc[i]) / close.iloc[i]
                    if distance < min_distance:
                        min_distance = distance
                        nearest_level = level_name
            
            distance_to_fib.iloc[i] = min_distance * 100  # As percentage
            nearest_fib_level.iloc[i] = nearest_level
        
        # Confluence detection (multiple Fib levels close together)
        confluence_zones = self._detect_confluence(fib_levels, tolerance=0.01)
        
        # Primary value is the 50% retracement level
        primary_value = fib_levels['fib_50%']
        
        return IndicatorResult(
            name=self.name,
            values=primary_value,
            params=self.params,
            signals=signals,
            additional_series={
                **fib_levels,
                'swing_high': swing_high,
                'swing_low': swing_low,
                'distance_to_fib': distance_to_fib,
                'confluence_strength': confluence_zones
            },
            metadata={
                'current_nearest_fib': nearest_fib_level.iloc[-1],
                'distance_to_nearest': float(distance_to_fib.iloc[-1]),
                'trend_direction': 'up' if fib_levels['fib_0%'].iloc[-1] < fib_levels['fib_100%'].iloc[-1] else 'down',
                'key_levels': {
                    name: float(level.iloc[-1]) if pd.notna(level.iloc[-1]) else None
                    for name, level in fib_levels.items()
                    if name in ['fib_38.2%', 'fib_50%', 'fib_61.8%']
                }
            }
        )
    
    def _detect_confluence(self, levels: Dict[str, pd.Series], tolerance: float) -> pd.Series:
        """Detect areas where multiple Fibonacci levels cluster"""
        confluence = pd.Series(0, index=levels[list(levels.keys())[0]].index)
        
        level_values = list(levels.values())
        
        for i in range(len(confluence)):
            count = 0
            for j in range(len(level_values)):
                for k in range(j + 1, len(level_values)):
                    if (pd.notna(level_values[j].iloc[i]) and 
                        pd.notna(level_values[k].iloc[i])):
                        if abs(level_values[j].iloc[i] - level_values[k].iloc[i]) / level_values[j].iloc[i] < tolerance:
                            count += 1
            
            confluence.iloc[i] = count
        
        return confluence


class SupportResistanceIndicator(Indicator):
    """Support and Resistance Levels - Identifies key price levels"""
    
    def __init__(self, lookback: int = 100, min_touches: int = 2):
        params = {
            'lookback': lookback,
            'min_touches': min_touches
        }
        super().__init__('support_resistance', params)
    
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate support and resistance levels"""
        if not self.validate_dataframe(df):
            raise ValueError("DataFrame missing required OHLCV columns")
        
        high = df['high']
        low = df['low']
        close = df['close']
        volume = df['volume']
        
        lookback = self.params['lookback']
        min_touches = self.params['min_touches']
        
        # Initialize level tracking
        support_levels = pd.Series(np.nan, index=df.index)
        resistance_levels = pd.Series(np.nan, index=df.index)
        level_strength = pd.Series(0, index=df.index)
        
        # Track all potential levels
        all_levels = []
        
        for i in range(lookback, len(df)):
            window_high = high.iloc[i-lookback:i]
            window_low = low.iloc[i-lookback:i]
            window_close = close.iloc[i-lookback:i]
            window_volume = volume.iloc[i-lookback:i]
            
            # Find local extrema
            local_highs = argrelextrema(window_high.values, np.greater, order=5)[0]
            local_lows = argrelextrema(window_low.values, np.less, order=5)[0]
            
            # Identify potential levels
            potential_levels = []
            
            # Add highs as potential resistance
            for idx in local_highs:
                level = window_high.iloc[idx]
                potential_levels.append({
                    'price': level,
                    'type': 'resistance',
                    'volume': window_volume.iloc[idx]
                })
            
            # Add lows as potential support
            for idx in local_lows:
                level = window_low.iloc[idx]
                potential_levels.append({
                    'price': level,
                    'type': 'support',
                    'volume': window_volume.iloc[idx]
                })
            
            # Test each level for validity (multiple touches)
            valid_levels = []
            
            for level_info in potential_levels:
                level = level_info['price']
                touches = 0
                tolerance = level * 0.002  # 0.2% tolerance
                
                # Count touches
                for j in range(len(window_high)):
                    # Check if high or low touched the level
                    if (abs(window_high.iloc[j] - level) < tolerance or
                        abs(window_low.iloc[j] - level) < tolerance):
                        touches += 1
                
                if touches >= min_touches:
                    level_info['touches'] = touches
                    level_info['strength'] = touches * (1 + level_info['volume'] / window_volume.mean())
                    valid_levels.append(level_info)
            
            # Sort by strength and select strongest levels
            valid_levels.sort(key=lambda x: x['strength'], reverse=True)
            
            # Find nearest support and resistance
            current_price = close.iloc[i]
            
            nearest_support = None
            nearest_resistance = None
            max_support_strength = 0
            max_resistance_strength = 0
            
            for level_info in valid_levels:
                if level_info['price'] < current_price:
                    # Potential support
                    if level_info['strength'] > max_support_strength:
                        nearest_support = level_info['price']
                        max_support_strength = level_info['strength']
                else:
                    # Potential resistance
                    if nearest_resistance is None or level_info['price'] < nearest_resistance:
                        nearest_resistance = level_info['price']
                        max_resistance_strength = level_info['strength']
            
            # Store levels
            if nearest_support:
                support_levels.iloc[i] = nearest_support
            if nearest_resistance:
                resistance_levels.iloc[i] = nearest_resistance
            
            # Calculate combined strength
            level_strength.iloc[i] = max_support_strength + max_resistance_strength
            
            # Store all valid levels for this period
            all_levels.append(valid_levels)
        
        # Forward fill levels
        support_levels = support_levels.fillna(method='ffill')
        resistance_levels = resistance_levels.fillna(method='ffill')
        
        # Generate signals based on level breaks
        signals = pd.Series(0, index=df.index)
        
        for i in range(1, len(close)):
            if pd.notna(support_levels.iloc[i]) and pd.notna(resistance_levels.iloc[i]):
                # Breakout above resistance
                if close.iloc[i-1] <= resistance_levels.iloc[i] and close.iloc[i] > resistance_levels.iloc[i]:
                    signals.iloc[i] = 2  # Strong buy on breakout
                # Breakdown below support
                elif close.iloc[i-1] >= support_levels.iloc[i] and close.iloc[i] < support_levels.iloc[i]:
                    signals.iloc[i] = -2  # Strong sell on breakdown
                # Bounce from support
                elif low.iloc[i] <= support_levels.iloc[i] * 1.002 and close.iloc[i] > support_levels.iloc[i]:
                    signals.iloc[i] = 1  # Buy on support bounce
                # Rejection from resistance
                elif high.iloc[i] >= resistance_levels.iloc[i] * 0.998 and close.iloc[i] < resistance_levels.iloc[i]:
                    signals.iloc[i] = -1  # Sell on resistance rejection
        
        # Calculate distance to levels
        distance_to_support = ((close - support_levels) / close) * 100
        distance_to_resistance = ((resistance_levels - close) / close) * 100
        
        # Price position relative to levels
        price_position = pd.Series('between', index=df.index)
        price_position[close > resistance_levels] = 'above_resistance'
        price_position[close < support_levels] = 'below_support'
        
        # Level reliability score (based on historical accuracy)
        level_reliability = self._calculate_reliability(
            support_levels, resistance_levels, high, low, lookback=20
        )
        
        return IndicatorResult(
            name=self.name,
            values=support_levels,  # Primary value is support
            params=self.params,
            signals=signals,
            additional_series={
                'resistance_levels': resistance_levels,
                'level_strength': level_strength,
                'distance_to_support': distance_to_support,
                'distance_to_resistance': distance_to_resistance,
                'level_reliability': level_reliability
            },
            metadata={
                'current_support': float(support_levels.iloc[-1]) if pd.notna(support_levels.iloc[-1]) else None,
                'current_resistance': float(resistance_levels.iloc[-1]) if pd.notna(resistance_levels.iloc[-1]) else None,
                'price_position': price_position.iloc[-1],
                'support_distance': float(distance_to_support.iloc[-1]),
                'resistance_distance': float(distance_to_resistance.iloc[-1]),
                'level_reliability_score': float(level_reliability.iloc[-1])
            }
        )
    
    def _calculate_reliability(
        self,
        support: pd.Series,
        resistance: pd.Series,
        high: pd.Series,
        low: pd.Series,
        lookback: int
    ) -> pd.Series:
        """Calculate how reliable the levels have been historically"""
        reliability = pd.Series(0.5, index=support.index)
        
        for i in range(lookback, len(support)):
            successful_tests = 0
            total_tests = 0
            
            # Look back and count successful support/resistance tests
            for j in range(i-lookback, i):
                # Test support
                if pd.notna(support.iloc[j]):
                    if low.iloc[j] <= support.iloc[j] * 1.002:
                        total_tests += 1
                        if low.iloc[j] >= support.iloc[j] * 0.998:  # Held support
                            successful_tests += 1
                
                # Test resistance
                if pd.notna(resistance.iloc[j]):
                    if high.iloc[j] >= resistance.iloc[j] * 0.998:
                        total_tests += 1
                        if high.iloc[j] <= resistance.iloc[j] * 1.002:  # Held resistance
                            successful_tests += 1
            
            if total_tests > 0:
                reliability.iloc[i] = successful_tests / total_tests
        
        return reliability