"""
Planner - Goal understanding and step planning.

Responsible for:
1. Understanding the user's natural language request
2. Breaking it down into a structured goal
3. Creating an ordered plan of executable steps
4. Re-planning when failures or new information arise
"""

import json
import logging
from app.llm.client import LLMClient

logger = logging.getLogger(__name__)


UNDERSTAND_GOAL_PROMPT = """You are an autonomous AI task worker for a company. Your job is to understand what the user wants accomplished.

## Company Context
{company_context}

## Available Tools
{tools_description}

## User's Request
{user_input}

Analyze the request and respond in JSON format with:
{{
    "goal": "Clear description of the end goal",
    "sub_goals": ["List of specific sub-goals that need to be achieved"],
    "required_info": ["Information needed to complete the task that we don't have yet"],
    "constraints": ["Any constraints or conditions mentioned or implied"],
    "task_type": "The category of this task (e.g., monitoring, incident_response, data_entry, communication)",
    "urgency": "low | medium | high",
    "needs_clarification": false,
    "clarification_question": null
}}

Be thorough in breaking down the goal. Consider company procedures and policies."""


CREATE_PLAN_PROMPT = """You are an autonomous AI task worker. Based on the goal analysis, create a concrete plan of executable steps.

## Goal Analysis
{goal}

## Company Context
{company_context}

## Available Tools
{tools_description}

## Already Discovered Information
{context_variables}

Create a plan as a JSON array of steps. Each step should specify exactly which tool to use and what parameters:

{{
    "plan": [
        {{
            "step_id": 0,
            "description": "What this step does",
            "tool": "tool_name",
            "action": "specific action within the tool",
            "params": {{"key": "value"}},
            "depends_on": [],
            "risk_level": "low|medium|high",
            "expected_outcome": "What we expect to happen",
            "failure_alternative": "What to try if this fails"
        }}
    ],
    "reasoning": "Brief explanation of why this plan structure was chosen"
}}

Available tools and their actions:
- browser: navigate, click, type, extract_text, screenshot, get_elements, select_option, wait
- file_operations: read, write, list, search
- api_request: GET, POST, PUT, DELETE to URLs
- send_email: send email with to, subject, body

Important:
- Use the company's internal portal URL for internal system interactions
- Check service status BEFORE creating tickets
- Include verification steps
- Mark email/notification steps as high risk
- Include steps to gather evidence (screenshots, data extraction)"""


REPLAN_PROMPT = """You are an autonomous AI task worker. Your original plan encountered an issue and needs adjustment.

## Original Plan
{original_plan}

## Steps Completed Successfully
{completed_steps}

## Failed Step
{failed_step}

## Error
{error}

## Current Context
{context_summary}

Create an adjusted plan that:
1. Doesn't repeat already completed steps
2. Addresses the failure with an alternative approach
3. Still achieves the original goal

Respond in the same JSON plan format as before."""


class Planner:
    """Handles goal understanding and step planning using LLM."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def understand_goal(
        self,
        user_input: str,
        company_context: str,
        tools_description: str,
    ) -> dict:
        """Parse user's natural language into a structured goal."""
        prompt = UNDERSTAND_GOAL_PROMPT.format(
            user_input=user_input,
            company_context=company_context,
            tools_description=tools_description,
        )

        messages = [
            {"role": "system", "content": "You are a precise task analysis AI. Always respond in valid JSON."},
            {"role": "user", "content": prompt},
        ]

        result = self.llm.chat_json(messages)
        logger.info(f"Goal understood: {result.get('goal', 'unknown')}")
        return result

    def create_plan(
        self,
        goal: dict,
        company_context: str,
        tools_description: str,
        context_variables: dict | None = None,
    ) -> tuple[list[dict], str]:
        """Generate an ordered list of action steps.
        
        Returns:
            Tuple of (plan_steps, reasoning)
        """
        prompt = CREATE_PLAN_PROMPT.format(
            goal=json.dumps(goal, indent=2),
            company_context=company_context,
            tools_description=tools_description,
            context_variables=json.dumps(context_variables or {}, indent=2),
        )

        messages = [
            {"role": "system", "content": "You are a precise task planning AI. Always respond in valid JSON."},
            {"role": "user", "content": prompt},
        ]

        result = self.llm.chat_json(messages)
        plan = result.get("plan", [])
        reasoning = result.get("reasoning", "")
        logger.info(f"Plan created with {len(plan)} steps")
        return plan, reasoning

    def replan(
        self,
        original_plan: list[dict],
        completed_steps: list[dict],
        failed_step: dict,
        error: str,
        context_summary: str,
    ) -> tuple[list[dict], str]:
        """Adjust plan based on failures or new information."""
        prompt = REPLAN_PROMPT.format(
            original_plan=json.dumps(original_plan, indent=2),
            completed_steps=json.dumps(completed_steps, indent=2),
            failed_step=json.dumps(failed_step, indent=2),
            error=error,
            context_summary=context_summary,
        )

        messages = [
            {"role": "system", "content": "You are a precise task planning AI. Always respond in valid JSON."},
            {"role": "user", "content": prompt},
        ]

        result = self.llm.chat_json(messages)
        plan = result.get("plan", [])
        reasoning = result.get("reasoning", "Plan adjusted after failure")
        logger.info(f"Re-planned with {len(plan)} steps")
        return plan, reasoning
