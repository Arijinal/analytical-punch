"""
Breakout Punch Strategy - Trades range breakouts and chart pattern breakouts.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import uuid

from app.core.trading.base import TradingStrategy, Signal
from app.core.indicators.volatility import BollingerBandsIndicator, ATRIndicator
from app.core.indicators.trend import SMAIndicator, EMAIndicator
from app.core.indicators.volume import VolumeROCIndicator, OBVIndicator
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class BreakoutPunchStrategy(TradingStrategy):
    """
    Breakout strategy that identifies and trades range breakouts,
    consolidation breakouts, and chart pattern breakouts.
    
    Entry Conditions:
    - Price breaking above/below defined ranges
    - Volume expansion on breakout
    - Bollinger Band squeeze and expansion
    - Support/resistance level breaks
    - Triangle, flag, and pennant breakouts
    - Moving average breakouts
    
    Exit Conditions:
    - Failed breakout (false breakout)
    - Target achievement based on range size
    - ATR-based trailing stops
    - Volume decline after breakout
    """
    
    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            # Range detection
            'range_periods': 20,
            'range_threshold': 0.02,  # 2% range size minimum
            'breakout_threshold': 0.005,  # 0.5% breakout confirmation
            
            # Bollinger Band squeeze
            'bb_period': 20,
            'bb_std': 2.0,
            'squeeze_threshold': 0.1,  # Tight squeeze threshold
            'expansion_threshold': 0.15,  # Expansion confirmation
            
            # Volume confirmation
            'volume_ma_period': 20,
            'volume_breakout_multiplier': 1.5,  # 50% above average
            'volume_confirmation_periods': 3,
            
            # Moving averages
            'sma_fast': 20,
            'sma_slow': 50,
            'ema_period': 21,
            
            # ATR for stops and targets
            'atr_period': 14,
            'atr_stop_multiplier': 1.5,
            'atr_target_multiplier': 3.0,
            
            # Pattern recognition
            'triangle_periods': 15,
            'flag_periods': 10,
            'consolidation_periods': 12,
            'support_resistance_touches': 2,
            
            # Risk management
            'min_risk_reward': 2.0,
            'max_holding_periods': 72,  # Hours
            'min_confidence': 0.65,
            'false_breakout_threshold': 0.003,  # 0.3%
            
            # Filters
            'trend_filter': True,
            'volume_filter': True,
            'volatility_filter': True,
            'time_filter': True  # Avoid news times
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("breakout_punch", default_params)
        
        # Initialize indicators
        self.bb = BollingerBandsIndicator(
            period=self.parameters['bb_period'],
            std_dev=self.parameters['bb_std']
        )
        self.atr = ATRIndicator(period=self.parameters['atr_period'])
        self.sma_fast = SMAIndicator(period=self.parameters['sma_fast'])
        self.sma_slow = SMAIndicator(period=self.parameters['sma_slow'])
        self.ema = EMAIndicator(period=self.parameters['ema_period'])
        self.volume_roc = VolumeROCIndicator(period=5)
        self.obv = OBVIndicator()
    
    async def generate_signals(
        self, 
        symbol: str, 
        df: pd.DataFrame, 
        indicators: Dict[str, Any]
    ) -> List[Signal]:
        """Generate breakout trading signals"""
        
        if len(df) < max(self.parameters['sma_slow'], self.parameters['range_periods']) + 20:
            return []
        
        signals = []
        
        try:
            # Calculate indicators
            bb_data = self.bb.calculate(df)
            atr_values = self.atr.calculate(df)
            sma_fast_values = self.sma_fast.calculate(df)
            sma_slow_values = self.sma_slow.calculate(df)
            ema_values = self.ema.calculate(df)
            volume_roc_values = self.volume_roc.calculate(df)
            obv_values = self.obv.calculate(df)
            
            # Get current values
            current_price = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            current_time = df.index[-1]
            
            # Calculate volume moving average
            volume_ma = df['volume'].rolling(self.parameters['volume_ma_period']).mean().iloc[-1]
            volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1
            
            # Detect ranges and breakouts
            ranges = self._detect_ranges(df)
            
            # Check for bullish breakouts
            bullish_breakout = self._check_bullish_breakout(
                df, current_price, bb_data, atr_values.iloc[-1],
                sma_fast_values.iloc[-1], sma_slow_values.iloc[-1],
                ema_values.iloc[-1], volume_ratio, ranges
            )
            
            if bullish_breakout:
                signal = self._create_breakout_signal(
                    symbol, current_price, current_time, atr_values.iloc[-1],
                    bullish_breakout, 'buy'
                )
                if signal and signal.confidence >= self.parameters['min_confidence']:
                    signals.append(signal)
            
            # Check for bearish breakouts
            bearish_breakout = self._check_bearish_breakout(
                df, current_price, bb_data, atr_values.iloc[-1],
                sma_fast_values.iloc[-1], sma_slow_values.iloc[-1],
                ema_values.iloc[-1], volume_ratio, ranges
            )
            
            if bearish_breakout:
                signal = self._create_breakout_signal(
                    symbol, current_price, current_time, atr_values.iloc[-1],
                    bearish_breakout, 'sell'
                )
                if signal and signal.confidence >= self.parameters['min_confidence']:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating breakout signals for {symbol}: {e}")
            return []
    
    def _detect_ranges(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect trading ranges in price data"""
        ranges = []
        
        try:
            period = self.parameters['range_periods']
            recent_data = df.tail(period * 2)  # Look at more data for better range detection
            
            # Calculate rolling highs and lows
            rolling_high = recent_data['high'].rolling(period).max()
            rolling_low = recent_data['low'].rolling(period).min()
            
            # Current range
            current_high = rolling_high.iloc[-1]
            current_low = rolling_low.iloc[-1]
            range_size = (current_high - current_low) / current_low
            
            if range_size >= self.parameters['range_threshold']:
                ranges.append({
                    'high': current_high,
                    'low': current_low,
                    'size': range_size,
                    'middle': (current_high + current_low) / 2,
                    'age': period  # How long this range has been forming
                })
            
            # Also detect shorter-term ranges
            short_period = period // 2
            short_high = recent_data['high'].tail(short_period).max()
            short_low = recent_data['low'].tail(short_period).min()
            short_range_size = (short_high - short_low) / short_low
            
            if short_range_size >= self.parameters['range_threshold'] * 0.5:
                ranges.append({
                    'high': short_high,
                    'low': short_low,
                    'size': short_range_size,
                    'middle': (short_high + short_low) / 2,
                    'age': short_period
                })
            
        except Exception as e:
            logger.error(f"Error detecting ranges: {e}")
        
        return ranges
    
    def _check_bullish_breakout(
        self,
        df: pd.DataFrame,
        current_price: float,
        bb_data: Dict[str, pd.Series],
        atr: float,
        sma_fast: float,
        sma_slow: float,
        ema: float,
        volume_ratio: float,
        ranges: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Check for bullish breakout conditions"""
        
        conditions = {}
        score = 0
        max_score = 0
        breakout_level = None
        range_size = 0
        
        # Range breakout
        max_score += 30
        for range_data in ranges:
            resistance = range_data['high']
            breakout_price = resistance * (1 + self.parameters['breakout_threshold'])
            
            if current_price >= breakout_price:
                conditions['range_breakout'] = True
                score += 30
                breakout_level = resistance
                range_size = range_data['size']
                break
        
        # Bollinger Band breakout
        max_score += 20
        bb_upper = bb_data['upper'].iloc[-1]
        bb_middle = bb_data['middle'].iloc[-1]
        bb_width = (bb_data['upper'].iloc[-1] - bb_data['lower'].iloc[-1]) / bb_middle
        
        # Check for squeeze followed by expansion
        if bb_width <= self.parameters['squeeze_threshold']:
            # Was in squeeze
            prev_bb_width = (bb_data['upper'].iloc[-2] - bb_data['lower'].iloc[-2]) / bb_data['middle'].iloc[-2]
            if bb_width > prev_bb_width and current_price > bb_upper:
                conditions['bb_squeeze_breakout'] = True
                score += 20
        elif current_price > bb_upper:
            conditions['bb_breakout'] = True
            score += 15
        
        # Moving average breakout
        max_score += 15
        if self.parameters['trend_filter']:
            if (current_price > sma_fast > sma_slow and 
                current_price > ema and
                sma_fast > sma_slow):
                conditions['ma_alignment'] = True
                score += 15
        else:
            score += 15
        
        # Volume confirmation
        max_score += 15
        if self.parameters['volume_filter']:
            if volume_ratio >= self.parameters['volume_breakout_multiplier']:
                conditions['volume_breakout'] = True
                score += 15
        else:
            score += 15
        
        # Price momentum
        max_score += 10
        price_change = (current_price - df['close'].iloc[-2]) / df['close'].iloc[-2]
        if price_change > 0.002:  # 0.2% momentum
            conditions['price_momentum'] = True
            score += 10
        
        # Support/resistance break confirmation
        max_score += 10
        if self._check_support_resistance_break(df, current_price, 'bullish'):
            conditions['sr_break'] = True
            score += 10
        
        confidence = score / max_score if max_score > 0 else 0
        
        if confidence >= 0.6:
            return {
                'conditions': conditions,
                'confidence': confidence,
                'score': score,
                'max_score': max_score,
                'breakout_level': breakout_level or bb_upper,
                'range_size': range_size,
                'volume_ratio': volume_ratio
            }
        
        return None
    
    def _check_bearish_breakout(
        self,
        df: pd.DataFrame,
        current_price: float,
        bb_data: Dict[str, pd.Series],
        atr: float,
        sma_fast: float,
        sma_slow: float,
        ema: float,
        volume_ratio: float,
        ranges: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Check for bearish breakout conditions"""
        
        conditions = {}
        score = 0
        max_score = 0
        breakout_level = None
        range_size = 0
        
        # Range breakdown
        max_score += 30
        for range_data in ranges:
            support = range_data['low']
            breakdown_price = support * (1 - self.parameters['breakout_threshold'])
            
            if current_price <= breakdown_price:
                conditions['range_breakdown'] = True
                score += 30
                breakout_level = support
                range_size = range_data['size']
                break
        
        # Bollinger Band breakdown
        max_score += 20
        bb_lower = bb_data['lower'].iloc[-1]
        bb_middle = bb_data['middle'].iloc[-1]
        bb_width = (bb_data['upper'].iloc[-1] - bb_data['lower'].iloc[-1]) / bb_middle
        
        if bb_width <= self.parameters['squeeze_threshold']:
            prev_bb_width = (bb_data['upper'].iloc[-2] - bb_data['lower'].iloc[-2]) / bb_data['middle'].iloc[-2]
            if bb_width > prev_bb_width and current_price < bb_lower:
                conditions['bb_squeeze_breakdown'] = True
                score += 20
        elif current_price < bb_lower:
            conditions['bb_breakdown'] = True
            score += 15
        
        # Moving average breakdown
        max_score += 15
        if self.parameters['trend_filter']:
            if (current_price < sma_fast < sma_slow and 
                current_price < ema and
                sma_fast < sma_slow):
                conditions['ma_alignment'] = True
                score += 15
        else:
            score += 15
        
        # Volume confirmation
        max_score += 15
        if self.parameters['volume_filter']:
            if volume_ratio >= self.parameters['volume_breakout_multiplier']:
                conditions['volume_breakdown'] = True
                score += 15
        else:
            score += 15
        
        # Price momentum
        max_score += 10
        price_change = (current_price - df['close'].iloc[-2]) / df['close'].iloc[-2]
        if price_change < -0.002:  # -0.2% momentum
            conditions['price_momentum'] = True
            score += 10
        
        # Support/resistance break confirmation
        max_score += 10
        if self._check_support_resistance_break(df, current_price, 'bearish'):
            conditions['sr_break'] = True
            score += 10
        
        confidence = score / max_score if max_score > 0 else 0
        
        if confidence >= 0.6:
            return {
                'conditions': conditions,
                'confidence': confidence,
                'score': score,
                'max_score': max_score,
                'breakout_level': breakout_level or bb_lower,
                'range_size': range_size,
                'volume_ratio': volume_ratio
            }
        
        return None
    
    def _check_support_resistance_break(
        self, 
        df: pd.DataFrame, 
        current_price: float, 
        direction: str
    ) -> bool:
        """Check if price is breaking significant support/resistance"""
        try:
            # Look for significant levels in recent data
            lookback = self.parameters['range_periods']
            recent_data = df.tail(lookback)
            
            if direction == 'bullish':
                # Find resistance levels (recent highs)
                resistance_levels = []
                for i in range(2, len(recent_data) - 2):
                    if (recent_data.iloc[i]['high'] > recent_data.iloc[i-1]['high'] and
                        recent_data.iloc[i]['high'] > recent_data.iloc[i-2]['high'] and
                        recent_data.iloc[i]['high'] > recent_data.iloc[i+1]['high'] and
                        recent_data.iloc[i]['high'] > recent_data.iloc[i+2]['high']):
                        resistance_levels.append(recent_data.iloc[i]['high'])
                
                # Check if current price is breaking any resistance
                for level in resistance_levels:
                    if current_price > level * (1 + self.parameters['breakout_threshold']):
                        return True
            
            else:  # bearish
                # Find support levels (recent lows)
                support_levels = []
                for i in range(2, len(recent_data) - 2):
                    if (recent_data.iloc[i]['low'] < recent_data.iloc[i-1]['low'] and
                        recent_data.iloc[i]['low'] < recent_data.iloc[i-2]['low'] and
                        recent_data.iloc[i]['low'] < recent_data.iloc[i+1]['low'] and
                        recent_data.iloc[i]['low'] < recent_data.iloc[i+2]['low']):
                        support_levels.append(recent_data.iloc[i]['low'])
                
                # Check if current price is breaking any support
                for level in support_levels:
                    if current_price < level * (1 - self.parameters['breakout_threshold']):
                        return True
        
        except Exception:
            pass
        
        return False
    
    def _create_breakout_signal(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        atr: float,
        signal_data: Dict[str, Any],
        direction: str
    ) -> Optional[Signal]:
        """Create breakout signal"""
        
        breakout_level = signal_data['breakout_level']
        range_size = signal_data.get('range_size', 0)
        
        if direction == 'buy':
            # Stop below breakout level
            stop_loss = breakout_level - (atr * self.parameters['atr_stop_multiplier'])
            
            # Target based on range size or ATR
            if range_size > 0:
                target_distance = max(
                    breakout_level * range_size,  # Range-based target
                    atr * self.parameters['atr_target_multiplier']  # ATR-based target
                )
            else:
                target_distance = atr * self.parameters['atr_target_multiplier']
            
            take_profit = price + target_distance
            risk = price - stop_loss
            reward = take_profit - price
            
        else:  # sell
            # Stop above breakout level
            stop_loss = breakout_level + (atr * self.parameters['atr_stop_multiplier'])
            
            # Target based on range size or ATR
            if range_size > 0:
                target_distance = max(
                    breakout_level * range_size,
                    atr * self.parameters['atr_target_multiplier']
                )
            else:
                target_distance = atr * self.parameters['atr_target_multiplier']
            
            take_profit = price - target_distance
            risk = stop_loss - price
            reward = price - take_profit
        
        # Risk-reward validation
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        if risk_reward_ratio < self.parameters['min_risk_reward']:
            return None
        
        return Signal(
            id=str(uuid.uuid4()),
            symbol=symbol,
            direction=direction,
            confidence=signal_data['confidence'],
            price=price,
            timestamp=timestamp,
            strategy=self.name,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=risk_reward_ratio,
            indicators={
                'conditions': signal_data['conditions'],
                'breakout_level': breakout_level,
                'range_size': range_size,
                'volume_ratio': signal_data['volume_ratio'],
                'atr': atr,
                'risk': risk,
                'reward': reward,
                'score': signal_data['score'],
                'max_score': signal_data['max_score']
            }
        )
    
    def get_required_indicators(self) -> List[str]:
        """Get list of required indicators"""
        return ['bollinger', 'atr', 'sma', 'ema', 'volume']
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters"""
        required_params = [
            'range_periods', 'bb_period', 'atr_period',
            'volume_breakout_multiplier', 'min_risk_reward',
            'min_confidence', 'breakout_threshold'
        ]
        
        for param in required_params:
            if param not in self.parameters:
                logger.error(f"Missing required parameter: {param}")
                return False
        
        if self.parameters['min_risk_reward'] < 1.0:
            logger.error("min_risk_reward must be >= 1.0")
            return False
        
        return True
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information"""
        return {
            'name': self.name,
            'description': 'Breakout strategy trading range breaks and pattern breakouts',
            'type': 'breakout',
            'timeframes': ['5m', '15m', '1h', '4h'],
            'parameters': self.parameters,
            'required_indicators': self.get_required_indicators(),
            'risk_level': 'moderate_to_high',
            'typical_holding_period': '1-24 hours',
            'market_conditions': 'consolidating markets ready to break'
        }