"""
Execution Log - Full audit trail of agent actions.

Records every action the agent takes for:
- Debugging and transparency
- Post-task review
- Evidence of work performed
"""

import json
import os
import logging
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)


class ExecutionLog:
    """Audit trail for agent actions."""

    def __init__(self):
        self.entries: list[dict] = []
        self.task_id: str = ""

    def reset(self, task_id: str):
        """Reset log for a new task."""
        self.entries = []
        self.task_id = task_id

    def log(
        self,
        event_type: str,
        description: str,
        details: dict | None = None,
    ):
        """Log an event."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "description": description,
            "details": details or {},
        }
        self.entries.append(entry)
        logger.info(f"[{event_type}] {description}")

    def log_tool_call(
        self,
        tool_name: str,
        params: dict,
        result_success: bool,
        result_data: str | None = None,
        error: str | None = None,
    ):
        """Log a tool execution."""
        self.log(
            event_type="TOOL_CALL",
            description=f"Tool: {tool_name}",
            details={
                "tool": tool_name,
                "params": {k: str(v)[:200] for k, v in params.items()},
                "success": result_success,
                "result": str(result_data)[:500] if result_data else None,
                "error": error,
            },
        )

    def log_planning(self, plan: list[dict]):
        """Log plan creation."""
        self.log(
            event_type="PLAN_CREATED",
            description=f"Created plan with {len(plan)} steps",
            details={"plan": plan},
        )

    def log_approval(self, step_description: str, approved: bool, reason: str = ""):
        """Log human approval decision."""
        self.log(
            event_type="APPROVAL",
            description=f"{'Approved' if approved else 'Rejected'}: {step_description}",
            details={"approved": approved, "reason": reason},
        )

    def log_recovery(self, original_error: str, recovery_action: str):
        """Log a recovery attempt."""
        self.log(
            event_type="RECOVERY",
            description=f"Recovery from: {original_error}",
            details={"original_error": original_error, "action": recovery_action},
        )

    def log_verification(self, verified: bool, evidence: dict):
        """Log outcome verification."""
        self.log(
            event_type="VERIFICATION",
            description=f"Outcome {'verified ✅' if verified else 'not verified ❌'}",
            details={"verified": verified, "evidence": evidence},
        )

    def get_summary(self) -> str:
        """Get a human-readable summary of the execution log."""
        if not self.entries:
            return "No actions recorded."

        lines = [f"Execution Log ({len(self.entries)} entries):"]
        for entry in self.entries:
            time = entry["timestamp"].split("T")[1][:8]
            lines.append(f"  [{time}] {entry['event_type']}: {entry['description']}")
        return "\n".join(lines)

    def save_to_file(self):
        """Save log to a JSON file."""
        os.makedirs(settings.EXECUTION_LOGS_DIR, exist_ok=True)
        filename = f"log_{self.task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(settings.EXECUTION_LOGS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "task_id": self.task_id,
                    "entries": self.entries,
                    "total_events": len(self.entries),
                },
                f,
                indent=2,
                default=str,
            )
        logger.info(f"Execution log saved: {filepath}")
        return filepath
