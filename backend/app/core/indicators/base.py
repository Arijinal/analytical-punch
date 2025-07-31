from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import numpy as np
from dataclasses import dataclass, field

from app.utils.cache import usage_tracker
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class IndicatorResult:
    """Standard result format for all indicators"""
    name: str
    values: pd.Series
    params: Dict[str, Any]
    signals: Optional[pd.Series] = None
    additional_series: Dict[str, pd.Series] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        result = {
            'name': self.name,
            'values': self.values.replace({np.nan: None}).tolist(),
            'params': self.params,
            'timestamps': self.values.index.tolist() if isinstance(self.values.index, pd.DatetimeIndex) else None
        }
        
        if self.signals is not None:
            result['signals'] = self.signals.replace({np.nan: None}).tolist()
        
        if self.additional_series:
            result['additional'] = {
                name: series.replace({np.nan: None}).tolist()
                for name, series in self.additional_series.items()
            }
        
        if self.metadata:
            result['metadata'] = self.metadata
        
        return result


class Indicator(ABC):
    """Base class for all technical indicators"""
    
    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.params = params or {}
        self.logger = logger
        
    @abstractmethod
    async def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """
        Calculate indicator values
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            IndicatorResult with calculated values
        """
        pass
    
    async def calculate_with_tracking(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate indicator and track usage"""
        # Track usage
        await usage_tracker.track_indicator(self.name, self.params)
        
        # Calculate
        result = await self.calculate(df)
        
        return result
    
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """Validate input DataFrame has required columns"""
        required = ['open', 'high', 'low', 'close', 'volume']
        return all(col in df.columns for col in required)
    
    def _ensure_series(self, data: Union[pd.Series, np.ndarray], index: pd.Index) -> pd.Series:
        """Ensure data is a properly indexed Series"""
        if isinstance(data, pd.Series):
            return data
        return pd.Series(data, index=index)
    
    def _detect_crossovers(self, series1: pd.Series, series2: pd.Series) -> pd.Series:
        """Detect crossover points between two series"""
        # Positive = series1 crosses above series2
        # Negative = series1 crosses below series2
        diff = series1 - series2
        diff_shifted = diff.shift(1)
        
        crossovers = pd.Series(0, index=series1.index)
        crossovers[(diff > 0) & (diff_shifted <= 0)] = 1  # Bullish crossover
        crossovers[(diff < 0) & (diff_shifted >= 0)] = -1  # Bearish crossover
        
        return crossovers
    
    def _calculate_divergence(
        self,
        price: pd.Series,
        indicator: pd.Series,
        lookback: int = 20
    ) -> pd.Series:
        """
        Detect divergences between price and indicator
        
        Returns:
            Series with values:
            1 = Bullish divergence (price lower low, indicator higher low)
            -1 = Bearish divergence (price higher high, indicator lower high)
            0 = No divergence
        """
        divergence = pd.Series(0, index=price.index)
        
        # Rolling windows for peaks and troughs
        price_highs = price.rolling(window=lookback, center=True).max()
        price_lows = price.rolling(window=lookback, center=True).min()
        ind_highs = indicator.rolling(window=lookback, center=True).max()
        ind_lows = indicator.rolling(window=lookback, center=True).min()
        
        # Detect peaks and troughs
        is_price_peak = (price == price_highs)
        is_price_trough = (price == price_lows)
        is_ind_peak = (indicator == ind_highs)
        is_ind_trough = (indicator == ind_lows)
        
        # Look for divergences
        for i in range(lookback, len(price)):
            # Bearish divergence: price higher high, indicator lower high
            if is_price_peak.iloc[i]:
                prev_peaks = price[is_price_peak][:i]
                if len(prev_peaks) > 0:
                    prev_price_peak = prev_peaks.iloc[-1]
                    if price.iloc[i] > prev_price_peak:
                        # Price made higher high, check indicator
                        ind_at_price_peak = indicator.iloc[i]
                        prev_ind_peaks = indicator[is_ind_peak][:i]
                        if len(prev_ind_peaks) > 0:
                            prev_ind_peak = prev_ind_peaks.iloc[-1]
                            if ind_at_price_peak < prev_ind_peak:
                                divergence.iloc[i] = -1
            
            # Bullish divergence: price lower low, indicator higher low
            if is_price_trough.iloc[i]:
                prev_troughs = price[is_price_trough][:i]
                if len(prev_troughs) > 0:
                    prev_price_trough = prev_troughs.iloc[-1]
                    if price.iloc[i] < prev_price_trough:
                        # Price made lower low, check indicator
                        ind_at_price_trough = indicator.iloc[i]
                        prev_ind_troughs = indicator[is_ind_trough][:i]
                        if len(prev_ind_troughs) > 0:
                            prev_ind_trough = prev_ind_troughs.iloc[-1]
                            if ind_at_price_trough > prev_ind_trough:
                                divergence.iloc[i] = 1
        
        return divergence
    
    def _smooth_series(
        self,
        series: pd.Series,
        window: int = 3,
        method: str = 'sma'
    ) -> pd.Series:
        """Apply smoothing to reduce noise"""
        if method == 'sma':
            return series.rolling(window=window, min_periods=1).mean()
        elif method == 'ema':
            return series.ewm(span=window, adjust=False).mean()
        else:
            return series


class IndicatorManager:
    """Manages and calculates multiple indicators efficiently"""
    
    def __init__(self):
        self.indicators: Dict[str, Indicator] = {}
        self._register_indicators()
    
    def _register_indicators(self):
        """Register all available indicators"""
        from app.core.indicators.trend import SMAIndicator, EMAIndicator, IchimokuIndicator
        from app.core.indicators.momentum import RSIIndicator, MACDIndicator, StochasticIndicator
        from app.core.indicators.volatility import BollingerBandsIndicator, ATRIndicator
        from app.core.indicators.volume import OBVIndicator, VolumeROCIndicator
        from app.core.indicators.levels import FibonacciIndicator, SupportResistanceIndicator
        
        # Trend indicators
        self.indicators['sma'] = SMAIndicator()
        self.indicators['ema'] = EMAIndicator()
        self.indicators['ichimoku'] = IchimokuIndicator()
        
        # Momentum indicators
        self.indicators['rsi'] = RSIIndicator()
        self.indicators['macd'] = MACDIndicator()
        self.indicators['stochastic'] = StochasticIndicator()
        
        # Volatility indicators
        self.indicators['bollinger_bands'] = BollingerBandsIndicator()
        self.indicators['atr'] = ATRIndicator()
        
        # Volume indicators
        self.indicators['obv'] = OBVIndicator()
        self.indicators['volume_roc'] = VolumeROCIndicator()
        
        # Level indicators
        self.indicators['fibonacci'] = FibonacciIndicator()
        self.indicators['support_resistance'] = SupportResistanceIndicator()
    
    async def calculate_all(
        self,
        df: pd.DataFrame,
        indicator_names: Optional[List[str]] = None,
        params: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, IndicatorResult]:
        """
        Calculate multiple indicators in one pass
        
        Args:
            df: OHLCV DataFrame
            indicator_names: List of indicators to calculate (None = all)
            params: Custom parameters for each indicator
            
        Returns:
            Dictionary of indicator results
        """
        results = {}
        
        # Default to all indicators if none specified
        if indicator_names is None:
            indicator_names = list(self.indicators.keys())
        
        # Calculate each indicator
        for name in indicator_names:
            if name not in self.indicators:
                logger.warning(f"Unknown indicator: {name}")
                continue
            
            try:
                indicator = self.indicators[name]
                
                # Apply custom parameters if provided
                if params and name in params:
                    indicator.params.update(params[name])
                
                # Calculate with tracking
                result = await indicator.calculate_with_tracking(df)
                results[name] = result
                
            except Exception as e:
                logger.error(f"Error calculating {name}: {e}")
                # Continue with other indicators
        
        return results
    
    def get_indicator(self, name: str) -> Optional[Indicator]:
        """Get specific indicator instance"""
        return self.indicators.get(name)
    
    def list_indicators(self) -> List[Dict[str, Any]]:
        """List all available indicators with their parameters"""
        return [
            {
                'name': name,
                'params': indicator.params,
                'description': indicator.__doc__
            }
            for name, indicator in self.indicators.items()
        ]