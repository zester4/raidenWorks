from sqlalchemy import Column, String, Integer, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SessionHistory(Base):
    __tablename__ = "session_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False)
    user_prompt = Column(String, nullable=False)
    plan = Column(JSON, nullable=True)
    session_variables = Column(JSON, nullable=True)
    final_result = Column(JSON, nullable=True)
    session_config = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_error = Column(String, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    total_steps_executed = Column(Integer, nullable=True)
