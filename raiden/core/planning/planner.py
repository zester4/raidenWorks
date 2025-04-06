import jsonimport logging




































# ...existing code...        return prompt_parts            prompt_parts.append(create_image_part(screenshot_base64))        if screenshot_base64:        prompt_parts = [Part.from_text(formatted_prompt_text)]        )            vision_context_section=vision_section  # <-- Added            dom_context_section=dom_section,       # <-- Added            user_prompt=user_prompt,            plan_schema=json.dumps(PLAN_JSON_SCHEMA_DESCRIPTION, indent=2),        formatted_prompt_text = PLANNING_SYSTEM_PROMPT_TEMPLATE.format(        # Format the main system prompt template            # ... (add image part) ...            vision_section = VISION_CONTEXT_SECTION_TEMPLATE        if screenshot_base64:        vision_section = ""  # Initialized but not passed to .format()            dom_section = DOM_CONTEXT_SECTION_TEMPLATE.format(dom_snapshot=simplified_dom)            # ... (DOM simplification logic) ...        if dom_snapshot:        dom_section = ""  # Initialized but not passed to .format()        # Prepare context sections    ) -> List[Part]:        self, user_prompt: str, dom_snapshot: Optional[str] = None, screenshot_base64: Optional[str] = None    def _construct_prompt(    # ...existing code...class Planner:# ...existing code...from raiden.core.planning.llm_client import Part, create_image_partfrom typing import Optional, Listimport json
from typing import Optional, List, Dict, Any
from pydantic import ValidationError
from vertexai.generative_models import Part
from raiden.core.models.internal_models import Plan, ActionStep
from .llm_client import LLMClient, create_image_part

logger = logging.getLogger(__name__)

PLAN_JSON_SCHEMA_DESCRIPTION = ActionStep.model_json_schema()

PLANNING_SYSTEM_PROMPT_TEMPLATE = """
You are Raiden, an expert autonomous web automation agent. Your sole task is to create a step-by-step plan as a JSON array to fulfill the user's request using browser actions.

**Input Provided:**
1.  User Request: The high-level task.
2.  Current DOM Snapshot (Optional, Simplified HTML).
3.  Current Screenshot (Optional, Image data).

**Your Task:**
Generate a plan consisting of a JSON array of action objects. Each object in the array represents ONE browser action step.

**CRITICAL OUTPUT REQUIREMENTS:**
*   Your *entire* response MUST be a single, valid JSON array string, starting with `[` and ending with `]`.
*   Each object within the array MUST strictly conform to this JSON schema for an ActionStep:
    ```json
    {{plan_schema}}
    ```
*   **Field Names MUST Match Exactly:** Use `step_id`, `action_type`, `selector`, `target_url`, `text_to_type`, `scroll_direction`, `extraction_variable`, `wait_timeout_ms`, `prompt_to_user`, `human_readable_reasoning`, `screenshot_filename`, etc., precisely as defined in the schema. **DO NOT use different names like 'action', 'reason', 'url', 'text', 'variable'.**
*   **`step_id` is MANDATORY:** Start at 0 and increment sequentially for each step.
*   **`action_type` is MANDATORY:** Choose ONE from the allowed types below.
*   Include `human_readable_reasoning` (briefly explaining the step's purpose) for each step.
*   Ensure all other required fields for the chosen `action_type` (like `selector` for click/type, `target_url` for navigate) are present.
*   Do NOT include any text, explanations, apologies, or markdown formatting outside the main JSON array structure.

**Allowed Action Types (`action_type` field):**
*   `navigate`: Go to a URL (`target_url` required).
*   `click`: Click an element (`selector` required).
*   `type`: Type text (`selector` and `text_to_type` required).
*   `scroll`: Scroll page/element (`scroll_direction` like 'up', 'down', 'element' required. If 'element', `selector` also required).
*   `extract_text`: Extract text (`selector` and `extraction_variable` required).
*   `wait_for_selector`: Wait for element (`selector` required, `state` optional - defaults to 'visible').
*   `wait_for_load_state`: Wait for page state (`state` optional - defaults to 'load').
*   `screenshot`: Take screenshot (`screenshot_filename` optional).
*   `ask_user`: Pause and ask (`prompt_to_user` required). Use ONLY when essential.

**Context:**
*   User Request: "{{user_prompt}}"
{dom_context_section}
{vision_context_section}

Generate the plan as a valid JSON array string adhering strictly to all requirements. JSON ONLY.
"""

class PlanningError(Exception):
    pass

class Planner:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def _construct_prompt(
        self, user_prompt: str, dom_snapshot: Optional[str] = None, screenshot_base64: Optional[str] = None
    ) -> List[Part]:
        prompt_parts = []
        formatted_prompt = PLANNING_SYSTEM_PROMPT_TEMPLATE.format(
            user_prompt=user_prompt,
            dom_snapshot=dom_snapshot or "None",
            plan_schema=json.dumps(PLAN_JSON_SCHEMA_DESCRIPTION, indent=2),
        )
        prompt_parts.append(Part.from_text(formatted_prompt))
        if screenshot_base64:
            prompt_parts.append(create_image_part(screenshot_base64))
        return prompt_parts

    async def generate_plan(
        self, user_prompt: str, dom_snapshot: Optional[str] = None, screenshot_base64: Optional[str] = None
    ) -> Plan:
        prompt_parts = self._construct_prompt(user_prompt, dom_snapshot, screenshot_base64)
        raw_plan_json, error_message = await self.llm_client.generate_content_async(prompt_parts, request_json_output=True)
        if error_message:
            raise PlanningError(f"LLM failed to generate plan: {error_message}")
        try:
            plan_data = json.loads(raw_plan_json)
            return Plan.model_validate({"steps": plan_data})
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse or validate plan: {e}")
            raise PlanningError(f"Plan parsing/validation failed: {e}")
