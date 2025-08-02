"""
Trend Punch Strategy - Follows strong trends with pullback entries.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid

from app.core.trading.base import TradingStrategy, Signal
from app.core.indicators.trend import SMAIndicator, EMAIndicator
from app.core.indicators.momentum import RSIIndicator, MACDIndicator
from app.core.indicators.volatility import ATRIndicator
from app.core.indicators.volume import OBVIndicator
from app.core.indicators.adx import ADXIndicator
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class TrendPunchStrategy(TradingStrategy):
    """
    Trend-following strategy that enters on pullbacks in strong trends
    and rides the trend with trailing stops.
    
    Entry Conditions:
    - Strong trend confirmed by multiple timeframes
    - ADX showing strong directional movement
    - Price pullback to key moving averages
    - RSI pullback but not oversold/overbought
    - Volume supporting the trend
    - MACD alignment with trend
    
    Exit Conditions:
    - Trend reversal signals
    - Moving average breaks
    - ADX declining below threshold
    - Trailing stop hits
    - Target achievement
    """
    
    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            # Trend identification
            'sma_fast': 20,
            'sma_medium': 50,
            'sma_slow': 200,
            'ema_fast': 12,
            'ema_slow': 26,
            
            # ADX for trend strength
            'adx_period': 14,
            'adx_threshold': 25,  # Strong trend threshold
            'adx_very_strong': 40,
            
            # MACD
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            
            # RSI for pullback entries
            'rsi_period': 14,
            'rsi_pullback_bull_max': 45,  # Max RSI for bullish pullback entry
            'rsi_pullback_bear_min': 55,  # Min RSI for bearish pullback entry
            'rsi_extreme_high': 80,
            'rsi_extreme_low': 20,
            
            # ATR for stops and position sizing
            'atr_period': 14,
            'atr_stop_multiplier': 2.5,
            'atr_trail_multiplier': 2.0,
            
            # Pullback parameters
            'pullback_max_pct': 0.08,  # Max 8% pullback from trend high/low
            'pullback_ma_levels': [20, 50],  # MAs to watch for pullback support
            'pullback_min_bars': 2,  # Minimum bars for pullback
            'pullback_max_bars': 10,  # Maximum bars for pullback
            
            # Volume confirmation
            'volume_ma_period': 20,
            'volume_trend_threshold': 1.1,  # 10% above average
            
            # Risk management
            'min_risk_reward': 2.5,
            'max_holding_periods': 168,  # Hours (1 week max)
            'min_confidence': 0.4,  # Lowered from 0.7 to generate more signals
            'position_size_atr_factor': 0.02,  # 2% risk per ATR
            
            # Trend filters
            'require_all_ma_alignment': True,
            'require_adx_rising': True,
            'require_macd_alignment': True,
            'require_volume_trend': True,
            
            # Exit conditions
            'trail_stop_trigger_pct': 0.15,  # Start trailing after 15% profit
            'trend_reversal_bars': 3,  # Bars to confirm trend reversal
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("trend_punch", default_params)
        
        # Initialize indicators
        self.sma_fast = SMAIndicator(periods=[self.parameters['sma_fast']])
        self.sma_medium = SMAIndicator(periods=[self.parameters['sma_medium']])
        self.sma_slow = SMAIndicator(periods=[self.parameters['sma_slow']])
        self.ema_fast = EMAIndicator(periods=[self.parameters['ema_fast']])
        self.ema_slow = EMAIndicator(periods=[self.parameters['ema_slow']])
        
        self.adx = ADXIndicator(period=self.parameters['adx_period'])
        self.macd = MACDIndicator(
            fast=self.parameters['macd_fast'],
            slow=self.parameters['macd_slow'],
            signal=self.parameters['macd_signal']
        )
        self.rsi = RSIIndicator(period=self.parameters['rsi_period'])
        self.atr = ATRIndicator(period=self.parameters['atr_period'])
        self.obv = OBVIndicator()
    
    async def generate_signals(
        self, 
        symbol: str, 
        df: pd.DataFrame, 
        indicators: Dict[str, Any]
    ) -> List[Signal]:
        """Generate trend-following signals"""
        
        if len(df) < max(self.parameters['sma_slow'], self.parameters['adx_period']) + 20:
            return []
        
        signals = []
        
        try:
            # Calculate all indicators
            sma_fast_result = await self.sma_fast.calculate(df)
            sma_medium_result = await self.sma_medium.calculate(df)
            sma_slow_result = await self.sma_slow.calculate(df)
            ema_fast_result = await self.ema_fast.calculate(df)
            ema_slow_result = await self.ema_slow.calculate(df)
            
            adx_result = await self.adx.calculate(df)
            macd_result = await self.macd.calculate(df)
            rsi_result = await self.rsi.calculate(df)
            atr_result = await self.atr.calculate(df)
            obv_result = await self.obv.calculate(df)
            
            # Get current values
            current_price = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            current_time = df.index[-1]
            
            # Volume analysis
            volume_ma = df['volume'].rolling(self.parameters['volume_ma_period']).mean().iloc[-1]
            volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1
            
            # Analyze trend direction and strength
            trend_analysis = self._analyze_trend(
                df, sma_fast_result, sma_medium_result, sma_slow_result,
                ema_fast_result, ema_slow_result, adx_result, macd_result, obv_result
            )
            
            if not trend_analysis:
                return []
            
            # Check for bullish pullback entry
            if trend_analysis['direction'] == 'bullish':
                pullback_signal = self._check_bullish_pullback(
                    df, current_price, trend_analysis,
                    sma_fast_result.values.iloc[-1], sma_medium_result.values.iloc[-1],
                    rsi_result.values.iloc[-1], atr_result.values.iloc[-1], volume_ratio
                )
                
                if pullback_signal:
                    signal = self._create_trend_signal(
                        symbol, current_price, current_time, atr_result.values.iloc[-1],
                        pullback_signal, 'buy', trend_analysis
                    )
                    if signal and signal.confidence >= self.parameters['min_confidence']:
                        signals.append(signal)
            
            # Check for bearish pullback entry
            elif trend_analysis['direction'] == 'bearish':
                pullback_signal = self._check_bearish_pullback(
                    df, current_price, trend_analysis,
                    sma_fast_result.values.iloc[-1], sma_medium_result.values.iloc[-1],
                    rsi_result.values.iloc[-1], atr_result.values.iloc[-1], volume_ratio
                )
                
                if pullback_signal:
                    signal = self._create_trend_signal(
                        symbol, current_price, current_time, atr_result.values.iloc[-1],
                        pullback_signal, 'sell', trend_analysis
                    )
                    if signal and signal.confidence >= self.parameters['min_confidence']:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating trend signals for {symbol}: {e}")
            return []
    
    def _analyze_trend(
        self,
        df: pd.DataFrame,
        sma_fast_result: Any,  # IndicatorResult
        sma_medium_result: Any,  # IndicatorResult
        sma_slow_result: Any,  # IndicatorResult
        ema_fast_result: Any,  # IndicatorResult
        ema_slow_result: Any,  # IndicatorResult
        adx_result: Any,  # IndicatorResult
        macd_result: Any,  # IndicatorResult
        obv_result: Any  # IndicatorResult
    ) -> Optional[Dict[str, Any]]:
        """Analyze overall trend direction and strength"""
        
        current_price = df['close'].iloc[-1]
        
        # Moving average alignment
        sma_fast_current = sma_fast_result.values.iloc[-1]
        sma_medium_current = sma_medium_result.values.iloc[-1]
        sma_slow_current = sma_slow_result.values.iloc[-1]
        ema_fast_current = ema_fast_result.values.iloc[-1]
        ema_slow_current = ema_slow_result.values.iloc[-1]
        
        # ADX values
        adx_current = adx_result.values.iloc[-1]  # ADX is the primary value
        di_plus = adx_result.additional_series['di_plus'].iloc[-1]
        di_minus = adx_result.additional_series['di_minus'].iloc[-1]
        
        # MACD values
        macd_current = macd_result.values.iloc[-1]  # MACD line
        macd_signal = macd_result.additional_series['signal_line'].iloc[-1]
        
        # OBV trend
        obv_values = obv_result.values
        obv_ma = obv_values.rolling(20).mean()
        obv_trend = 'rising' if obv_values.iloc[-1] > obv_ma.iloc[-1] else 'falling'
        
        # Determine trend direction
        bullish_signals = 0
        bearish_signals = 0
        
        # Moving average alignment
        if (current_price > sma_fast_current > sma_medium_current > sma_slow_current and
            ema_fast_current > ema_slow_current):
            bullish_signals += 3
        elif (current_price < sma_fast_current < sma_medium_current < sma_slow_current and
              ema_fast_current < ema_slow_current):
            bearish_signals += 3
        
        # ADX direction
        if adx_current >= self.parameters['adx_threshold']:
            if di_plus > di_minus:
                bullish_signals += 2
            else:
                bearish_signals += 2
        
        # MACD alignment
        if macd_current > macd_signal and macd_current > 0:
            bullish_signals += 1
        elif macd_current < macd_signal and macd_current < 0:
            bearish_signals += 1
        
        # OBV trend
        if obv_trend == 'rising':
            bullish_signals += 1
        else:
            bearish_signals += 1
        
        # Determine overall trend
        if bullish_signals >= 4 and bullish_signals > bearish_signals:
            direction = 'bullish'
        elif bearish_signals >= 4 and bearish_signals > bullish_signals:
            direction = 'bearish'
        else:
            return None  # No clear trend
        
        # Calculate trend strength
        strength_score = adx_current / 100  # Normalize ADX
        if adx_current >= self.parameters['adx_very_strong']:
            strength = 'very_strong'
            strength_score += 0.2
        elif adx_current >= self.parameters['adx_threshold']:
            strength = 'strong'
        else:
            strength = 'weak'
            strength_score *= 0.5
        
        # Check if ADX is rising (strengthening trend)
        adx_rising = adx_result.values.iloc[-1] > adx_result.values.iloc[-3]
        
        return {
            'direction': direction,
            'strength': strength,
            'strength_score': min(strength_score, 1.0),
            'adx': adx_current,
            'adx_rising': adx_rising,
            'di_plus': di_plus,
            'di_minus': di_minus,
            'bullish_signals': bullish_signals,
            'bearish_signals': bearish_signals,
            'obv_trend': obv_trend
        }
    
    def _check_bullish_pullback(
        self,
        df: pd.DataFrame,
        current_price: float,
        trend_analysis: Dict[str, Any],
        sma_fast: float,
        sma_medium: float,
        rsi_current: float,
        atr: float,
        volume_ratio: float
    ) -> Optional[Dict[str, Any]]:
        """Check for bullish pullback entry opportunity"""
        
        conditions = {}
        score = 0
        max_score = 0
        
        # Find recent trend high
        lookback = self.parameters['pullback_max_bars'] + 5
        recent_high = df['high'].tail(lookback).max()
        pullback_pct = (recent_high - current_price) / recent_high
        
        # Pullback size validation
        max_score += 25
        if 0.01 <= pullback_pct <= self.parameters['pullback_max_pct']:
            conditions['pullback_size_ok'] = True
            if pullback_pct <= 0.05:  # Sweet spot: 1-5% pullback
                score += 25
            else:
                score += 20
        
        # RSI in pullback zone (not oversold, but pulled back)
        max_score += 20
        if (self.parameters['rsi_extreme_low'] < rsi_current <= 
            self.parameters['rsi_pullback_bull_max']):
            conditions['rsi_pullback_zone'] = True
            score += 20
        
        # Price near key moving average support
        max_score += 20
        ma_support_found = False
        for ma_period in self.parameters['pullback_ma_levels']:
            if ma_period == 20:
                ma_value = sma_fast
            elif ma_period == 50:
                ma_value = sma_medium
            else:
                continue
            
            distance_to_ma = abs(current_price - ma_value) / ma_value
            if distance_to_ma <= 0.02:  # Within 2% of MA
                conditions[f'ma_{ma_period}_support'] = True
                ma_support_found = True
                break
        
        if ma_support_found:
            score += 20
        
        # Trend strength confirmation
        max_score += 15
        if trend_analysis['strength_score'] >= 0.6:
            conditions['strong_trend'] = True
            score += 15
        elif trend_analysis['strength_score'] >= 0.4:
            score += 10
        
        # ADX rising (trend getting stronger)
        max_score += 10
        if not self.parameters['require_adx_rising'] or trend_analysis['adx_rising']:
            conditions['adx_rising'] = True
            score += 10
        
        # Volume confirmation
        max_score += 10
        if (not self.parameters['require_volume_trend'] or 
            volume_ratio >= self.parameters['volume_trend_threshold']):
            conditions['volume_ok'] = True
            score += 10
        
        confidence = score / max_score if max_score > 0 else 0
        
        if confidence >= 0.6:
            return {
                'conditions': conditions,
                'confidence': confidence,
                'score': score,
                'max_score': max_score,
                'pullback_pct': pullback_pct,
                'recent_high': recent_high,
                'trend_strength': trend_analysis['strength_score']
            }
        
        return None
    
    def _check_bearish_pullback(
        self,
        df: pd.DataFrame,
        current_price: float,
        trend_analysis: Dict[str, Any],
        sma_fast: float,
        sma_medium: float,
        rsi_current: float,
        atr: float,
        volume_ratio: float
    ) -> Optional[Dict[str, Any]]:
        """Check for bearish pullback entry opportunity"""
        
        conditions = {}
        score = 0
        max_score = 0
        
        # Find recent trend low
        lookback = self.parameters['pullback_max_bars'] + 5
        recent_low = df['low'].tail(lookback).min()
        pullback_pct = (current_price - recent_low) / recent_low
        
        # Pullback size validation
        max_score += 25
        if 0.01 <= pullback_pct <= self.parameters['pullback_max_pct']:
            conditions['pullback_size_ok'] = True
            if pullback_pct <= 0.05:
                score += 25
            else:
                score += 20
        
        # RSI in pullback zone (not overbought, but pulled back)
        max_score += 20
        if (self.parameters['rsi_pullback_bear_min'] <= rsi_current < 
            self.parameters['rsi_extreme_high']):
            conditions['rsi_pullback_zone'] = True
            score += 20
        
        # Price near key moving average resistance
        max_score += 20
        ma_resistance_found = False
        for ma_period in self.parameters['pullback_ma_levels']:
            if ma_period == 20:
                ma_value = sma_fast
            elif ma_period == 50:
                ma_value = sma_medium
            else:
                continue
            
            distance_to_ma = abs(current_price - ma_value) / ma_value
            if distance_to_ma <= 0.02:
                conditions[f'ma_{ma_period}_resistance'] = True
                ma_resistance_found = True
                break
        
        if ma_resistance_found:
            score += 20
        
        # Trend strength confirmation
        max_score += 15
        if trend_analysis['strength_score'] >= 0.6:
            conditions['strong_trend'] = True
            score += 15
        elif trend_analysis['strength_score'] >= 0.4:
            score += 10
        
        # ADX rising
        max_score += 10
        if not self.parameters['require_adx_rising'] or trend_analysis['adx_rising']:
            conditions['adx_rising'] = True
            score += 10
        
        # Volume confirmation
        max_score += 10
        if (not self.parameters['require_volume_trend'] or 
            volume_ratio >= self.parameters['volume_trend_threshold']):
            conditions['volume_ok'] = True
            score += 10
        
        confidence = score / max_score if max_score > 0 else 0
        
        if confidence >= 0.6:
            return {
                'conditions': conditions,
                'confidence': confidence,
                'score': score,
                'max_score': max_score,
                'pullback_pct': pullback_pct,
                'recent_low': recent_low,
                'trend_strength': trend_analysis['strength_score']
            }
        
        return None
    
    def _create_trend_signal(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        atr: float,
        signal_data: Dict[str, Any],
        direction: str,
        trend_analysis: Dict[str, Any]
    ) -> Optional[Signal]:
        """Create trend-following signal"""
        
        if direction == 'buy':
            # Stop below recent swing low or ATR-based
            stop_loss = price - (atr * self.parameters['atr_stop_multiplier'])
            
            # Target based on trend strength and ATR
            target_multiplier = 3.0 + (trend_analysis['strength_score'] * 2.0)  # 3-5x ATR
            take_profit = price + (atr * target_multiplier)
            
            risk = price - stop_loss
            reward = take_profit - price
            
        else:  # sell
            # Stop above recent swing high or ATR-based
            stop_loss = price + (atr * self.parameters['atr_stop_multiplier'])
            
            # Target based on trend strength
            target_multiplier = 3.0 + (trend_analysis['strength_score'] * 2.0)
            take_profit = price - (atr * target_multiplier)
            
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
                'pullback_pct': signal_data.get('pullback_pct', 0),
                'trend_direction': trend_analysis['direction'],
                'trend_strength': trend_analysis['strength'],
                'adx': trend_analysis['adx'],
                'atr': atr,
                'risk': risk,
                'reward': reward,
                'score': signal_data['score'],
                'max_score': signal_data['max_score']
            }
        )
    
    def get_required_indicators(self) -> List[str]:
        """Get list of required indicators"""
        return ['sma', 'ema', 'adx', 'macd', 'rsi', 'atr', 'obv']
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters"""
        required_params = [
            'sma_fast', 'sma_medium', 'sma_slow',
            'adx_period', 'adx_threshold',
            'rsi_period', 'atr_period',
            'min_risk_reward', 'min_confidence'
        ]
        
        for param in required_params:
            if param not in self.parameters:
                logger.error(f"Missing required parameter: {param}")
                return False
        
        # Validate MA periods are in ascending order
        if not (self.parameters['sma_fast'] < self.parameters['sma_medium'] < 
                self.parameters['sma_slow']):
            logger.error("SMA periods must be in ascending order")
            return False
        
        return True
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information"""
        return {
            'name': self.name,
            'description': 'Trend-following strategy entering on pullbacks in strong trends',
            'type': 'trend_following',
            'timeframes': ['1h', '4h', '1d'],
            'parameters': self.parameters,
            'required_indicators': self.get_required_indicators(),
            'risk_level': 'moderate',
            'typical_holding_period': '1-7 days',
            'market_conditions': 'strong trending markets with clear direction'
        }