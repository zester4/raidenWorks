# raiden/db/models.py
"""
Defines SQLAlchemy ORM models for database tables.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Import necessary types from SQLAlchemy
from sqlalchemy import (
    String,
    DateTime,
    JSON, # Use JSON or JSONB depending on dialect support (JSONB preferred for Postgres)
    Text,
    Integer,
    Index,
    Boolean, # Boolean might be useful later
    Float    # Added for duration_seconds
)
# Use PostgreSQL specific types for better performance/features on Postgres/Neon
from sqlalchemy.dialects.postgresql import UUID, JSONB
# Import ORM mapping tools
from sqlalchemy.orm import Mapped, mapped_column, relationship
# Import SQL functions like now()
from sqlalchemy.sql import func

# Import the Base from our sibling base.py file
from .base import Base
# Import SessionStatus type for status column typing if desired (optional)
# from raiden.core.constants import SessionStatus

class SessionHistory(Base):
    """
    SQLAlchemy model representing the persisted history of a Raiden session.
    Maps to the 'session_history' table.
    """
    __tablename__ = "session_history"

    # Use server-side UUID generation if possible, or client-side default
    # Ensure primary_key=True
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # session_id should be unique and indexed for lookups
    session_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    # Status is important for filtering, use index=True
    # Use String here, SessionStatus enum validation happens in Pydantic models
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Store the original prompt
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Store complex objects as JSONB for flexibility and queryability in Postgres
    # Use nullable=True as these might not exist initially
    plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    session_variables: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True, default=dict)
    final_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True) # Store result as JSON
    session_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Timestamps - Use server defaults and timezone=True for consistency
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Error details - use Text for potentially long messages
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Resource usage (example fields, adjust as needed)
    total_steps_executed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Store duration in seconds

    # Indexing important query fields
    __table_args__ = (
        Index("ix_session_history_created_at", created_at.desc()),
        # Add other indexes if needed, e.g., Index("ix_session_history_status", status) if filtering by status often
    )

    def __repr__(self):
        return f"<SessionHistory(session_id='{self.session_id}', status='{self.status}', created_at='{self.created_at}')>"