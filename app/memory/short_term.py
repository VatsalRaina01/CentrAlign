"""
Short-Term Memory - Current task context.

Maintains the agent's working memory during a single task execution:
- Goal and sub-goals
- Current plan and step progress
- Observations from tool executions
- Discovered information (context variables)
- Conversation history with the LLM
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StepRecord:
    """Record of an executed step."""
    step_id: int
    description: str
    tool: str
    params: dict
    result_success: bool
    result_data: Any
    result_error: str | None
    timestamp: str
    screenshot_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "tool": self.tool,
            "params": self.params,
            "result_success": self.result_success,
            "result_data": str(self.result_data)[:1000] if self.result_data else None,
            "result_error": self.result_error,
            "timestamp": self.timestamp,
            "screenshot_path": self.screenshot_path,
        }


class ShortTermMemory:
    """Working memory for the current task."""

    def __init__(self):
        self.task_id: str = ""
        self.original_input: str = ""
        self.goal: dict = {}
        self.plan: list[dict] = []
        self.executed_steps: list[StepRecord] = []
        self.current_step_index: int = 0
        self.context_variables: dict[str, Any] = {}
        self.observations: list[str] = []
        self.messages: list[dict] = []  # LLM conversation history
        self.start_time: str = ""
        self.status: str = "idle"  # idle, planning, executing, verifying, complete, failed

    def reset(self, task_id: str, user_input: str):
        """Reset memory for a new task."""
        self.__init__()
        self.task_id = task_id
        self.original_input = user_input
        self.start_time = datetime.now().isoformat()
        self.status = "planning"

    def add_step_result(
        self,
        step_id: int,
        description: str,
        tool: str,
        params: dict,
        success: bool,
        data: Any,
        error: str | None = None,
        screenshot_path: str | None = None,
    ):
        """Record a completed step."""
        record = StepRecord(
            step_id=step_id,
            description=description,
            tool=tool,
            params=params,
            result_success=success,
            result_data=data,
            result_error=error,
            timestamp=datetime.now().isoformat(),
            screenshot_path=screenshot_path,
        )
        self.executed_steps.append(record)
        self.current_step_index = step_id + 1

    def add_observation(self, observation: str):
        """Add an observation from the agent's reasoning."""
        self.observations.append(observation)

    def update_variable(self, key: str, value: Any):
        """Store a discovered piece of information."""
        self.context_variables[key] = value

    def get_context_summary(self) -> str:
        """Get a compact summary of current context for LLM prompts."""
        parts = [
            f"Task: {self.original_input}",
            f"Status: {self.status}",
        ]

        if self.context_variables:
            parts.append(f"Discovered information: {self.context_variables}")

        if self.executed_steps:
            recent = self.executed_steps[-5:]  # Last 5 steps
            step_summaries = []
            for s in recent:
                status = "✅" if s.result_success else "❌"
                data_preview = str(s.result_data)[:200] if s.result_data else ""
                step_summaries.append(
                    f"  {status} Step {s.step_id}: {s.description} → {data_preview}"
                )
            parts.append("Recent steps:\n" + "\n".join(step_summaries))

        if self.observations:
            recent_obs = self.observations[-3:]
            parts.append("Recent observations:\n  " + "\n  ".join(recent_obs))

        return "\n".join(parts)

    def get_failed_steps(self) -> list[StepRecord]:
        """Get all failed steps."""
        return [s for s in self.executed_steps if not s.result_success]

    def get_all_screenshots(self) -> list[str]:
        """Get all screenshot paths from executed steps."""
        return [
            s.screenshot_path
            for s in self.executed_steps
            if s.screenshot_path
        ]

    def to_dict(self) -> dict:
        """Serialize for logging."""
        return {
            "task_id": self.task_id,
            "original_input": self.original_input,
            "goal": self.goal,
            "plan": self.plan,
            "executed_steps": [s.to_dict() for s in self.executed_steps],
            "current_step_index": self.current_step_index,
            "context_variables": {
                k: str(v)[:500] for k, v in self.context_variables.items()
            },
            "observations": self.observations,
            "start_time": self.start_time,
            "status": self.status,
        }
