import numpy as np
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class BacktestMetrics:
    """Calculate comprehensive backtest performance metrics"""
    
    def calculate(self, portfolio: Any, initial_capital: float) -> Dict[str, Any]:
        """Calculate all backtest metrics"""
        
        if not portfolio.closed_trades and not portfolio.equity_curve:
            return self._empty_metrics()
        
        # Basic metrics
        total_trades = len(portfolio.closed_trades)
        winning_trades = [t for t in portfolio.closed_trades if t.profit is not None and t.profit > 0]
        losing_trades = [t for t in portfolio.closed_trades if t.profit is not None and t.profit <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # Profit/Loss metrics - handle None values
        total_profit = sum(t.profit for t in portfolio.closed_trades if t.profit is not None)
        gross_profit = sum(t.profit for t in winning_trades if t.profit is not None)
        gross_loss = sum(t.profit for t in losing_trades if t.profit is not None)
        
        # Average metrics
        avg_win = gross_profit / len(winning_trades) if winning_trades else 0
        avg_loss = gross_loss / len(losing_trades) if losing_trades else 0
        
        # Profit factor
        profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float('inf')
        
        # Returns
        final_equity = portfolio.equity_curve[-1] if portfolio.equity_curve else initial_capital
        total_return = (final_equity - initial_capital) / initial_capital
        
        # Calculate daily returns from equity curve
        equity_series = pd.Series(portfolio.equity_curve, index=portfolio.timestamps)
        daily_returns = equity_series.resample('D').last().pct_change().dropna()
        
        # Risk metrics
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns)
        sortino_ratio = self._calculate_sortino_ratio(daily_returns)
        max_drawdown, max_dd_duration = self._calculate_max_drawdown(equity_series)
        
        # Additional metrics
        calmar_ratio = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Trade duration stats
        trade_durations = [t.duration.total_seconds() / 3600 for t in portfolio.closed_trades if t.duration]
        avg_trade_duration = np.mean(trade_durations) if trade_durations else 0
        
        # Consecutive wins/losses
        max_consecutive_wins = self._max_consecutive(portfolio.closed_trades, True)
        max_consecutive_losses = self._max_consecutive(portfolio.closed_trades, False)
        
        # Return metrics dictionary
        metrics = {
            # Trade statistics
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_trade_duration_hours": avg_trade_duration,
            
            # Profit/Loss
            "total_profit": total_profit,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor if profit_factor != float('inf') else 999,
            
            # Returns
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "final_equity": final_equity,
            
            # Risk metrics
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown * 100,
            "max_drawdown_duration_days": max_dd_duration,
            "calmar_ratio": calmar_ratio,
            
            # Streaks
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,
            
            # Risk/Reward
            "avg_risk_reward_ratio": self._calculate_avg_rr(portfolio.closed_trades),
            
            # Additional stats
            "best_trade": max((t.profit_pct for t in portfolio.closed_trades if t.profit_pct is not None), default=0),
            "worst_trade": min((t.profit_pct for t in portfolio.closed_trades if t.profit_pct is not None), default=0),
            "recovery_factor": total_profit / abs(max_drawdown) / initial_capital if max_drawdown != 0 else 0,
            "expectancy": (win_rate * avg_win) + ((1 - win_rate) * avg_loss) if total_trades > 0 else 0
        }
        
        return metrics
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "avg_trade_duration_hours": 0,
            "total_profit": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "profit_factor": 0,
            "total_return": 0,
            "total_return_pct": 0,
            "final_equity": 0,
            "sharpe_ratio": 0,
            "sortino_ratio": 0,
            "max_drawdown": 0,
            "max_drawdown_pct": 0,
            "max_drawdown_duration_days": 0,
            "calmar_ratio": 0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "avg_risk_reward_ratio": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "recovery_factor": 0,
            "expectancy": 0
        }
    
    def _calculate_sharpe_ratio(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio from returns"""
        if len(returns) < 2:
            return 0
        
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        
        if returns.std() == 0:
            return 0
        
        return np.sqrt(252) * (excess_returns.mean() / returns.std())
    
    def _calculate_sortino_ratio(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (uses downside deviation)"""
        if len(returns) < 2:
            return 0
        
        excess_returns = returns - (risk_free_rate / 252)
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0
        
        return np.sqrt(252) * (excess_returns.mean() / downside_returns.std())
    
    def _calculate_max_drawdown(self, equity_series: pd.Series) -> tuple:
        """Calculate maximum drawdown and duration"""
        if len(equity_series) < 2:
            return 0, 0
        
        # Calculate running maximum
        running_max = equity_series.expanding().max()
        
        # Calculate drawdown series
        drawdown = (equity_series - running_max) / running_max
        
        # Find maximum drawdown
        max_drawdown = drawdown.min()
        
        # Calculate max drawdown duration
        drawdown_start = None
        max_duration = 0
        current_duration = 0
        
        for i in range(len(drawdown)):
            if drawdown.iloc[i] < 0:
                if drawdown_start is None:
                    drawdown_start = equity_series.index[i]
                current_duration = (equity_series.index[i] - drawdown_start).days
                max_duration = max(max_duration, current_duration)
            else:
                drawdown_start = None
                current_duration = 0
        
        return max_drawdown, max_duration
    
    def _max_consecutive(self, trades: List[Any], wins: bool) -> int:
        """Calculate maximum consecutive wins or losses"""
        if not trades:
            return 0
        
        max_streak = 0
        current_streak = 0
        
        for trade in trades:
            if wins and trade.profit > 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            elif not wins and trade.profit <= 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def _calculate_avg_rr(self, trades: List[Any]) -> float:
        """Calculate average risk/reward ratio"""
        if not trades:
            return 0
        
        rr_ratios = []
        
        for trade in trades:
            if trade.stop_loss and trade.entry_price:
                risk = abs(trade.entry_price - trade.stop_loss)
                reward = abs(trade.exit_price - trade.entry_price) if trade.exit_price else 0
                
                if risk > 0:
                    rr_ratios.append(reward / risk)
        
        return np.mean(rr_ratios) if rr_ratios else 0
    
    def generate_report(self, metrics: Dict[str, Any]) -> str:
        """Generate a human-readable report from metrics"""
        report = f"""
Backtest Performance Report
==========================

Overall Performance:
- Total Return: {metrics['total_return_pct']:.2f}%
- Final Equity: ${metrics['final_equity']:,.2f}
- Total Trades: {metrics['total_trades']}

Win/Loss Statistics:
- Win Rate: {metrics['win_rate']*100:.1f}%
- Profit Factor: {metrics['profit_factor']:.2f}
- Average Win: ${metrics['avg_win']:,.2f}
- Average Loss: ${metrics['avg_loss']:,.2f}
- Best Trade: {metrics['best_trade']:.2f}%
- Worst Trade: {metrics['worst_trade']:.2f}%

Risk Metrics:
- Sharpe Ratio: {metrics['sharpe_ratio']:.2f}
- Sortino Ratio: {metrics['sortino_ratio']:.2f}
- Max Drawdown: {metrics['max_drawdown_pct']:.2f}%
- Calmar Ratio: {metrics['calmar_ratio']:.2f}

Trade Analysis:
- Average Trade Duration: {metrics['avg_trade_duration_hours']:.1f} hours
- Max Consecutive Wins: {metrics['max_consecutive_wins']}
- Max Consecutive Losses: {metrics['max_consecutive_losses']}
- Expectancy: ${metrics['expectancy']:,.2f}
"""
        return report