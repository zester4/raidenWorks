import logging
import base64
from typing import Optional, List, Tuple

import vertexai
from vertexai.generative_models import GenerativeModel, Part, Content, GenerationConfig, SafetySetting
from raiden.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    "HARM_CATEGORY_HATE_SPEECH": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    "HARM_CATEGORY_DANGEROUS_CONTENT": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
}

_vertex_initialized = False

def _initialize_vertex_ai():
    global _vertex_initialized
    if not _vertex_initialized:
        try:
            vertexai.init(project=settings.gemini_project_id, location=settings.gemini_location)
            _vertex_initialized = True
            logger.info("Vertex AI SDK initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI SDK: {e}", exc_info=True)
            raise RuntimeError("Vertex AI SDK initialization failed.") from e

class LLMClient:
    def __init__(self, model_name: Optional[str] = None):
        _initialize_vertex_ai()
        self.model_name = model_name or settings.gemini_model_name
        self.generation_config = GenerationConfig(
            temperature=0.2,
            max_output_tokens=8192,
        )
        self.safety_settings = [
            SafetySetting(category=cat, threshold=thresh)
            for cat, thresh in DEFAULT_SAFETY_SETTINGS.items()
        ]
        try:
            self.model = GenerativeModel(self.model_name)
            logger.info(f"LLMClient initialized with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize GenerativeModel for {self.model_name}: {e}", exc_info=True)
            raise RuntimeError(f"Could not load Gemini model {self.model_name}") from e

    async def generate_content_async(
        self, prompt_parts: List[Part], request_json_output: bool = True
    ) -> Tuple[Optional[str], Optional[str]]:
        contents = [Content(role="user", parts=prompt_parts)]
        gen_config = self.generation_config.to_dict()
        gen_config["response_mime_type"] = "application/json" if request_json_output else "text/plain"
        try:
            response = await self.model.generate_content_async(
                contents,
                generation_config=GenerationConfig.from_dict(gen_config),
                safety_settings=self.safety_settings,
                stream=False,
            )
            if not response.candidates:
                return None, "No response generated."
            first_candidate = response.candidates[0]
            if not first_candidate.content or not first_candidate.content.parts:
                return None, "Empty content."
            return first_candidate.content.parts[0].text, None
        except ValueError as ve:
            logger.error(f"Value error during LLM content generation: {ve}", exc_info=True)
            return None, f"Invalid request data: {ve}"
        except Exception as e:
            logger.error(f"LLM content generation failed: {e}", exc_info=True)
            return None, f"LLM API call failed: {e}"

def create_image_part(image_data_base64: str, mime_type: str = "image/png") -> Part:
    return Part.from_data(data=base64.b64decode(image_data_base64), mime_type=mime_type)
