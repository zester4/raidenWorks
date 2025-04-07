"""add indices

Revision ID: 002_add_indices
Revises: 001_initial
Create Date: 2025-04-06

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '002_add_indices'
down_revision = '001_initial'
branch_labels = None
depends_on = None

def upgrade():
    # Create indices for better query performance
    op.create_index('idx_sessions_status', 'sessions', ['status'])
    op.create_index('idx_sessions_created_at', 'sessions', ['created_at'])
    op.create_index('idx_sessions_updated_at', 'sessions', ['updated_at'])

def downgrade():
    # Remove indices
    op.drop_index('idx_sessions_status')
    op.drop_index('idx_sessions_created_at')
    op.drop_index('idx_sessions_updated_at')