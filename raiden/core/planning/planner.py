import logging
import json
from typing import Optional, List, Dict, Any
from pydantic import ValidationError
from vertexai.generative_models import Part
from raiden.core.models.internal_models import Plan, ActionStep
from .llm_client import LLMClient, create_image_part

logger = logging.getLogger(__name__)

PLAN_JSON_SCHEMA_DESCRIPTION = ActionStep.model_json_schema()

PLANNING_SYSTEM_PROMPT_TEMPLATE = """
You are Raiden, an expert autonomous web automation agent. Your goal is to create a step-by-step plan to fulfill the user's request by interacting with a web browser.

**Input:**
1. User Request: {{user_prompt}}
2. Current DOM Snapshot: {{dom_snapshot}}
3. Current Screenshot: (if provided)

**Output:**
A JSON array of action steps conforming to this schema:
{{plan_schema}}
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
