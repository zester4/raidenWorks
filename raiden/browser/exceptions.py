class BrowserError(Exception):
    """Base class for all browser control related errors."""
    def __init__(self, message: str, session_id: str = "N/A", step_id: int = -1):
        self.session_id = session_id
        self.step_id = step_id
        super().__init__(f"Session {session_id} | Step {step_id}: {message}")

class InitializationError(BrowserError):
    """Error during Playwright or browser initialization."""
    pass

class SessionManagementError(BrowserError):
    """Error managing browser sessions/contexts."""
    pass

class NavigationError(BrowserError):
    """Error occurred during a page navigation action."""
    pass

class ElementNotFoundError(BrowserError):
    """Failed to find a specified element on the page."""
    pass

class InvalidSelectorError(BrowserError):
    """The provided selector (CSS/XPath) is invalid."""
    pass

class ActionTimeoutError(BrowserError):
    """A browser action timed out before completion."""
    pass

class ActionExecutionError(BrowserError):
    """Generic error during the execution of a browser action."""
    pass

class VisionIntegrationError(BrowserError):
    """Error related to vision-based element interaction."""
    pass
