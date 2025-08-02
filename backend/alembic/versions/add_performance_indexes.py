"""Add performance indexes for faster queries

Revision ID: add_performance_indexes
Revises: 
Create Date: 2025-08-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_performance_indexes'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes for commonly queried columns"""
    
    # Trading bots indexes
    op.create_index('idx_bot_status_created', 'trading_bots', ['status', 'created_at'])
    
    # Positions indexes
    op.create_index('idx_position_bot_symbol_entry', 'positions', ['bot_id', 'symbol', 'entry_time'])
    
    # Orders indexes
    op.create_index('idx_order_created_status', 'orders', ['created_at', 'status'])
    op.create_index('idx_order_bot_created', 'orders', ['bot_id', 'created_at'])
    
    # Trades indexes
    op.create_index('idx_trade_exit_time', 'trades', ['exit_time'])
    op.create_index('idx_trade_strategy_time', 'trades', ['strategy', 'exit_time'])
    
    # Signals indexes
    op.create_index('idx_signal_timestamp', 'signals', ['timestamp'])
    op.create_index('idx_signal_symbol_time', 'signals', ['symbol', 'timestamp'])
    
    # Market data indexes
    op.create_index('idx_market_data_time', 'market_data', ['timestamp'])
    
    # System logs indexes
    op.create_index('idx_log_timestamp', 'system_logs', ['timestamp'])


def downgrade():
    """Remove performance indexes"""
    
    # Remove all indexes
    op.drop_index('idx_bot_status_created', 'trading_bots')
    op.drop_index('idx_position_bot_symbol_entry', 'positions')
    op.drop_index('idx_order_created_status', 'orders')
    op.drop_index('idx_order_bot_created', 'orders')
    op.drop_index('idx_trade_exit_time', 'trades')
    op.drop_index('idx_trade_strategy_time', 'trades')
    op.drop_index('idx_signal_timestamp', 'signals')
    op.drop_index('idx_signal_symbol_time', 'signals')
    op.drop_index('idx_market_data_time', 'market_data')
    op.drop_index('idx_log_timestamp', 'system_logs')