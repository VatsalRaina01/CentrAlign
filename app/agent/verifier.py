"""
Verifier - Outcome verification.

After all steps are complete, the verifier:
1. Reviews the execution history
2. Determines if the original goal was achieved
3. Identifies any missing items
4. Generates evidence and a summary
"""

import json
import logging
from app.llm.client import LLMClient

logger = logging.getLogger(__name__)


VERIFY_PROMPT = """You are an autonomous AI task worker verifying whether the requested task was completed successfully.

## Original User Request
{original_input}

## Goal Analysis
{goal}

## Execution Summary
{execution_summary}

## Context Variables (Discovered Information)
{context_variables}

## Screenshots Taken
{screenshots}

Review the execution and determine if the task was completed. Respond in JSON:
{{
    "verified": true/false,
    "confidence": 0.0 to 1.0,
    "evidence": {{
        "completed_items": ["List of things that were successfully done"],
        "screenshots": ["Paths of relevant screenshots"],
        "data_collected": {{"key": "value pairs of collected data"}}
    }},
    "missing_items": ["List of things that were NOT done or could not be verified"],
    "summary": "A clear, concise summary of what was accomplished for the user",
    "recommendations": ["Any follow-up actions the user should take"]
}}

Be honest about what was and wasn't verified. Only mark as verified if there's evidence."""


class Verifier:
    """Checks whether the overall goal was achieved."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def verify_outcome(
        self,
        original_input: str,
        goal: dict,
        execution_summary: str,
        context_variables: dict,
        screenshots: list[str],
    ) -> dict:
        """
        Determine if the requested outcome was achieved.

        Returns dict with:
        - verified: Whether the outcome was confirmed
        - confidence: 0.0 to 1.0 confidence score
        - evidence: Proof of completion
        - missing_items: What wasn't completed
        - summary: Human-readable summary
        - recommendations: Follow-up suggestions
        """
        prompt = VERIFY_PROMPT.format(
            original_input=original_input,
            goal=json.dumps(goal, indent=2),
            execution_summary=execution_summary,
            context_variables=json.dumps(context_variables, indent=2, default=str),
            screenshots=json.dumps(screenshots),
        )

        messages = [
            {"role": "system", "content": "You are a precise verification AI. Always respond in valid JSON."},
            {"role": "user", "content": prompt},
        ]

        try:
            result = self.llm.chat_json(messages)
            verified = result.get("verified", False)
            confidence = result.get("confidence", 0.0)
            logger.info(
                f"Verification: {'✅ PASSED' if verified else '❌ FAILED'} "
                f"(confidence: {confidence:.1%})"
            )
            return result
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return {
                "verified": False,
                "confidence": 0.0,
                "evidence": {},
                "missing_items": ["Verification process itself failed"],
                "summary": "Unable to verify outcome due to an error.",
                "recommendations": ["Please review the execution logs manually."],
            }
