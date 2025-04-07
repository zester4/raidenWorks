import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import ValidationError
from vertexai.generative_models import Part
from raiden.core.models.internal_models import Plan, ActionStep
from .llm_client import LLMClient, create_image_part

logger = logging.getLogger(__name__)

PLAN_JSON_SCHEMA_DESCRIPTION = ActionStep.model_json_schema()

PLANNING_SYSTEM_PROMPT_TEMPLATE = """
You are Raiden, an expert autonomous web automation agent. Your task is to create a precise and literal step-by-step plan that EXACTLY matches the user's request.

**CRITICAL RULES:**
1. You MUST follow the user's instructions EXACTLY as given. Do not add, modify, or interpret beyond what is explicitly requested.
2. If the user asks to go to google.com, use EXACTLY "https://www.google.com" - never maps.google.com or any other subdomain.
3. Never add steps that weren't specifically requested by the user.
4. Never change the user's intended website or search terms.
5. For Google search:
   - Search box selector: "textarea[name='q']"
   - Search button selector: "button[type='submit']" or "[name='btnK']"

**CRITICAL RULES FOR GOOGLE SEARCH:**
1. If the user asks to search Google:
   - Use EXACTLY "https://www.google.com"
   - Search box selector: "textarea[name='q']"
   - Submit search by pressing Enter after typing (don't try to click the search button)
   - For search results: wait for "#search" to appear
2. NEVER modify the search terms - use EXACTLY what the user specified
3. NEVER add extra steps not requested by the user

**EXAMPLE Google Search Plan:**
For "search Google for OpenAI":
[
  {
    "step_id": 0,
    "action_type": "navigate",
    "target_url": "https://www.google.com",
    "human_readable_reasoning": "Navigate to Google homepage"
  },
  {
    "step_id": 1,
    "action_type": "type",
    "selector": "textarea[name='q']",
    "text_to_type": "OpenAI",
    "human_readable_reasoning": "Type the exact search query"
  },
  {
    "step_id": 2,
    "action_type": "wait_for_selector",
    "selector": "#search",
    "human_readable_reasoning": "Wait for search results to load"
  }
]

**INPUT:**
User Request: A specific task to automate in the browser.
{dom_context_section}
{vision_context_section}

**OUTPUT REQUIREMENTS:**
Your response must be a single, valid JSON array containing action steps that:
1. Follow the user's request LITERALLY
2. Include ONLY steps specifically needed for the requested task
3. Use correct selectors for the target website
4. Conform to this schema:
```json
{{plan_schema}}
```

**STEP REQUIREMENTS:**
- Each step needs:
  * `step_id`: Sequential number starting from 0
  * `action_type`: One of the allowed types
  * Required fields for that action type
  * `human_readable_reasoning`: Brief explanation
- Return ONLY the JSON array, no other text

**ALLOWED ACTION TYPES:**
- `navigate`: Go to URL (`target_url` required)
- `click`: Click element (`selector` required)
- `type`: Type text (`selector` and `text_to_type` required)
- `scroll`: Scroll page (`scroll_direction` required)
- `extract_text`: Extract text (`selector` and `extraction_variable` required)
- `wait_for_selector`: Wait for element (`selector` required)
- `wait_for_load_state`: Wait for page state
- `screenshot`: Take screenshot (`screenshot_filename` optional)
- `ask_user`: Pause for input (`prompt_to_user` required)

**USER REQUEST:**
"{{user_prompt}}"

"""

class PlanningError(Exception):
    pass

class Planner:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def _construct_prompt(
        self, user_prompt: str, dom_snapshot: Optional[str] = None, screenshot_base64: Optional[str] = None
    ) -> List[dict]:
        # Prepare context sections
        dom_section = ""
        if dom_snapshot:
            dom_section = f"**DOM Snapshot:**\n{dom_snapshot}"

        vision_section = ""
        if screenshot_base64:
            vision_section = "**Screenshot Provided**"

        # Get the schema and escape curly braces
        schema_json = json.dumps(PLAN_JSON_SCHEMA_DESCRIPTION, indent=2)
        
        # Format the main system prompt template
        formatted_prompt_text = f'''
You are Raiden, an expert autonomous web automation agent. Your task is to create a precise and literal step-by-step plan that EXACTLY matches the user's request.

**CRITICAL RULES:**
1. You MUST follow the user's instructions EXACTLY as given. Do not add, modify, or interpret beyond what is explicitly requested.
2. If the user asks to go to google.com, use EXACTLY "https://www.google.com" - never maps.google.com or any other subdomain.
3. Never add steps that weren't specifically requested by the user.
4. Never change the user's intended website or search terms.

**CRITICAL RULES FOR GOOGLE SEARCH:**
1. If the user asks to search Google:
   - Use EXACTLY "https://www.google.com"
   - Search box selector: "textarea[name='q']"
   - Submit search by pressing Enter after typing
   - After search submission, wait for "div.g" (search result container) to appear
2. NEVER modify the search terms - use EXACTLY what the user specified
3. NEVER add extra steps not requested by the user

**EXAMPLE Google Search Plan:**
[
  {{
    "step_id": 0,
    "action_type": "navigate",
    "target_url": "https://www.google.com",
    "human_readable_reasoning": "Navigate to Google homepage"
  }},
  {{
    "step_id": 1,
    "action_type": "type",
    "selector": "textarea[name='q']",
    "text_to_type": "OpenAI",
    "human_readable_reasoning": "Type the exact search query"
  }},
  {{
    "step_id": 2,
    "action_type": "wait_for_selector",
    "selector": "div.g",
    "human_readable_reasoning": "Wait for search results to load"
  }}
]

**INPUT:**
User Request: {user_prompt}
{dom_section}
{vision_section}

**OUTPUT REQUIREMENTS:**
Your response must be a single, valid JSON array containing action steps that:
1. Follow the user's request LITERALLY
2. Include ONLY steps specifically needed for the requested task
3. Use correct selectors for the target website
4. Conform to this schema:
```json
{schema_json}
```

**STEP REQUIREMENTS:**
- Each step needs:
  * `step_id`: Sequential number starting from 0
  * `action_type`: One of the allowed types
  * Required fields for that action type
  * `human_readable_reasoning`: Brief explanation
- Return ONLY the JSON array, no other text

**ALLOWED ACTION TYPES:**
- `navigate`: Go to URL (`target_url` required)
- `click`: Click element (`selector` required)
- `type`: Type text (`selector` and `text_to_type` required)
- `scroll`: Scroll page (`scroll_direction` required)
- `extract_text`: Extract text (`selector` and `extraction_variable` required)
- `wait_for_selector`: Wait for element (`selector` required)
- `wait_for_load_state`: Wait for page state
- `screenshot`: Take screenshot (`screenshot_filename` optional)
- `ask_user`: Pause for input (`prompt_to_user` required)
'''

        # Create parts in the new format
        prompt_parts = [{"text": formatted_prompt_text}]
        if screenshot_base64:
            prompt_parts.append({"image": screenshot_base64})
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
