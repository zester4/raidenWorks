from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from raiden.core.constants import SessionStatus

class Session(BaseModel):
    id: str
    status: str
    created_at: str

class SessionCreateRequest(BaseModel):
    """Request body for creating a new session."""
    prompt: str = Field(..., min_length=1, description="User's natural language instruction.")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Optional session-specific configurations.")

class SessionCreateResponse(BaseModel):
    """Response body after successfully initiating session creation."""
    session_id: str = Field(..., description="Unique identifier for the newly created session.")
    status: SessionStatus = Field(..., description="Initial status (e.g., INITIALIZING, PLANNING).")
    message: str = Field(default="Session creation initiated.", description="Informational message.")

class SessionStatusResponse(BaseModel):
    """Response body containing the current status and details of a session."""
    session_id: str
    status: SessionStatus
    user_prompt: str
    plan: Optional[Dict[str, Any]] = None
    current_step_index: int = 0
    session_variables: Dict[str, Any] = Field(default_factory=dict)
    last_error: Optional[str] = None
    ask_user_prompt: Optional[str] = None
    final_result: Optional[Any] = None
    created_at: datetime
    updated_at: datetime
    session_config: Optional[Dict[str, Any]] = None

class SessionUpdateRequest(BaseModel):
    """Request body for providing user response to a paused session."""
    user_response: str = Field(..., min_length=1, description="User's response to the agent's question.")

class SessionUpdateResponse(BaseModel):
    """Response body after successfully submitting user input or triggering resume."""
    session_id: str
    status: SessionStatus
    message: str

class ErrorDetail(BaseModel):
    """Standard structure for error responses."""
    detail: str = Field(..., description="Description of the error.")
    session_id: Optional[str] = Field(default=None)
    step_id: Optional[int] = Field(default=None)

class SessionListResponse(BaseModel):
    """Response body for listing sessions."""
    sessions: List[Dict[str, Any]]
    total: int
