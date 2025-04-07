import logging
import asyncio
from typing import Optional, Dict, Tuple, Any, AsyncContextManager
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from raiden.core.config import settings
from raiden.core.constants import ActionStatus, ACTION_STATUS_CONTINUE, ACTION_STATUS_ERROR, ACTION_STATUS_ASK_USER
from raiden.core.orchestration.retry_handler import RetryHandler
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
        self._retry_handler = RetryHandler()  # Initialize retry handler
        logger.info("BrowserControlLayer initialized with retry mechanism.")

    async def initialize(self) -> None:
        async with self._lock:
            if self._playwright and self._browser:
                logger.warning("BCL already initialized.")
                return
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=False,  # Ensure the browser is always visible
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

    async def execute_navigate(self, session_id: str, step: Any, **kwargs) -> Tuple[ActionStatus, Dict[str, Any]]:
        if not hasattr(step, 'target_url') or not step.target_url:
            raise NavigationError("No target URL provided for navigation action", session_id=session_id)
            
        try:
            async with self.get_page_for_session(session_id) as page:
                # Use a longer timeout for initial navigation
                page.set_default_timeout(60000)  # 60 seconds for navigation
                response = await page.goto(str(step.target_url), 
                                        wait_until="networkidle",  # Wait for network to be idle
                                        timeout=60000)  # 60 second timeout
                # Reset timeout to default for other operations
                page.set_default_timeout(settings.browser_default_timeout_ms)
                status_code = response.status if response else None
                return ACTION_STATUS_CONTINUE, {"final_url": page.url, "status_code": status_code}
        except PlaywrightTimeoutError as e:
            raise ActionTimeoutError(f"Navigation timed out: {e}", session_id=session_id) from e
        except PlaywrightError as e:
            raise NavigationError(f"Navigation failed: {e}", session_id=session_id) from e

    async def execute_wait_for_selector(self, session_id: str, step: Any, **kwargs) -> Tuple[ActionStatus, Dict[str, Any]]:
        """Waits for an element with retry mechanism."""
        if not hasattr(step, 'selector') or not step.selector:
            raise InvalidSelectorError("No selector provided for wait_for_selector action", session_id=session_id)
            
        async def wait_action():
            async with self.get_page_for_session(session_id) as page:
                logger.info(f"""
╔══════════════════════════════════════════════
║ Waiting for Element
║ Selector: {step.selector}
╚══════════════════════════════════════════════""")
                
                # For Google search results, use multiple selectors
                if step.selector in ['#search', 'div.g']:
                    search_selectors = [
                        '#center_col',  # Main column containing results
                        '#rcnt',        # Another main container
                        '#search',      # General search container
                        'div.g',        # Individual result containers
                        '#rso',         # Organic search results
                        '#main'         # Main content area
                    ]
                    
                    for selector in search_selectors:
                        try:
                            logger.info(f"→ Checking for results using '{selector}'...")
                            await page.wait_for_selector(selector, timeout=5000)
                            logger.info(f"✓ Found search results with selector: {selector}")
                            return ACTION_STATUS_CONTINUE, {}
                        except PlaywrightTimeoutError:
                            continue
                    
                    raise PlaywrightTimeoutError("No search result selectors found")
                
                # For non-search selectors, use standard behavior
                logger.info(f"→ Waiting for selector: {step.selector}")
                await page.wait_for_selector(step.selector)
                logger.info(f"✓ Found element")
                return ACTION_STATUS_CONTINUE, {}

        try:
            return await self._retry_handler.execute_with_retry('wait_for_selector', wait_action)
        except (ActionExecutionError, ActionTimeoutError) as e:
            logger.error(f"Failed to wait for selector after all retries: {e}")
            async with self.get_page_for_session(session_id) as page:
                page_html = await page.content()
                logger.debug(f"Page HTML at failure: {page_html}")
            raise

    async def execute_wait_for_load_state(self, session_id: str, step: Any, **kwargs) -> Tuple[ActionStatus, Dict[str, Any]]:
        """Waits for a specific page load state."""
        try:
            state = getattr(step, 'state', 'load')  # Default to 'load' if not specified
            async with self.get_page_for_session(session_id) as page:
                await page.wait_for_load_state(state)
                return ACTION_STATUS_CONTINUE, {}
        except PlaywrightTimeoutError as e:
            raise ActionTimeoutError(f"Timeout waiting for page load state '{state}': {e}", session_id=session_id) from e
        except PlaywrightError as e:
            raise ActionExecutionError(f"Failed to wait for page load state '{state}': {e}", session_id=session_id) from e

    async def execute_click(self, session_id: str, step: Any, **kwargs) -> Tuple[ActionStatus, Dict[str, Any]]:
        """Clicks on an element matching the selector."""
        if not hasattr(step, 'selector') or not step.selector:
            raise InvalidSelectorError("No selector provided for click action", session_id=session_id)
            
        try:
            async with self.get_page_for_session(session_id) as page:
                element = await page.wait_for_selector(step.selector)
                if not element:
                    raise ElementNotFoundError(f"Element with selector '{step.selector}' not found", session_id=session_id)
                await element.click()
                return ACTION_STATUS_CONTINUE, {}
        except PlaywrightTimeoutError as e:
            raise ActionTimeoutError(f"Timeout waiting for element '{step.selector}': {e}", session_id=session_id) from e
        except PlaywrightError as e:
            raise ActionExecutionError(f"Failed to click element '{step.selector}': {e}", session_id=session_id) from e

    async def _try_google_search_strategies(self, page, element, text: str, max_retries: int = 3) -> bool:
        """Try different strategies to enter and submit a Google search."""
        
        async def strategy1():
            await element.fill("")
            await element.type(text, delay=50)
            await element.press('Enter')
            await page.wait_for_load_state('domcontentloaded')
            
        async def strategy2():
            await element.fill(text)
            await page.keyboard.press('Enter')
            await page.wait_for_load_state('domcontentloaded')
            
        async def strategy3():
            await element.fill(text)
            await page.wait_for_timeout(1000)  # Wait for suggestions
            await element.press('Enter')
            await page.wait_for_load_state('domcontentloaded')

        strategies = [strategy1, strategy2, strategy3]

        for attempt, strategy in enumerate(strategies, 1):
            if attempt > max_retries:
                return False
            
            try:
                logger.info(f"""
╔══════════════════════════════════════════════
║ Search Strategy Attempt {attempt}/{max_retries}
╚══════════════════════════════════════════════""")
                
                await strategy()
                
                # Check if search was successful by looking for any of these indicators
                success_indicators = ['#search', '#main', '#rcnt', 'div.g']
                for indicator in success_indicators:
                    try:
                        await page.wait_for_selector(indicator, timeout=5000)
                        logger.info(f"✓ Search successful (detected {indicator})")
                        return True
                    except:
                        continue
                        
            except Exception as e:
                logger.warning(f"Strategy {attempt} failed: {e}")
                continue
                
        return False

    async def execute_type(self, session_id: str, step: Any, **kwargs) -> Tuple[ActionStatus, Dict[str, Any]]:
        """Types text into an element with retry mechanism."""
        if not hasattr(step, 'selector') or not step.selector:
            raise InvalidSelectorError("No selector provided for type action", session_id=session_id)
        if not hasattr(step, 'text_to_type') or not step.text_to_type:
            raise ActionExecutionError("No text provided for type action", session_id=session_id)

        async def type_action():
            async with self.get_page_for_session(session_id) as page:
                logger.info(f"""
╔══════════════════════════════════════════════
║ Typing Action
║ Selector: {step.selector}
║ Text: {step.text_to_type}
╚══════════════════════════════════════════════""")
                
                logger.info("→ Waiting for input element...")
                element = await page.wait_for_selector(step.selector, state='visible')
                if not element:
                    raise ElementNotFoundError(f"Element with selector '{step.selector}' not found", session_id=session_id)
                
                logger.info("→ Clearing existing text...")
                await element.fill("")
                
                logger.info("→ Typing text...")
                await element.type(step.text_to_type, delay=50)  # Add slight delay between keypresses
                
                # If this is a Google search box, handle the search submission
                if step.selector == "textarea[name='q']":
                    logger.info("→ Submitting search...")
                    await element.press('Enter')
                    await page.wait_for_load_state('networkidle')
                
                return ACTION_STATUS_CONTINUE, {}

        try:
            return await self._retry_handler.execute_with_retry('type', type_action)
        except (ActionExecutionError, ActionTimeoutError) as e:
            logger.error(f"Failed to execute type action after all retries: {e}")
            raise

    async def execute_ask_user(self, session_id: str, step: Any, **kwargs) -> Tuple[ActionStatus, Dict[str, Any]]:
        """Handles pausing execution to ask for user input."""
        if not hasattr(step, 'prompt_to_user') or not step.prompt_to_user:
            raise ActionExecutionError("No prompt provided for ask_user action", session_id=session_id)
            
        return ACTION_STATUS_ASK_USER, {
            "ask_user_prompt": step.prompt_to_user
        }
