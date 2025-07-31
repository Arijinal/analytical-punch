import logging
import sys
from typing import Optional
import structlog
from structlog.stdlib import LoggerFactory
from app.config import get_config

config = get_config()


def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """Setup structured logger with proper formatting"""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer() if config.DEBUG else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Setup standard logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT,
        stream=sys.stdout
    )
    
    # Get logger
    logger = structlog.get_logger(name) if name else structlog.get_logger()
    
    return logger