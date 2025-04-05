from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from raiden.core.models.internal_models import SessionState

class BaseSessionStorage(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save_session(self, session_state: SessionState) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionState]:
        raise NotImplementedError

    @abstractmethod
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[SessionState]:
        raise NotImplementedError

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
