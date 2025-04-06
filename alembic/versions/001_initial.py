"""initial

Revision ID: 001
Revises: 
Create Date: 2024-03-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('session_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('user_prompt', sa.Text(), nullable=False),
        sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('session_variables', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('final_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('session_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('total_steps_executed', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_session_history_session_id', 'session_history', ['session_id'], unique=True)
    op.create_index('ix_session_history_status', 'session_history', ['status'])
    op.create_index('ix_session_history_created_at', 'session_history', ['created_at'])

def downgrade() -> None:
    op.drop_table('session_history')
