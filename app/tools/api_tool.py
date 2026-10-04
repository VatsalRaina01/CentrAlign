"""
API Tool - HTTP request tool for interacting with APIs.

Allows the agent to:
- Make GET, POST, PUT, DELETE requests
- Send JSON payloads
- Handle API responses
"""

import logging
import httpx
from app.tools.base import BaseTool, ToolResult, RiskLevel

logger = logging.getLogger(__name__)


class APITool(BaseTool):
    """HTTP API request tool."""

    @property
    def name(self) -> str:
        return "api_request"

    @property
    def description(self) -> str:
        return (
            "Make HTTP API requests (GET, POST, PUT, DELETE) to external "
            "or internal services. Supports JSON payloads and headers."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "api_request",
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE"],
                            "description": "HTTP method.",
                        },
                        "url": {
                            "type": "string",
                            "description": "The API endpoint URL.",
                        },
                        "body": {
                            "type": "object",
                            "description": "JSON request body (for POST/PUT).",
                        },
                        "headers": {
                            "type": "object",
                            "description": "Additional HTTP headers.",
                        },
                    },
                    "required": ["method", "url"],
                },
            },
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Make an HTTP request."""
        method = kwargs.get("method") or kwargs.get("action") or "GET"
        method = method.upper()
        url = kwargs.get("url")
        body = kwargs.get("body") or kwargs.get("data") or kwargs.get("json")
        headers = kwargs.get("headers", {})

        if not url:
            return ToolResult(success=False, error="No URL provided")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                request_kwargs = {
                    "method": method,
                    "url": url,
                    "headers": {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        **headers,
                    },
                }

                if body and method in ("POST", "PUT"):
                    request_kwargs["json"] = body

                response = await client.request(**request_kwargs)

                # Try to parse JSON response
                try:
                    response_data = response.json()
                except Exception:
                    response_data = response.text

                # Truncate very large responses
                response_str = str(response_data)
                if len(response_str) > 5000:
                    response_data = response_str[:5000] + "... [truncated]"

                return ToolResult(
                    success=response.is_success,
                    data=response_data,
                    error=None if response.is_success else f"HTTP {response.status_code}",
                    metadata={
                        "status_code": response.status_code,
                        "method": method,
                        "url": url,
                    },
                )

        except httpx.TimeoutException:
            return ToolResult(success=False, error=f"Request timed out: {url}")
        except httpx.ConnectError:
            return ToolResult(success=False, error=f"Connection failed: {url}")
        except Exception as e:
            return ToolResult(success=False, error=f"API request failed: {str(e)}")
