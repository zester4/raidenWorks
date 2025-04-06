# Initialize the models module

from .session_models import (
    # Request Models
    SessionConfigRequest,  # <-- Added
    SessionCreateRequest,
    SessionUpdateRequest,
    # Response Models
    SessionCreateResponse,
    SessionStatusResponse,
    SessionUpdateResponse,
    ErrorDetail,
    SessionListResponse,  # If adding listing endpoint later
)

__all__ = [
    # Request Models
    "SessionConfigRequest",  # <-- Added
    "SessionCreateRequest",
    "SessionUpdateRequest",
    # Response Models
    "SessionCreateResponse",
    "SessionStatusResponse",
    "SessionUpdateResponse",
    "ErrorDetail",
    "SessionListResponse",
]