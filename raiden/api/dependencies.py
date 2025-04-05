# raiden/api/dependencies.py
"""
Sets up dependency injection for core Raiden services using FastAPI's Depends.
Initializes service instances upon application startup.
"""

import logging
from typing import Optional, Annotated, TYPE_CHECKING

from fastapi import Depends, HTTPException, status

# Import core components (resolve imports carefully)
from raiden.core.session.manager import SessionManager
from raiden.core.session.storage.redis_storage import RedisSessionStorage
from raiden.core.session.storage.postgres_storage import PostgresSessionStorage
from raiden.core.planning.llm_client import LLMClient
from raiden.core.planning.planner import Planner
from raiden.core.orchestration.orchestrator import TaskOrchestrator
# Import exceptions for error mapping
from raiden.core.orchestration.orchestrator import OrchestrationError

# Use TYPE_CHECKING for BCL to avoid runtime circular import if driver imports things from api/deps
if TYPE_CHECKING:
    from raiden.browser.driver import BrowserControlLayer


logger = logging.getLogger(__name__)

# --- Global instances (initialized on startup) ---
# These act as singletons for the application lifetime
_redis_storage: Optional[RedisSessionStorage] = None
_postgres_storage: Optional[PostgresSessionStorage] = None
_session_manager: Optional[SessionManager] = None
_llm_client: Optional[LLMClient] = None
_planner: Optional[Planner] = None
_bcl: Optional['BrowserControlLayer'] = None # Use string hint or TYPE_CHECKING
_orchestrator: Optional[TaskOrchestrator] = None

async def initialize_dependencies():
    """Initializes all core service instances. Called on app startup."""
    global _redis_storage, _postgres_storage, _session_manager, _llm_client, _planner, _bcl, _orchestrator
    # Avoid re-initialization if already done (e.g., during reload)
    if _session_manager:
         logger.warning("Dependencies seem to be already initialized. Skipping re-initialization.")
         return

    logger.info("Initializing core application dependencies...")

    try:
        # Storage Layers
        _redis_storage = RedisSessionStorage()
        _postgres_storage = PostgresSessionStorage()

        # Session Manager (depends on storage)
        _session_manager = SessionManager(cache_storage=_redis_storage, persistent_storage=_postgres_storage)
        await _session_manager.initialize_stores() # Important: Initialize underlying connections

        # LLM Client and Planner
        _llm_client = LLMClient() # Uses config from settings
        _planner = Planner(llm_client=_llm_client)

        # Browser Control Layer - Import here to avoid top-level circularity if BCL imports deps
        from raiden.browser.driver import BrowserControlLayer
        _bcl = BrowserControlLayer()
        await _bcl.initialize() # Important: Start Playwright

        # Task Orchestrator (depends on SessionManager and BCL)
        _orchestrator = TaskOrchestrator(session_manager=_session_manager, browser_controller=_bcl)

        logger.info("Core application dependencies initialized successfully.")
    except Exception as e:
         logger.critical(f"CRITICAL ERROR during dependency initialization: {e}", exc_info=True)
         # Depending on policy, might want to exit or prevent app start
         raise RuntimeError("Failed to initialize critical application dependencies") from e


async def shutdown_dependencies():
    """Gracefully shuts down dependencies. Called on app shutdown."""
    global _session_manager, _bcl, _redis_storage, _postgres_storage, _llm_client, _planner, _orchestrator
    logger.info("Shutting down core application dependencies...")
    if _bcl:
         await _bcl.shutdown()
         _bcl = None
    if _session_manager:
         await _session_manager.close_stores()
         _session_manager = None
    # Reset other globals too for cleaner shutdown/restart cycles
    _redis_storage = None
    _postgres_storage = None
    _llm_client = None
    _planner = None
    _orchestrator = None
    logger.info("Core application dependencies shut down complete.")


# --- Dependency Provider Functions ---
# These are used by FastAPI's Depends() in endpoint signatures

def get_session_manager() -> SessionManager:
    if _session_manager is None:
         # This might happen if accessed before lifespan startup completes
         logger.error("SessionManager accessed before initialization.")
         raise RuntimeError("SessionManager not initialized.")
    return _session_manager

def get_planner() -> Planner:
     if _planner is None:
          logger.error("Planner accessed before initialization.")
          raise RuntimeError("Planner not initialized.")
     return _planner

def get_orchestrator() -> TaskOrchestrator:
    if _orchestrator is None:
         logger.error("TaskOrchestrator accessed before initialization.")
         raise RuntimeError("TaskOrchestrator not initialized.")
    return _orchestrator

def get_bcl() -> 'BrowserControlLayer': # Use string hint or TYPE_CHECKING
     if _bcl is None:
          logger.error("BrowserControlLayer accessed before initialization.")
          raise RuntimeError("BrowserControlLayer not initialized.")
     return _bcl

# --- Type hints for dependency injection ---
# Improves readability in endpoint signatures
SessionManagerDep = Annotated[SessionManager, Depends(get_session_manager)]
PlannerDep = Annotated[Planner, Depends(get_planner)]
OrchestratorDep = Annotated[TaskOrchestrator, Depends(get_orchestrator)]
BCLDep = Annotated['BrowserControlLayer', Depends(get_bcl)] # Use string hint

# --- Utility for session existence check ---
async def get_session_or_404(session_id: str, session_manager: SessionManagerDep) -> None:
    """Dependency that checks if a session exists, raising 404 if not."""
    try:
        session = await session_manager.get_session(session_id) # Check active cache
        if not session:
            logger.warning(f"Session ID '{session_id}' not found in active cache.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session with ID '{session_id}' not found.",
            )
    except RuntimeError as e: # Catch errors from storage access itself
        logger.error(f"Error accessing storage while checking session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage error checking session {session_id}."
        )
    # If session exists, this dependency doesn't return anything, just validates.

# Ensure the dependency function itself uses the Annotated type hint
SessionExistsDep = Annotated[None, Depends(get_session_or_404)]