import logging
import asyncio
from typing import Callable, Any, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)

class RetryHandler:
    """Handles retries for browser actions with exponential backoff."""
    
    def __init__(self, max_retries: int = 5, initial_delay: float = 1.0, max_delay: float = 15.0, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self._retry_counts: Dict[str, int] = {}

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff."""
        delay = min(self.initial_delay * (self.backoff_factor ** (attempt - 1)), self.max_delay)
        return delay

    async def execute_with_retry(self, operation_name: str, operation: Callable[..., Any], **kwargs) -> Any:
        """Execute an operation with retry logic.
        
        Args:
            operation_name: Name of the operation for logging
            operation: Async callable to execute
            **kwargs: Additional arguments to pass to the operation
        
        Returns:
            The result of the successful operation
        
        Raises:
            The last exception encountered after all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"Attempt {attempt}/{self.max_retries} for operation: {operation_name}")
                return await operation(**kwargs)
                
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt} failed for {operation_name}. "
                        f"Retrying in {delay:.1f}s... Error: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {self.max_retries} attempts failed for {operation_name}. "
                        f"Last error: {str(e)}"
                    )
                    
        if last_exception:
            raise last_exception