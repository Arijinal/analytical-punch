"""
Smart Order Execution System with slippage protection and advanced order types.
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np

from app.core.trading.base import (
    Order, OrderType, OrderSide, OrderStatus, Position, Signal
)
from app.core.trading.exchange import BinanceExchange
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ExecutionStrategy(Enum):
    """Order execution strategies"""
    IMMEDIATE = "immediate"  # Market order
    TWAP = "twap"  # Time-weighted average price
    VWAP = "vwap"  # Volume-weighted average price
    ICEBERG = "iceberg"  # Hidden size orders
    ADAPTIVE = "adaptive"  # Smart routing based on conditions


@dataclass
class ExecutionParams:
    """Parameters for order execution"""
    strategy: ExecutionStrategy = ExecutionStrategy.IMMEDIATE
    max_slippage: float = 0.005  # 0.5% max slippage
    time_limit: int = 300  # 5 minutes max execution time
    chunk_size: Optional[float] = None  # For TWAP/ICEBERG
    participation_rate: float = 0.2  # Max 20% of volume
    price_improvement_wait: int = 30  # Seconds to wait for better price
    retry_attempts: int = 3
    
    # Advanced parameters
    hidden_size_pct: float = 0.1  # 10% visible for iceberg
    volatility_adjustment: bool = True
    spread_threshold: float = 0.002  # 0.2% max spread
    volume_threshold: float = 100  # Minimum volume required


@dataclass
class ExecutionReport:
    """Report of order execution"""
    order_id: str
    symbol: str
    requested_amount: float
    executed_amount: float
    average_price: float
    requested_price: Optional[float]
    total_slippage: float
    execution_time: float
    fees_paid: float
    strategy_used: ExecutionStrategy
    chunks_executed: int
    success: bool
    error_message: Optional[str] = None
    market_impact: float = 0.0
    price_improvement: float = 0.0


class SmartOrderManager:
    """
    Smart order execution system that optimizes trade execution
    to minimize slippage and market impact.
    """
    
    def __init__(self, exchange: BinanceExchange):
        self.exchange = exchange
        self.active_orders: Dict[str, Order] = {}
        self.execution_reports: List[ExecutionReport] = []
        self.market_data_cache: Dict[str, Dict] = {}
        self.volume_profiles: Dict[str, List[float]] = {}
        
        # Performance tracking
        self.total_slippage_saved = 0.0
        self.total_fees_saved = 0.0
        self.execution_success_rate = 0.0
        
        # Event handlers
        self.on_execution_complete: List[Callable] = []
        self.on_execution_failed: List[Callable] = []
    
    async def execute_order(
        self,
        signal: Signal,
        position_size: float,
        execution_params: Optional[ExecutionParams] = None
    ) -> ExecutionReport:
        """Execute an order with smart routing"""
        
        execution_params = execution_params or ExecutionParams()
        
        # Create base order
        order = Order(
            id=str(uuid.uuid4()),
            symbol=signal.symbol,
            type=OrderType.MARKET,  # Will be adjusted based on strategy
            side=OrderSide.BUY if signal.direction == 'buy' else OrderSide.SELL,
            amount=position_size,
            price=signal.price
        )
        
        start_time = datetime.utcnow()
        
        try:
            # Update market data
            await self._update_market_data(signal.symbol)
            
            # Choose optimal execution strategy
            if execution_params.strategy == ExecutionStrategy.ADAPTIVE:
                execution_params.strategy = await self._choose_execution_strategy(
                    order, execution_params
                )
            
            # Execute based on chosen strategy
            if execution_params.strategy == ExecutionStrategy.IMMEDIATE:
                report = await self._execute_immediate(order, execution_params)
            elif execution_params.strategy == ExecutionStrategy.TWAP:
                report = await self._execute_twap(order, execution_params)
            elif execution_params.strategy == ExecutionStrategy.VWAP:
                report = await self._execute_vwap(order, execution_params)
            elif execution_params.strategy == ExecutionStrategy.ICEBERG:
                report = await self._execute_iceberg(order, execution_params)
            else:
                report = await self._execute_immediate(order, execution_params)
            
            # Calculate execution metrics
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            report.execution_time = execution_time
            
            # Store report
            self.execution_reports.append(report)
            
            # Emit completion event
            for handler in self.on_execution_complete:
                try:
                    await handler(report)
                except Exception as e:
                    logger.error(f"Error in execution complete handler: {e}")
            
            return report
            
        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            
            # Create failure report
            report = ExecutionReport(
                order_id=order.id,
                symbol=order.symbol,
                requested_amount=order.amount,
                executed_amount=0.0,
                average_price=0.0,
                requested_price=order.price,
                total_slippage=0.0,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                fees_paid=0.0,
                strategy_used=execution_params.strategy,
                chunks_executed=0,
                success=False,
                error_message=str(e)
            )
            
            # Emit failure event
            for handler in self.on_execution_failed:
                try:
                    await handler(report)
                except Exception:
                    pass
            
            return report
    
    async def _execute_immediate(
        self, 
        order: Order, 
        params: ExecutionParams
    ) -> ExecutionReport:
        """Execute market order immediately"""
        
        # Check spread before execution
        market_data = self.market_data_cache.get(order.symbol, {})
        bid = market_data.get('bid', 0)
        ask = market_data.get('ask', 0)
        
        if bid > 0 and ask > 0:
            spread_pct = (ask - bid) / ((ask + bid) / 2)
            if spread_pct > params.spread_threshold:
                logger.warning(f"Wide spread detected: {spread_pct:.4f} for {order.symbol}")
        
        # Execute order
        start_price = ask if order.side == OrderSide.BUY else bid
        order_id = await self.exchange.place_order(order)
        
        # Wait for fill
        filled_order = await self._wait_for_fill(order_id, params.time_limit)
        
        if not filled_order or not filled_order.is_filled:
            raise Exception("Order not filled within time limit")
        
        # Calculate slippage
        executed_price = filled_order.filled_price
        if order.side == OrderSide.BUY:
            slippage = (executed_price - start_price) / start_price
        else:
            slippage = (start_price - executed_price) / start_price
        
        # Check slippage tolerance
        if abs(slippage) > params.max_slippage:
            logger.warning(f"High slippage: {slippage:.4f} for {order.symbol}")
        
        return ExecutionReport(
            order_id=order_id,
            symbol=order.symbol,
            requested_amount=order.amount,
            executed_amount=filled_order.filled_amount,
            average_price=executed_price,
            requested_price=start_price,
            total_slippage=slippage,
            execution_time=0,  # Will be set by caller
            fees_paid=filled_order.commission,
            strategy_used=ExecutionStrategy.IMMEDIATE,
            chunks_executed=1,
            success=True
        )
    
    async def _execute_twap(
        self, 
        order: Order, 
        params: ExecutionParams
    ) -> ExecutionReport:
        """Execute using Time-Weighted Average Price strategy"""
        
        chunk_size = params.chunk_size or (order.amount / 5)  # 5 chunks by default
        time_interval = params.time_limit / max(1, order.amount / chunk_size)
        
        executed_amount = 0.0
        total_cost = 0.0
        total_fees = 0.0
        chunks_executed = 0
        
        remaining_amount = order.amount
        
        while remaining_amount > 0 and chunks_executed < 20:  # Max 20 chunks
            try:
                # Calculate chunk size (smaller chunks towards the end)
                current_chunk = min(chunk_size, remaining_amount)
                
                # Create chunk order
                chunk_order = Order(
                    id=str(uuid.uuid4()),
                    symbol=order.symbol,
                    type=OrderType.MARKET,
                    side=order.side,
                    amount=current_chunk
                )
                
                # Execute chunk
                chunk_order_id = await self.exchange.place_order(chunk_order)
                filled_chunk = await self._wait_for_fill(chunk_order_id, 60)  # 1 min per chunk
                
                if filled_chunk and filled_chunk.is_filled:
                    executed_amount += filled_chunk.filled_amount
                    total_cost += filled_chunk.filled_amount * filled_chunk.filled_price
                    total_fees += filled_chunk.commission
                    remaining_amount -= filled_chunk.filled_amount
                    chunks_executed += 1
                    
                    # Wait before next chunk (unless it's the last one)
                    if remaining_amount > 0:
                        await asyncio.sleep(min(time_interval, 30))  # Max 30s between chunks
                else:
                    logger.warning(f"TWAP chunk {chunks_executed + 1} failed to fill")
                    break
                
            except Exception as e:
                logger.error(f"Error in TWAP chunk {chunks_executed + 1}: {e}")
                break
        
        if executed_amount == 0:
            raise Exception("No chunks executed successfully")
        
        average_price = total_cost / executed_amount
        initial_price = self.market_data_cache.get(order.symbol, {}).get('last', average_price)
        
        if order.side == OrderSide.BUY:
            slippage = (average_price - initial_price) / initial_price
        else:
            slippage = (initial_price - average_price) / initial_price
        
        return ExecutionReport(
            order_id=order.id,
            symbol=order.symbol,
            requested_amount=order.amount,
            executed_amount=executed_amount,
            average_price=average_price,
            requested_price=initial_price,
            total_slippage=slippage,
            execution_time=0,
            fees_paid=total_fees,
            strategy_used=ExecutionStrategy.TWAP,
            chunks_executed=chunks_executed,
            success=executed_amount >= order.amount * 0.9  # 90% fill threshold
        )
    
    async def _execute_vwap(
        self, 
        order: Order, 
        params: ExecutionParams
    ) -> ExecutionReport:
        """Execute using Volume-Weighted Average Price strategy"""
        
        # Get volume profile
        volume_profile = await self._get_volume_profile(order.symbol)
        
        if not volume_profile:
            # Fallback to TWAP if no volume data
            return await self._execute_twap(order, params)
        
        # Calculate volume-based chunks
        total_volume = sum(volume_profile)
        target_participation = total_volume * params.participation_rate
        
        chunks = []
        remaining_amount = order.amount
        
        for volume in volume_profile:
            if remaining_amount <= 0:
                break
            
            # Calculate chunk size based on volume proportion
            volume_proportion = volume / total_volume
            chunk_size = min(
                remaining_amount,
                order.amount * volume_proportion,
                target_participation * volume_proportion
            )
            
            if chunk_size > 0:
                chunks.append(chunk_size)
                remaining_amount -= chunk_size
        
        # Execute chunks
        executed_amount = 0.0
        total_cost = 0.0
        total_fees = 0.0
        chunks_executed = 0
        
        for i, chunk_size in enumerate(chunks):
            try:
                chunk_order = Order(
                    id=str(uuid.uuid4()),
                    symbol=order.symbol,
                    type=OrderType.MARKET,
                    side=order.side,
                    amount=chunk_size
                )
                
                chunk_order_id = await self.exchange.place_order(chunk_order)
                filled_chunk = await self._wait_for_fill(chunk_order_id, 60)
                
                if filled_chunk and filled_chunk.is_filled:
                    executed_amount += filled_chunk.filled_amount
                    total_cost += filled_chunk.filled_amount * filled_chunk.filled_price
                    total_fees += filled_chunk.commission
                    chunks_executed += 1
                    
                    # Wait between chunks based on volume pattern
                    if i < len(chunks) - 1:
                        wait_time = max(5, min(30, 60 / len(chunks)))
                        await asyncio.sleep(wait_time)
                else:
                    break
                
            except Exception as e:
                logger.error(f"Error in VWAP chunk {i + 1}: {e}")
                break
        
        if executed_amount == 0:
            raise Exception("No VWAP chunks executed successfully")
        
        average_price = total_cost / executed_amount
        initial_price = self.market_data_cache.get(order.symbol, {}).get('last', average_price)
        
        if order.side == OrderSide.BUY:
            slippage = (average_price - initial_price) / initial_price
        else:
            slippage = (initial_price - average_price) / initial_price
        
        return ExecutionReport(
            order_id=order.id,
            symbol=order.symbol,
            requested_amount=order.amount,
            executed_amount=executed_amount,
            average_price=average_price,
            requested_price=initial_price,
            total_slippage=slippage,
            execution_time=0,
            fees_paid=total_fees,
            strategy_used=ExecutionStrategy.VWAP,
            chunks_executed=chunks_executed,
            success=executed_amount >= order.amount * 0.9
        )
    
    async def _execute_iceberg(
        self, 
        order: Order, 
        params: ExecutionParams
    ) -> ExecutionReport:
        """Execute using Iceberg strategy (hidden size)"""
        
        visible_size = order.amount * params.hidden_size_pct
        total_executed = 0.0
        total_cost = 0.0
        total_fees = 0.0
        chunks_executed = 0
        
        remaining_amount = order.amount
        
        while remaining_amount > 0:
            try:
                # Show only a small portion
                current_visible = min(visible_size, remaining_amount)
                
                # Create limit order at best bid/ask
                market_data = self.market_data_cache.get(order.symbol, {})
                if order.side == OrderSide.BUY:
                    limit_price = market_data.get('bid', 0)
                else:
                    limit_price = market_data.get('ask', 0)
                
                if limit_price == 0:
                    # Fallback to market order
                    chunk_order = Order(
                        id=str(uuid.uuid4()),
                        symbol=order.symbol,
                        type=OrderType.MARKET,
                        side=order.side,
                        amount=current_visible
                    )
                else:
                    chunk_order = Order(
                        id=str(uuid.uuid4()),
                        symbol=order.symbol,
                        type=OrderType.LIMIT,
                        side=order.side,
                        amount=current_visible,
                        price=limit_price
                    )
                
                chunk_order_id = await self.exchange.place_order(chunk_order)
                
                # Wait for partial or full fill
                filled_chunk = await self._wait_for_fill(
                    chunk_order_id, 
                    params.price_improvement_wait,
                    allow_partial=True
                )
                
                if filled_chunk and filled_chunk.filled_amount > 0:
                    total_executed += filled_chunk.filled_amount
                    total_cost += filled_chunk.filled_amount * filled_chunk.filled_price
                    total_fees += filled_chunk.commission
                    remaining_amount -= filled_chunk.filled_amount
                    chunks_executed += 1
                    
                    # If not fully filled, cancel and try again
                    if not filled_chunk.is_filled:
                        await self.exchange.cancel_order(chunk_order_id)
                else:
                    # Cancel unfilled order
                    await self.exchange.cancel_order(chunk_order_id)
                    break
                
                # Short pause before next iceberg slice
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in Iceberg chunk {chunks_executed + 1}: {e}")
                break
        
        if total_executed == 0:
            raise Exception("No Iceberg chunks executed successfully")
        
        average_price = total_cost / total_executed
        initial_price = self.market_data_cache.get(order.symbol, {}).get('last', average_price)
        
        if order.side == OrderSide.BUY:
            slippage = (average_price - initial_price) / initial_price
        else:
            slippage = (initial_price - average_price) / initial_price
        
        return ExecutionReport(
            order_id=order.id,
            symbol=order.symbol,
            requested_amount=order.amount,
            executed_amount=total_executed,
            average_price=average_price,
            requested_price=initial_price,
            total_slippage=slippage,
            execution_time=0,
            fees_paid=total_fees,
            strategy_used=ExecutionStrategy.ICEBERG,
            chunks_executed=chunks_executed,
            success=total_executed >= order.amount * 0.9
        )
    
    async def _choose_execution_strategy(
        self, 
        order: Order, 
        params: ExecutionParams
    ) -> ExecutionStrategy:
        """Choose optimal execution strategy based on market conditions"""
        
        market_data = self.market_data_cache.get(order.symbol, {})
        
        # Get market metrics
        spread_pct = 0
        volume = market_data.get('volume', 0)
        
        bid = market_data.get('bid', 0)
        ask = market_data.get('ask', 0)
        
        if bid > 0 and ask > 0:
            spread_pct = (ask - bid) / ((ask + bid) / 2)
        
        # Decision logic
        order_size_usd = order.amount * market_data.get('last', 0)
        
        # Small orders - immediate execution
        if order_size_usd < 1000:
            return ExecutionStrategy.IMMEDIATE
        
        # Large orders in low volume - TWAP
        if order_size_usd > 10000 and volume < params.volume_threshold:
            return ExecutionStrategy.TWAP
        
        # Very large orders - Iceberg
        if order_size_usd > 50000:
            return ExecutionStrategy.ICEBERG
        
        # Wide spreads - VWAP
        if spread_pct > params.spread_threshold:
            return ExecutionStrategy.VWAP
        
        # Normal conditions - TWAP for medium orders
        if order_size_usd > 5000:
            return ExecutionStrategy.TWAP
        
        return ExecutionStrategy.IMMEDIATE
    
    async def _update_market_data(self, symbol: str):
        """Update market data cache"""
        try:
            ticker = await self.exchange.get_ticker(symbol)
            order_book = await self.exchange.get_order_book(symbol, limit=5)
            
            self.market_data_cache[symbol] = {
                **ticker,
                'bid': order_book['bids'][0][0] if order_book['bids'] else 0,
                'ask': order_book['asks'][0][0] if order_book['asks'] else 0,
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error updating market data for {symbol}: {e}")
    
    async def _get_volume_profile(self, symbol: str) -> List[float]:
        """Get volume profile for VWAP execution"""
        try:
            # Get recent volume data
            df = await self.exchange.get_ohlcv(symbol, '5m', limit=48)  # 4 hours of 5min data
            
            if df.empty:
                return []
            
            # Calculate volume profile (simplified)
            volume_profile = df['volume'].rolling(window=6).mean().fillna(0).tolist()
            return volume_profile[-12:]  # Last hour in 5-min chunks
            
        except Exception as e:
            logger.error(f"Error getting volume profile for {symbol}: {e}")
            return []
    
    async def _wait_for_fill(
        self, 
        order_id: str, 
        timeout: int, 
        allow_partial: bool = False
    ) -> Optional[Order]:
        """Wait for order to fill"""
        
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                order = await self.exchange.get_order_status(order_id)
                
                if order.is_filled:
                    return order
                
                if allow_partial and order.filled_amount > 0:
                    return order
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Error checking order status {order_id}: {e}")
                await asyncio.sleep(2)
        
        return None
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get execution performance metrics"""
        if not self.execution_reports:
            return {}
        
        successful_reports = [r for r in self.execution_reports if r.success]
        
        if not successful_reports:
            return {'success_rate': 0.0}
        
        avg_slippage = np.mean([abs(r.total_slippage) for r in successful_reports])
        avg_execution_time = np.mean([r.execution_time for r in successful_reports])
        total_fees = sum(r.fees_paid for r in successful_reports)
        
        strategy_usage = {}
        for report in successful_reports:
            strategy = report.strategy_used.value
            strategy_usage[strategy] = strategy_usage.get(strategy, 0) + 1
        
        return {
            'success_rate': len(successful_reports) / len(self.execution_reports),
            'avg_slippage': avg_slippage,
            'avg_execution_time': avg_execution_time,
            'total_fees_paid': total_fees,
            'total_orders': len(self.execution_reports),
            'successful_orders': len(successful_reports),
            'strategy_usage': strategy_usage,
            'slippage_saved': self.total_slippage_saved,
            'fees_saved': self.total_fees_saved
        }