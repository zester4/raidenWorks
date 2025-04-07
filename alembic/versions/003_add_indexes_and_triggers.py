"""add indexes and triggers

Revision ID: 003_add_indexes_and_triggers
Revises: 002_add_indices
Create Date: 2025-04-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_add_indexes_and_triggers'
down_revision = '002_add_indices'
branch_labels = None
depends_on = None

def upgrade():
    # Create trigger to automatically update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute("""
        CREATE TRIGGER update_sessions_updated_at
            BEFORE UPDATE ON sessions
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

def downgrade():
    op.execute("DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")