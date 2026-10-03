"""
Recovery Manager - Failure handling and retries.

When a step fails, the recovery manager decides:
1. Retry the same action
2. Try an alternative approach
3. Ask the human for guidance
4. Abort the task
"""

import logging
from app.config import settings

logger = logging.getLogger(__name__)


class RecoveryManager:
    """Handles failures with retries and alternatives."""

    def __init__(self):
        self.max_retries = settings.MAX_RETRIES
        self.attempt_counts: dict[int, int] = {}  # step_id → attempt count

    def reset(self):
        """Reset attempt counts for a new task."""
        self.attempt_counts = {}

    def handle_failure(
        self,
        step: dict,
        error: str,
    ) -> dict:
        """
        Decide how to handle a step failure.

        Returns:
            dict with:
            - action: "retry" | "alternative" | "ask_human" | "skip" | "abort"
            - modified_step: Modified step dict (for retry/alternative)
            - message: Human-readable explanation
        """
        step_id = step.get("step_id", 0)
        attempts = self.attempt_counts.get(step_id, 0) + 1
        self.attempt_counts[step_id] = attempts

        description = step.get("description", "Unknown step")
        failure_alt = step.get("failure_alternative", "")

        logger.warning(
            f"Handling failure for step {step_id} (attempt {attempts}/{self.max_retries}): {error}"
        )

        # Check if we've exceeded max retries
        if attempts > self.max_retries:
            if failure_alt:
                # Try the alternative approach
                logger.info(f"Max retries exceeded, trying alternative: {failure_alt}")
                return {
                    "action": "alternative",
                    "modified_step": {
                        **step,
                        "description": f"[ALTERNATIVE] {failure_alt}",
                        "step_id": step_id,
                    },
                    "message": f"Step '{description}' failed after {self.max_retries} retries. "
                               f"Trying alternative: {failure_alt}",
                }
            else:
                # Ask for human help
                return {
                    "action": "ask_human",
                    "modified_step": None,
                    "message": f"Step '{description}' failed after {self.max_retries} retries. "
                               f"Error: {error}. Human guidance needed.",
                }

        # Determine retry strategy based on error type
        if self._is_transient_error(error):
            return {
                "action": "retry",
                "modified_step": step,
                "message": f"Transient error on step '{description}' "
                           f"(attempt {attempts}/{self.max_retries}). Retrying...",
            }
        elif self._is_not_found_error(error):
            # Modify selector or approach
            return {
                "action": "retry",
                "modified_step": step,
                "message": f"Element/resource not found for step '{description}' "
                           f"(attempt {attempts}/{self.max_retries}). Retrying with modified approach...",
            }
        else:
            # Unknown error - retry with decreasing confidence
            return {
                "action": "retry",
                "modified_step": step,
                "message": f"Step '{description}' failed: {error}. "
                           f"Retrying (attempt {attempts}/{self.max_retries})...",
            }

    def _is_transient_error(self, error: str) -> bool:
        """Check if error is likely transient (network, timeout, etc.)."""
        transient_patterns = [
            "timeout", "timed out", "connection", "network",
            "temporary", "503", "502", "429", "rate limit",
        ]
        error_lower = error.lower()
        return any(pattern in error_lower for pattern in transient_patterns)

    def _is_not_found_error(self, error: str) -> bool:
        """Check if error is about a missing element/resource."""
        not_found_patterns = [
            "not found", "no element", "selector", "404",
            "element not", "unable to find", "does not exist",
        ]
        error_lower = error.lower()
        return any(pattern in error_lower for pattern in not_found_patterns)
