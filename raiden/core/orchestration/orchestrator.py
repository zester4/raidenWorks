import logging
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING
from raiden.core.models.internal_models import SessionState, ActionStep
from raiden.core.constants import (
    SessionStatus,
    ActionStatus,
    SESSION_STATUS_RUNNING,
    SESSION_STATUS_PAUSED_ASK_USER,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_FAILED,
    ACTION_STATUS_CONTINUE,
    ACTION_STATUS_ASK_USER,
    ACTION_STATUS_DONE,
    ACTION_STATUS_ERROR,
    MAX_PLAN_STEPS,
)
from raiden.core.session.manager import SessionManager

if TYPE_CHECKING:
    from raiden.browser.driver import BrowserControlLayer

logger = logging.getLogger(__name__)

class OrchestrationError(Exception):
    pass

class TaskOrchestrator:
    def __init__(self, session_manager: SessionManager, browser_controller: 'BrowserControlLayer'):
        self.session_manager = session_manager
        self.bcl: 'BrowserControlLayer' = browser_controller
        logger.info("TaskOrchestrator initialized.")

    async def execute_step(self, session_id: str, session_state: SessionState, step: ActionStep) -> Tuple[ActionStatus, Optional[Dict[str, Any]]]:
        """
        Executes a single ActionStep using the Browser Control Layer (BCL).

        Args:
            session_id: The ID of the current session.
            session_state: The current state of the session (needed for context like variables).
            step: The ActionStep to execute.

        Returns:
            A tuple containing:
            (action_status: ActionStatus, result_data: Optional[Dict[str, Any]])
            result_data might contain extracted text, error details, or user prompts.
        """
        # Use getattr for safe access to the optional attribute
        reason = getattr(step, 'human_readable_reasoning', None) or 'N/A'
        logger.info(f"Session {session_id}: Executing Step {step.step_id}: {step.action_type} - Reason: {reason}")

        action_method_name = f"execute_{step.action_type}"
        if not hasattr(self.bcl, action_method_name):
            logger.error(f"Session {session_id}: BrowserControlLayer does not support action '{step.action_type}' (method '{action_method_name}' missing).")
            return ACTION_STATUS_ERROR, {"error": f"Unsupported action type: {step.action_type}"}

        action_method = getattr(self.bcl, action_method_name)

        try:
            # Pass the full step object, session variables, and session config to the BCL method
            action_status, result_data = await action_method(
                session_id=session_id,
                step=step,
                session_variables=session_state.session_variables,
                session_config=session_state.session_config,
            )
            logger.debug(f"Session {session_id}: Step {step.step_id} completed with status {action_status}.")
            return action_status, result_data or {}
        except Exception as e:
            logger.error(f"Session {session_id}: Unhandled exception during BCL action execution for step {step.step_id} ({step.action_type}): {e}", exc_info=True)
            return ACTION_STATUS_ERROR, {"error": f"BCL execution failed: {type(e).__name__} - {e}"}

    async def run_session(self, session_id: str, user_response: Optional[str] = None) -> SessionState:
        logger.info(f"Starting execution for session {session_id}.")
        session_state = await self.session_manager.get_session(session_id)
        if not session_state:
            raise OrchestrationError(f"Session {session_id} not found.")

        if session_state.status not in [SESSION_STATUS_RUNNING, SESSION_STATUS_PAUSED_ASK_USER]:
            logger.warning(f"Session {session_id} is in non-runnable state: {session_state.status}.")
            return session_state

        if session_state.status == SESSION_STATUS_PAUSED_ASK_USER and user_response:
            session_state.session_variables["last_user_response"] = user_response
            session_state = await self.session_manager.update_session(session_id, {"status": SESSION_STATUS_RUNNING})

        steps = session_state.plan.steps
        step_count = 0

        while session_state.current_step_index < len(steps) and step_count < MAX_PLAN_STEPS:
            step = steps[session_state.current_step_index]
            action_status, result_data = await self.execute_step(session_id, session_state, step)

            updates: Dict[str, Any] = {}
            should_break = False

            if action_status == ACTION_STATUS_CONTINUE:
                updates["current_step_index"] = session_state.current_step_index + 1
                if step.extraction_variable and "extracted_text" in result_data:
                    session_state.session_variables[step.extraction_variable] = result_data["extracted_text"]
                    updates["session_variables"] = session_state.session_variables

            elif action_status == ACTION_STATUS_ASK_USER:
                updates["status"] = SESSION_STATUS_PAUSED_ASK_USER
                updates["ask_user_prompt"] = result_data.get("ask_user_prompt", "Agent needs input.")
                should_break = True

            elif action_status == ACTION_STATUS_DONE:
                updates["status"] = SESSION_STATUS_COMPLETED
                updates["final_result"] = result_data.get("final_result", "Task completed successfully.")
                should_break = True

            elif action_status == ACTION_STATUS_ERROR:
                updates["status"] = SESSION_STATUS_FAILED
                updates["last_error"] = result_data.get("error", "Unknown error.")
                should_break = True

            if updates:
                session_state = await self.session_manager.update_session(session_id, updates)

            if should_break:
                break

            step_count += 1

        if step_count >= MAX_PLAN_STEPS:
            await self.session_manager.update_session(session_id, {"status": SESSION_STATUS_FAILED, "last_error": "Exceeded maximum steps."})

        final_state = await self.session_manager.get_session(session_id)
        if not final_state:
            raise OrchestrationError(f"Session {session_id} lost after execution.")
        return final_state
