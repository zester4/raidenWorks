import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Depends
from raiden.api.models import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStatusResponse,
    SessionUpdateRequest,
    SessionUpdateResponse,
    ErrorDetail,
    SessionConfigRequest,  # <-- Add this import
)
from raiden.api.dependencies import (
    SessionManagerDep,
    PlannerDep,
    OrchestratorDep,
    get_session_or_404,
)
from raiden.core.constants import SESSION_STATUS_PAUSED_ASK_USER, SESSION_STATUS_FAILED

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorDetail, "description": "Invalid input data"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorDetail, "description": "Session not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorDetail, "description": "Internal server error"},
    },
)

async def run_planning_and_execution(session_id: str, planner: PlannerDep, orchestrator: OrchestratorDep, manager: SessionManagerDep):
    logger.info(f"Background Task: Starting planning for session {session_id}.")
    try:
        session_state = await manager.get_session(session_id)
        if not session_state:
            logger.error(f"Background Task: Session {session_id} not found.")
            return
        plan = await planner.generate_plan(user_prompt=session_state.user_prompt)
        updates = {"plan": plan, "status": "RUNNING"}
        session_state = await manager.update_session(session_id, updates)
        if session_state:
            await orchestrator.run_session(session_id)
    except Exception as e:
        logger.error(f"Background Task: Error during planning or execution for session {session_id}: {e}", exc_info=True)
        await manager.update_session(session_id, {"status": SESSION_STATUS_FAILED, "last_error": str(e)})

@router.post(
    "/",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new automation session",
    description="Initiates a new Raiden session. The agent will start planning and executing the task based on the provided prompt in the background.",
)
async def create_session(
    request: SessionCreateRequest,
    background_tasks: BackgroundTasks,
    manager: SessionManagerDep,
    planner: PlannerDep,
    orchestrator: OrchestratorDep,
):
    """
    Creates a new Raiden session.

    - Takes a user prompt and optional configuration.
    - Creates the initial session state.
    - Adds a background task to perform planning and start execution.
    - Returns immediately with the session ID and initial status.
    """
    logger.info(f"Received request to create session for prompt: '{request.prompt[:50]}...'")
    try:
        # Extract session config safely
        session_config_dict = {}  # Default to empty dict
        if request.config and isinstance(request.config, SessionConfigRequest):
            # Only call model_dump if it's the expected Pydantic model instance
            session_config_dict = request.config.model_dump(exclude_unset=True, exclude_none=True)
        elif isinstance(request.config, dict):
            # If it's already a dict, use it (filter None values manually if needed)
            logger.warning("Received session config as a raw dictionary instead of Pydantic model. Using as is.")
            session_config_dict = {k: v for k, v in request.config.items() if v is not None}
        elif request.config is not None:
            # Log if it's some other unexpected type
            logger.warning(f"Received unexpected type for session config: {type(request.config)}. Ignoring.")

        # Create session state synchronously first
        initial_session = await manager.create_session(
            user_prompt=request.prompt,
            session_config=session_config_dict  # Pass the prepared dict
        )
        session_id = initial_session.session_id
        logger.info(f"Session {session_id} created with initial status: {initial_session.status}")

        # Add the planning and execution logic to run in the background
        background_tasks.add_task(
            run_planning_and_execution,
            session_id=session_id,
            planner=planner,
            orchestrator=orchestrator,
            session_manager=manager  # Pass manager for status updates within task
        )
        logger.debug(f"Added background task for planning/execution for session {session_id}")

        # Return 202 Accepted with session ID
        return SessionCreateResponse(
            session_id=session_id,
            status=initial_session.status,  # Return the status *before* background task starts planning
            message="Session accepted. Planning and execution started in background."
        )
    except Exception as e:
        # Catch errors during synchronous session creation
        logger.error(f"Failed to initiate session creation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate session: {e}"
        )

@router.get(
    "/{session_id}",
    response_model=SessionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get session status and details",
    description="Retrieves the current status, plan (if available), variables, and results for a specific session.",
    dependencies=[Depends(get_session_or_404)],
)
async def get_session_status(
    session_id: str,
    manager: SessionManagerDep,
):
    session_state = await manager.get_session(session_id)
    if not session_state:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal state inconsistency.")
    return SessionStatusResponse.model_validate(session_state)

@router.post(
    "/{session_id}/respond",
    response_model=SessionUpdateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Provide user input to a paused session",
    description="Submits a user's response when a session's status is PAUSED_ASK_USER, allowing execution to resume.",
    dependencies=[Depends(get_session_or_404)],
)
async def respond_to_session(
    session_id: str,
    request: SessionUpdateRequest,
    background_tasks: BackgroundTasks,
    manager: SessionManagerDep,
    orchestrator: OrchestratorDep,
):
    session = await manager.get_session(session_id)
    if session.status != SESSION_STATUS_PAUSED_ASK_USER:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Session {session_id} is not waiting for user input.")
    background_tasks.add_task(orchestrator.run_session, session_id=session_id, user_response=request.user_response)
    return SessionUpdateResponse(session_id=session_id, status="RUNNING", message="Response received. Resuming execution in background.")

@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Terminate an active session",
    description="Stops an ongoing session and cleans up associated resources (like the browser context). Historical data might be preserved.",
    dependencies=[Depends(get_session_or_404)],
)
async def terminate_session(
    session_id: str,
    manager: SessionManagerDep,
    bcl: OrchestratorDep,
):
    await bcl.close_session_context(session_id)
    await manager.delete_session(session_id)
    return None
