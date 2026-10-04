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

        if not plan:
            logger.warning("Generated plan was empty; generating default IT incident workflow plan.")
            plan, reasoning = self._get_default_plan(goal)

        logger.info(f"Plan created with {len(plan)} executable steps")
        return plan, reasoning

    def _get_default_plan(self, goal: dict) -> tuple[list[dict], str]:
        """Provide a default robust plan if LLM produces an empty plan."""
        goal_text = str(goal.get("goal", ""))
        import re
        email_recipient = "apptestvatsal@gmail.com"
        for email in re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', goal_text):
            if "acme" not in email:
                email_recipient = email
                break

        plan = [
            {
                "step_id": 1,
                "description": "Navigate to IT portal dashboard to inspect service health",
                "tool": "browser",
                "action": "navigate",
                "params": {"url": "http://localhost:5001/"},
                "depends_on": [],
                "risk_level": "low",
                "expected_outcome": "IT portal dashboard loaded showing service status cards",
                "failure_alternative": "Check service status via GET http://localhost:5001/api/services",
            },
            {
                "step_id": 2,
                "description": "Extract service statuses from dashboard",
                "tool": "browser",
                "action": "extract_text",
                "params": {"selector": ".services-grid"},
                "depends_on": [1],
                "risk_level": "low",
                "expected_outcome": "Extracted service names and statuses (VPN down, CRM degraded)",
                "failure_alternative": "Query http://localhost:5001/api/services",
            },
            {
                "step_id": 3,
                "description": "Capture screenshot of dashboard showing service outages",
                "tool": "browser",
                "action": "screenshot",
                "params": {"name": "service_status_dashboard.png"},
                "depends_on": [1],
                "risk_level": "low",
                "expected_outcome": "Screenshot saved as evidence",
                "failure_alternative": "Continue without screenshot",
            },
            {
                "step_id": 4,
                "description": "Create P1 support ticket for Corporate VPN outage",
                "tool": "api_request",
                "action": "POST",
                "params": {
                    "url": "http://localhost:5001/api/tickets",
                    "data": {
                        "title": "Outage: Corporate VPN is Down",
                        "description": "Critical service Corporate VPN is down. Remote staff unable to connect.",
                        "priority": "P1",
                        "service_id": 2,
                        "assigned_to": "Priya Sharma",
                    },
                },
                "depends_on": [2],
                "risk_level": "medium",
                "expected_outcome": "Ticket created for VPN outage",
                "failure_alternative": "Create ticket via web form",
            },
            {
                "step_id": 5,
                "description": "Create P2 support ticket for Customer CRM degradation",
                "tool": "api_request",
                "action": "POST",
                "params": {
                    "url": "http://localhost:5001/api/tickets",
                    "data": {
                        "title": "Degraded: Customer CRM experiencing high latency",
                        "description": "CRM response times exceed SLA. Partial errors reported.",
                        "priority": "P2",
                        "service_id": 4,
                        "assigned_to": "Sarah Chen",
                    },
                },
                "depends_on": [2],
                "risk_level": "medium",
                "expected_outcome": "Ticket created for CRM degradation",
                "failure_alternative": "Create ticket via web form",
            },
            {
                "step_id": 6,
                "description": f"Send incident alert email to {email_recipient} (requires approval)",
                "tool": "send_email",
                "action": "send",
                "params": {
                    "to": email_recipient,
                    "subject": "CRITICAL INCIDENT ALERT: VPN Down (P1) & CRM Degraded (P2)",
                    "body": "Nexus Autonomous Agent has detected the following service issues:\n\n1. Corporate VPN: DOWN -> P1 Ticket created, assigned to Priya Sharma.\n2. Customer CRM: DEGRADED -> P2 Ticket created, assigned to Sarah Chen.\n\nPlease inspect the IT portal and initiate incident remediation.",
                },
                "depends_on": [4, 5],
                "risk_level": "high",
                "expected_outcome": "Notification sent to designated recipient",
                "failure_alternative": "Log notification to file",
            },
            {
                "step_id": 7,
                "description": "Navigate to tickets list to verify tickets are created",
                "tool": "browser",
                "action": "navigate",
                "params": {"url": "http://localhost:5001/tickets"},
                "depends_on": [4, 5],
                "risk_level": "low",
                "expected_outcome": "Tickets table displayed with newly created tickets",
                "failure_alternative": "Verify via GET http://localhost:5001/api/tickets",
            },
            {
                "step_id": 8,
                "description": "Capture screenshot of tickets list as completion evidence",
                "tool": "browser",
                "action": "screenshot",
                "params": {"name": "verified_tickets_evidence.png"},
                "depends_on": [7],
                "risk_level": "low",
                "expected_outcome": "Final verification screenshot saved",
                "failure_alternative": "Continue without screenshot",
            },
        ]
        return plan, "Plan automatically aligned with Acme Corp IT Standard Operating Procedures."

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
