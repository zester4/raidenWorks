from typing import Literal, Final

# --- Session Statuses ---
SESSION_STATUS_INITIALIZING: Final[Literal["INITIALIZING"]] = "INITIALIZING"
SESSION_STATUS_PLANNING: Final[Literal["PLANNING"]] = "PLANNING"
SESSION_STATUS_RUNNING: Final[Literal["RUNNING"]] = "RUNNING"
SESSION_STATUS_PAUSED_ASK_USER: Final[Literal["PAUSED_ASK_USER"]] = "PAUSED_ASK_USER"
SESSION_STATUS_COMPLETED: Final[Literal["COMPLETED"]] = "COMPLETED"
SESSION_STATUS_FAILED: Final[Literal["FAILED"]] = "FAILED"

SessionStatus = Literal[
    "INITIALIZING",
    "PLANNING",
    "RUNNING",
    "PAUSED_ASK_USER",
    "COMPLETED",
    "FAILED",
]

# --- Action Types ---
ACTION_TYPE_NAVIGATE: Final[Literal["navigate"]] = "navigate"
ACTION_TYPE_CLICK: Final[Literal["click"]] = "click"
ACTION_TYPE_TYPE: Final[Literal["type"]] = "type"
ACTION_TYPE_SCROLL: Final[Literal["scroll"]] = "scroll"
ACTION_TYPE_EXTRACT_TEXT: Final[Literal["extract_text"]] = "extract_text"
ACTION_TYPE_SCREENSHOT: Final[Literal["screenshot"]] = "screenshot"
ACTION_TYPE_WAIT_FOR_SELECTOR: Final[Literal["wait_for_selector"]] = "wait_for_selector"
ACTION_TYPE_WAIT_FOR_LOAD_STATE: Final[Literal["wait_for_load_state"]] = "wait_for_load_state"
ACTION_TYPE_ASK_USER: Final[Literal["ask_user"]] = "ask_user"

ActionType = Literal[
    "navigate",
    "click",
    "type",
    "scroll",
    "extract_text",
    "screenshot",
    "wait_for_selector",
    "wait_for_load_state",
    "ask_user",
]

# --- Action Statuses ---
ACTION_STATUS_CONTINUE: Final[Literal["CONTINUE"]] = "CONTINUE"
ACTION_STATUS_ASK_USER: Final[Literal["ASK_USER"]] = "ASK_USER"
ACTION_STATUS_DONE: Final[Literal["DONE"]] = "DONE"  # Indicates the action completed the whole task
ACTION_STATUS_ERROR: Final[Literal["ERROR"]] = "ERROR"

ActionStatus = Literal[
    "CONTINUE",
    "ASK_USER",
    "DONE",
    "ERROR",
]

# --- Default Timeouts ---
DEFAULT_PLAYWRIGHT_TIMEOUT_MS: Final[int] = 30_000
DEFAULT_SESSION_TIMEOUT_SECONDS: Final[int] = 3600

# --- Other Constants ---
MAX_PLAN_STEPS: Final[int] = 100  # Safety limit for execution loops
