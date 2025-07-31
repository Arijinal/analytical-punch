import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import asyncio

from app.core.indicators.base import IndicatorManager, IndicatorResult
from app.data.manager import data_manager
from app.config import get_config
from app.utils.logger import setup_logger

config = get_config()
logger = setup_logger(__name__)


class Signal:
    """Represents a trading signal"""
    
    def __init__(
        self,
        strategy: str,
        direction: str,  # 'buy' or 'sell'
        strength: float,  # 0-100
        entry_price: float,
        stop_loss: float,
        take_profit_levels: List[float],
        risk_reward_ratio: float,
        confidence: float,  # 0-1
        timeframe: str,
        reasoning: str,
        indicators_used: List[str]
    ):
        self.strategy = strategy
        self.direction = direction
        self.strength = strength
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit_levels = take_profit_levels
        self.risk_reward_ratio = risk_reward_ratio
        self.confidence = confidence
        self.timeframe = timeframe
        self.reasoning = reasoning
        self.indicators_used = indicators_used
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convert signal to dictionary for API response"""
        return {
            'strategy': self.strategy,
            'direction': self.direction,
            'strength': self.strength,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit_levels': self.take_profit_levels,
            'risk_reward_ratio': self.risk_reward_ratio,
            'confidence': self.confidence,
            'timeframe': self.timeframe,
            'reasoning': self.reasoning,
            'indicators_used': self.indicators_used,
            'timestamp': self.timestamp.isoformat()
        }


class SignalGenerator:
    """Generates trading signals using the 4 Punch Strategies"""
    
    def __init__(self):
        self.indicator_manager = IndicatorManager()
        self.strategies = {
            'momentum_punch': self._momentum_punch_strategy,
            'value_punch': self._value_punch_strategy,
            'breakout_punch': self._breakout_punch_strategy,
            'trend_punch': self._trend_punch_strategy
        }
        self.timeframes = ['15m', '1h', '4h', '1d']  # Multi-timeframe analysis
    
    async def generate_signals(
        self,
        symbol: str,
        primary_timeframe: str = '1h'
    ) -> List[Signal]:
        """Generate signals across all strategies"""
        signals = []
        
        try:
            # Fetch data for multiple timeframes
            mtf_data = await self._fetch_multi_timeframe_data(symbol, primary_timeframe)
            
            # Calculate indicators for each timeframe
            mtf_indicators = {}
            for tf, df in mtf_data.items():
                if not df.empty:
                    indicators = await self.indicator_manager.calculate_all(df)
                    mtf_indicators[tf] = indicators
            
            # Run each strategy
            for strategy_name, strategy_func in self.strategies.items():
                try:
                    strategy_signals = await strategy_func(
                        symbol, primary_timeframe, mtf_data, mtf_indicators
                    )
                    signals.extend(strategy_signals)
                except Exception as e:
                    logger.error(f"Error in {strategy_name}: {e}")
            
            # Filter signals by confidence threshold
            signals = [s for s in signals if s.confidence >= config.SIGNAL_CONFIDENCE_THRESHOLD]
            
            # Sort by confidence and strength
            signals.sort(key=lambda x: (x.confidence, x.strength), reverse=True)
            
            # Limit number of signals in non-personal mode
            if not config.PERSONAL_MODE and len(signals) > 3:
                signals = signals[:3]
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {e}")
            return []
    
    async def _fetch_multi_timeframe_data(
        self,
        symbol: str,
        primary_timeframe: str
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple timeframes"""
        mtf_data = {}
        
        # Determine timeframes to fetch based on primary
        if primary_timeframe in ['1m', '5m', '15m']:
            timeframes = ['5m', '15m', '1h', '4h']
        elif primary_timeframe in ['30m', '1h']:
            timeframes = ['15m', '1h', '4h', '1d']
        else:
            timeframes = ['1h', '4h', '1d', '1w']
        
        # Fetch data concurrently
        tasks = []
        for tf in timeframes:
            task = data_manager.fetch_ohlcv(symbol, tf, limit=200)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for tf, result in zip(timeframes, results):
            if isinstance(result, pd.DataFrame):
                mtf_data[tf] = result
            else:
                logger.warning(f"Failed to fetch {tf} data: {result}")
                mtf_data[tf] = pd.DataFrame()
        
        return mtf_data
    
    async def _momentum_punch_strategy(
        self,
        symbol: str,
        timeframe: str,
        mtf_data: Dict[str, pd.DataFrame],
        mtf_indicators: Dict[str, Dict[str, IndicatorResult]]
    ) -> List[Signal]:
        """Momentum Punch - Trend following with momentum confirmation"""
        signals = []
        
        # Get primary timeframe data
        primary_df = mtf_data.get(timeframe, pd.DataFrame())
        if primary_df.empty:
            return signals
        
        primary_indicators = mtf_indicators.get(timeframe, {})
        
        # Required indicators
        rsi = primary_indicators.get('rsi')
        macd = primary_indicators.get('macd')
        ema = primary_indicators.get('ema')
        atr = primary_indicators.get('atr')
        
        if not all([rsi, macd, ema, atr]):
            return signals
        
        # Get latest values
        latest_idx = -1
        current_price = primary_df['close'].iloc[latest_idx]
        
        # Check momentum conditions
        rsi_value = rsi.values.iloc[latest_idx]
        macd_value = macd.values.iloc[latest_idx]
        macd_signal = macd.additional_series['signal_line'].iloc[latest_idx]
        macd_histogram = macd.additional_series['histogram'].iloc[latest_idx]
        
        # EMA alignment (12, 26, 50)
        ema_12 = ema.values.iloc[latest_idx]
        ema_26 = ema.additional_series.get('ema_26', pd.Series()).iloc[latest_idx] if 'ema_26' in ema.additional_series else None
        ema_50 = ema.additional_series.get('ema_50', pd.Series()).iloc[latest_idx] if 'ema_50' in ema.additional_series else None
        
        # ATR for stops
        atr_value = atr.values.iloc[latest_idx]
        
        # Bullish momentum signal
        if (30 < rsi_value < 70 and  # Not overbought/oversold
            macd_value > macd_signal and  # MACD above signal
            macd_histogram > 0 and  # Positive histogram
            current_price > ema_12):  # Price above short EMA
            
            # Check higher timeframe confirmation
            htf_confirmation = self._check_higher_timeframe_trend(mtf_indicators, 'bullish')
            
            # Calculate strength
            strength = min(100, (
                (rsi_value - 50) +  # RSI momentum
                (macd_histogram * 100) +  # MACD strength
                (10 if htf_confirmation else 0)  # HTF bonus
            ))
            
            # Risk management
            stop_loss = current_price - (2 * atr_value)
            take_profit_1 = current_price + (1.5 * atr_value)
            take_profit_2 = current_price + (3 * atr_value)
            take_profit_3 = current_price + (5 * atr_value)
            
            risk_reward = (take_profit_2 - current_price) / (current_price - stop_loss)
            
            signal = Signal(
                strategy='momentum_punch',
                direction='buy',
                strength=strength,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit_levels=[take_profit_1, take_profit_2, take_profit_3],
                risk_reward_ratio=risk_reward,
                confidence=0.7 + (0.1 if htf_confirmation else 0),
                timeframe=timeframe,
                reasoning=f"Strong bullish momentum detected. RSI at {rsi_value:.1f}, "
                         f"MACD crossed above signal with expanding histogram. "
                         f"Price above short-term EMA. "
                         f"{'Higher timeframe confirms trend. ' if htf_confirmation else ''}"
                         f"Entry: ${current_price:.2f}, Stop: ${stop_loss:.2f}, "
                         f"Target: ${take_profit_2:.2f} (RR: {risk_reward:.1f})",
                indicators_used=['rsi', 'macd', 'ema', 'atr']
            )
            signals.append(signal)
        
        # Bearish momentum signal
        elif (30 < rsi_value < 70 and  # Not overbought/oversold
              macd_value < macd_signal and  # MACD below signal
              macd_histogram < 0 and  # Negative histogram
              current_price < ema_12):  # Price below short EMA
            
            htf_confirmation = self._check_higher_timeframe_trend(mtf_indicators, 'bearish')
            
            strength = min(100, (
                (50 - rsi_value) +
                (abs(macd_histogram) * 100) +
                (10 if htf_confirmation else 0)
            ))
            
            stop_loss = current_price + (2 * atr_value)
            take_profit_1 = current_price - (1.5 * atr_value)
            take_profit_2 = current_price - (3 * atr_value)
            take_profit_3 = current_price - (5 * atr_value)
            
            risk_reward = (current_price - take_profit_2) / (stop_loss - current_price)
            
            signal = Signal(
                strategy='momentum_punch',
                direction='sell',
                strength=strength,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit_levels=[take_profit_1, take_profit_2, take_profit_3],
                risk_reward_ratio=risk_reward,
                confidence=0.7 + (0.1 if htf_confirmation else 0),
                timeframe=timeframe,
                reasoning=f"Strong bearish momentum detected. RSI at {rsi_value:.1f}, "
                         f"MACD crossed below signal with expanding histogram. "
                         f"Price below short-term EMA. "
                         f"{'Higher timeframe confirms trend. ' if htf_confirmation else ''}"
                         f"Entry: ${current_price:.2f}, Stop: ${stop_loss:.2f}, "
                         f"Target: ${take_profit_2:.2f} (RR: {risk_reward:.1f})",
                indicators_used=['rsi', 'macd', 'ema', 'atr']
            )
            signals.append(signal)
        
        return signals
    
    async def _value_punch_strategy(
        self,
        symbol: str,
        timeframe: str,
        mtf_data: Dict[str, pd.DataFrame],
        mtf_indicators: Dict[str, Dict[str, IndicatorResult]]
    ) -> List[Signal]:
        """Value Punch - Mean reversion at extremes"""
        signals = []
        
        primary_df = mtf_data.get(timeframe, pd.DataFrame())
        if primary_df.empty:
            return signals
        
        primary_indicators = mtf_indicators.get(timeframe, {})
        
        # Required indicators
        rsi = primary_indicators.get('rsi')
        bollinger = primary_indicators.get('bollinger_bands')
        stochastic = primary_indicators.get('stochastic')
        atr = primary_indicators.get('atr')
        
        if not all([rsi, bollinger, stochastic, atr]):
            return signals
        
        latest_idx = -1
        current_price = primary_df['close'].iloc[latest_idx]
        
        # Get indicator values
        rsi_value = rsi.values.iloc[latest_idx]
        bb_upper = bollinger.additional_series['upper_band'].iloc[latest_idx]
        bb_lower = bollinger.additional_series['lower_band'].iloc[latest_idx]
        bb_middle = bollinger.values.iloc[latest_idx]
        percent_b = bollinger.additional_series['percent_b'].iloc[latest_idx]
        
        stoch_k = stochastic.values.iloc[latest_idx]
        stoch_d = stochastic.additional_series['slow_d'].iloc[latest_idx]
        
        atr_value = atr.values.iloc[latest_idx]
        
        # Check for divergences
        rsi_divergence = rsi.additional_series.get('divergence', pd.Series()).iloc[latest_idx] if 'divergence' in rsi.additional_series else 0
        
        # Oversold bounce signal
        if (rsi_value < 30 and  # RSI oversold
            percent_b < 0.2 and  # Near lower Bollinger Band
            stoch_k < 20 and  # Stochastic oversold
            stoch_k > stoch_d):  # Stochastic turning up
            
            strength = min(100, (
                (30 - rsi_value) * 2 +  # More oversold = stronger
                (20 - stoch_k) +
                (20 if rsi_divergence > 0 else 0)  # Bullish divergence bonus
            ))
            
            stop_loss = min(bb_lower - atr_value, current_price - (1.5 * atr_value))
            take_profit_1 = bb_middle
            take_profit_2 = bb_middle + (bb_middle - bb_lower) * 0.5
            take_profit_3 = bb_upper
            
            risk_reward = (take_profit_1 - current_price) / (current_price - stop_loss)
            
            signal = Signal(
                strategy='value_punch',
                direction='buy',
                strength=strength,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit_levels=[take_profit_1, take_profit_2, take_profit_3],
                risk_reward_ratio=risk_reward,
                confidence=0.65 + (0.15 if rsi_divergence > 0 else 0),
                timeframe=timeframe,
                reasoning=f"Oversold bounce opportunity. RSI at extreme low {rsi_value:.1f}, "
                         f"price near lower Bollinger Band (% B: {percent_b:.2f}). "
                         f"Stochastic showing reversal signal. "
                         f"{'Bullish divergence detected. ' if rsi_divergence > 0 else ''}"
                         f"Mean reversion target at ${bb_middle:.2f}",
                indicators_used=['rsi', 'bollinger_bands', 'stochastic', 'atr']
            )
            signals.append(signal)
        
        # Overbought reversal signal
        elif (rsi_value > 70 and  # RSI overbought
              percent_b > 0.8 and  # Near upper Bollinger Band
              stoch_k > 80 and  # Stochastic overbought
              stoch_k < stoch_d):  # Stochastic turning down
            
            strength = min(100, (
                (rsi_value - 70) * 2 +
                (stoch_k - 80) +
                (20 if rsi_divergence < 0 else 0)  # Bearish divergence bonus
            ))
            
            stop_loss = max(bb_upper + atr_value, current_price + (1.5 * atr_value))
            take_profit_1 = bb_middle
            take_profit_2 = bb_middle - (bb_upper - bb_middle) * 0.5
            take_profit_3 = bb_lower
            
            risk_reward = (current_price - take_profit_1) / (stop_loss - current_price)
            
            signal = Signal(
                strategy='value_punch',
                direction='sell',
                strength=strength,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit_levels=[take_profit_1, take_profit_2, take_profit_3],
                risk_reward_ratio=risk_reward,
                confidence=0.65 + (0.15 if rsi_divergence < 0 else 0),
                timeframe=timeframe,
                reasoning=f"Overbought reversal opportunity. RSI at extreme high {rsi_value:.1f}, "
                         f"price near upper Bollinger Band (% B: {percent_b:.2f}). "
                         f"Stochastic showing reversal signal. "
                         f"{'Bearish divergence detected. ' if rsi_divergence < 0 else ''}"
                         f"Mean reversion target at ${bb_middle:.2f}",
                indicators_used=['rsi', 'bollinger_bands', 'stochastic', 'atr']
            )
            signals.append(signal)
        
        return signals
    
    async def _breakout_punch_strategy(
        self,
        symbol: str,
        timeframe: str,
        mtf_data: Dict[str, pd.DataFrame],
        mtf_indicators: Dict[str, Dict[str, IndicatorResult]]
    ) -> List[Signal]:
        """Breakout Punch - Volatility expansion trades"""
        signals = []
        
        primary_df = mtf_data.get(timeframe, pd.DataFrame())
        if primary_df.empty:
            return signals
        
        primary_indicators = mtf_indicators.get(timeframe, {})
        
        # Required indicators
        bollinger = primary_indicators.get('bollinger_bands')
        atr = primary_indicators.get('atr')
        volume_roc = primary_indicators.get('volume_roc')
        support_resistance = primary_indicators.get('support_resistance')
        
        if not all([bollinger, atr]):
            return signals
        
        latest_idx = -1
        current_price = primary_df['close'].iloc[latest_idx]
        current_volume = primary_df['volume'].iloc[latest_idx]
        
        # Bollinger Band squeeze detection
        squeeze = bollinger.additional_series.get('squeeze', pd.Series())
        squeeze_release = bollinger.additional_series.get('squeeze_release', pd.Series())
        
        # ATR for volatility
        atr_value = atr.values.iloc[latest_idx]
        volatility_expanding = atr.metadata.get('volatility_expanding', False)
        
        # Volume confirmation
        volume_spike = False
        if volume_roc:
            volume_roc_value = volume_roc.values.iloc[latest_idx]
            volume_spike = volume_roc_value > 50  # 50% increase
        
        # Support/Resistance levels
        resistance_level = None
        support_level = None
        if support_resistance:
            resistance_level = support_resistance.additional_series.get('resistance_levels', pd.Series()).iloc[latest_idx]
            support_level = support_resistance.values.iloc[latest_idx]
        
        # Check for squeeze release breakout
        if (not squeeze.empty and len(squeeze_release) > 0 and
            squeeze_release.iloc[latest_idx] != 0):
            
            direction = 'buy' if squeeze_release.iloc[latest_idx] > 0 else 'sell'
            
            strength = min(100, (
                50 +  # Base strength for squeeze release
                (20 if volatility_expanding else 0) +
                (20 if volume_spike else 0) +
                (10 if direction == 'buy' and resistance_level and current_price > resistance_level else 0)
            ))
            
            if direction == 'buy':
                stop_loss = current_price - (1.5 * atr_value)
                take_profit_1 = current_price + (2 * atr_value)
                take_profit_2 = current_price + (4 * atr_value)
                take_profit_3 = current_price + (6 * atr_value)
            else:
                stop_loss = current_price + (1.5 * atr_value)
                take_profit_1 = current_price - (2 * atr_value)
                take_profit_2 = current_price - (4 * atr_value)
                take_profit_3 = current_price - (6 * atr_value)
            
            risk_reward = abs(take_profit_2 - current_price) / abs(current_price - stop_loss)
            
            signal = Signal(
                strategy='breakout_punch',
                direction=direction,
                strength=strength,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit_levels=[take_profit_1, take_profit_2, take_profit_3],
                risk_reward_ratio=risk_reward,
                confidence=0.75 + (0.1 if volume_spike else 0),
                timeframe=timeframe,
                reasoning=f"Bollinger Band squeeze release detected! "
                         f"Volatility expanding after compression period. "
                         f"{'Volume surge confirms breakout. ' if volume_spike else ''}"
                         f"Targeting {4:.0f}x ATR move (${take_profit_2:.2f})",
                indicators_used=['bollinger_bands', 'atr', 'volume_roc', 'support_resistance']
            )
            signals.append(signal)
        
        # Level breakout signal
        elif resistance_level and support_level:
            # Resistance breakout
            if (current_price > resistance_level * 1.002 and  # 0.2% above resistance
                primary_df['close'].iloc[-2] <= resistance_level and  # Previous close below
                volatility_expanding):
                
                strength = min(100, (
                    60 +  # Base breakout strength
                    (20 if volume_spike else 0) +
                    (20 if volatility_expanding else 0)
                ))
                
                stop_loss = resistance_level - (0.5 * atr_value)  # Below broken resistance
                take_profit_1 = current_price + (2 * atr_value)
                take_profit_2 = current_price + (4 * atr_value)
                take_profit_3 = current_price + (6 * atr_value)
                
                risk_reward = (take_profit_2 - current_price) / (current_price - stop_loss)
                
                signal = Signal(
                    strategy='breakout_punch',
                    direction='buy',
                    strength=strength,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit_levels=[take_profit_1, take_profit_2, take_profit_3],
                    risk_reward_ratio=risk_reward,
                    confidence=0.7 + (0.1 if volume_spike else 0),
                    timeframe=timeframe,
                    reasoning=f"Resistance breakout at ${resistance_level:.2f}! "
                             f"Price broke key level with "
                             f"{'strong volume' if volume_spike else 'expanding volatility'}. "
                             f"Former resistance should act as support",
                    indicators_used=['support_resistance', 'atr', 'volume_roc']
                )
                signals.append(signal)
            
            # Support breakdown
            elif (current_price < support_level * 0.998 and  # 0.2% below support
                  primary_df['close'].iloc[-2] >= support_level and  # Previous close above
                  volatility_expanding):
                
                strength = min(100, (
                    60 +
                    (20 if volume_spike else 0) +
                    (20 if volatility_expanding else 0)
                ))
                
                stop_loss = support_level + (0.5 * atr_value)  # Above broken support
                take_profit_1 = current_price - (2 * atr_value)
                take_profit_2 = current_price - (4 * atr_value)
                take_profit_3 = current_price - (6 * atr_value)
                
                risk_reward = (current_price - take_profit_2) / (stop_loss - current_price)
                
                signal = Signal(
                    strategy='breakout_punch',
                    direction='sell',
                    strength=strength,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit_levels=[take_profit_1, take_profit_2, take_profit_3],
                    risk_reward_ratio=risk_reward,
                    confidence=0.7 + (0.1 if volume_spike else 0),
                    timeframe=timeframe,
                    reasoning=f"Support breakdown at ${support_level:.2f}! "
                             f"Price broke key level with "
                             f"{'strong volume' if volume_spike else 'expanding volatility'}. "
                             f"Former support should act as resistance",
                    indicators_used=['support_resistance', 'atr', 'volume_roc']
                )
                signals.append(signal)
        
        return signals
    
    async def _trend_punch_strategy(
        self,
        symbol: str,
        timeframe: str,
        mtf_data: Dict[str, pd.DataFrame],
        mtf_indicators: Dict[str, Dict[str, IndicatorResult]]
    ) -> List[Signal]:
        """Trend Punch - Strong directional moves with multiple confirmations"""
        signals = []
        
        primary_df = mtf_data.get(timeframe, pd.DataFrame())
        if primary_df.empty:
            return signals
        
        primary_indicators = mtf_indicators.get(timeframe, {})
        
        # Required indicators
        ichimoku = primary_indicators.get('ichimoku')
        sma = primary_indicators.get('sma')
        macd = primary_indicators.get('macd')
        obv = primary_indicators.get('obv')
        atr = primary_indicators.get('atr')
        
        if not all([ichimoku, sma, atr]):
            return signals
        
        latest_idx = -1
        current_price = primary_df['close'].iloc[latest_idx]
        
        # Ichimoku cloud analysis
        cloud_position = ichimoku.metadata.get('current_position', '')
        tk_position = ichimoku.metadata.get('tk_position', '')
        cloud_trend = ichimoku.metadata.get('cloud_trend', '')
        
        # SMA alignment
        sma_20 = sma.values.iloc[latest_idx]
        sma_50 = sma.additional_series.get('sma_50', pd.Series()).iloc[latest_idx] if 'sma_50' in sma.additional_series else None
        sma_200 = sma.additional_series.get('sma_200', pd.Series()).iloc[latest_idx] if 'sma_200' in sma.additional_series else None
        
        # Perfect alignment check
        bullish_alignment = False
        bearish_alignment = False
        
        if sma_50 and sma_200:
            bullish_alignment = (current_price > sma_20 > sma_50 > sma_200)
            bearish_alignment = (current_price < sma_20 < sma_50 < sma_200)
        
        # Volume trend
        volume_trend = 'neutral'
        if obv:
            obv_trend = obv.metadata.get('obv_trend_direction', 'neutral')
            volume_trend = obv_trend
        
        # ATR for stops
        atr_value = atr.values.iloc[latest_idx]
        
        # Strong bullish trend signal
        if (cloud_position == 'above_cloud' and
            tk_position == 'bullish' and
            cloud_trend == 'bullish' and
            (bullish_alignment or current_price > sma_20)):
            
            # Multi-timeframe confirmation
            htf_confirmation = self._check_all_timeframes_aligned(mtf_indicators, 'bullish')
            
            strength = min(100, (
                40 +  # Base Ichimoku strength
                (20 if bullish_alignment else 10) +  # SMA alignment
                (10 if volume_trend == 'bullish' else 0) +  # Volume confirmation
                (20 if htf_confirmation else 0)  # Multi-timeframe
            ))
            
            # Aggressive stops for trend following
            stop_loss = max(
                ichimoku.additional_series['kijun_sen'].iloc[latest_idx],
                current_price - (2 * atr_value)
            )
            
            # Extended targets for trend
            take_profit_1 = current_price + (3 * atr_value)
            take_profit_2 = current_price + (5 * atr_value)
            take_profit_3 = current_price + (8 * atr_value)
            
            risk_reward = (take_profit_2 - current_price) / (current_price - stop_loss)
            
            signal = Signal(
                strategy='trend_punch',
                direction='buy',
                strength=strength,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit_levels=[take_profit_1, take_profit_2, take_profit_3],
                risk_reward_ratio=risk_reward,
                confidence=0.8 + (0.15 if htf_confirmation else 0),
                timeframe=timeframe,
                reasoning=f"Strong bullish trend identified! Ichimoku shows price above cloud "
                         f"with bullish TK cross. "
                         f"{'Perfect SMA alignment (20>50>200). ' if bullish_alignment else ''}"
                         f"{'All timeframes aligned. ' if htf_confirmation else ''}"
                         f"Ride the trend with trailing stop at Kijun-sen",
                indicators_used=['ichimoku', 'sma', 'obv', 'atr']
            )
            signals.append(signal)
        
        # Strong bearish trend signal
        elif (cloud_position == 'below_cloud' and
              tk_position == 'bearish' and
              cloud_trend == 'bearish' and
              (bearish_alignment or current_price < sma_20)):
            
            htf_confirmation = self._check_all_timeframes_aligned(mtf_indicators, 'bearish')
            
            strength = min(100, (
                40 +
                (20 if bearish_alignment else 10) +
                (10 if volume_trend == 'bearish' else 0) +
                (20 if htf_confirmation else 0)
            ))
            
            stop_loss = min(
                ichimoku.additional_series['kijun_sen'].iloc[latest_idx],
                current_price + (2 * atr_value)
            )
            
            take_profit_1 = current_price - (3 * atr_value)
            take_profit_2 = current_price - (5 * atr_value)
            take_profit_3 = current_price - (8 * atr_value)
            
            risk_reward = (current_price - take_profit_2) / (stop_loss - current_price)
            
            signal = Signal(
                strategy='trend_punch',
                direction='sell',
                strength=strength,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit_levels=[take_profit_1, take_profit_2, take_profit_3],
                risk_reward_ratio=risk_reward,
                confidence=0.8 + (0.15 if htf_confirmation else 0),
                timeframe=timeframe,
                reasoning=f"Strong bearish trend identified! Ichimoku shows price below cloud "
                         f"with bearish TK cross. "
                         f"{'Perfect SMA alignment (20<50<200). ' if bearish_alignment else ''}"
                         f"{'All timeframes aligned. ' if htf_confirmation else ''}"
                         f"Ride the trend with trailing stop at Kijun-sen",
                indicators_used=['ichimoku', 'sma', 'obv', 'atr']
            )
            signals.append(signal)
        
        return signals
    
    def _check_higher_timeframe_trend(
        self,
        mtf_indicators: Dict[str, Dict[str, IndicatorResult]],
        expected_trend: str
    ) -> bool:
        """Check if higher timeframes confirm the trend"""
        confirmations = 0
        total_checks = 0
        
        # Check each timeframe
        for tf, indicators in mtf_indicators.items():
            if tf in ['4h', '1d']:  # Higher timeframes
                # Check SMA trend
                if 'sma' in indicators:
                    sma = indicators['sma']
                    if sma.metadata.get('trend', 0) == (1 if expected_trend == 'bullish' else -1):
                        confirmations += 1
                    total_checks += 1
                
                # Check MACD trend
                if 'macd' in indicators:
                    macd = indicators['macd']
                    if macd.metadata.get('above_zero', False) == (expected_trend == 'bullish'):
                        confirmations += 1
                    total_checks += 1
        
        return confirmations >= total_checks * 0.6 if total_checks > 0 else False
    
    def _check_all_timeframes_aligned(
        self,
        mtf_indicators: Dict[str, Dict[str, IndicatorResult]],
        expected_trend: str
    ) -> bool:
        """Check if all timeframes are aligned in the same direction"""
        aligned_count = 0
        total_timeframes = 0
        
        for tf, indicators in mtf_indicators.items():
            trend_score = 0
            checks = 0
            
            # Check multiple indicators per timeframe
            if 'sma' in indicators:
                sma = indicators['sma']
                if sma.metadata.get('trend', 0) == (1 if expected_trend == 'bullish' else -1):
                    trend_score += 1
                checks += 1
            
            if 'macd' in indicators:
                macd = indicators['macd']
                if macd.metadata.get('above_zero', False) == (expected_trend == 'bullish'):
                    trend_score += 1
                checks += 1
            
            if 'rsi' in indicators:
                rsi = indicators['rsi']
                rsi_value = rsi.values.iloc[-1] if not rsi.values.empty else 50
                if (expected_trend == 'bullish' and rsi_value > 50) or \
                   (expected_trend == 'bearish' and rsi_value < 50):
                    trend_score += 1
                checks += 1
            
            # Timeframe is aligned if majority of indicators agree
            if checks > 0 and trend_score >= checks * 0.6:
                aligned_count += 1
            
            total_timeframes += 1
        
        # All timeframes aligned if 80%+ agree
        return aligned_count >= total_timeframes * 0.8 if total_timeframes > 0 else False