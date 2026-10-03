"""
Email Tool - Agentmail integration for sending notifications.

Allows the agent to send email notifications via the Agentmail API.
This is a HIGH risk tool - requires human approval before sending.
"""

import logging
import httpx
from app.tools.base import BaseTool, ToolResult, RiskLevel
from app.config import settings

logger = logging.getLogger(__name__)

AGENTMAIL_API_BASE = "https://api.agentmail.to/v0"


class EmailTool(BaseTool):
    """Email sending tool via Agentmail API."""

    @property
    def name(self) -> str:
        return "send_email"

    @property
    def description(self) -> str:
        return (
            "Send email notifications to team members or stakeholders. "
            "Requires specifying the recipient, subject, and body. "
            "This is a high-risk action that requires human approval."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email address.",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line.",
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content (plain text or HTML).",
                        },
                    },
                    "required": ["to", "subject", "body"],
                },
            },
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Send an email via Agentmail API."""
        to = kwargs.get("to")
        subject = kwargs.get("subject")
        body = kwargs.get("body")

        if not all([to, subject, body]):
            return ToolResult(
                success=False, error="Missing required fields: to, subject, body"
            )

        # Check if Agentmail is configured
        if not settings.AGENTMAIL_API_KEY:
            # Fallback to mock email
            return await self._mock_send(to, subject, body)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{AGENTMAIL_API_BASE}/emails",
                    headers={
                        "Authorization": f"Bearer {settings.AGENTMAIL_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": settings.AGENTMAIL_FROM_ADDRESS,
                        "to": [to],
                        "subject": subject,
                        "text": body,
                    },
                )

                if response.is_success:
                    response_data = response.json()
                    return ToolResult(
                        success=True,
                        data={
                            "message": "Email sent successfully",
                            "to": to,
                            "subject": subject,
                            "email_id": response_data.get("id", "unknown"),
                        },
                    )
                else:
                    logger.warning(
                        f"Agentmail API error: {response.status_code} - {response.text}"
                    )
                    # Fallback to mock on API error
                    return await self._mock_send(to, subject, body)

        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            # Fallback to mock on exception
            return await self._mock_send(to, subject, body)

    async def _mock_send(self, to: str, subject: str, body: str) -> ToolResult:
        """Mock email sending when Agentmail is unavailable."""
        logger.info(f"[MOCK EMAIL] To: {to} | Subject: {subject}")
        logger.info(f"[MOCK EMAIL] Body: {body[:200]}")

        return ToolResult(
            success=True,
            data={
                "message": "Email sent (mock mode)",
                "to": to,
                "subject": subject,
                "mode": "mock",
            },
            metadata={"mock": True},
        )
