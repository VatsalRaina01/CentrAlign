"""
Browser Tool - Playwright-based browser automation.

Allows the agent to:
- Navigate to URLs
- Click elements by CSS selector or text
- Type text into input fields
- Extract text content from pages
- Take screenshots for evidence
- List interactive elements to discover page structure
"""

import os
import logging
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from app.tools.base import BaseTool, ToolResult, RiskLevel
from app.config import settings

logger = logging.getLogger(__name__)


class BrowserTool(BaseTool):
    """Playwright-based browser automation tool."""

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "Interact with web pages: navigate to URLs, click elements, "
            "fill forms, extract text content, take screenshots, and "
            "list interactive elements on a page."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "browser",
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "navigate",
                                "click",
                                "type",
                                "extract_text",
                                "screenshot",
                                "get_elements",
                                "select_option",
                                "wait",
                            ],
                            "description": "The browser action to perform.",
                        },
                        "url": {
                            "type": "string",
                            "description": "URL to navigate to (for 'navigate' action).",
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector for the target element.",
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to type (for 'type' action) or text content of element to click.",
                        },
                        "wait_time": {
                            "type": "number",
                            "description": "Seconds to wait (for 'wait' action). Default: 2",
                        },
                    },
                    "required": ["action"],
                },
            },
        }

    async def _ensure_browser(self):
        """Initialize browser if not already running."""
        if not self._initialized:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            self._page = await self._context.new_page()
            self._initialized = True
            logger.info("Browser initialized successfully")

    async def execute(self, **kwargs) -> ToolResult:
        """Execute a browser action."""
        action = kwargs.get("action")
        if not action:
            return ToolResult(success=False, error="No action specified")

        await self._ensure_browser()

        action_map = {
            "navigate": self._navigate,
            "click": self._click,
            "type": self._type,
            "extract_text": self._extract_text,
            "screenshot": self._screenshot,
            "get_elements": self._get_elements,
            "select_option": self._select_option,
            "wait": self._wait,
        }

        handler = action_map.get(action)
        if not handler:
            return ToolResult(success=False, error=f"Unknown action: {action}")

        return await handler(**kwargs)

    async def _navigate(self, **kwargs) -> ToolResult:
        """Navigate to a URL."""
        url = kwargs.get("url")
        if not url:
            return ToolResult(success=False, error="No URL provided")

        try:
            response = await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            title = await self._page.title()
            # Take a screenshot automatically after navigation
            screenshot_path = await self._take_screenshot(f"nav_{title[:30]}")
            return ToolResult(
                success=True,
                data={
                    "url": self._page.url,
                    "title": title,
                    "status": response.status if response else "unknown",
                },
                screenshot_path=screenshot_path,
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Navigation failed: {str(e)}")

    async def _click(self, **kwargs) -> ToolResult:
        """Click an element by selector or text."""
        selector = kwargs.get("selector")
        text = kwargs.get("text")

        try:
            if selector:
                await self._page.click(selector, timeout=5000)
            elif text:
                # Try to find element by text content
                await self._page.click(f"text={text}", timeout=5000)
            else:
                return ToolResult(success=False, error="No selector or text provided for click")

            await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            screenshot_path = await self._take_screenshot("after_click")
            return ToolResult(
                success=True,
                data={"clicked": selector or text, "current_url": self._page.url},
                screenshot_path=screenshot_path,
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Click failed: {str(e)}")

    async def _type(self, **kwargs) -> ToolResult:
        """Type text into an input field."""
        selector = kwargs.get("selector")
        text = kwargs.get("text")

        if not selector or not text:
            return ToolResult(success=False, error="Both selector and text required for type action")

        try:
            await self._page.fill(selector, text, timeout=5000)
            return ToolResult(
                success=True,
                data={"typed": text, "into": selector},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Type failed: {str(e)}")

    async def _extract_text(self, **kwargs) -> ToolResult:
        """Extract text content from the page or a specific element."""
        selector = kwargs.get("selector")

        try:
            if selector:
                element = await self._page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                else:
                    return ToolResult(success=False, error=f"Element not found: {selector}")
            else:
                text = await self._page.inner_text("body")

            # Truncate very long text
            if len(text) > 5000:
                text = text[:5000] + "\n... [truncated]"

            return ToolResult(success=True, data=text)
        except Exception as e:
            return ToolResult(success=False, error=f"Text extraction failed: {str(e)}")

    async def _screenshot(self, **kwargs) -> ToolResult:
        """Take a screenshot of the current page."""
        try:
            screenshot_path = await self._take_screenshot("manual")
            return ToolResult(
                success=True,
                data={"screenshot_saved": screenshot_path, "url": self._page.url},
                screenshot_path=screenshot_path,
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Screenshot failed: {str(e)}")

    async def _get_elements(self, **kwargs) -> ToolResult:
        """List interactive elements on the page for the agent to discover."""
        try:
            elements = await self._page.evaluate("""
                () => {
                    const interactiveElements = [];
                    const selectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
                    const elements = document.querySelectorAll(selectors);
                    
                    elements.forEach((el, index) => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            const info = {
                                tag: el.tagName.toLowerCase(),
                                type: el.type || null,
                                text: (el.innerText || el.value || el.placeholder || '').trim().substring(0, 100),
                                id: el.id || null,
                                name: el.name || null,
                                href: el.href || null,
                                class: el.className ? el.className.substring(0, 100) : null,
                            };
                            
                            // Build a usable selector
                            if (el.id) {
                                info.selector = '#' + el.id;
                            } else if (el.name) {
                                info.selector = `${el.tagName.toLowerCase()}[name="${el.name}"]`;
                            } else {
                                info.selector = `${el.tagName.toLowerCase()}:nth-of-type(${index + 1})`;
                            }
                            
                            interactiveElements.push(info);
                        }
                    });
                    
                    return interactiveElements.slice(0, 50);
                }
            """)

            return ToolResult(
                success=True,
                data=elements,
                metadata={"element_count": len(elements)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Element listing failed: {str(e)}")

    async def _select_option(self, **kwargs) -> ToolResult:
        """Select an option from a dropdown."""
        selector = kwargs.get("selector")
        text = kwargs.get("text")

        if not selector or not text:
            return ToolResult(success=False, error="Both selector and text required")

        try:
            await self._page.select_option(selector, label=text, timeout=5000)
            return ToolResult(success=True, data={"selected": text, "in": selector})
        except Exception as e:
            return ToolResult(success=False, error=f"Select failed: {str(e)}")

    async def _wait(self, **kwargs) -> ToolResult:
        """Wait for a specified time."""
        wait_time = kwargs.get("wait_time", 2)
        try:
            await asyncio.sleep(float(wait_time))
            return ToolResult(success=True, data=f"Waited {wait_time} seconds")
        except Exception as e:
            return ToolResult(success=False, error=f"Wait failed: {str(e)}")

    async def _take_screenshot(self, label: str = "") -> str:
        """Internal helper to save a screenshot."""
        os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = "".join(c for c in label if c.isalnum() or c in "_-")[:30]
        filename = f"screenshot_{timestamp}_{safe_label}.png"
        filepath = os.path.join(settings.SCREENSHOTS_DIR, filename)
        await self._page.screenshot(path=filepath, full_page=False)
        logger.info(f"Screenshot saved: {filepath}")
        return filepath

    async def cleanup(self):
        """Close browser and release resources."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        logger.info("Browser cleaned up")
