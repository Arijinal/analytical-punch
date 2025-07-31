"""
Value Punch Strategy - Mean reversion and oversold/overbought conditions.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid

from app.core.trading.base import TradingStrategy, Signal
from app.core.indicators.momentum import RSIIndicator, StochasticIndicator
from app.core.indicators.trend import SMAIndicator, EMAIndicator
from app.core.indicators.volatility import BollingerBandsIndicator, ATRIndicator
from app.core.indicators.levels import FibonacciIndicator
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ValuePunchStrategy(TradingStrategy):
    """
    Value-based mean reversion strategy that identifies oversold/overbought
    conditions and trades back to fair value.
    
    Entry Conditions:
    - RSI extreme levels with reversal signals
    - Price touching Bollinger Band extremes
    - Stochastic oversold/overbought with divergence
    - Fibonacci retracement levels
    - Volume divergence
    - Support/resistance confluence
    
    Exit Conditions:
    - Return to mean (moving averages)
    - RSI normalization
    - Bollinger Band middle touch
    - Time-based exits for failed reversals
    """
    
    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            # RSI parameters
            'rsi_period': 14,
            'rsi_extreme_high': 75,
            'rsi_extreme_low': 25,
            'rsi_exit_high': 55,
            'rsi_exit_low': 45,
            
            # Stochastic parameters
            'stoch_k_period': 14,
            'stoch_d_period': 3,
            'stoch_smooth': 3,
            'stoch_overbought': 80,
            'stoch_oversold': 20,
            
            # Bollinger Bands
            'bb_period': 20,
            'bb_std': 2.0,
            'bb_extreme_threshold': 0.95,  # How close to bands
            
            # Moving averages for mean reversion
            'sma_short': 10,
            'sma_medium': 20,
            'sma_long': 50,
            'ema_period': 21,
            
            # ATR for stops
            'atr_period': 14,
            'atr_multiplier': 1.5,  # Tighter stops for mean reversion
            
            # Fibonacci levels
            'fib_lookback': 50,
            'fib_levels': [0.382, 0.5, 0.618],
            'fib_tolerance': 0.002,  # 0.2% tolerance
            
            # Volume analysis
            'volume_ma_period': 20,
            'volume_divergence_periods': 5,
            
            # Risk management
            'min_risk_reward': 1.5,
            'max_holding_periods': 24,  # Hours
            'min_confidence': 0.4,  # Lowered from 0.6 to generate more signals
            
            # Mean reversion specific
            'price_distance_threshold': 0.02,  # 2% from mean
            'rsi_divergence_periods': 5,
            'volatility_threshold': 0.03,  # 3% ATR
            
            # Filter parameters
            'trend_filter': False,  # Don't filter by trend for mean reversion
            'volume_filter': True,
            'volatility_filter': True
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("value_punch", default_params)
        
        # Initialize indicators
        self.rsi = RSIIndicator(period=self.parameters['rsi_period'])
        self.stoch = StochasticIndicator(
            k_period=self.parameters['stoch_k_period'],
            d_period=self.parameters['stoch_d_period'],
            smooth=self.parameters['stoch_smooth']
        )
        self.sma_short = SMAIndicator(period=self.parameters['sma_short'])
        self.sma_medium = SMAIndicator(period=self.parameters['sma_medium'])
        self.sma_long = SMAIndicator(period=self.parameters['sma_long'])
        self.ema = EMAIndicator(period=self.parameters['ema_period'])
        self.bb = BollingerBandsIndicator(
            period=self.parameters['bb_period'],
            std_dev=self.parameters['bb_std']
        )
        self.atr = ATRIndicator(period=self.parameters['atr_period'])
        self.fib = FibonacciIndicator(lookback=self.parameters['fib_lookback'])
    
    async def generate_signals(
        self, 
        symbol: str, 
        df: pd.DataFrame, 
        indicators: Dict[str, Any]
    ) -> List[Signal]:
        """Generate value-based mean reversion signals"""
        
        if len(df) < max(self.parameters['sma_long'], self.parameters['fib_lookback']) + 10:
            return []
        
        signals = []
        
        try:
            # Calculate all indicators
            rsi_result = await self.rsi.calculate(df)
            stoch_result = await self.stoch.calculate(df)
            sma_short_result = await self.sma_short.calculate(df)
            sma_medium_result = await self.sma_medium.calculate(df)
            sma_long_result = await self.sma_long.calculate(df) 
            ema_result = await self.ema.calculate(df)
            bb_result = await self.bb.calculate(df)
            atr_result = await self.atr.calculate(df)
            fib_result = await self.fib.calculate(df)
            
            # Get current values
            current_price = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            current_time = df.index[-1]
            
            rsi_current = rsi_result.values.iloc[-1]
            stoch_k = stoch_result.values.iloc[-1]  # %K is the primary value
            stoch_d = stoch_result.additional_series['slow_d'].iloc[-1]
            
            sma_short_current = sma_short_result.values.iloc[-1]
            sma_medium_current = sma_medium_result.values.iloc[-1]
            sma_long_current = sma_long_result.values.iloc[-1]
            ema_current = ema_result.values.iloc[-1]
            
            bb_upper = bb_result.additional_series['upper_band'].iloc[-1]
            bb_lower = bb_result.additional_series['lower_band'].iloc[-1]
            bb_middle = bb_result.values.iloc[-1]  # Middle band is the primary value
            
            atr_current = atr_result.values.iloc[-1]
            
            # Volume analysis
            volume_ma = df['volume'].rolling(self.parameters['volume_ma_period']).mean().iloc[-1]
            volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1
            
            # Check for oversold bounce signal
            oversold_signal = self._check_oversold_conditions(
                df, current_price, rsi_result, stoch_result, bb_result,
                sma_short_current, sma_medium_current, sma_long_current,
                ema_current, fib_result, volume_ratio, atr_current
            )
            
            if oversold_signal:
                signal = self._create_bounce_signal(
                    symbol, current_price, current_time, atr_current, 
                    oversold_signal, 'buy'
                )
                if signal and signal.confidence >= self.parameters['min_confidence']:
                    signals.append(signal)
            
            # Check for overbought pullback signal
            overbought_signal = self._check_overbought_conditions(
                df, current_price, rsi_result, stoch_result, bb_result,
                sma_short_current, sma_medium_current, sma_long_current,
                ema_current, fib_result, volume_ratio, atr_current
            )
            
            if overbought_signal:
                signal = self._create_bounce_signal(
                    symbol, current_price, current_time, atr_current,
                    overbought_signal, 'sell'
                )
                if signal and signal.confidence >= self.parameters['min_confidence']:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating value signals for {symbol}: {e}")
            return []
    
    def _check_oversold_conditions(
        self,
        df: pd.DataFrame,
        current_price: float,
        rsi_result: Any,  # IndicatorResult
        stoch_result: Any,  # IndicatorResult
        bb_result: Any,  # IndicatorResult
        sma_short: float,
        sma_medium: float,
        sma_long: float,
        ema: float,
        fib_result: Any,  # IndicatorResult
        volume_ratio: float,
        atr: float
    ) -> Optional[Dict[str, Any]]:
        """Check for oversold bounce conditions"""
        
        conditions = {}
        score = 0
        max_score = 0
        
        # RSI oversold with potential reversal
        max_score += 25
        rsi_current = rsi_result.values.iloc[-1]
        rsi_prev = rsi_result.values.iloc[-2]
        if rsi_current <= self.parameters['rsi_extreme_low']:
            if rsi_current > rsi_prev:  # Starting to turn up
                conditions['rsi_oversold_reversal'] = True
                score += 25
            elif rsi_current <= 15:  # Extremely oversold
                conditions['rsi_extremely_oversold'] = True
                score += 20
        
        # RSI bullish divergence
        max_score += 15
        if self._check_rsi_bullish_divergence(df, rsi_result.values):
            conditions['rsi_bullish_divergence'] = True
            score += 15
        
        # Stochastic oversold
        max_score += 15
        stoch_k = stoch_result.values.iloc[-1]  # %K
        stoch_d = stoch_result.additional_series['slow_d'].iloc[-1]
        if (stoch_k <= self.parameters['stoch_oversold'] and 
            stoch_d <= self.parameters['stoch_oversold']):
            if stoch_k > stoch_d:  # K crossing above D
                conditions['stoch_oversold_cross'] = True
                score += 15
            else:
                conditions['stoch_oversold'] = True
                score += 10
        
        # Bollinger Band touch
        max_score += 15
        bb_lower = bb_result.additional_series['lower_band'].iloc[-1]
        bb_middle = bb_result.values.iloc[-1]  # Middle band
        distance_to_lower = (current_price - bb_lower) / bb_lower
        if distance_to_lower <= 0.01:  # Within 1% of lower band
            conditions['bb_lower_touch'] = True
            score += 15
        
        # Price below multiple moving averages (oversold)
        max_score += 10
        ma_count = 0
        if current_price < sma_short:
            ma_count += 1
        if current_price < sma_medium:
            ma_count += 1
        if current_price < sma_long:
            ma_count += 1
        if current_price < ema:
            ma_count += 1
        
        if ma_count >= 3:
            conditions['price_below_mas'] = True
            score += 10
        elif ma_count >= 2:
            score += 5
        
        # Fibonacci support level
        max_score += 10
        if self._check_fibonacci_support(current_price, fib_result):
            conditions['fib_support'] = True
            score += 10
        
        # Volume confirmation (higher volume on decline)
        max_score += 10
        if self.parameters['volume_filter']:
            if volume_ratio >= 1.2:  # 20% above average
                conditions['volume_confirmation'] = True
                score += 10
        else:
            score += 10
        
        # Volatility check
        max_score += 10
        if self.parameters['volatility_filter']:
            atr_pct = (atr / current_price) * 100
            if atr_pct >= 2.0:  # At least 2% volatility for good R:R
                conditions['volatility_ok'] = True
                score += 10
        else:
            score += 10
        
        confidence = score / max_score if max_score > 0 else 0
        
        if confidence >= 0.5:  # At least 50% of conditions for value plays
            return {
                'conditions': conditions,
                'confidence': confidence,
                'score': score,
                'max_score': max_score,
                'mean_price': (sma_short + sma_medium + ema) / 3
            }
        
        return None
    
    def _check_overbought_conditions(
        self,
        df: pd.DataFrame,
        current_price: float,
        rsi_result: Any,  # IndicatorResult
        stoch_result: Any,  # IndicatorResult
        bb_result: Any,  # IndicatorResult
        sma_short: float,
        sma_medium: float,
        sma_long: float,
        ema: float,
        fib_result: Any,  # IndicatorResult
        volume_ratio: float,
        atr: float
    ) -> Optional[Dict[str, Any]]:
        """Check for overbought pullback conditions"""
        
        conditions = {}
        score = 0
        max_score = 0
        
        # RSI overbought with potential reversal
        max_score += 25
        rsi_current = rsi_result.values.iloc[-1]
        rsi_prev = rsi_result.values.iloc[-2]
        if rsi_current >= self.parameters['rsi_extreme_high']:
            if rsi_current < rsi_prev:  # Starting to turn down
                conditions['rsi_overbought_reversal'] = True
                score += 25
            elif rsi_current >= 85:  # Extremely overbought
                conditions['rsi_extremely_overbought'] = True
                score += 20
        
        # RSI bearish divergence
        max_score += 15
        if self._check_rsi_bearish_divergence(df, rsi_result.values):
            conditions['rsi_bearish_divergence'] = True
            score += 15
        
        # Stochastic overbought
        max_score += 15
        stoch_k = stoch_result.values.iloc[-1]  # %K
        stoch_d = stoch_result.additional_series['slow_d'].iloc[-1]
        if (stoch_k >= self.parameters['stoch_overbought'] and 
            stoch_d >= self.parameters['stoch_overbought']):
            if stoch_k < stoch_d:  # K crossing below D
                conditions['stoch_overbought_cross'] = True
                score += 15
            else:
                conditions['stoch_overbought'] = True
                score += 10
        
        # Bollinger Band touch
        max_score += 15
        bb_upper = bb_result.additional_series['upper_band'].iloc[-1]
        distance_to_upper = (bb_upper - current_price) / bb_upper
        if distance_to_upper <= 0.01:  # Within 1% of upper band
            conditions['bb_upper_touch'] = True
            score += 15
        
        # Price above multiple moving averages (overbought)
        max_score += 10
        ma_count = 0
        if current_price > sma_short:
            ma_count += 1
        if current_price > sma_medium:
            ma_count += 1
        if current_price > sma_long:
            ma_count += 1
        if current_price > ema:
            ma_count += 1
        
        if ma_count >= 3:
            conditions['price_above_mas'] = True
            score += 10
        elif ma_count >= 2:
            score += 5
        
        # Fibonacci resistance level
        max_score += 10
        if self._check_fibonacci_resistance(current_price, fib_result):
            conditions['fib_resistance'] = True
            score += 10
        
        # Volume confirmation
        max_score += 10
        if self.parameters['volume_filter']:
            if volume_ratio >= 1.2:
                conditions['volume_confirmation'] = True
                score += 10
        else:
            score += 10
        
        # Volatility check
        max_score += 10
        if self.parameters['volatility_filter']:
            atr_pct = (atr / current_price) * 100
            if atr_pct >= 2.0:
                conditions['volatility_ok'] = True
                score += 10
        else:
            score += 10
        
        confidence = score / max_score if max_score > 0 else 0
        
        if confidence >= 0.5:
            return {
                'conditions': conditions,
                'confidence': confidence,
                'score': score,
                'max_score': max_score,
                'mean_price': (sma_short + sma_medium + ema) / 3
            }
        
        return None
    
    def _check_rsi_bullish_divergence(self, df: pd.DataFrame, rsi_values: pd.Series) -> bool:
        """Check for RSI bullish divergence"""
        try:
            periods = self.parameters['rsi_divergence_periods']
            if len(df) < periods * 2:
                return False
            
            # Get recent lows
            recent_prices = df['close'].tail(periods)
            recent_rsi = rsi_values.tail(periods)
            
            # Find the lowest price and corresponding RSI
            min_price_idx = recent_prices.idxmin()
            min_rsi_at_min_price = recent_rsi.loc[min_price_idx]
            
            # Check if current RSI is higher than RSI at price low
            current_rsi = rsi_values.iloc[-1]
            current_price = df['close'].iloc[-1]
            
            # Bullish divergence: price made lower low, RSI made higher low
            if (current_price <= recent_prices.min() and 
                current_rsi > min_rsi_at_min_price):
                return True
                
        except Exception:
            pass
        
        return False
    
    def _check_rsi_bearish_divergence(self, df: pd.DataFrame, rsi_values: pd.Series) -> bool:
        """Check for RSI bearish divergence"""
        try:
            periods = self.parameters['rsi_divergence_periods']
            if len(df) < periods * 2:
                return False
            
            # Get recent highs
            recent_prices = df['close'].tail(periods)
            recent_rsi = rsi_values.tail(periods)
            
            # Find the highest price and corresponding RSI
            max_price_idx = recent_prices.idxmax()
            max_rsi_at_max_price = recent_rsi.loc[max_price_idx]
            
            # Check if current RSI is lower than RSI at price high
            current_rsi = rsi_values.iloc[-1]
            current_price = df['close'].iloc[-1]
            
            # Bearish divergence: price made higher high, RSI made lower high
            if (current_price >= recent_prices.max() and 
                current_rsi < max_rsi_at_max_price):
                return True
                
        except Exception:
            pass
        
        return False
    
    def _check_fibonacci_support(self, current_price: float, fib_result: Any) -> bool:
        """Check if price is near Fibonacci support level"""
        try:
            # Check if we have additional_series with fib levels
            if hasattr(fib_result, 'additional_series'):
                for level in self.parameters['fib_levels']:
                    fib_level_name = f'fib_{int(level*1000)}'
                    if fib_level_name in fib_result.additional_series:
                        fib_price = fib_result.additional_series[fib_level_name].iloc[-1]
                        tolerance = fib_price * self.parameters['fib_tolerance']
                        
                        if abs(current_price - fib_price) <= tolerance and current_price >= fib_price:
                            return True
        except Exception:
            pass
        
        return False
    
    def _check_fibonacci_resistance(self, current_price: float, fib_result: Any) -> bool:
        """Check if price is near Fibonacci resistance level"""
        try:
            if hasattr(fib_result, 'additional_series'):
                for level in self.parameters['fib_levels']:
                    fib_level_name = f'fib_{int(level*1000)}'
                    if fib_level_name in fib_result.additional_series:
                        fib_price = fib_result.additional_series[fib_level_name].iloc[-1]
                        tolerance = fib_price * self.parameters['fib_tolerance']
                        
                        if abs(current_price - fib_price) <= tolerance and current_price <= fib_price:
                            return True
        except Exception:
            pass
        
        return False
    
    def _create_bounce_signal(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        atr: float,
        signal_data: Dict[str, Any],
        direction: str
    ) -> Optional[Signal]:
        """Create mean reversion signal"""
        
        mean_price = signal_data['mean_price']
        
        if direction == 'buy':
            # For oversold bounce
            stop_loss = price - (atr * self.parameters['atr_multiplier'])
            # Target the mean or a bit beyond
            take_profit = min(mean_price, price + (price - stop_loss) * self.parameters['min_risk_reward'])
            
            risk = price - stop_loss
            reward = take_profit - price
            
        else:  # sell
            # For overbought pullback
            stop_loss = price + (atr * self.parameters['atr_multiplier'])
            # Target the mean or a bit beyond
            take_profit = max(mean_price, price - (stop_loss - price) * self.parameters['min_risk_reward'])
            
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
                'mean_price': mean_price,
                'atr': atr,
                'risk': risk,
                'reward': reward,
                'score': signal_data['score'],
                'max_score': signal_data['max_score']
            }
        )
    
    def get_required_indicators(self) -> List[str]:
        """Get list of required indicators"""
        return ['rsi', 'stochastic', 'sma', 'ema', 'bollinger', 'atr', 'fibonacci']
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters"""
        required_params = [
            'rsi_period', 'rsi_extreme_high', 'rsi_extreme_low',
            'stoch_k_period', 'bb_period', 'atr_period',
            'min_risk_reward', 'min_confidence'
        ]
        
        for param in required_params:
            if param not in self.parameters:
                logger.error(f"Missing required parameter: {param}")
                return False
        
        # Validate RSI levels
        if (self.parameters['rsi_extreme_low'] >= self.parameters['rsi_extreme_high']):
            logger.error("rsi_extreme_low must be less than rsi_extreme_high")
            return False
        
        return True
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information"""
        return {
            'name': self.name,
            'description': 'Mean reversion strategy trading oversold/overbought conditions',
            'type': 'mean_reversion',
            'timeframes': ['15m', '1h', '4h'],
            'parameters': self.parameters,
            'required_indicators': self.get_required_indicators(),
            'risk_level': 'moderate',
            'typical_holding_period': '1-12 hours',
            'market_conditions': 'ranging or consolidating markets'
        }