"""
Executor - Step execution and tool dispatch.

Takes a planned step and executes it by:
1. Resolving parameter references from context
2. Dispatching to the appropriate tool
3. Returning the tool result
"""

import json
import logging
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class Executor:
    """Dispatches planned steps to the appropriate tools."""

    def __init__(self, tools: dict[str, BaseTool]):
        self.tools = tools

    async def execute_step(
        self,
        step: dict,
        context_variables: dict,
    ) -> ToolResult:
        """
        Execute a single planned step.

        Args:
            step: The planned step dict with 'tool', 'action', 'params'.
            context_variables: Currently known variables for parameter resolution.

        Returns:
            ToolResult from the tool execution.
        """
        tool_name = step.get("tool")
        action = step.get("action", "")
        params = step.get("params", {})

        if not tool_name:
            return ToolResult(success=False, error="No tool specified in step")

        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}. Available: {list(self.tools.keys())}",
            )

        # Resolve parameter references from context (e.g., {{service_url}})
        resolved_params = self._resolve_params(params, context_variables)

        # Add the action to params if specified
        if action:
            resolved_params["action"] = action

        logger.info(
            f"Executing: {tool_name}.{action} with params: "
            f"{json.dumps({k: str(v)[:100] for k, v in resolved_params.items()})}"
        )

        # Execute with safety wrapper
        result = await tool.safe_execute(**resolved_params)

        if result.success:
            logger.info(f"Step succeeded: {step.get('description', '')}")
        else:
            logger.warning(f"Step failed: {result.error}")

        return result

    def _resolve_params(self, params: dict, context: dict) -> dict:
        """
        Resolve parameter references from context variables.

        Supports {{variable_name}} syntax in string values.
        Example: {"url": "{{portal_url}}/tickets"} with context {"portal_url": "http://localhost:5001"}
        resolves to {"url": "http://localhost:5001/tickets"}
        """
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                # Replace {{variable}} references
                for var_name, var_value in context.items():
                    placeholder = "{{" + var_name + "}}"
                    if placeholder in value:
                        value = value.replace(placeholder, str(var_value))
                resolved[key] = value
            elif isinstance(value, dict):
                resolved[key] = self._resolve_params(value, context)
            else:
                resolved[key] = value
        return resolved

    def get_available_tools_description(self) -> str:
        """Get a formatted description of all available tools for LLM prompts."""
        descriptions = []
        for name, tool in self.tools.items():
            schema = tool.get_schema()
            func = schema.get("function", {})
            params = func.get("parameters", {}).get("properties", {})
            param_list = ", ".join(
                f"{k}: {v.get('type', 'any')}" for k, v in params.items()
            )
            descriptions.append(
                f"- **{name}** ({tool.risk_level.value} risk): {tool.description}\n"
                f"  Parameters: {param_list}"
            )
        return "\n".join(descriptions)
