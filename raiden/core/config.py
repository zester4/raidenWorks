from pydantic import Field, PostgresDsn, RedisDsn, ValidationInfo, SecretStr, model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
from typing import Union, List, Optional
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Centralized configuration management for the Raiden application.
    """
    # Add development mode flag
    is_development_mode: bool = Field(
        default=False, 
        validation_alias="DEVELOPMENT_MODE",
        description="Enable development mode (disables certain security checks)"
    )

    # --- Application Core Settings ---
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    allowed_origins: list[str] = Field(default=["*"], validation_alias="ALLOWED_ORIGINS")

    # --- Gemini API Configuration ---
    gemini_api_key: SecretStr = Field(..., validation_alias="GEMINI_API_KEY")
    gemini_project_id: str = Field(validation_alias="GEMINI_PROJECT_ID")
    gemini_location: str = Field(validation_alias="GEMINI_LOCATION")
    gemini_model_name: str = Field(default="gemini-2.5-pro-preview-03-25", validation_alias="GEMINI_MODEL_NAME")

    # --- Redis Configuration ---
    redis_dsn_override: Optional[RedisDsn] = Field(default=None, validation_alias="REDIS_DSN")
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, validation_alias="REDIS_PASSWORD")
    computed_redis_dsn: Optional[RedisDsn] = None  # Computed DSN

    @model_validator(mode='after')
    def compute_final_redis_dsn(self) -> 'Settings':
        """Compute the final Redis DSN after all fields are loaded."""
        if self.redis_dsn_override:
            logger.info(f"Using provided Redis DSN override: {self.redis_dsn_override}")
            self.computed_redis_dsn = self.redis_dsn_override
        else:
            scheme = "redis"
            password = f":{self.redis_password}" if self.redis_password else ""
            assembled_dsn = f"{scheme}://{password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
            logger.debug(f"Assembled Redis DSN: {assembled_dsn.replace(self.redis_password or '', '******')}")
            try:
                self.computed_redis_dsn = RedisDsn(assembled_dsn)
            except Exception as e:
                logger.error(f"Failed to validate assembled Redis DSN '{assembled_dsn}': {e}")
                raise ValueError(f"Invalid Redis configuration: {e}") from e

        if not self.computed_redis_dsn:
            raise ValueError("Failed to determine a valid Redis DSN.")
        return self

    @model_validator(mode='after')
    def validate_security_settings(self) -> 'Settings':
        """Validate security-critical settings."""
        if "*" in self.allowed_origins and not self.is_development_mode:
            logger.warning("Wildcard CORS origin (*) detected in production mode")
            # In production, we'll just warn rather than error, as the setting might be intentional
            
        if not self.postgres_dsn.scheme.endswith("+asyncpg"):
            raise ValueError("Must use asyncpg driver for PostgreSQL")
            
        if not str(self.computed_redis_dsn).startswith("rediss://"):
            logger.warning("Redis connection is not using SSL (rediss://)")
            
        return self

    # --- PostgreSQL Configuration ---
    postgres_dsn: PostgresDsn = Field(..., validation_alias="POSTGRES_DSN")

    # --- Playwright / Browser Settings ---
    browser_default_headless: bool = Field(default=True, validation_alias="BROWSER_DEFAULT_HEADLESS")
    browser_default_record_video: bool = Field(default=False, validation_alias="BROWSER_DEFAULT_RECORD_VIDEO")
    browser_video_path: str = Field(default="/app/recordings/videos", validation_alias="BROWSER_VIDEO_PATH")
    browser_trace_path: str = Field(default="/app/recordings/traces", validation_alias="BROWSER_TRACE_PATH")
    browser_default_timeout_ms: int = Field(default=30000, validation_alias="BROWSER_DEFAULT_TIMEOUT_MS")

    # --- Model Configuration ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- CORS Validator ---
    @field_validator("allowed_origins", mode='before')
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, list):
            # If it's already a list (e.g., from default value or pre-parsed by pydantic-settings), use it directly
            logger.debug(f"ALLOWED_ORIGINS received as list: {v}")
            return v
        elif isinstance(v, str):
            # If it's a string from the environment variable
            v_stripped = v.strip()
            logger.debug(f"Processing ALLOWED_ORIGINS string: '{v_stripped}'")
            if v_stripped == "*":
                logger.debug("ALLOWED_ORIGINS interpreted as wildcard '*'.")
                return ["*"]
            elif v_stripped.startswith("[") and v_stripped.endswith("]"):
                # Attempt to parse as JSON array string
                try:
                    parsed_list = json.loads(v_stripped)
                    if isinstance(parsed_list, list):
                        logger.debug(f"ALLOWED_ORIGINS parsed from JSON string: {parsed_list}")
                        return parsed_list
                    else:
                        logger.error(f"Parsed JSON for ALLOWED_ORIGINS is not a list: {parsed_list}")
                        raise ValueError("Parsed JSON for ALLOWED_ORIGINS is not a list.")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON format for ALLOWED_ORIGINS string '{v_stripped}': {e}")
                    raise ValueError("Invalid JSON format for ALLOWED_ORIGINS string") from e
            else:
                # Assume comma-separated if not wildcard or JSON array
                origins = [origin.strip() for origin in v_stripped.split(",") if origin.strip()]
                logger.debug(f"ALLOWED_ORIGINS parsed from comma-separated string: {origins}")
                return origins
        # If it's neither a list nor a string that we could parse
        logger.error(f"Invalid type or format for ALLOWED_ORIGINS: Got {type(v).__name__}")
        raise TypeError(f"Invalid type for ALLOWED_ORIGINS: Expected a list, '*', JSON array string, or comma-separated string, but got {type(v).__name__}")

# --- Initialization and Export ---
try:
    settings = Settings()
except Exception as e:
    logging.exception(f"CRITICAL: Failed to load application settings: {e}")
    raise ValueError(f"Critical configuration error: {e}") from e
