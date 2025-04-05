import logging
import asyncio
from typing import Optional, Dict, Tuple, Any, AsyncContextManager
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from raiden.core.config import settings
from raiden.core.constants import ActionStatus, ACTION_STATUS_CONTINUE, ACTION_STATUS_ERROR
from .exceptions import (
    BrowserError,
    InitializationError,
    SessionManagementError,
    NavigationError,
    ElementNotFoundError,
    ActionTimeoutError,
    ActionExecutionError,
    InvalidSelectorError,
)

logger = logging.getLogger(__name__)

class BrowserControlLayer:
    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._session_contexts: Dict[str, BrowserContext] = {}
        self._lock = asyncio.Lock()
        logger.info("BrowserControlLayer initialized.")

    async def initialize(self) -> None:
        async with self._lock:
            if self._playwright and self._browser:
                logger.warning("BCL already initialized.")
                return
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=settings.browser_default_headless,
                    args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
                )
                logger.info("Playwright initialized and browser launched.")
            except Exception as e:
                logger.error(f"Failed to initialize Playwright: {e}", exc_info=True)
                await self.shutdown()
                raise InitializationError(f"Playwright initialization failed: {e}") from e

    async def shutdown(self) -> None:
        async with self._lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception as e:
                    logger.error(f"Error closing browser: {e}", exc_info=True)
                finally:
                    self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.error(f"Error stopping Playwright: {e}", exc_info=True)
                finally:
                    self._playwright = None
            self._session_contexts.clear()
            logger.info("BrowserControlLayer shutdown complete.")

    @asynccontextmanager
    async def get_page_for_session(self, session_id: str, session_config: Optional[Dict[str, Any]] = None) -> AsyncContextManager[Page]:
        if not self._browser:
            raise RuntimeError("BrowserControlLayer is not initialized.")
        context = self._session_contexts.get(session_id)
        if not context:
            try:
                context = await self._browser.new_context(accept_downloads=True)
                self._session_contexts[session_id] = context
            except PlaywrightError as e:
                raise SessionManagementError(f"Failed to create context: {e}", session_id=session_id) from e
        page = context.pages[0] if context.pages else await context.new_page()
        page.set_default_timeout(settings.browser_default_timeout_ms)
        try:
            yield page
        finally:
            pass

    async def close_session_context(self, session_id: str) -> None:
        async with self._lock:
            context = self._session_contexts.pop(session_id, None)
            if context:
                try:
                    await context.close()
                except PlaywrightError as e:
                    logger.error(f"Error closing context for session {session_id}: {e}", exc_info=True)

    async def execute_navigate(self, session_id: str, target_url: str, **kwargs) -> Tuple[ActionStatus, Dict[str, Any]]:
        try:
            async with self.get_page_for_session(session_id) as page:
                response = await page.goto(target_url, wait_until="domcontentloaded")
                status_code = response.status if response else None
                return ACTION_STATUS_CONTINUE, {"final_url": page.url, "status_code": status_code}
        except PlaywrightTimeoutError as e:
            raise ActionTimeoutError(f"Navigation timed out: {e}", session_id=session_id) from e
        except PlaywrightError as e:
            raise NavigationError(f"Navigation failed: {e}", session_id=session_id) from e
