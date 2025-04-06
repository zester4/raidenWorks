import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from raiden.core.models.internal_models import SessionState, Plan
from raiden.db.models import SessionHistory
from raiden.db.base import get_db_session, initialize_database, close_database
from .base_storage import BaseSessionStorage

logger = logging.getLogger(__name__)

class PostgresSessionStorage(BaseSessionStorage):
    async def initialize(self) -> None:
        logger.info("Initializing PostgreSQL storage...")
        try:
            await initialize_database()
            logger.info("PostgreSQL storage initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL storage: {e}", exc_info=True)
            raise

    def _map_pydantic_to_orm(self, session_state: SessionState) -> Dict[str, Any]:
        return {
            "session_id": session_state.session_id,
            "status": session_state.status,
            "user_prompt": session_state.user_prompt,
            # Use model_dump(mode='json') to ensure proper serialization of complex types like HttpUrl
            "plan": session_state.plan.model_dump(mode='json') if session_state.plan else None,
            "session_variables": session_state.session_variables,
            "final_result": session_state.final_result,
            "session_config": session_state.session_config,
            "created_at": session_state.created_at,
            "last_error": session_state.last_error,
            "completed_at": datetime.utcnow() if session_state.status in ["COMPLETED", "FAILED"] else None,
            "total_steps_executed": session_state.current_step_index,
        }

    def _map_orm_to_pydantic(self, db_session: SessionHistory) -> SessionState:
        return SessionState(
            session_id=db_session.session_id,
            status=db_session.status,
            user_prompt=db_session.user_prompt,
            plan=Plan.model_validate(db_session.plan) if db_session.plan else None,
            current_step_index=db_session.total_steps_executed or 0,
            session_variables=db_session.session_variables or {},
            last_error=db_session.last_error,
            final_result=db_session.final_result,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
            session_config=db_session.session_config,
        )

    async def save_session(self, session_state: SessionState) -> None:
        logger.debug(f"Saving session {session_state.session_id} to PostgreSQL.")
        orm_data = self._map_pydantic_to_orm(session_state)
        async with get_db_session() as db:
            try:
                stmt = select(SessionHistory).where(SessionHistory.session_id == session_state.session_id)
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    stmt_update = update(SessionHistory).where(SessionHistory.session_id == session_state.session_id).values(**orm_data)
                    await db.execute(stmt_update)
                    logger.info(f"Updated session {session_state.session_id} in PostgreSQL.")
                else:
                    db.add(SessionHistory(**orm_data))
                    logger.info(f"Inserted new session {session_state.session_id} into PostgreSQL.")
            except IntegrityError as e:
                logger.error(f"Integrity error saving session {session_state.session_id}: {e}", exc_info=True)
                raise RuntimeError(f"Integrity error for session {session_state.session_id}") from e
            except SQLAlchemyError as e:
                logger.error(f"Failed to save session {session_state.session_id}: {e}", exc_info=True)
                raise RuntimeError(f"Save operation failed for session {session_state.session_id}") from e

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        logger.debug(f"Retrieving session {session_id} from PostgreSQL.")
        async with get_db_session() as db:
            try:
                stmt = select(SessionHistory).where(SessionHistory.session_id == session_id)
                result = await db.execute(stmt)
                db_session = result.scalar_one_or_none()

                if db_session:
                    logger.debug(f"Session {session_id} retrieved successfully.")
                    return self._map_orm_to_pydantic(db_session)
                else:
                    logger.debug(f"Session {session_id} not found.")
                    return None
            except SQLAlchemyError as e:
                logger.error(f"Failed to retrieve session {session_id}: {e}", exc_info=True)
                raise RuntimeError(f"Get operation failed for session {session_id}") from e

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[SessionState]:
        logger.debug(f"Updating session {session_id} in PostgreSQL with updates: {updates}.")
        async with get_db_session() as db:
            try:
                stmt = update(SessionHistory).where(SessionHistory.session_id == session_id).values(**updates).returning(SessionHistory)
                result = await db.execute(stmt)
                updated_db_session = result.scalar_one_or_none()

                if updated_db_session:
                    logger.info(f"Session {session_id} updated successfully.")
                    return self._map_orm_to_pydantic(updated_db_session)
                else:
                    logger.warning(f"Session {session_id} not found for update.")
                    return None
            except SQLAlchemyError as e:
                logger.error(f"Failed to update session {session_id}: {e}", exc_info=True)
                raise RuntimeError(f"Update operation failed for session {session_id}") from e

    async def delete_session(self, session_id: str) -> bool:
        logger.debug(f"Deleting session {session_id} from PostgreSQL.")
        async with get_db_session() as db:
            try:
                stmt = delete(SessionHistory).where(SessionHistory.session_id == session_id)
                result = await db.execute(stmt)
                if result.rowcount > 0:
                    logger.info(f"Session {session_id} deleted successfully.")
                    return True
                else:
                    logger.debug(f"Session {session_id} not found for deletion.")
                    return False
            except SQLAlchemyError as e:
                logger.error(f"Failed to delete session {session_id}: {e}", exc_info=True)
                raise RuntimeError(f"Delete operation failed for session {session_id}") from e

    async def close(self) -> None:
        logger.info("Closing PostgreSQL storage.")
        await close_database()
        logger.info("PostgreSQL storage closed.")
