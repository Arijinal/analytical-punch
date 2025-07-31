"""
Enhanced exchange integration layer for trading bots.
"""

import asyncio
import ccxt.pro as ccxt
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import logging

from app.core.trading.base import (
    ExchangeInterface, Order, Position, OrderType, OrderSide, OrderStatus
)
from app.config import get_config
from app.utils.logger import setup_logger

config = get_config()
logger = setup_logger(__name__)


class BinanceExchange(ExchangeInterface):
    """Enhanced Binance exchange integration with trading capabilities"""
    
    def __init__(self, paper_trading: bool = True):
        self.paper_trading = paper_trading
        self.exchange = None
        self.connected = False
        self.paper_portfolio = {'USDT': 10000.0}  # Paper trading balance
        self.paper_positions = {}
        self.paper_orders = {}
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
        
    async def connect(self) -> bool:
        """Connect to Binance"""
        try:
            # Initialize exchange
            exchange_config = {
                'apiKey': config.BINANCE_API_KEY if not self.paper_trading else '',
                'secret': config.BINANCE_API_SECRET if not self.paper_trading else '',
                'sandbox': False,  # Use sandbox for testing
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True,
                }
            }
            
            if self.paper_trading:
                # Paper trading mode - no credentials needed
                exchange_config.pop('apiKey', None)
                exchange_config.pop('secret', None)
                self.exchange = ccxt.binance(exchange_config)
            else:
                # Live trading mode
                if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
                    raise ValueError("Binance API credentials not configured for live trading")
                self.exchange = ccxt.binance(exchange_config)
            
            # Test connection
            await self.exchange.load_markets()
            self.connected = True
            
            logger.info(f"Connected to Binance ({'paper' if self.paper_trading else 'live'} trading)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from exchange"""
        if self.exchange:
            await self.exchange.close()
        self.connected = False
        logger.info("Disconnected from Binance")
    
    async def _rate_limit(self):
        """Implement rate limiting"""
        current_time = datetime.utcnow().timestamp()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        self.last_request_time = datetime.utcnow().timestamp()
    
    async def get_balance(self) -> Dict[str, float]:
        """Get account balance"""
        if not self.connected:
            await self.connect()
        
        if self.paper_trading:
            return self.paper_portfolio.copy()
        
        try:
            await self._rate_limit()
            balance = await self.exchange.fetch_balance()
            
            # Return free balances only
            return {
                asset: info['free'] 
                for asset, info in balance.items() 
                if isinstance(info, dict) and info.get('free', 0) > 0
            }
            
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            raise
    
    async def place_order(self, order: Order) -> str:
        """Place an order"""
        if not self.connected:
            await self.connect()
        
        try:
            if self.paper_trading:
                return await self._place_paper_order(order)
            else:
                return await self._place_live_order(order)
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            order.status = OrderStatus.REJECTED
            raise
    
    async def _place_paper_order(self, order: Order) -> str:
        """Place paper trading order"""
        # Get current price
        ticker = await self.get_ticker(order.symbol)
        current_price = ticker['last']
        
        # Simulate order execution for market orders
        if order.type == OrderType.MARKET:
            order.filled_price = current_price
            order.filled_amount = order.amount
            order.status = OrderStatus.FILLED
            order.updated_at = datetime.utcnow()
            
            # Update paper portfolio
            base_asset, quote_asset = order.symbol.split('/')
            
            if order.side == OrderSide.BUY:
                required_quote = order.amount * current_price
                if self.paper_portfolio.get(quote_asset, 0) >= required_quote:
                    self.paper_portfolio[quote_asset] -= required_quote
                    self.paper_portfolio[base_asset] = self.paper_portfolio.get(base_asset, 0) + order.amount
                else:
                    order.status = OrderStatus.REJECTED
                    raise ValueError("Insufficient balance for paper trade")
            
            elif order.side == OrderSide.SELL:
                if self.paper_portfolio.get(base_asset, 0) >= order.amount:
                    self.paper_portfolio[base_asset] -= order.amount
                    received_quote = order.amount * current_price
                    self.paper_portfolio[quote_asset] = self.paper_portfolio.get(quote_asset, 0) + received_quote
                else:
                    order.status = OrderStatus.REJECTED
                    raise ValueError("Insufficient balance for paper trade")
        
        # Store paper order
        self.paper_orders[order.id] = order
        
        logger.info(f"Paper order placed: {order.id} - {order.side.value} {order.amount} {order.symbol}")
        return order.id
    
    async def _place_live_order(self, order: Order) -> str:
        """Place live order"""
        await self._rate_limit()
        
        # Prepare order parameters
        order_params = {
            'symbol': order.symbol,
            'side': order.side.value,
            'amount': order.amount,
            'type': order.type.value,
        }
        
        if order.type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and order.price:
            order_params['price'] = order.price
        
        if order.type in [OrderType.STOP, OrderType.STOP_LIMIT] and order.stop_price:
            order_params['stopPrice'] = order.stop_price
        
        # Place order
        result = await self.exchange.create_order(**order_params)
        
        # Update order with exchange response
        order.id = result['id']
        order.status = OrderStatus(result['status'].lower())
        order.filled_amount = result.get('filled', 0)
        order.filled_price = result.get('average')
        order.updated_at = datetime.utcnow()
        
        logger.info(f"Live order placed: {order.id} - {order.side.value} {order.amount} {order.symbol}")
        return order.id
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if not self.connected:
            await self.connect()
        
        try:
            if self.paper_trading:
                if order_id in self.paper_orders:
                    self.paper_orders[order_id].status = OrderStatus.CANCELLED
                    return True
                return False
            else:
                await self._rate_limit()
                await self.exchange.cancel_order(order_id)
                return True
                
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def get_order_status(self, order_id: str) -> Order:
        """Get order status"""
        if not self.connected:
            await self.connect()
        
        try:
            if self.paper_trading:
                return self.paper_orders.get(order_id)
            
            await self._rate_limit()
            result = await self.exchange.fetch_order(order_id)
            
            # Convert to our Order format
            order = Order(
                id=result['id'],
                symbol=result['symbol'],
                type=OrderType(result['type']),
                side=OrderSide(result['side']),
                amount=result['amount'],
                price=result.get('price'),
                status=OrderStatus(result['status'].lower()),
                filled_amount=result.get('filled', 0),
                filled_price=result.get('average'),
                commission=result.get('fee', {}).get('cost', 0)
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error fetching order status {order_id}: {e}")
            raise
    
    async def get_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        if not self.connected:
            await self.connect()
        
        positions = {}
        
        try:
            if self.paper_trading:
                # Calculate positions from paper portfolio
                for asset, balance in self.paper_portfolio.items():
                    if balance > 0 and asset != 'USDT':
                        # Get current price
                        symbol = f"{asset}/USDT"
                        try:
                            ticker = await self.get_ticker(symbol)
                            current_price = ticker['last']
                            
                            positions[symbol] = Position(
                                symbol=symbol,
                                side='long',
                                size=balance,
                                entry_price=current_price,  # Simplified for paper trading
                                current_price=current_price,
                                entry_time=datetime.utcnow()
                            )
                        except:
                            continue  # Skip if can't get price
            else:
                # Get positions from exchange (for margin/futures)
                # Spot positions would be calculated from balances
                balance = await self.exchange.fetch_balance()
                
                for asset, info in balance.items():
                    if isinstance(info, dict) and info.get('free', 0) > 0:
                        symbol = f"{asset}/USDT"
                        try:
                            ticker = await self.get_ticker(symbol)
                            current_price = ticker['last']
                            
                            positions[symbol] = Position(
                                symbol=symbol,
                                side='long',
                                size=info['free'],
                                entry_price=current_price,  # Would need historical data
                                current_price=current_price,
                                entry_time=datetime.utcnow()
                            )
                        except:
                            continue
            
            return positions
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return {}
    
    async def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get ticker data"""
        if not self.connected:
            await self.connect()
        
        try:
            await self._rate_limit()
            ticker = await self.exchange.fetch_ticker(symbol)
            
            return {
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0),
                'last': ticker.get('last', 0),
                'volume': ticker.get('quoteVolume', 0),
                'change': ticker.get('change', 0),
                'percentage': ticker.get('percentage', 0),
                'high': ticker.get('high', 0),
                'low': ticker.get('low', 0),
                'timestamp': ticker.get('timestamp', 0)
            }
            
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            raise
    
    async def get_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = '1h', 
        limit: int = 100
    ) -> pd.DataFrame:
        """Get OHLCV data"""
        if not self.connected:
            await self.connect()
        
        try:
            await self._rate_limit()
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            raise
    
    async def get_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Get order book"""
        if not self.connected:
            await self.connect()
        
        try:
            await self._rate_limit()
            order_book = await self.exchange.fetch_order_book(symbol, limit)
            
            return {
                'bids': order_book['bids'][:limit],
                'asks': order_book['asks'][:limit],
                'timestamp': order_book.get('timestamp', 0),
                'symbol': symbol
            }
            
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {e}")
            raise
    
    def calculate_fees(self, symbol: str, amount: float, price: float) -> float:
        """Calculate trading fees"""
        # Binance spot trading fee is typically 0.1%
        return amount * price * 0.001
    
    async def get_trading_fees(self, symbol: str) -> Dict[str, float]:
        """Get trading fees for symbol"""
        if not self.connected:
            await self.connect()
        
        try:
            if self.paper_trading:
                return {'maker': 0.001, 'taker': 0.001}
            
            # In real implementation, would fetch from exchange
            return {'maker': 0.001, 'taker': 0.001}
            
        except Exception as e:
            logger.error(f"Error fetching trading fees for {symbol}: {e}")
            return {'maker': 0.001, 'taker': 0.001}
    
    async def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol is tradeable"""
        if not self.connected:
            await self.connect()
        
        try:
            markets = self.exchange.markets
            return symbol in markets and markets[symbol].get('active', False)
        except:
            return False
    
    async def get_minimum_order_size(self, symbol: str) -> float:
        """Get minimum order size for symbol"""
        if not self.connected:
            await self.connect()
        
        try:
            markets = self.exchange.markets
            if symbol in markets:
                return markets[symbol].get('limits', {}).get('amount', {}).get('min', 0.001)
            return 0.001
        except:
            return 0.001
    
    async def get_price_precision(self, symbol: str) -> int:
        """Get price precision for symbol"""
        if not self.connected:
            await self.connect()
        
        try:
            markets = self.exchange.markets
            if symbol in markets:
                return markets[symbol].get('precision', {}).get('price', 8)
            return 8
        except:
            return 8
    
    async def get_amount_precision(self, symbol: str) -> int:
        """Get amount precision for symbol"""
        if not self.connected:
            await self.connect()
        
        try:
            markets = self.exchange.markets
            if symbol in markets:
                return markets[symbol].get('precision', {}).get('amount', 8)
            return 8
        except:
            return 8