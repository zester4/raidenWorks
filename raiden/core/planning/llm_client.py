import logging
import base64
from typing import Optional, List, Tuple
from google import genai
from google.genai import types
from raiden.core.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.gemini_model_name
        try:
            # Configure the Gemini API with direct API key
            self.client = genai.Client(
                api_key=settings.gemini_api_key.get_secret_value(),
            )
            logger.info(f"LLMClient initialized with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize Gemini client: {e}") from e

    async def generate_content_async(
        self, prompt_parts: List[dict], request_json_output: bool = True
    ) -> Tuple[Optional[str], Optional[str]]:
        try:
            # Convert our prompt parts to Gemini format
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=part["text"]) if "text" in part
                        else types.Part.from_data(data=base64.b64decode(part["image"]), mime_type="image/jpeg")
                        for part in prompt_parts if isinstance(part, dict)
                    ]
                )
            ]

            # Set response type based on request
            generate_content_config = types.GenerateContentConfig(
                response_mime_type="application/json" if request_json_output else "text/plain",
                temperature=0.2,
                max_output_tokens=8192,
            )

            # Get the full response text
            response_text = ""
            for chunk in self.client.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=generate_content_config,
            ):
                if chunk.text:
                    response_text += chunk.text

            if not response_text:
                return None, "No response generated."
            
            return response_text, None

        except ValueError as ve:
            logger.error(f"Value error during LLM content generation: {ve}", exc_info=True)
            return None, f"Invalid request data: {ve}"
        except Exception as e:
            logger.error(f"LLM content generation failed: {e}", exc_info=True)
            return None, f"LLM API call failed: {e}"

def create_image_part(image_data_base64: str, mime_type: str = "image/jpeg") -> dict:
    return {
        "image": image_data_base64
    }
