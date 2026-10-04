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


UNDERSTAND_GOAL_PROMPT = """You are an autonomous AI task worker for Acme Corp. Your job is to understand what the user wants accomplished.

## Company Context
{company_context}

## Enterprise IT Infrastructure
- Internal IT Portal: http://localhost:5001
- Services Dashboard: http://localhost:5001/
- Tickets Dashboard: http://localhost:5001/tickets
- Create Ticket API: POST http://localhost:5001/api/tickets
- All necessary permissions and credentials are fully granted. Do NOT ask for API credentials, tokens, or confirmation.

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
    "task_type": "incident_response",
    "urgency": "high",
    "needs_clarification": false,
    "clarification_question": null
}}

Be thorough in breaking down the goal. Consider company procedures and policies. Set needs_clarification to false."""


CREATE_PLAN_PROMPT = """You are an autonomous AI task worker. Based on the goal analysis, create a concrete plan of executable steps.

## Goal Analysis
{goal}

## Company Context
{company_context}

## Enterprise IT Portal & API Endpoints
- Base URL: http://localhost:5001
- Check Services: browser navigate to "http://localhost:5001/" or API GET "http://localhost:5001/api/services"
- Create Ticket: API POST "http://localhost:5001/api/tickets" with JSON {{"title": str, "description": str, "priority": "P1"|"P2", "service_id": int, "assigned_to": str}}
- View Tickets: browser navigate to "http://localhost:5001/tickets"
- Notifications: send_email tool with "to", "subject", "body"
- Do NOT use file_operations to search for user credentials or config files. All systems are live at http://localhost:5001.

## Available Tools
{tools_description}

## Already Discovered Information
{context_variables}

Create a plan as a JSON array of steps. Each step should specify exactly which tool to use and what parameters:

{{
    "plan": [
        {{
            "step_id": 1,
            "description": "What this step does",
            "tool": "browser | api_request | send_email",
            "action": "navigate | click | type | extract_text | screenshot | GET | POST | send",
            "params": {{"key": "value"}},
            "depends_on": [],
            "risk_level": "low|medium|high",
            "expected_outcome": "What we expect to happen",
            "failure_alternative": "What to try if this fails"
        }}
    ],
    "reasoning": "Brief explanation of why this plan structure was chosen"
}}

Rules for the plan:
1. First, check service statuses by navigating to "http://localhost:5001/" (browser) or querying "http://localhost:5001/api/services" (api_request).
2. Take a screenshot of the dashboard as visual evidence.
3. For any down service (e.g. Corporate VPN), create a P1 ticket via POST http://localhost:5001/api/tickets assigned to the responsible team member (Priya Sharma).
4. For any degraded service (e.g. Customer CRM), create a P2 ticket via POST http://localhost:5001/api/tickets assigned to Sarah Chen.
5. Send the incident alert email to the specified recipient (e.g., apptestvatsal@gmail.com or IT team) using 'send_email' (marked risk_level: high).
6. Verify outcome by navigating to "http://localhost:5001/tickets" and taking a screenshot.
7. NEVER use 'file_operations' to look for credentials or tokens. All API access is local and pre-authenticated."""


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
2. Addresses the failure with an alternative approach using valid tools ('browser', 'api_request', 'file_operations', 'send_email')
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
        raw_plan = result.get("plan", [])
        reasoning = result.get("reasoning", "")

        # Sanitize plan: ensure every step has an executable tool
        valid_tools = {"browser", "api_request", "file_operations", "send_email"}
        plan = []
        for step in raw_plan:
            tool_name = str(step.get("tool", "")).lower().strip()
            desc = step.get("description", "").lower()
            if tool_name not in valid_tools:
                # Infer correct tool or skip non-tool steps
                if any(w in desc for w in ["email", "notify", "alert", "mail"]):
                    step["tool"] = "send_email"
                elif any(w in desc for w in ["ticket", "api", "post"]):
                    step["tool"] = "api_request"
                elif any(w in desc for w in ["portal", "dashboard", "browser", "navigate", "page", "status"]):
                    step["tool"] = "browser"
                else:
                    logger.info(f"Skipping non-executable step: {step.get('description')}")
                    continue
            plan.append(step)

        logger.info(f"Plan created with {len(plan)} executable steps")
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
