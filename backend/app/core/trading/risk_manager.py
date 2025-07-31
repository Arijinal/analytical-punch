"""
Comprehensive risk management framework for trading bots.
"""

import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np

from app.core.trading.base import (
    RiskManager, Order, Portfolio, Position, Signal, Trade, RiskLevel
)
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class RiskMetrics:
    """Risk metrics for portfolio"""
    max_drawdown: float
    var_95: float  # Value at Risk 95%
    sharpe_ratio: float
    volatility: float
    beta: float
    concentration_risk: float
    correlation_risk: float


@dataclass
class RiskLimits:
    """Risk limits configuration"""
    max_position_size: float = 0.1  # 10% of portfolio per position
    max_portfolio_risk: float = 0.02  # 2% portfolio risk per trade
    max_daily_loss: float = 0.05  # 5% daily loss limit
    max_drawdown: float = 0.15  # 15% max drawdown
    max_correlation: float = 0.7  # Max correlation between positions
    max_leverage: float = 1.0  # No leverage by default
    min_risk_reward: float = 1.5  # Minimum risk/reward ratio
    max_open_positions: int = 5  # Maximum open positions
    max_trades_per_day: int = 10  # Maximum trades per day
    
    # Asset concentration limits
    max_single_asset: float = 0.25  # 25% max in single asset
    max_sector_exposure: float = 0.4  # 40% max in single sector
    
    # Time-based limits
    trading_hours_start: str = "09:30"
    trading_hours_end: str = "16:00"
    no_trading_days: List[str] = None  # ['saturday', 'sunday']


class AdvancedRiskManager(RiskManager):
    """Advanced risk management with multiple risk models"""
    
    def __init__(self, risk_limits: Optional[RiskLimits] = None):
        self.risk_limits = risk_limits or RiskLimits()
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.last_trade_date = None
        self.max_portfolio_value = 0.0
        self.equity_curve = []
        
        # Risk models
        self.kelly_criterion = KellyCriterion()
        self.var_calculator = VaRCalculator()
        self.correlation_monitor = CorrelationMonitor()
        
    def validate_order(self, order: Order, portfolio: Portfolio) -> bool:
        """Validate if order passes all risk checks"""
        try:
            # Update daily counters
            self._update_daily_counters()
            
            # Basic validations
            if not self._validate_basic_limits(order, portfolio):
                return False
            
            # Position size validation
            if not self._validate_position_size(order, portfolio):
                return False
            
            # Portfolio risk validation
            if not self._validate_portfolio_risk(order, portfolio):
                return False
            
            # Correlation validation
            if not self._validate_correlation(order, portfolio):
                return False
            
            # Time-based validation
            if not self._validate_trading_hours():
                return False
            
            # Daily limits validation
            if not self._validate_daily_limits():
                return False
            
            logger.info(f"Order {order.id} passed all risk validations")
            return True
            
        except Exception as e:
            logger.error(f"Risk validation error: {e}")
            return False
    
    def _validate_basic_limits(self, order: Order, portfolio: Portfolio) -> bool:
        """Validate basic risk limits"""
        # Check maximum open positions
        if len(portfolio.positions) >= self.risk_limits.max_open_positions:
            logger.warning(f"Maximum open positions ({self.risk_limits.max_open_positions}) reached")
            return False
        
        # Check if we already have a position in this symbol
        if order.symbol in portfolio.positions and order.side.value == 'buy':
            logger.warning(f"Already have position in {order.symbol}")
            return False
        
        return True
    
    def _validate_position_size(self, order: Order, portfolio: Portfolio) -> bool:
        """Validate position size limits"""
        order_value = order.amount * (order.price or 0)
        max_position_value = portfolio.total_value * self.risk_limits.max_position_size
        
        if order_value > max_position_value:
            logger.warning(f"Order value {order_value} exceeds max position size {max_position_value}")
            return False
        
        # Check single asset concentration
        base_asset = order.symbol.split('/')[0]
        current_asset_value = sum(
            pos.market_value for pos in portfolio.positions.values()
            if pos.symbol.startswith(base_asset)
        )
        
        total_asset_value = current_asset_value + order_value
        max_asset_value = portfolio.total_value * self.risk_limits.max_single_asset
        
        if total_asset_value > max_asset_value:
            logger.warning(f"Asset concentration for {base_asset} would exceed limit")
            return False
        
        return True
    
    def _validate_portfolio_risk(self, order: Order, portfolio: Portfolio) -> bool:
        """Validate portfolio-level risk"""
        # Check maximum daily loss
        if self.daily_pnl < -portfolio.total_value * self.risk_limits.max_daily_loss:
            logger.warning("Daily loss limit reached")
            return False
        
        # Check maximum drawdown
        if portfolio.total_value > 0:
            current_drawdown = (self.max_portfolio_value - portfolio.total_value) / self.max_portfolio_value
            if current_drawdown > self.risk_limits.max_drawdown:
                logger.warning(f"Maximum drawdown {current_drawdown:.2%} exceeded")
                return False
        
        return True
    
    def _validate_correlation(self, order: Order, portfolio: Portfolio) -> bool:
        """Validate correlation risk"""
        if len(portfolio.positions) < 2:
            return True
        
        # This is a simplified correlation check
        # In production, would use actual price correlations
        base_asset = order.symbol.split('/')[0]
        similar_positions = [
            pos for pos in portfolio.positions.values()
            if pos.symbol.split('/')[0] in ['BTC', 'ETH'] and base_asset in ['BTC', 'ETH']
        ]
        
        if len(similar_positions) >= 2:
            logger.warning("High correlation risk detected")
            return False
        
        return True
    
    def _validate_trading_hours(self) -> bool:
        """Validate trading hours"""
        # Crypto markets are 24/7, but can add restrictions if needed
        current_time = datetime.utcnow()
        
        # Example: No trading on maintenance days
        if current_time.weekday() == 6 and current_time.hour < 6:  # Sunday early morning
            logger.warning("Trading restricted during maintenance window")
            return False
        
        return True
    
    def _validate_daily_limits(self) -> bool:
        """Validate daily trading limits"""
        if self.daily_trades >= self.risk_limits.max_trades_per_day:
            logger.warning(f"Daily trade limit {self.risk_limits.max_trades_per_day} reached")
            return False
        
        return True
    
    def _update_daily_counters(self):
        """Update daily trading counters"""
        current_date = datetime.utcnow().date()
        
        if self.last_trade_date != current_date:
            # Reset daily counters
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.last_trade_date = current_date
    
    def calculate_position_size(
        self, 
        signal: Signal, 
        portfolio: Portfolio, 
        risk_per_trade: float
    ) -> float:
        """Calculate optimal position size using multiple methods"""
        
        # Method 1: Fixed percentage risk
        fixed_size = self._calculate_fixed_risk_size(signal, portfolio, risk_per_trade)
        
        # Method 2: Kelly Criterion
        kelly_size = self.kelly_criterion.calculate_size(signal, portfolio)
        
        # Method 3: Volatility-based sizing
        volatility_size = self._calculate_volatility_size(signal, portfolio)
        
        # Use the most conservative size
        sizes = [fixed_size, kelly_size, volatility_size]
        optimal_size = min(size for size in sizes if size > 0)
        
        # Apply maximum position size limit
        max_size = portfolio.total_value * self.risk_limits.max_position_size / signal.price
        optimal_size = min(optimal_size, max_size)
        
        logger.info(f"Position size calculated: {optimal_size} (methods: {sizes})")
        return optimal_size
    
    def _calculate_fixed_risk_size(
        self, 
        signal: Signal, 
        portfolio: Portfolio, 
        risk_per_trade: float
    ) -> float:
        """Calculate position size based on fixed risk per trade"""
        if not signal.stop_loss:
            return 0.0
        
        risk_amount = portfolio.total_value * risk_per_trade
        price_risk = abs(signal.price - signal.stop_loss)
        
        if price_risk > 0:
            return risk_amount / price_risk
        
        return 0.0
    
    def _calculate_volatility_size(self, signal: Signal, portfolio: Portfolio) -> float:
        """Calculate position size based on volatility"""
        # Simplified volatility-based sizing
        # In production, would use historical volatility data
        base_size = portfolio.total_value * 0.05 / signal.price  # 5% base allocation
        
        # Adjust for signal confidence
        confidence_multiplier = signal.confidence if signal.confidence > 0.5 else 0.5
        
        return base_size * confidence_multiplier
    
    def check_portfolio_risk(self, portfolio: Portfolio) -> Dict[str, Any]:
        """Comprehensive portfolio risk assessment"""
        
        # Update max portfolio value
        if portfolio.total_value > self.max_portfolio_value:
            self.max_portfolio_value = portfolio.total_value
        
        # Calculate risk metrics
        metrics = self._calculate_risk_metrics(portfolio)
        
        # Check risk limits
        risk_alerts = []
        
        # Drawdown check
        if portfolio.total_value > 0:
            current_drawdown = (self.max_portfolio_value - portfolio.total_value) / self.max_portfolio_value
            if current_drawdown > self.risk_limits.max_drawdown * 0.8:  # 80% of limit
                risk_alerts.append(f"Approaching max drawdown: {current_drawdown:.2%}")
        
        # Concentration check
        concentration = self._calculate_concentration_risk(portfolio)
        if concentration > 0.8:
            risk_alerts.append(f"High concentration risk: {concentration:.2%}")
        
        # Daily loss check
        daily_loss_pct = abs(self.daily_pnl) / portfolio.total_value if portfolio.total_value > 0 else 0
        if daily_loss_pct > self.risk_limits.max_daily_loss * 0.8:
            risk_alerts.append(f"Approaching daily loss limit: {daily_loss_pct:.2%}")
        
        return {
            'risk_metrics': metrics,
            'risk_alerts': risk_alerts,
            'daily_trades': self.daily_trades,
            'daily_pnl': self.daily_pnl,
            'max_drawdown': current_drawdown if portfolio.total_value > 0 else 0,
            'concentration_risk': concentration
        }
    
    def _calculate_risk_metrics(self, portfolio: Portfolio) -> Dict[str, float]:
        """Calculate comprehensive risk metrics"""
        if not self.equity_curve or len(self.equity_curve) < 2:
            return {
                'max_drawdown': 0.0,
                'var_95': 0.0,
                'sharpe_ratio': 0.0,
                'volatility': 0.0,
                'concentration_risk': 0.0
            }
        
        returns = np.diff(self.equity_curve) / np.array(self.equity_curve[:-1])
        
        return {
            'max_drawdown': self._calculate_max_drawdown(),
            'var_95': np.percentile(returns, 5) if len(returns) > 0 else 0.0,
            'sharpe_ratio': self._calculate_sharpe_ratio(returns),
            'volatility': np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0.0,
            'concentration_risk': self._calculate_concentration_risk(portfolio)
        }
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity curve"""
        if len(self.equity_curve) < 2:
            return 0.0
        
        peak = self.equity_curve[0]
        max_dd = 0.0
        
        for value in self.equity_curve[1:]:
            if value > peak:
                peak = value
            
            drawdown = (peak - value) / peak
            max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def _calculate_sharpe_ratio(self, returns: np.ndarray) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualized Sharpe ratio (assuming daily returns)
        return (mean_return * 252) / (std_return * np.sqrt(252))
    
    def _calculate_concentration_risk(self, portfolio: Portfolio) -> float:
        """Calculate portfolio concentration risk"""
        if not portfolio.positions:
            return 0.0
        
        total_value = sum(pos.market_value for pos in portfolio.positions.values())
        if total_value == 0:
            return 0.0
        
        # Calculate Herfindahl-Hirschman Index
        weights = [pos.market_value / total_value for pos in portfolio.positions.values()]
        hhi = sum(w**2 for w in weights)
        
        return hhi
    
    def update_after_trade(self, trade: Trade, portfolio: Portfolio):
        """Update risk manager after trade execution"""
        self.daily_trades += 1
        self.daily_pnl += trade.pnl
        self.equity_curve.append(portfolio.total_value)
        
        # Keep only last 252 days of equity curve (1 year)
        if len(self.equity_curve) > 252:
            self.equity_curve = self.equity_curve[-252:]
    
    def get_risk_score(self, portfolio: Portfolio) -> float:
        """Calculate overall risk score (0-100, higher = riskier)"""
        risk_factors = []
        
        # Drawdown factor
        if portfolio.total_value > 0:
            drawdown = (self.max_portfolio_value - portfolio.total_value) / self.max_portfolio_value
            risk_factors.append(min(drawdown / self.risk_limits.max_drawdown, 1.0) * 30)
        
        # Concentration factor
        concentration = self._calculate_concentration_risk(portfolio)
        risk_factors.append(concentration * 25)
        
        # Daily loss factor
        daily_loss_pct = abs(self.daily_pnl) / portfolio.total_value if portfolio.total_value > 0 else 0
        risk_factors.append(min(daily_loss_pct / self.risk_limits.max_daily_loss, 1.0) * 25)
        
        # Position count factor
        position_factor = len(portfolio.positions) / self.risk_limits.max_open_positions
        risk_factors.append(position_factor * 20)
        
        return sum(risk_factors)


class KellyCriterion:
    """Kelly Criterion for position sizing"""
    
    def calculate_size(self, signal: Signal, portfolio: Portfolio) -> float:
        """Calculate Kelly optimal position size"""
        # Simplified Kelly calculation
        # In production, would use historical win rate and average win/loss
        
        if not signal.risk_reward_ratio or signal.risk_reward_ratio <= 0:
            return 0.0
        
        # Estimate win probability from signal confidence
        win_prob = signal.confidence
        lose_prob = 1 - win_prob
        
        # Average win/loss from risk-reward ratio
        avg_win = signal.risk_reward_ratio
        avg_loss = 1.0
        
        # Kelly formula: f = (bp - q) / b
        # where b = avg_win/avg_loss, p = win_prob, q = lose_prob
        b = avg_win / avg_loss
        kelly_fraction = (b * win_prob - lose_prob) / b
        
        # Conservative Kelly (use half Kelly to reduce risk)
        kelly_fraction = max(0, min(kelly_fraction * 0.5, 0.25))  # Max 25% of portfolio
        
        return portfolio.total_value * kelly_fraction / signal.price


class VaRCalculator:
    """Value at Risk calculator"""
    
    def calculate_var(self, portfolio: Portfolio, confidence: float = 0.95) -> float:
        """Calculate portfolio VaR"""
        # Simplified VaR calculation
        # In production, would use Monte Carlo or historical simulation
        
        total_value = portfolio.total_value
        if total_value == 0:
            return 0.0
        
        # Estimate portfolio volatility (simplified)
        portfolio_volatility = 0.02  # 2% daily volatility assumption
        
        # Calculate VaR using normal distribution
        from scipy.stats import norm
        var = total_value * norm.ppf(1 - confidence) * portfolio_volatility
        
        return abs(var)


class CorrelationMonitor:
    """Monitor correlation between positions"""
    
    def __init__(self):
        self.correlation_matrix = {}
    
    def update_correlations(self, price_data: Dict[str, List[float]]):
        """Update correlation matrix with new price data"""
        # Simplified correlation calculation
        # In production, would use rolling correlations
        pass
    
    def get_portfolio_correlation(self, portfolio: Portfolio) -> float:
        """Get average correlation of portfolio positions"""
        # Simplified - return estimated correlation
        return 0.3  # 30% average correlation assumption