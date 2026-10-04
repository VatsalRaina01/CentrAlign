"""
Approval Gate - Human-in-the-loop approval system.

Controls which actions require human approval based on risk levels:
- LOW risk: Auto-approved (read operations, screenshots)
- MEDIUM risk: Configurable (writes to internal systems)
- HIGH risk: Always requires approval (emails, external comms)
"""

import asyncio
import logging
from app.tools.base import RiskLevel

logger = logging.getLogger(__name__)


class ApprovalGate:
    """Human-in-the-loop approval system with configurable thresholds."""

    def __init__(self):
        # Risk levels that are auto-approved (no human needed)
        # LOW (reads, screenshots) and MEDIUM (internal writes/tickets) are auto-approved.
        # HIGH (external emails/notifications) always requires human confirmation.
        self.auto_approve_levels = {RiskLevel.LOW, RiskLevel.MEDIUM}
        # Pending approval requests: step_id → asyncio.Event
        self.pending_approvals: dict[int, asyncio.Event] = {}
        # Approval results: step_id → (approved, reason)
        self.approval_results: dict[int, tuple[bool, str]] = {}
        # Callback for notifying UI about approval requests
        self._approval_callback = None

    def set_approval_callback(self, callback):
        """Set callback function for notifying UI about approval requests."""
        self._approval_callback = callback

    async def check_approval(
        self,
        step: dict,
        risk_level: RiskLevel,
    ) -> tuple[bool, str]:
        """
        Check if an action needs human approval.

        Args:
            step: The planned step dict.
            risk_level: Risk level of the action.

        Returns:
            Tuple of (approved: bool, reason: str)
        """
        # Auto-approve low-risk actions
        if risk_level in self.auto_approve_levels:
            logger.info(f"Auto-approved (risk: {risk_level.value}): {step.get('description', '')}")
            return True, "Auto-approved (low risk)"

        step_id = step.get("step_id", 0)
        description = step.get("description", "Unknown action")

        logger.info(
            f"Requesting approval for step {step_id} "
            f"(risk: {risk_level.value}): {description}"
        )

        # Create an event to wait on
        approval_event = asyncio.Event()
        self.pending_approvals[step_id] = approval_event

        # Notify UI about approval request
        if self._approval_callback:
            await self._approval_callback({
                "type": "approval_request",
                "step_id": step_id,
                "description": description,
                "risk_level": risk_level.value,
                "tool": step.get("tool", ""),
                "params": step.get("params", {}),
            })

        # Wait for approval (with timeout)
        try:
            await asyncio.wait_for(approval_event.wait(), timeout=300)
            approved, reason = self.approval_results.get(step_id, (False, "Unknown"))
            logger.info(
                f"Approval {'granted' if approved else 'denied'} for step {step_id}: {reason}"
            )
            return approved, reason
        except asyncio.TimeoutError:
            logger.warning(f"Approval timed out for step {step_id}")
            return False, "Approval timed out"
        finally:
            self.pending_approvals.pop(step_id, None)
            self.approval_results.pop(step_id, None)

    def submit_approval(self, step_id: int, approved: bool, reason: str = ""):
        """Submit an approval decision (called from UI)."""
        self.approval_results[step_id] = (approved, reason)
        event = self.pending_approvals.get(step_id)
        if event:
            event.set()
            logger.info(f"Approval submitted for step {step_id}: {'✅' if approved else '❌'}")
        else:
            logger.warning(f"No pending approval found for step {step_id}")

    def get_pending_approvals(self) -> list[int]:
        """Get list of step IDs awaiting approval."""
        return list(self.pending_approvals.keys())

    def get_risk_level_for_step(self, step: dict, tool_risk: RiskLevel) -> RiskLevel:
        """
        Determine the effective risk level for a step.
        Some actions within a tool may have different risk levels.
        """
        # Email is always high risk
        if step.get("tool") == "send_email":
            return RiskLevel.HIGH

        # Browser operations that are read-only
        if step.get("tool") == "browser":
            action = step.get("action", "")
            if action in ("navigate", "extract_text", "screenshot", "get_elements", "wait"):
                return RiskLevel.LOW
            description = step.get("description", "").lower()
            if any(word in description for word in ["submit", "delete", "send", "confirm"]):
                return RiskLevel.HIGH
            return RiskLevel.LOW

        # API requests
        if step.get("tool") == "api_request":
            method = step.get("method") or step.get("action") or step.get("params", {}).get("method", "GET")
            if str(method).upper() == "GET":
                return RiskLevel.LOW
            return RiskLevel.MEDIUM

        return tool_risk
