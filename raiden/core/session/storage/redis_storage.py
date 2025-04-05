import logging
from typing import Optional, Dict, Any
from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from raiden.core.config import settings
from raiden.core.models.internal_models import SessionState
from raiden.core.constants import DEFAULT_SESSION_TIMEOUT_SECONDS
from .base_storage import BaseSessionStorage

logger = logging.getLogger(__name__)

class RedisSessionStorage(BaseSessionStorage):
    _client: Optional[Redis] = None
    _prefix: str = "raiden:session:"

    async def initialize(self) -> None:
        """Initializes the Redis connection pool and client using the computed DSN."""
        if not self._client:
            try:
                computed_dsn = settings.computed_redis_dsn
                if not computed_dsn:
                    raise ValueError("Redis DSN is not configured in settings.")

                dsn_str = str(computed_dsn).replace(settings.redis_password or '', '******')
                logger.info(f"Initializing Redis connection pool using computed DSN: {dsn_str}")

                self._client = Redis.from_url(
                    str(computed_dsn),  # Pass the computed Redis DSN
                    encoding="utf-8",
                    decode_responses=True
                )
                await self._client.ping()
                logger.info("Redis connection pool initialized successfully.")
            except RedisConnectionError as e:
                logger.error(f"Failed to connect to Redis using DSN: {e}", exc_info=True)
                raise ConnectionError(f"Could not connect to Redis: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected error during Redis initialization: {e}", exc_info=True)
                raise RuntimeError(f"Unexpected Redis initialization error: {e}") from e

    def _get_redis_key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def save_session(self, session_state: SessionState) -> None:
        if not self._client:
            raise RuntimeError("Redis client not initialized.")
        redis_key = self._get_redis_key(session_state.session_id)
        try:
            session_json = session_state.model_dump_json()
            await self._client.set(redis_key, session_json, ex=DEFAULT_SESSION_TIMEOUT_SECONDS)
        except RedisError as e:
            logger.error(f"Failed to save session {session_state.session_id}: {e}", exc_info=True)
            raise RuntimeError(f"Redis save operation failed for session {session_state.session_id}") from e

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        if not self._client:
            raise RuntimeError("Redis client not initialized.")
        redis_key = self._get_redis_key(session_id)
        try:
            session_json = await self._client.get(redis_key)
            if session_json:
                return SessionState.model_validate_json(session_json)
            return None
        except RedisError as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}", exc_info=True)
            raise RuntimeError(f"Redis get operation failed for session {session_id}") from e

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[SessionState]:
        current_session = await self.get_session(session_id)
        if not current_session:
            return None
        try:
            updated_session = current_session.model_copy(update=updates)
            await self.save_session(updated_session)
            return updated_session
        except ValueError as e:
            logger.error(f"Invalid update data for session {session_id}: {e}", exc_info=True)
            raise ValueError(f"Invalid update data for session {session_id}") from e

    async def delete_session(self, session_id: str) -> bool:
        if not self._client:
            raise RuntimeError("Redis client not initialized.")
        redis_key = self._get_redis_key(session_id)
        try:
            result = await self._client.delete(redis_key)
            return result > 0
        except RedisError as e:
            logger.error(f"Failed to delete session {session_id}: {e}", exc_info=True)
            raise RuntimeError(f"Redis delete operation failed for session {session_id}") from e

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
