"""
Base Tool Interface.

All agent tools implement this interface, providing:
- A uniform schema for the LLM to understand available tools
- Risk classification for the human-in-the-loop approval system
- Consistent result reporting
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time


class RiskLevel(Enum):
    """Risk classification for tool actions.
    
    LOW:    Read-only operations, no side effects (auto-approved)
    MEDIUM: Writes to internal systems (may need approval)
    HIGH:   External communications, irreversible actions (requires approval)
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolResult:
    """Standardized result from any tool execution."""

    success: bool
    data: Any = None
    error: str | None = None
    screenshot_path: str | None = None
    execution_time: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "success": self.success,
            "data": str(self.data) if self.data is not None else None,
            "error": self.error,
            "screenshot_path": self.screenshot_path,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }

    def summary(self) -> str:
        """Get a human-readable summary of the result."""
        if self.success:
            data_preview = str(self.data)[:500] if self.data else "No data"
            return f"✅ Success: {data_preview}"
        else:
            return f"❌ Failed: {self.error}"


class BaseTool(ABC):
    """Abstract base class for all agent tools.
    
    Each tool must define:
    - name: Unique identifier
    - description: What the tool does (shown to LLM)
    - risk_level: Default risk level for approval system
    - get_schema(): OpenAI function-calling compatible schema
    - execute(): The actual tool implementation
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @property
    @abstractmethod
    def risk_level(self) -> RiskLevel:
        """Default risk level for this tool."""
        ...

    @abstractmethod
    def get_schema(self) -> dict:
        """
        Return OpenAI function-calling compatible schema.
        
        Format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "What this tool does",
                "parameters": {
                    "type": "object",
                    "properties": { ... },
                    "required": [ ... ]
                }
            }
        }
        """
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        ...

    async def safe_execute(self, **kwargs) -> ToolResult:
        """Execute with timing and error handling."""
        start_time = time.time()
        try:
            result = await self.execute(**kwargs)
            result.execution_time = time.time() - start_time
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Tool '{self.name}' failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    async def cleanup(self):
        """Optional cleanup method. Override in subclasses that need it."""
        pass
