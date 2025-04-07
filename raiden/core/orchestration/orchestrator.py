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
        """Executes a single action step and provides detailed logging."""
        reason = getattr(step, 'human_readable_reasoning', None) or 'N/A'
        logger.info(f"""
==================================================
Executing Step {step.step_id + 1}/{len(session_state.plan.steps)}
Action: {step.action_type}
Purpose: {reason}
==================================================
""")

        action_method_name = f"execute_{step.action_type}"
        if not hasattr(self.bcl, action_method_name):
            error_msg = f"Unsupported action type: {step.action_type}"
            logger.error(f"Session {session_id}: {error_msg}")
            return ACTION_STATUS_ERROR, {"error": error_msg}

        try:
            # Pass the full step object and context to BCL
            action_status, result_data = await getattr(self.bcl, action_method_name)(
                session_id=session_id,
                step=step,
                session_variables=session_state.session_variables,
                session_config=session_state.session_config,
            )

            # Log the result based on status
            if action_status == ACTION_STATUS_CONTINUE:
                logger.info(f"✓ Step completed successfully")
                if "extracted_text" in result_data:
                    logger.info(f"  └─ Extracted: {result_data['extracted_text']}")
            elif action_status == ACTION_STATUS_ASK_USER:
                logger.info(f"? Waiting for user input: {result_data.get('ask_user_prompt')}")
            elif action_status == ACTION_STATUS_DONE:
                logger.info(f"✓ Task completed: {result_data.get('final_result')}")
            elif action_status == ACTION_STATUS_ERROR:
                logger.error(f"✗ Step failed: {result_data.get('error')}")

            return action_status, result_data or {}

        except Exception as e:
            error_msg = f"Failed to execute {step.action_type}: {str(e)}"
            logger.error(f"Session {session_id}: {error_msg}", exc_info=True)
            return ACTION_STATUS_ERROR, {"error": error_msg}

    async def run_session(self, session_id: str, user_response: Optional[str] = None) -> SessionState:
        """Executes a session with detailed progress logging."""
        logger.info(f"""
==================================================
Starting Session: {session_id}
==================================================
""")
        session_state = await self.session_manager.get_session(session_id)
        if not session_state:
            raise OrchestrationError(f"Session {session_id} not found.")

        if session_state.status not in [SESSION_STATUS_RUNNING, SESSION_STATUS_PAUSED_ASK_USER]:
            logger.warning(f"Session {session_id} is in non-runnable state: {session_state.status}.")
            return session_state

        if session_state.status == SESSION_STATUS_PAUSED_ASK_USER and user_response:
            logger.info(f"Session {session_id}: Resuming with user response")
            session_state.session_variables["last_user_response"] = user_response
            session_state = await self.session_manager.update_session(session_id, {"status": SESSION_STATUS_RUNNING})

        steps = session_state.plan.steps
        total_steps = len(steps)
        step_count = 0
        
        logger.info(f"Session {session_id}: Starting execution of {total_steps} steps")

        while session_state.current_step_index < len(steps) and step_count < MAX_PLAN_STEPS:
            step = steps[session_state.current_step_index]
            logger.info(f"Session {session_id}: Executing step {step.step_id + 1}/{total_steps} - {step.action_type}")
            if step.human_readable_reasoning:
                logger.info(f"Session {session_id}: Step purpose: {step.human_readable_reasoning}")
                
            action_status, result_data = await self.execute_step(session_id, session_state, step)

            updates: Dict[str, Any] = {}
            should_break = False

            if action_status == ACTION_STATUS_CONTINUE:
                logger.debug(f"Session {session_id}: Step completed successfully")
                updates["current_step_index"] = session_state.current_step_index + 1
                if step.extraction_variable and "extracted_text" in result_data:
                    extracted = result_data["extracted_text"]
                    logger.info(f"Session {session_id}: Extracted '{extracted}' into variable '{step.extraction_variable}'")
                    session_state.session_variables[step.extraction_variable] = extracted
                    updates["session_variables"] = session_state.session_variables

            elif action_status == ACTION_STATUS_ASK_USER:
                prompt = result_data.get("ask_user_prompt", "Agent needs input.")
                logger.info(f"Session {session_id}: Pausing for user input: {prompt}")
                updates["status"] = SESSION_STATUS_PAUSED_ASK_USER
                updates["ask_user_prompt"] = prompt
                should_break = True

            elif action_status == ACTION_STATUS_DONE:
                result = result_data.get("final_result", "Task completed successfully.")
                logger.info(f"Session {session_id}: Task completed - {result}")
                updates["status"] = SESSION_STATUS_COMPLETED
                updates["final_result"] = result
                should_break = True

            elif action_status == ACTION_STATUS_ERROR:
                error = result_data.get("error", "Unknown error.")
                logger.error(f"Session {session_id}: Step failed - {error}")
                updates["status"] = SESSION_STATUS_FAILED
                updates["last_error"] = error
                should_break = True

            if updates:
                session_state = await self.session_manager.update_session(session_id, updates)

            if should_break:
                break

            step_count += 1

        if step_count >= MAX_PLAN_STEPS:
            logger.error(f"Session {session_id}: Exceeded maximum number of steps ({MAX_PLAN_STEPS})")
            await self.session_manager.update_session(session_id, {"status": SESSION_STATUS_FAILED, "last_error": "Exceeded maximum steps."})

        final_state = await self.session_manager.get_session(session_id)
        if not final_state:
            raise OrchestrationError(f"Session {session_id} lost after execution.")
            
        logger.info(f"Session {session_id}: Final status: {final_state.status}")
        if final_state.status == SESSION_STATUS_COMPLETED:
            logger.info(f"Session {session_id}: Final result: {final_state.final_result}")
        elif final_state.status == SESSION_STATUS_FAILED:
            logger.error(f"Session {session_id}: Final error: {final_state.last_error}")
            
        return final_state
