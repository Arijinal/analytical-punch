"""
Symbol normalization service for handling different symbol formats across data sources
"""

from typing import Dict, List, Optional, Tuple
import re
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class SymbolNormalizer:
    """
    Handles symbol format conversion between frontend and different data sources
    """
    
    def __init__(self):
        # Standard format mapping (base-quote pairs)
        self.standard_symbols = {
            # Cryptocurrency pairs
            'BTC-USD': {'base': 'BTC', 'quote': 'USD', 'type': 'crypto'},
            'BTC-USDT': {'base': 'BTC', 'quote': 'USDT', 'type': 'crypto'},
            'ETH-USD': {'base': 'ETH', 'quote': 'USD', 'type': 'crypto'},
            'ETH-USDT': {'base': 'ETH', 'quote': 'USDT', 'type': 'crypto'},
            'LTC-USD': {'base': 'LTC', 'quote': 'USD', 'type': 'crypto'},
            'BCH-USD': {'base': 'BCH', 'quote': 'USD', 'type': 'crypto'},
            'ADA-USD': {'base': 'ADA', 'quote': 'USD', 'type': 'crypto'},
            'DOT-USD': {'base': 'DOT', 'quote': 'USD', 'type': 'crypto'},
            'LINK-USD': {'base': 'LINK', 'quote': 'USD', 'type': 'crypto'},
            'SOL-USD': {'base': 'SOL', 'quote': 'USD', 'type': 'crypto'},
            'AVAX-USD': {'base': 'AVAX', 'quote': 'USD', 'type': 'crypto'},
            'MATIC-USD': {'base': 'MATIC', 'quote': 'USD', 'type': 'crypto'},
            'UNI-USD': {'base': 'UNI', 'quote': 'USD', 'type': 'crypto'},
            'ATOM-USD': {'base': 'ATOM', 'quote': 'USD', 'type': 'crypto'},
            
            # Stock symbols
            'AAPL': {'base': 'AAPL', 'quote': 'USD', 'type': 'stock'},
            'GOOGL': {'base': 'GOOGL', 'quote': 'USD', 'type': 'stock'},
            'MSFT': {'base': 'MSFT', 'quote': 'USD', 'type': 'stock'},
            'TSLA': {'base': 'TSLA', 'quote': 'USD', 'type': 'stock'},
            'AMZN': {'base': 'AMZN', 'quote': 'USD', 'type': 'stock'},
            'SPY': {'base': 'SPY', 'quote': 'USD', 'type': 'etf'},
            'QQQ': {'base': 'QQQ', 'quote': 'USD', 'type': 'etf'},
        }
        
        # Source-specific conversions
        self.source_mappings = {
            'coingecko': {
                'BTC-USD': 'bitcoin',
                'BTC-USDT': 'bitcoin',
                'ETH-USD': 'ethereum',
                'ETH-USDT': 'ethereum',
                'LTC-USD': 'litecoin',
                'BCH-USD': 'bitcoin-cash',
                'ADA-USD': 'cardano',
                'DOT-USD': 'polkadot',
                'LINK-USD': 'chainlink',
                'SOL-USD': 'solana',
                'AVAX-USD': 'avalanche-2',
                'MATIC-USD': 'matic-network',
                'UNI-USD': 'uniswap',
                'ATOM-USD': 'cosmos'
            },
            'kraken': {
                'BTC-USD': 'XBTUSD',
                'BTC-USDT': 'XBTUSD',
                'ETH-USD': 'ETHUSD',
                'ETH-USDT': 'ETHUSD',
                'LTC-USD': 'LTCUSD',
                'BCH-USD': 'BCHUSD',
                'ADA-USD': 'ADAUSD',
                'DOT-USD': 'DOTUSD',
                'LINK-USD': 'LINKUSD',
                'ATOM-USD': 'ATOMUSD'
            },
            'coinbase': {
                'BTC-USD': 'BTC-USD',
                'BTC-USDT': 'BTC-USD',  # Coinbase uses USD not USDT
                'ETH-USD': 'ETH-USD',
                'ETH-USDT': 'ETH-USD',
                'LTC-USD': 'LTC-USD',
                'BCH-USD': 'BCH-USD',
                'ADA-USD': 'ADA-USD',
                'DOT-USD': 'DOT-USD',
                'LINK-USD': 'LINK-USD',
                'ATOM-USD': 'ATOM-USD'
            },
            'binance': {
                'BTC-USD': 'BTCUSDT',
                'BTC-USDT': 'BTCUSDT',
                'ETH-USD': 'ETHUSDT',
                'ETH-USDT': 'ETHUSDT',
                'LTC-USD': 'LTCUSDT',
                'BCH-USD': 'BCHUSDT',
                'ADA-USD': 'ADAUSDT',
                'DOT-USD': 'DOTUSDT',
                'LINK-USD': 'LINKUSDT',
                'SOL-USD': 'SOLUSDT',
                'AVAX-USD': 'AVAXUSDT',
                'MATIC-USD': 'MATICUSDT',
                'UNI-USD': 'UNIUSDT',
                'ATOM-USD': 'ATOMUSDT'
            },
            'yahoo': {
                'BTC-USD': 'BTC-USD',
                'BTC-USDT': 'BTC-USD',
                'ETH-USD': 'ETH-USD',
                'ETH-USDT': 'ETH-USD',
                'AAPL': 'AAPL',
                'GOOGL': 'GOOGL',
                'MSFT': 'MSFT',
                'TSLA': 'TSLA',
                'AMZN': 'AMZN',
                'SPY': 'SPY',
                'QQQ': 'QQQ'
            }
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Convert any symbol format to standard format (BASE-QUOTE)
        
        Examples:
        - BTC/USDT -> BTC-USDT
        - BTCUSDT -> BTC-USDT
        - bitcoin -> BTC-USD (for CoinGecko)
        - XBTUSD -> BTC-USD (for Kraken)
        """
        symbol = symbol.upper().strip()
        
        # Check if already in standard format
        if symbol in self.standard_symbols:
            return symbol
        
        # Handle slash notation (BTC/USDT -> BTC-USDT)
        if '/' in symbol:
            return symbol.replace('/', '-')
        
        # Handle concatenated format (BTCUSDT -> BTC-USDT)
        normalized = self._parse_concatenated_symbol(symbol)
        if normalized:
            return normalized
        
        # Handle source-specific reverse mapping
        for source, mappings in self.source_mappings.items():
            for standard, source_format in mappings.items():
                if symbol == source_format:
                    return standard
        
        # Handle single stock symbols (AAPL -> AAPL)
        if self._is_stock_symbol(symbol):
            return symbol
        
        # If no conversion found, return as-is
        logger.warning(f"Could not normalize symbol: {symbol}")
        return symbol
    
    def convert_for_source(self, symbol: str, source: str) -> str:
        """
        Convert standard symbol format to source-specific format
        
        Args:
            symbol: Symbol in standard format (e.g., BTC-USD)
            source: Data source name (e.g., 'coingecko', 'kraken')
        
        Returns:
            Source-specific symbol format
        """
        # First normalize the input symbol
        normalized = self.normalize_symbol(symbol)
        
        # Get source-specific mapping
        if source in self.source_mappings:
            source_map = self.source_mappings[source]
            if normalized in source_map:
                return source_map[normalized]
        
        # If no specific mapping, return normalized format
        return normalized
    
    def get_symbol_info(self, symbol: str) -> Dict:
        """Get information about a symbol"""
        normalized = self.normalize_symbol(symbol)
        
        if normalized in self.standard_symbols:
            info = self.standard_symbols[normalized].copy()
            info['normalized'] = normalized
            info['original'] = symbol
            return info
        
        # Parse unknown symbol
        return {
            'base': self._extract_base(normalized),
            'quote': 'USD',  # Default quote
            'type': 'unknown',
            'normalized': normalized,
            'original': symbol
        }
    
    def is_crypto_symbol(self, symbol: str) -> bool:
        """Check if symbol represents a cryptocurrency"""
        info = self.get_symbol_info(symbol)
        return info['type'] == 'crypto'
    
    def is_stock_symbol(self, symbol: str) -> bool:
        """Check if symbol represents a stock"""
        info = self.get_symbol_info(symbol)
        return info['type'] in ['stock', 'etf']
    
    def get_compatible_sources(self, symbol: str) -> List[str]:
        """Get list of data sources that support this symbol"""
        normalized = self.normalize_symbol(symbol)
        compatible = []
        
        for source, mappings in self.source_mappings.items():
            if normalized in mappings:
                compatible.append(source)
        
        return compatible
    
    def _parse_concatenated_symbol(self, symbol: str) -> Optional[str]:
        """Parse concatenated symbol like BTCUSDT -> BTC-USDT"""
        common_quotes = ['USDT', 'BUSD', 'USDC', 'USD', 'BTC', 'ETH', 'BNB']
        
        for quote in common_quotes:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base = symbol[:-len(quote)]
                if len(base) >= 2:  # Valid base currency
                    return f"{base}-{quote}"
        
        return None
    
    def _extract_base(self, symbol: str) -> str:
        """Extract base currency from symbol"""
        if '-' in symbol:
            return symbol.split('-')[0]
        if '/' in symbol:
            return symbol.split('/')[0]
        return symbol
    
    def _is_stock_symbol(self, symbol: str) -> bool:
        """Basic stock symbol detection"""
        # Stock symbols are typically 1-5 uppercase letters
        return bool(re.match(r'^[A-Z]{1,5}$', symbol))
    
    def get_display_format(self, symbol: str) -> str:
        """Get user-friendly display format"""
        normalized = self.normalize_symbol(symbol)
        
        # For crypto, use slash notation
        if self.is_crypto_symbol(normalized):
            return normalized.replace('-', '/')
        
        # For stocks, use as-is
        return normalized
    
    def get_popular_symbols(self) -> List[Dict]:
        """Get list of popular symbols with display info"""
        popular = [
            'BTC-USD', 'ETH-USD', 'LTC-USD', 'BCH-USD',
            'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'SPY'
        ]
        
        result = []
        for symbol in popular:
            info = self.get_symbol_info(symbol)
            result.append({
                'symbol': symbol,
                'display': self.get_display_format(symbol),
                'type': info['type'],
                'base': info['base'],
                'quote': info['quote']
            })
        
        return result


# Global instance
symbol_normalizer = SymbolNormalizer()