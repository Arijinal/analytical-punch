import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from app.core.signals.generator import Signal
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class SignalScorer:
    """Scores and ranks trading signals based on historical performance"""
    
    def __init__(self):
        self.performance_history = {}
        self.win_rates = {}
        self.average_returns = {}
    
    async def score_signals(
        self,
        signals: List[Signal],
        historical_data: Optional[pd.DataFrame] = None
    ) -> List[Signal]:
        """Score and rank signals based on multiple factors"""
        
        for signal in signals:
            # Calculate composite score
            score = self._calculate_composite_score(signal, historical_data)
            
            # Update signal with score
            signal.score = score
            
            # Add historical performance if available
            if signal.strategy in self.win_rates:
                signal.historical_win_rate = self.win_rates[signal.strategy]
            else:
                signal.historical_win_rate = 0.5  # Default 50%
        
        # Sort by score
        signals.sort(key=lambda x: x.score, reverse=True)
        
        return signals
    
    def _calculate_composite_score(
        self,
        signal: Signal,
        historical_data: Optional[pd.DataFrame] = None
    ) -> float:
        """Calculate composite score from multiple factors"""
        
        # Base score from signal confidence
        score = signal.confidence * 40  # 40% weight
        
        # Risk/Reward contribution
        rr_score = min(signal.risk_reward_ratio / 3.0, 1.0) * 20  # 20% weight, capped at 3:1
        score += rr_score
        
        # Strength contribution
        strength_score = (signal.strength / 100) * 20  # 20% weight
        score += strength_score
        
        # Historical performance (if available)
        if signal.strategy in self.win_rates:
            win_rate = self.win_rates[signal.strategy]
            performance_score = win_rate * 10  # 10% weight
            score += performance_score
        else:
            score += 5  # Default 5% for unknown performance
        
        # Timeframe bonus (higher timeframes more reliable)
        timeframe_scores = {
            '1m': 0, '5m': 1, '15m': 2, '30m': 3,
            '1h': 5, '4h': 7, '1d': 10, '1w': 10
        }
        tf_score = timeframe_scores.get(signal.timeframe, 5)
        score += tf_score  # 10% weight
        
        # Recent volatility adjustment (if historical data provided)
        if historical_data is not None and len(historical_data) > 20:
            volatility = historical_data['close'].pct_change().std() * 100
            if volatility < 1:  # Low volatility
                score *= 0.8  # Reduce score
            elif volatility > 5:  # High volatility
                if signal.strategy == 'breakout_punch':
                    score *= 1.2  # Boost breakout signals
                else:
                    score *= 0.9  # Slightly reduce others
        
        return min(score, 100)  # Cap at 100
    
    def update_performance(
        self,
        strategy: str,
        result: Dict[str, float]
    ):
        """Update historical performance metrics"""
        
        if strategy not in self.performance_history:
            self.performance_history[strategy] = []
        
        self.performance_history[strategy].append(result)
        
        # Recalculate win rate
        wins = sum(1 for r in self.performance_history[strategy] if r['profit'] > 0)
        total = len(self.performance_history[strategy])
        
        self.win_rates[strategy] = wins / total if total > 0 else 0.5
        
        # Calculate average return
        returns = [r['return_pct'] for r in self.performance_history[strategy]]
        self.average_returns[strategy] = np.mean(returns) if returns else 0
    
    def get_strategy_stats(self, strategy: str) -> Dict:
        """Get performance statistics for a strategy"""
        
        if strategy not in self.performance_history:
            return {
                'total_trades': 0,
                'win_rate': 0.5,
                'average_return': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'sharpe_ratio': 0
            }
        
        history = self.performance_history[strategy]
        returns = [r['return_pct'] for r in history]
        
        stats = {
            'total_trades': len(history),
            'win_rate': self.win_rates.get(strategy, 0.5),
            'average_return': np.mean(returns),
            'best_trade': max(returns) if returns else 0,
            'worst_trade': min(returns) if returns else 0,
            'sharpe_ratio': self._calculate_sharpe_ratio(returns)
        }
        
        return stats
    
    def _calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.02
    ) -> float:
        """Calculate Sharpe ratio for returns"""
        
        if not returns or len(returns) < 2:
            return 0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - (risk_free_rate / 252)  # Daily risk-free rate
        
        if np.std(excess_returns) == 0:
            return 0
        
        return np.sqrt(252) * (np.mean(excess_returns) / np.std(excess_returns))
    
    def generate_signal_report(self, signals: List[Signal]) -> Dict:
        """Generate comprehensive report for signals"""
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_signals': len(signals),
            'signals_by_strategy': {},
            'signals_by_direction': {
                'buy': len([s for s in signals if s.direction == 'buy']),
                'sell': len([s for s in signals if s.direction == 'sell'])
            },
            'average_confidence': np.mean([s.confidence for s in signals]) if signals else 0,
            'average_risk_reward': np.mean([s.risk_reward_ratio for s in signals]) if signals else 0,
            'top_signals': []
        }
        
        # Count by strategy
        for signal in signals:
            if signal.strategy not in report['signals_by_strategy']:
                report['signals_by_strategy'][signal.strategy] = 0
            report['signals_by_strategy'][signal.strategy] += 1
        
        # Top 3 signals
        for signal in signals[:3]:
            report['top_signals'].append({
                'strategy': signal.strategy,
                'direction': signal.direction,
                'confidence': signal.confidence,
                'risk_reward': signal.risk_reward_ratio,
                'reasoning': signal.reasoning
            })
        
        return report