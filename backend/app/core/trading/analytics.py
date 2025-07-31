"""
Performance analytics and reporting for trading bots.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from app.database.trading_db import (
    trade_repository, bot_repository, position_repository
)
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class PerformanceReport:
    """Comprehensive performance report"""
    bot_id: str
    bot_name: str
    period_start: datetime
    period_end: datetime
    
    # Basic metrics
    total_return: float
    total_return_pct: float
    annualized_return: float
    max_drawdown: float
    max_drawdown_duration: int  # days
    
    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional VaR 95%
    
    # Trading metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    
    # Time-based metrics
    avg_trade_duration: timedelta
    avg_time_in_market: float
    trades_per_day: float
    
    # Strategy breakdown
    strategy_performance: Dict[str, Dict[str, float]]
    
    # Symbol breakdown
    symbol_performance: Dict[str, Dict[str, float]]
    
    # Monthly/daily returns
    monthly_returns: List[Dict[str, Any]]
    daily_returns: List[float]
    
    # Drawdown analysis
    drawdown_periods: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'bot_id': self.bot_id,
            'bot_name': self.bot_name,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'total_return': self.total_return,
            'total_return_pct': self.total_return_pct,
            'annualized_return': self.annualized_return,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'var_95': self.var_95,
            'cvar_95': self.cvar_95,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'expectancy': self.expectancy,
            'avg_trade_duration': str(self.avg_trade_duration),
            'avg_time_in_market': self.avg_time_in_market,
            'trades_per_day': self.trades_per_day,
            'strategy_performance': self.strategy_performance,
            'symbol_performance': self.symbol_performance,
            'monthly_returns': self.monthly_returns,
            'daily_returns': self.daily_returns,
            'drawdown_periods': self.drawdown_periods
        }


class PerformanceAnalyzer:
    """
    Comprehensive performance analysis for trading bots with
    advanced metrics and risk analysis.
    """
    
    def __init__(self):
        self.risk_free_rate = 0.02  # 2% annual risk-free rate
    
    async def generate_report(
        self,
        bot_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> PerformanceReport:
        """Generate comprehensive performance report"""
        
        # Get bot info
        bot = bot_repository.get_bot(bot_id)
        if not bot:
            raise ValueError(f"Bot {bot_id} not found")
        
        # Set default date range
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = bot.created_at
        
        # Get trades
        trades = trade_repository.get_bot_trades(bot_id, limit=10000)
        trades = [t for t in trades if start_date <= t.exit_time <= end_date]
        
        if not trades:
            # Return empty report
            return self._create_empty_report(bot, start_date, end_date)
        
        # Calculate basic metrics
        total_pnl = sum(trade.pnl for trade in trades)
        initial_capital = bot.initial_capital or 10000
        total_return_pct = (total_pnl / initial_capital) * 100
        
        # Calculate time-based metrics
        period_days = (end_date - start_date).days
        annualized_return = self._calculate_annualized_return(total_return_pct, period_days)
        
        # Trading metrics
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / len(trades) if trades else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        profit_factor = (
            abs(avg_win * len(winning_trades)) / abs(avg_loss * len(losing_trades))
            if losing_trades and avg_loss < 0 else float('inf') if winning_trades else 0
        )
        
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
        
        # Create equity curve
        equity_curve = self._create_equity_curve(trades, initial_capital)
        
        # Risk metrics
        daily_returns = self._calculate_daily_returns(equity_curve)
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns)
        sortino_ratio = self._calculate_sortino_ratio(daily_returns)
        
        # Drawdown analysis
        max_drawdown, max_dd_duration, drawdown_periods = self._analyze_drawdowns(equity_curve)
        
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # VaR calculations
        var_95 = np.percentile(daily_returns, 5) if daily_returns else 0
        cvar_95 = np.mean([r for r in daily_returns if r <= var_95]) if daily_returns else 0
        
        # Strategy breakdown
        strategy_performance = self._analyze_strategy_performance(trades)
        
        # Symbol breakdown
        symbol_performance = self._analyze_symbol_performance(trades)
        
        # Monthly returns
        monthly_returns = self._calculate_monthly_returns(trades, start_date, end_date)
        
        # Time metrics
        trade_durations = [
            (t.exit_time - t.entry_time).total_seconds() / 3600  # hours
            for t in trades if t.duration_seconds
        ]
        avg_trade_duration = timedelta(hours=np.mean(trade_durations)) if trade_durations else timedelta()
        
        trades_per_day = len(trades) / max(1, period_days)
        
        # Time in market (simplified)
        avg_time_in_market = 0.5  # Placeholder - would need position-level data
        
        return PerformanceReport(
            bot_id=bot_id,
            bot_name=bot.name,
            period_start=start_date,
            period_end=end_date,
            total_return=total_pnl,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            var_95=var_95,
            cvar_95=cvar_95,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_trade_duration=avg_trade_duration,
            avg_time_in_market=avg_time_in_market,
            trades_per_day=trades_per_day,
            strategy_performance=strategy_performance,
            symbol_performance=symbol_performance,
            monthly_returns=monthly_returns,
            daily_returns=daily_returns,
            drawdown_periods=drawdown_periods
        )
    
    def _create_empty_report(self, bot, start_date: datetime, end_date: datetime) -> PerformanceReport:
        """Create empty report for bots with no trades"""
        return PerformanceReport(
            bot_id=bot.id,
            bot_name=bot.name,
            period_start=start_date,
            period_end=end_date,
            total_return=0.0,
            total_return_pct=0.0,
            annualized_return=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            var_95=0.0,
            cvar_95=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            expectancy=0.0,
            avg_trade_duration=timedelta(),
            avg_time_in_market=0.0,
            trades_per_day=0.0,
            strategy_performance={},
            symbol_performance={},
            monthly_returns=[],
            daily_returns=[],
            drawdown_periods=[]
        )
    
    def _calculate_annualized_return(self, total_return_pct: float, days: int) -> float:
        """Calculate annualized return"""
        if days <= 0:
            return 0.0
        
        years = days / 365.25
        if years <= 0:
            return 0.0
        
        return ((1 + total_return_pct / 100) ** (1 / years) - 1) * 100
    
    def _create_equity_curve(self, trades: List, initial_capital: float) -> List[Tuple[datetime, float]]:
        """Create equity curve from trades"""
        equity_curve = [(trades[0].entry_time, initial_capital)] if trades else []
        current_equity = initial_capital
        
        for trade in sorted(trades, key=lambda x: x.exit_time):
            current_equity += trade.pnl
            equity_curve.append((trade.exit_time, current_equity))
        
        return equity_curve
    
    def _calculate_daily_returns(self, equity_curve: List[Tuple[datetime, float]]) -> List[float]:
        """Calculate daily returns from equity curve"""
        if len(equity_curve) < 2:
            return []
        
        # Group by day
        daily_values = {}
        for timestamp, value in equity_curve:
            date_key = timestamp.date()
            daily_values[date_key] = value
        
        # Calculate daily returns
        dates = sorted(daily_values.keys())
        returns = []
        
        for i in range(1, len(dates)):
            prev_value = daily_values[dates[i-1]]
            curr_value = daily_values[dates[i]]
            
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                returns.append(daily_return)
        
        return returns
    
    def _calculate_sharpe_ratio(self, daily_returns: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if not daily_returns:
            return 0.0
        
        returns_array = np.array(daily_returns)
        excess_returns = returns_array - (self.risk_free_rate / 252)  # Daily risk-free rate
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    
    def _calculate_sortino_ratio(self, daily_returns: List[float]) -> float:
        """Calculate Sortino ratio (downside deviation)"""
        if not daily_returns:
            return 0.0
        
        returns_array = np.array(daily_returns)
        excess_returns = returns_array - (self.risk_free_rate / 252)
        
        # Only consider negative returns for downside deviation
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf') if np.mean(excess_returns) > 0 else 0.0
        
        downside_deviation = np.std(downside_returns)
        
        if downside_deviation == 0:
            return 0.0
        
        return np.mean(excess_returns) / downside_deviation * np.sqrt(252)
    
    def _analyze_drawdowns(
        self, 
        equity_curve: List[Tuple[datetime, float]]
    ) -> Tuple[float, int, List[Dict[str, Any]]]:
        """Analyze drawdowns"""
        if len(equity_curve) < 2:
            return 0.0, 0, []
        
        peak = equity_curve[0][1]
        max_drawdown = 0.0
        max_dd_duration = 0
        drawdown_periods = []
        
        current_drawdown_start = None
        current_drawdown_peak = peak
        
        for timestamp, value in equity_curve[1:]:
            if value > peak:
                # New peak
                if current_drawdown_start:
                    # End of drawdown period
                    duration = (timestamp - current_drawdown_start).days
                    drawdown_periods.append({
                        'start': current_drawdown_start.isoformat(),
                        'end': timestamp.isoformat(),
                        'peak': current_drawdown_peak,
                        'trough': min(v for _, v in equity_curve if current_drawdown_start <= _ <= timestamp),
                        'duration_days': duration,
                        'recovery': True
                    })
                    current_drawdown_start = None
                
                peak = value
                current_drawdown_peak = peak
            else:
                # In drawdown
                if current_drawdown_start is None:
                    current_drawdown_start = timestamp
                
                drawdown = (peak - value) / peak
                max_drawdown = max(max_drawdown, drawdown)
                
                if current_drawdown_start:
                    duration = (timestamp - current_drawdown_start).days
                    max_dd_duration = max(max_dd_duration, duration)
        
        # Handle ongoing drawdown
        if current_drawdown_start:
            final_timestamp = equity_curve[-1][0]
            duration = (final_timestamp - current_drawdown_start).days
            drawdown_periods.append({
                'start': current_drawdown_start.isoformat(),
                'end': final_timestamp.isoformat(),
                'peak': current_drawdown_peak,
                'trough': equity_curve[-1][1],
                'duration_days': duration,
                'recovery': False
            })
        
        return max_drawdown, max_dd_duration, drawdown_periods
    
    def _analyze_strategy_performance(self, trades: List) -> Dict[str, Dict[str, float]]:
        """Analyze performance by strategy"""
        strategy_stats = {}
        
        for trade in trades:
            strategy = trade.strategy
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'trades': [],
                    'total_pnl': 0.0,
                    'wins': 0,
                    'losses': 0
                }
            
            strategy_stats[strategy]['trades'].append(trade)
            strategy_stats[strategy]['total_pnl'] += trade.pnl
            
            if trade.pnl > 0:
                strategy_stats[strategy]['wins'] += 1
            else:
                strategy_stats[strategy]['losses'] += 1
        
        # Calculate metrics for each strategy
        result = {}
        for strategy, stats in strategy_stats.items():
            total_trades = len(stats['trades'])
            win_rate = stats['wins'] / total_trades if total_trades > 0 else 0
            
            avg_win = np.mean([t.pnl for t in stats['trades'] if t.pnl > 0]) if stats['wins'] > 0 else 0
            avg_loss = np.mean([t.pnl for t in stats['trades'] if t.pnl < 0]) if stats['losses'] > 0 else 0
            
            profit_factor = (
                abs(avg_win * stats['wins']) / abs(avg_loss * stats['losses'])
                if stats['losses'] > 0 and avg_loss < 0 else float('inf') if stats['wins'] > 0 else 0
            )
            
            result[strategy] = {
                'total_trades': total_trades,
                'total_pnl': stats['total_pnl'],
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor
            }
        
        return result
    
    def _analyze_symbol_performance(self, trades: List) -> Dict[str, Dict[str, float]]:
        """Analyze performance by symbol"""
        symbol_stats = {}
        
        for trade in trades:
            symbol = trade.symbol
            if symbol not in symbol_stats:
                symbol_stats[symbol] = {
                    'trades': [],
                    'total_pnl': 0.0,
                    'wins': 0,
                    'losses': 0
                }
            
            symbol_stats[symbol]['trades'].append(trade)
            symbol_stats[symbol]['total_pnl'] += trade.pnl
            
            if trade.pnl > 0:
                symbol_stats[symbol]['wins'] += 1
            else:
                symbol_stats[symbol]['losses'] += 1
        
        # Calculate metrics for each symbol
        result = {}
        for symbol, stats in symbol_stats.items():
            total_trades = len(stats['trades'])
            win_rate = stats['wins'] / total_trades if total_trades > 0 else 0
            
            result[symbol] = {
                'total_trades': total_trades,
                'total_pnl': stats['total_pnl'],
                'win_rate': win_rate
            }
        
        return result
    
    def _calculate_monthly_returns(
        self, 
        trades: List, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Calculate monthly returns"""
        monthly_returns = []
        
        # Group trades by month
        current_date = start_date.replace(day=1)
        
        while current_date <= end_date:
            # Get next month
            if current_date.month == 12:
                next_month = current_date.replace(year=current_date.year + 1, month=1)
            else:
                next_month = current_date.replace(month=current_date.month + 1)
            
            # Get trades for this month
            month_trades = [
                t for t in trades
                if current_date <= t.exit_time < next_month
            ]
            
            month_pnl = sum(t.pnl for t in month_trades)
            
            monthly_returns.append({
                'year': current_date.year,
                'month': current_date.month,
                'month_name': current_date.strftime('%B'),
                'pnl': month_pnl,
                'trades': len(month_trades)
            })
            
            current_date = next_month
        
        return monthly_returns
    
    async def compare_bots(
        self, 
        bot_ids: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Compare performance of multiple bots"""
        
        reports = {}
        for bot_id in bot_ids:
            try:
                report = await self.generate_report(bot_id, start_date, end_date)
                reports[bot_id] = report
            except Exception as e:
                logger.error(f"Error generating report for bot {bot_id}: {e}")
                continue
        
        if not reports:
            return {}
        
        # Create comparison summary
        comparison = {
            'bots': {bot_id: report.to_dict() for bot_id, report in reports.items()},
            'summary': {
                'best_return': max(reports.values(), key=lambda r: r.total_return_pct),
                'best_sharpe': max(reports.values(), key=lambda r: r.sharpe_ratio),
                'lowest_drawdown': min(reports.values(), key=lambda r: r.max_drawdown),
                'most_trades': max(reports.values(), key=lambda r: r.total_trades),
                'best_win_rate': max(reports.values(), key=lambda r: r.win_rate)
            }
        }
        
        # Convert best performers to dict format
        for key, report in comparison['summary'].items():
            comparison['summary'][key] = {
                'bot_id': report.bot_id,
                'bot_name': report.bot_name,
                'value': getattr(report, key.split('_')[-1]) if hasattr(report, key.split('_')[-1]) else 0
            }
        
        return comparison
    
    async def generate_risk_report(self, bot_id: str) -> Dict[str, Any]:
        """Generate detailed risk analysis report"""
        
        trades = trade_repository.get_bot_trades(bot_id, limit=10000)
        if not trades:
            return {}
        
        # Calculate various risk metrics
        returns = [t.pnl_pct / 100 for t in trades]  # Convert to decimal
        
        # Basic risk metrics
        volatility = np.std(returns) * np.sqrt(252) if returns else 0  # Annualized
        skewness = self._calculate_skewness(returns)
        kurtosis = self._calculate_kurtosis(returns)
        
        # Risk of ruin
        win_rate = len([r for r in returns if r > 0]) / len(returns) if returns else 0
        avg_win = np.mean([r for r in returns if r > 0]) if returns else 0
        avg_loss = np.mean([r for r in returns if r < 0]) if returns else 0
        
        risk_of_ruin = self._calculate_risk_of_ruin(win_rate, avg_win, abs(avg_loss))
        
        # Consecutive losses analysis
        consecutive_losses = self._analyze_consecutive_losses(returns)
        
        return {
            'bot_id': bot_id,
            'total_trades_analyzed': len(trades),
            'volatility_annualized': volatility,
            'skewness': skewness,
            'kurtosis': kurtosis,
            'risk_of_ruin': risk_of_ruin,
            'max_consecutive_losses': consecutive_losses['max_consecutive'],
            'avg_consecutive_losses': consecutive_losses['avg_consecutive'],
            'win_rate': win_rate,
            'avg_win_pct': avg_win * 100,
            'avg_loss_pct': avg_loss * 100,
            'risk_metrics': {
                'var_99': np.percentile(returns, 1) * 100 if returns else 0,
                'cvar_99': np.mean([r for r in returns if r <= np.percentile(returns, 1)]) * 100 if returns else 0,
                'maximum_loss': min(returns) * 100 if returns else 0,
                'loss_probability': len([r for r in returns if r < 0]) / len(returns) if returns else 0
            }
        }
    
    def _calculate_skewness(self, returns: List[float]) -> float:
        """Calculate skewness of returns"""
        if len(returns) < 3:
            return 0.0
        
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return 0.0
        
        skewness = np.mean(((returns_array - mean_return) / std_return) ** 3)
        return skewness
    
    def _calculate_kurtosis(self, returns: List[float]) -> float:
        """Calculate kurtosis of returns"""
        if len(returns) < 4:
            return 0.0
        
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return 0.0
        
        kurtosis = np.mean(((returns_array - mean_return) / std_return) ** 4) - 3
        return kurtosis
    
    def _calculate_risk_of_ruin(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate risk of ruin using Kelly criterion"""
        if avg_loss == 0 or win_rate == 0:
            return 0.0
        
        # Kelly fraction
        kelly_f = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
        
        if kelly_f <= 0:
            return 1.0  # 100% risk of ruin
        
        # Simplified risk of ruin calculation
        # This is a basic approximation
        risk_of_ruin = (1 - win_rate) / win_rate
        return min(risk_of_ruin, 1.0)
    
    def _analyze_consecutive_losses(self, returns: List[float]) -> Dict[str, float]:
        """Analyze consecutive losses"""
        if not returns:
            return {'max_consecutive': 0, 'avg_consecutive': 0}
        
        consecutive_counts = []
        current_consecutive = 0
        
        for ret in returns:
            if ret < 0:
                current_consecutive += 1
            else:
                if current_consecutive > 0:
                    consecutive_counts.append(current_consecutive)
                current_consecutive = 0
        
        # Don't forget the last streak
        if current_consecutive > 0:
            consecutive_counts.append(current_consecutive)
        
        max_consecutive = max(consecutive_counts) if consecutive_counts else 0
        avg_consecutive = np.mean(consecutive_counts) if consecutive_counts else 0
        
        return {
            'max_consecutive': max_consecutive,
            'avg_consecutive': avg_consecutive
        }


# Global analyzer instance
performance_analyzer = PerformanceAnalyzer()