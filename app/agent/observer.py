"""
Observer - Result analysis and state updates.

After each tool execution, the observer:
1. Analyzes the result using the LLM
2. Extracts useful information for context
3. Determines if the step achieved its goal
4. Suggests what should happen next
"""

import json
import logging
from app.llm.client import LLMClient
from app.tools.base import ToolResult

logger = logging.getLogger(__name__)


OBSERVE_PROMPT = """You are an autonomous AI task worker observing the result of an action you just took.

## Current Task Context
{context_summary}

## Step Just Executed
{step_description}

## Tool Used
{tool_name}

## Result
Success: {success}
Data: {result_data}
Error: {error}

## Original Plan Remaining Steps
{remaining_steps}

Analyze this result and respond in JSON:
{{
    "step_succeeded": true/false,
    "extracted_data": {{"key": "value pairs of any useful information discovered"}},
    "observation": "Brief description of what happened and what was learned",
    "needs_replanning": false,
    "replanning_reason": null,
    "next_step_ready": true/false,
    "next_step_modifications": null,
    "important_finding": null
}}

Important:
- Extract ALL useful data from the result (service statuses, IDs, URLs, names, values)
- Flag if the result suggests the plan needs adjustment
- Note if the next planned step needs parameter modifications based on what we learned"""


class Observer:
    """Analyzes tool results and updates agent state."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def analyze_result(
        self,
        step: dict,
        result: ToolResult,
        context_summary: str,
        remaining_steps: list[dict],
    ) -> dict:
        """
        Use LLM to interpret tool result and extract useful information.

        Returns dict with:
        - step_succeeded: Whether the step achieved its intended purpose
        - extracted_data: Key-value pairs of discovered information
        - observation: What happened in plain text
        - needs_replanning: Whether the plan needs adjustment
        - replanning_reason: Why replanning is needed
        """
        # Prepare result data for prompt
        result_data = str(result.data)[:3000] if result.data else "No data"

        prompt = OBSERVE_PROMPT.format(
            context_summary=context_summary,
            step_description=step.get("description", "Unknown step"),
            tool_name=step.get("tool", "Unknown"),
            success=result.success,
            result_data=result_data,
            error=result.error or "None",
            remaining_steps=json.dumps(remaining_steps[:5], indent=2),
        )

        messages = [
            {"role": "system", "content": "You are a precise observation AI. Always respond in valid JSON."},
            {"role": "user", "content": prompt},
        ]

        try:
            analysis = self.llm.chat_json(messages)
            logger.info(f"Observation: {analysis.get('observation', 'N/A')}")
            return analysis
        except Exception as e:
            logger.error(f"Observer failed: {e}")
            # Fallback to basic analysis
            return {
                "step_succeeded": result.success,
                "extracted_data": {},
                "observation": f"Tool {'succeeded' if result.success else 'failed'}: {result_data[:200]}",
                "needs_replanning": not result.success,
                "replanning_reason": result.error if not result.success else None,
                "next_step_ready": result.success,
                "next_step_modifications": None,
                "important_finding": None,
            }
