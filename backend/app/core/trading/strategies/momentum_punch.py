"""
Momentum Punch Strategy - Trades momentum breakouts with dynamic stops.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid

from app.core.trading.base import TradingStrategy, Signal
from app.core.indicators.momentum import RSIIndicator, MACDIndicator, StochasticIndicator
from app.core.indicators.trend import SMAIndicator, EMAIndicator
from app.core.indicators.volatility import BollingerBandsIndicator, ATRIndicator
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class MomentumPunchStrategy(TradingStrategy):
    """
    Momentum-based strategy that identifies strong directional moves
    and enters with proper risk management.
    
    Entry Conditions:
    - RSI breaking above 60 (bullish) or below 40 (bearish)
    - MACD histogram increasing
    - Price above/below key moving averages
    - Volume confirmation
    - Bollinger Band squeeze breakout
    
    Exit Conditions:
    - ATR-based trailing stops
    - RSI extreme levels (>80 or <20)
    - MACD divergence
    - Time-based exits
    """
    
    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            # RSI parameters
            'rsi_period': 14,
            'rsi_overbought': 80,
            'rsi_oversold': 20,
            'rsi_entry_bull': 60,
            'rsi_entry_bear': 40,
            
            # MACD parameters
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            
            # Moving average parameters
            'sma_fast': 20,
            'sma_slow': 50,
            'ema_period': 21,
            
            # Bollinger Bands
            'bb_period': 20,
            'bb_std': 2.0,
            'bb_squeeze_threshold': 0.1,  # Low volatility threshold
            
            # ATR for stops
            'atr_period': 14,
            'atr_multiplier': 2.0,
            
            # Volume confirmation
            'volume_ma_period': 20,
            'volume_threshold': 1.2,  # 20% above average
            
            # Risk management
            'min_risk_reward': 2.0,
            'max_holding_periods': 48,  # Hours
            'min_confidence': 0.4,  # Lowered from 0.65 to generate more signals
            
            # Signal filtering
            'trend_filter': True,
            'volume_filter': True,
            'volatility_filter': True
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("momentum_punch", default_params)
        
        # Initialize indicators
        self.rsi = RSIIndicator(period=self.parameters['rsi_period'])
        self.macd = MACDIndicator(
            fast=self.parameters['macd_fast'],
            slow=self.parameters['macd_slow'],
            signal=self.parameters['macd_signal']
        )
        self.sma_fast = SMAIndicator(periods=[self.parameters['sma_fast']])
        self.sma_slow = SMAIndicator(periods=[self.parameters['sma_slow']])
        self.ema = EMAIndicator(periods=[self.parameters['ema_period']])
        self.bb = BollingerBandsIndicator(
            period=self.parameters['bb_period'],
            std_dev=self.parameters['bb_std']
        )
        self.atr = ATRIndicator(period=self.parameters['atr_period'])
    
    async def generate_signals(
        self, 
        symbol: str, 
        df: pd.DataFrame, 
        indicators: Dict[str, Any]
    ) -> List[Signal]:
        """Generate momentum-based trading signals"""
        
        if len(df) < max(self.parameters['sma_slow'], self.parameters['macd_slow']) + 10:
            return []
        
        signals = []
        
        try:
            # Calculate all indicators
            rsi_result = await self.rsi.calculate(df)
            macd_result = await self.macd.calculate(df)
            sma_fast_result = await self.sma_fast.calculate(df)
            sma_slow_result = await self.sma_slow.calculate(df)
            ema_result = await self.ema.calculate(df)
            bb_result = await self.bb.calculate(df)
            atr_result = await self.atr.calculate(df)
            
            # Get current values (last row)
            current_price = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            current_time = df.index[-1]
            
            # RSI values
            rsi_current = rsi_result.values.iloc[-1]
            rsi_prev = rsi_result.values.iloc[-2]
            
            # MACD values
            macd_current = macd_result.values.iloc[-1]  # MACD line
            macd_signal_current = macd_result.additional_series['signal_line'].iloc[-1]
            macd_hist_current = macd_result.additional_series['histogram'].iloc[-1]
            macd_hist_prev = macd_result.additional_series['histogram'].iloc[-2]
            
            # Moving averages
            sma_fast_current = sma_fast_result.values.iloc[-1]
            sma_slow_current = sma_slow_result.values.iloc[-1]
            ema_current = ema_result.values.iloc[-1]
            
            # Bollinger Bands
            bb_middle = bb_result.values.iloc[-1]  # Middle band (SMA)
            bb_upper = bb_result.additional_series['upper_band'].iloc[-1]
            bb_lower = bb_result.additional_series['lower_band'].iloc[-1]
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle != 0 else 0
            
            # ATR
            atr_current = atr_result.values.iloc[-1]
            
            # Volume analysis
            volume_ma = df['volume'].rolling(self.parameters['volume_ma_period']).mean().iloc[-1]
            volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1
            
            # Check for bullish momentum signal
            bullish_signal = self._check_bullish_momentum(
                current_price, rsi_current, rsi_prev, macd_current, 
                macd_signal_current, macd_hist_current, macd_hist_prev,
                sma_fast_current, sma_slow_current, ema_current,
                bb_upper, bb_lower, bb_middle, bb_width,
                volume_ratio, atr_current
            )
            
            if bullish_signal:
                signal = self._create_bullish_signal(
                    symbol, current_price, current_time, atr_current, bullish_signal
                )
                if signal and signal.confidence >= self.parameters['min_confidence']:
                    signals.append(signal)
            
            # Check for bearish momentum signal
            bearish_signal = self._check_bearish_momentum(
                current_price, rsi_current, rsi_prev, macd_current,
                macd_signal_current, macd_hist_current, macd_hist_prev,
                sma_fast_current, sma_slow_current, ema_current,
                bb_upper, bb_lower, bb_middle, bb_width,
                volume_ratio, atr_current
            )
            
            if bearish_signal:
                signal = self._create_bearish_signal(
                    symbol, current_price, current_time, atr_current, bearish_signal
                )
                if signal and signal.confidence >= self.parameters['min_confidence']:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating momentum signals for {symbol}: {e}")
            return []
    
    def _check_bullish_momentum(
        self,
        price: float,
        rsi_current: float,
        rsi_prev: float,
        macd_current: float,
        macd_signal_current: float,
        macd_hist_current: float,
        macd_hist_prev: float,
        sma_fast: float,
        sma_slow: float,
        ema: float,
        bb_upper: float,
        bb_lower: float,
        bb_middle: float,
        bb_width: float,
        volume_ratio: float,
        atr: float
    ) -> Optional[Dict[str, Any]]:
        """Check for bullish momentum conditions"""
        
        conditions = {}
        score = 0
        max_score = 0
        
        # RSI momentum breakout
        max_score += 20
        if (rsi_current > self.parameters['rsi_entry_bull'] and 
            rsi_prev <= self.parameters['rsi_entry_bull'] and
            rsi_current < self.parameters['rsi_overbought']):
            conditions['rsi_breakout'] = True
            score += 20
        
        # MACD momentum
        max_score += 15
        if macd_current > macd_signal_current and macd_hist_current > macd_hist_prev:
            conditions['macd_momentum'] = True
            score += 15
        
        # Trend alignment
        max_score += 15
        if self.parameters['trend_filter']:
            if price > sma_fast > sma_slow and price > ema:
                conditions['trend_alignment'] = True
                score += 15
        else:
            score += 15  # Skip filter
        
        # Bollinger Band breakout
        max_score += 10
        if self.parameters['volatility_filter']:
            if bb_width < self.parameters['bb_squeeze_threshold']:
                # Squeeze breakout
                if price > bb_middle:
                    conditions['bb_squeeze_breakout'] = True
                    score += 10
        else:
            score += 10  # Skip filter
        
        # Volume confirmation
        max_score += 10
        if self.parameters['volume_filter']:
            if volume_ratio >= self.parameters['volume_threshold']:
                conditions['volume_confirmation'] = True
                score += 10
        else:
            score += 10  # Skip filter
        
        # Price position
        max_score += 10
        if price > bb_middle:
            conditions['price_position'] = True
            score += 10
        
        # Volatility check (ATR not too high)
        max_score += 10
        atr_pct = (atr / price) * 100
        if atr_pct < 5.0:  # Less than 5% volatility
            conditions['volatility_ok'] = True
            score += 10
        
        # MACD above zero line (additional momentum)
        max_score += 10
        if macd_current > 0:
            conditions['macd_positive'] = True
            score += 10
        
        confidence = score / max_score if max_score > 0 else 0
        
        # Lower threshold to generate more signals while still maintaining quality
        if confidence >= 0.4:  # At least 40% of conditions met
            return {
                'conditions': conditions,
                'confidence': confidence,
                'score': score,
                'max_score': max_score
            }
        
        return None
    
    def _check_bearish_momentum(
        self,
        price: float,
        rsi_current: float,
        rsi_prev: float,
        macd_current: float,
        macd_signal_current: float,
        macd_hist_current: float,
        macd_hist_prev: float,
        sma_fast: float,
        sma_slow: float,
        ema: float,
        bb_upper: float,
        bb_lower: float,
        bb_middle: float,
        bb_width: float,
        volume_ratio: float,
        atr: float
    ) -> Optional[Dict[str, Any]]:
        """Check for bearish momentum conditions"""
        
        conditions = {}
        score = 0
        max_score = 0
        
        # RSI momentum breakdown
        max_score += 20
        if (rsi_current < self.parameters['rsi_entry_bear'] and 
            rsi_prev >= self.parameters['rsi_entry_bear'] and
            rsi_current > self.parameters['rsi_oversold']):
            conditions['rsi_breakdown'] = True
            score += 20
        
        # MACD momentum
        max_score += 15
        if macd_current < macd_signal_current and macd_hist_current < macd_hist_prev:
            conditions['macd_momentum'] = True
            score += 15
        
        # Trend alignment
        max_score += 15
        if self.parameters['trend_filter']:
            if price < sma_fast < sma_slow and price < ema:
                conditions['trend_alignment'] = True
                score += 15
        else:
            score += 15  # Skip filter
        
        # Bollinger Band breakdown
        max_score += 10
        if self.parameters['volatility_filter']:
            if bb_width < self.parameters['bb_squeeze_threshold']:
                # Squeeze breakdown
                if price < bb_middle:
                    conditions['bb_squeeze_breakdown'] = True
                    score += 10
        else:
            score += 10  # Skip filter
        
        # Volume confirmation
        max_score += 10
        if self.parameters['volume_filter']:
            if volume_ratio >= self.parameters['volume_threshold']:
                conditions['volume_confirmation'] = True
                score += 10
        else:
            score += 10  # Skip filter
        
        # Price position
        max_score += 10
        if price < bb_middle:
            conditions['price_position'] = True
            score += 10
        
        # Volatility check
        max_score += 10
        atr_pct = (atr / price) * 100
        if atr_pct < 5.0:
            conditions['volatility_ok'] = True
            score += 10
        
        # MACD below zero line
        max_score += 10
        if macd_current < 0:
            conditions['macd_negative'] = True
            score += 10
        
        confidence = score / max_score if max_score > 0 else 0
        
        if confidence >= 0.4:
            return {
                'conditions': conditions,
                'confidence': confidence,
                'score': score,
                'max_score': max_score
            }
        
        return None
    
    def _create_bullish_signal(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        atr: float,
        signal_data: Dict[str, Any]
    ) -> Optional[Signal]:
        """Create bullish momentum signal"""
        
        # Calculate stop loss and take profit
        stop_loss = price - (atr * self.parameters['atr_multiplier'])
        risk = price - stop_loss
        
        # Calculate take profit based on risk-reward ratio
        take_profit = price + (risk * self.parameters['min_risk_reward'])
        
        # Risk-reward validation
        risk_reward_ratio = (take_profit - price) / risk if risk > 0 else 0
        
        if risk_reward_ratio < self.parameters['min_risk_reward']:
            return None
        
        return Signal(
            id=str(uuid.uuid4()),
            symbol=symbol,
            direction='buy',
            confidence=signal_data['confidence'],
            price=price,
            timestamp=timestamp,
            strategy=self.name,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=risk_reward_ratio,
            indicators={
                'conditions': signal_data['conditions'],
                'atr': atr,
                'risk': risk,
                'score': signal_data['score'],
                'max_score': signal_data['max_score']
            }
        )
    
    def _create_bearish_signal(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        atr: float,
        signal_data: Dict[str, Any]
    ) -> Optional[Signal]:
        """Create bearish momentum signal"""
        
        # Calculate stop loss and take profit for short
        stop_loss = price + (atr * self.parameters['atr_multiplier'])
        risk = stop_loss - price
        
        # Calculate take profit
        take_profit = price - (risk * self.parameters['min_risk_reward'])
        
        # Risk-reward validation
        risk_reward_ratio = (price - take_profit) / risk if risk > 0 else 0
        
        if risk_reward_ratio < self.parameters['min_risk_reward']:
            return None
        
        return Signal(
            id=str(uuid.uuid4()),
            symbol=symbol,
            direction='sell',
            confidence=signal_data['confidence'],
            price=price,
            timestamp=timestamp,
            strategy=self.name,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=risk_reward_ratio,
            indicators={
                'conditions': signal_data['conditions'],
                'atr': atr,
                'risk': risk,
                'score': signal_data['score'],
                'max_score': signal_data['max_score']
            }
        )
    
    def get_required_indicators(self) -> List[str]:
        """Get list of required indicators"""
        return ['rsi', 'macd', 'sma', 'ema', 'bollinger', 'atr']
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters"""
        required_params = [
            'rsi_period', 'macd_fast', 'macd_slow', 'macd_signal',
            'sma_fast', 'sma_slow', 'bb_period', 'atr_period',
            'min_risk_reward', 'min_confidence'
        ]
        
        for param in required_params:
            if param not in self.parameters:
                logger.error(f"Missing required parameter: {param}")
                return False
        
        # Validate parameter ranges
        if self.parameters['min_risk_reward'] < 1.0:
            logger.error("min_risk_reward must be >= 1.0")
            return False
        
        if not 0 < self.parameters['min_confidence'] <= 1.0:
            logger.error("min_confidence must be between 0 and 1")
            return False
        
        return True
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information"""
        return {
            'name': self.name,
            'description': 'Momentum-based strategy trading breakouts with proper risk management',
            'type': 'momentum',
            'timeframes': ['5m', '15m', '1h', '4h'],
            'parameters': self.parameters,
            'required_indicators': self.get_required_indicators(),
            'risk_level': 'moderate',
            'typical_holding_period': '2-24 hours',
            'market_conditions': 'trending markets with good volatility'
        }