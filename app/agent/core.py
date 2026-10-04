"""
Agent Core - Main orchestration loop.

This is the heart of Nexus. It implements the full agent loop:
Goal → Understand → Plan → Execute → Observe → Adapt → Verify → Complete

The core coordinates all components:
- Planner: Understands goals and creates plans
- Executor: Dispatches steps to tools
- Observer: Analyzes results
- Verifier: Confirms outcomes
- RecoveryManager: Handles failures
- ApprovalGate: Human-in-the-loop
- Memory: Short-term (task) and long-term (company)
- ExecutionLog: Audit trail
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator

from app.llm.client import LLMClient
from app.agent.planner import Planner
from app.agent.executor import Executor
from app.agent.observer import Observer
from app.agent.verifier import Verifier
from app.agent.recovery import RecoveryManager
from app.agent.approval import ApprovalGate
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.memory.execution_log import ExecutionLog
from app.tools.base import BaseTool, RiskLevel
from app.tools.browser_tool import BrowserTool
from app.tools.file_tool import FileTool
from app.tools.api_tool import APITool
from app.tools.email_tool import EmailTool
from app.config import settings

logger = logging.getLogger(__name__)


class AgentCore:
    """
    Main agent loop orchestrator.

    Implements: Goal → Understand → Plan → Execute → Observe → Adapt → Verify → Complete
    """

    def __init__(self):
        # LLM
        self.llm = LLMClient()

        # Tools
        self.tools: dict[str, BaseTool] = {
            "browser": BrowserTool(),
            "file_operations": FileTool(),
            "api_request": APITool(),
            "send_email": EmailTool(),
        }

        # Agent components
        self.planner = Planner(self.llm)
        self.executor = Executor(self.tools)
        self.observer = Observer(self.llm)
        self.verifier = Verifier(self.llm)
        self.recovery = RecoveryManager()
        self.approval = ApprovalGate()

        # Memory
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.execution_log = ExecutionLog()

        # Status callback for UI updates
        self._status_callback = None

    def set_status_callback(self, callback):
        """Set callback for sending status updates to the UI."""
        self._status_callback = callback

    def set_approval_callback(self, callback):
        """Set callback for approval requests."""
        self.approval.set_approval_callback(callback)

    async def _emit_status(self, event_type: str, data: dict):
        """Send a status update to the UI."""
        if self._status_callback:
            await self._status_callback({
                "type": event_type,
                "timestamp": datetime.now().isoformat(),
                **data,
            })

    async def run(self, user_input: str) -> dict:
        """
        Process a user task through the full agent loop.

        Args:
            user_input: Natural language task description.

        Returns:
            Final result dict with summary, evidence, verification status.
        """
        # Initialize for new task
        task_id = str(uuid.uuid4())[:8]
        self.short_term.reset(task_id, user_input)
        self.execution_log.reset(task_id)
        self.recovery.reset()

        self.execution_log.log("TASK_START", f"New task: {user_input}")
        await self._emit_status("task_start", {"task_id": task_id, "input": user_input})

        try:
            # ──────────────────────────────────────
            # PHASE 1: UNDERSTAND THE GOAL
            # ──────────────────────────────────────
            await self._emit_status("phase", {"phase": "understanding", "message": "🧠 Understanding your request..."})

            # Load company context
            self.long_term.load()
            company_context = self.long_term.get_company_context()
            tools_description = self.executor.get_available_tools_description()

            # Understand the goal
            goal = self.planner.understand_goal(user_input, company_context, tools_description)
            self.short_term.goal = goal
            self.execution_log.log("GOAL_UNDERSTOOD", f"Goal: {goal.get('goal', '')}")

            await self._emit_status("goal", {
                "goal": goal.get("goal", ""),
                "sub_goals": goal.get("sub_goals", []),
                "urgency": goal.get("urgency", "medium"),
            })

            # Check if clarification is needed
            if goal.get("needs_clarification"):
                await self._emit_status("clarification_needed", {
                    "question": goal.get("clarification_question", "Could you provide more details?"),
                })
                # In a full implementation, we'd wait for user response
                # For prototype, we proceed with best effort

            # ──────────────────────────────────────
            # PHASE 2: CREATE THE PLAN
            # ──────────────────────────────────────
            await self._emit_status("phase", {"phase": "planning", "message": "📋 Creating execution plan..."})

            plan, reasoning = self.planner.create_plan(
                goal, company_context, tools_description,
                self.short_term.context_variables,
            )
            self.short_term.plan = plan
            self.short_term.status = "executing"
            self.execution_log.log_planning(plan)

            await self._emit_status("plan", {
                "steps": plan,
                "reasoning": reasoning,
                "total_steps": len(plan),
            })

            # ──────────────────────────────────────
            # PHASE 3: EXECUTE THE PLAN
            # ──────────────────────────────────────
            await self._emit_status("phase", {"phase": "executing", "message": "⚡ Executing plan..."})

            step_index = 0
            max_steps = settings.MAX_STEPS

            while step_index < len(plan) and step_index < max_steps:
                step = plan[step_index]
                step_id = step.get("step_id", step_index)

                await self._emit_status("step_start", {
                    "step_id": step_id,
                    "step_index": step_index + 1,
                    "total_steps": len(plan),
                    "description": step.get("description", ""),
                    "tool": step.get("tool", ""),
                })

                # ── 3a: CHECK TOOL & APPROVAL ──
                tool_name = step.get("tool", "")
                tool = self.tools.get(tool_name)

                # Skip non-executable / informational steps without asking approval
                if not tool:
                    logger.warning(f"Step {step_id} has non-executable tool '{tool_name}'. Skipping.")
                    await self._emit_status("step_skipped", {
                        "step_id": step_id,
                        "reason": f"Non-executable step: {step.get('description', '')}",
                    })
                    self.short_term.add_observation(
                        f"Informational note: {step.get('description', '')}"
                    )
                    step_index += 1
                    continue

                tool_risk = tool.risk_level
                effective_risk = self.approval.get_risk_level_for_step(step, tool_risk)

                if effective_risk in (RiskLevel.MEDIUM, RiskLevel.HIGH):
                    await self._emit_status("approval_check", {
                        "step_id": step_id,
                        "description": step.get("description", ""),
                        "risk_level": effective_risk.value,
                    })

                approved, approval_reason = await self.approval.check_approval(step, effective_risk)
                self.execution_log.log_approval(step.get("description", ""), approved, approval_reason)

                if not approved:
                    await self._emit_status("step_skipped", {
                        "step_id": step_id,
                        "reason": f"Not approved: {approval_reason}",
                    })
                    self.short_term.add_observation(
                        f"Step {step_id} skipped (not approved): {approval_reason}"
                    )
                    step_index += 1
                    continue

                # ── 3b: EXECUTE THE STEP ──
                result = await self.executor.execute_step(
                    step, self.short_term.context_variables,
                )

                # Log the execution
                self.execution_log.log_tool_call(
                    step.get("tool", ""),
                    step.get("params", {}),
                    result.success,
                    str(result.data)[:500] if result.data else None,
                    result.error,
                )

                self.short_term.add_step_result(
                    step_id=step_id,
                    description=step.get("description", ""),
                    tool=step.get("tool", ""),
                    params=step.get("params", {}),
                    success=result.success,
                    data=result.data,
                    error=result.error,
                    screenshot_path=result.screenshot_path,
                )

                # ── 3c: OBSERVE THE RESULT ──
                remaining_steps = plan[step_index + 1:]
                observation = self.observer.analyze_result(
                    step, result,
                    self.short_term.get_context_summary(),
                    remaining_steps,
                )

                # Update context with extracted data
                extracted_data = observation.get("extracted_data", {})
                for key, value in extracted_data.items():
                    self.short_term.update_variable(key, value)

                self.short_term.add_observation(
                    observation.get("observation", "No observation")
                )

                await self._emit_status("step_complete", {
                    "step_id": step_id,
                    "success": result.success,
                    "observation": observation.get("observation", ""),
                    "screenshot": result.screenshot_path,
                    "extracted_data": extracted_data,
                })

                # ── 3d: HANDLE FAILURE / ADAPT ──
                if not result.success:
                    recovery = self.recovery.handle_failure(step, result.error or "Unknown error")
                    self.execution_log.log_recovery(
                        result.error or "Unknown error",
                        recovery["action"],
                    )

                    await self._emit_status("recovery", {
                        "action": recovery["action"],
                        "message": recovery["message"],
                    })

                    if recovery["action"] == "retry":
                        # Don't advance step_index — retry same step
                        plan[step_index] = recovery["modified_step"]
                        await asyncio.sleep(1)  # Brief pause before retry
                        continue

                    elif recovery["action"] == "alternative":
                        plan[step_index] = recovery["modified_step"]
                        continue

                    elif recovery["action"] in ("ask_human", "skip"):
                        await self._emit_status("human_help_needed", {
                            "message": recovery["message"],
                            "step": step,
                        })
                        # Skip and continue to next step
                        step_index += 1
                        continue

                    elif recovery["action"] == "abort":
                        self.short_term.status = "failed"
                        break

                # Check if replanning is needed
                if observation.get("needs_replanning"):
                    await self._emit_status("phase", {
                        "phase": "replanning",
                        "message": f"🔄 Adjusting plan: {observation.get('replanning_reason', '')}",
                    })

                    completed = [s.to_dict() for s in self.short_term.executed_steps]
                    new_plan, new_reasoning = self.planner.replan(
                        plan, completed, step, result.error or "",
                        self.short_term.get_context_summary(),
                    )
                    plan = new_plan
                    self.short_term.plan = plan
                    step_index = 0  # Start from the beginning of new plan
                    continue

                step_index += 1

            # ──────────────────────────────────────
            # PHASE 4: VERIFY THE OUTCOME
            # ──────────────────────────────────────
            await self._emit_status("phase", {"phase": "verifying", "message": "🔍 Verifying outcome..."})
            self.short_term.status = "verifying"

            verification = self.verifier.verify_outcome(
                original_input=user_input,
                goal=self.short_term.goal,
                execution_summary=self.execution_log.get_summary(),
                context_variables=self.short_term.context_variables,
                screenshots=self.short_term.get_all_screenshots(),
            )

            self.execution_log.log_verification(
                verification.get("verified", False),
                verification.get("evidence", {}),
            )

            # ──────────────────────────────────────
            # PHASE 5: COMPLETE
            # ──────────────────────────────────────
            self.short_term.status = "complete"

            # Save execution log
            log_path = self.execution_log.save_to_file()

            # Save task outcome to long-term memory
            self.long_term.save_task_outcome({
                "task": user_input,
                "goal": self.short_term.goal.get("goal", ""),
                "verified": verification.get("verified", False),
                "summary": verification.get("summary", ""),
                "steps_executed": len(self.short_term.executed_steps),
                "steps_failed": len(self.short_term.get_failed_steps()),
            })

            # Build final result
            final_result = {
                "task_id": task_id,
                "status": "complete",
                "verified": verification.get("verified", False),
                "confidence": verification.get("confidence", 0.0),
                "summary": verification.get("summary", "Task processing complete."),
                "evidence": verification.get("evidence", {}),
                "missing_items": verification.get("missing_items", []),
                "recommendations": verification.get("recommendations", []),
                "screenshots": self.short_term.get_all_screenshots(),
                "execution_log_path": log_path,
                "steps_executed": len(self.short_term.executed_steps),
                "steps_failed": len(self.short_term.get_failed_steps()),
                "context_variables": self.short_term.context_variables,
            }

            await self._emit_status("task_complete", final_result)

            self.execution_log.log("TASK_COMPLETE", verification.get("summary", "Done"))
            return final_result

        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            self.short_term.status = "failed"
            self.execution_log.log("TASK_ERROR", str(e))

            error_result = {
                "task_id": task_id,
                "status": "error",
                "verified": False,
                "summary": f"Task failed with error: {str(e)}",
                "error": str(e),
            }

            await self._emit_status("task_error", error_result)
            return error_result

    async def cleanup(self):
        """Clean up resources (browser, etc.)."""
        for tool in self.tools.values():
            await tool.cleanup()
        logger.info("Agent cleanup complete")

    def submit_approval(self, step_id: int, approved: bool, reason: str = ""):
        """Submit an approval decision from the UI."""
        self.approval.submit_approval(step_id, approved, reason)
