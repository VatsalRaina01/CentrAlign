"""
Long-Term Memory - Persistent company knowledge.

Loads and serves company-specific context from JSON files:
- Company information (name, departments, contacts)
- IT services and their details
- Standard operating procedures
- Escalation policies
- Past task outcomes (learned from previous executions)
"""

import json
import os
import logging
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)


class LongTermMemory:
    """Persistent company knowledge loaded from JSON files."""

    def __init__(self):
        self.knowledge_dir = settings.KNOWLEDGE_DIR
        self.company_info: dict = {}
        self.services: dict = {}
        self.procedures: dict = {}
        self.escalation_policy: dict = {}
        self.past_tasks: list[dict] = []
        self._loaded = False

    def load(self):
        """Load all knowledge files from disk."""
        if self._loaded:
            return

        os.makedirs(self.knowledge_dir, exist_ok=True)

        self.company_info = self._load_json("company_info.json")
        self.services = self._load_json("services.json")
        self.procedures = self._load_json("procedures.json")
        self.escalation_policy = self._load_json("escalation_policy.json")
        self.past_tasks = self._load_json("past_tasks.json")

        if not isinstance(self.past_tasks, list):
            self.past_tasks = []

        self._loaded = True
        logger.info(f"Long-term memory loaded from {self.knowledge_dir}")

    def _load_json(self, filename: str) -> dict | list:
        """Load a single JSON file."""
        filepath = os.path.join(self.knowledge_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in {filepath}")
                return {}
        return {}

    def _save_json(self, filename: str, data):
        """Save data to a JSON file."""
        filepath = os.path.join(self.knowledge_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def get_company_context(self) -> str:
        """Get a formatted string of all company knowledge for LLM prompts."""
        self.load()

        parts = []

        if self.company_info:
            parts.append(f"## Company Information\n{json.dumps(self.company_info, indent=2)}")

        if self.services:
            parts.append(f"## IT Services\n{json.dumps(self.services, indent=2)}")

        if self.procedures:
            parts.append(f"## Standard Operating Procedures\n{json.dumps(self.procedures, indent=2)}")

        if self.escalation_policy:
            parts.append(f"## Escalation Policy\n{json.dumps(self.escalation_policy, indent=2)}")

        if self.past_tasks:
            recent = self.past_tasks[-5:]  # Last 5 tasks
            parts.append(f"## Recent Task History\n{json.dumps(recent, indent=2)}")

        return "\n\n".join(parts) if parts else "No company knowledge available."

    def get_relevant_procedures(self, task_type: str) -> dict:
        """Get procedures relevant to a specific task type."""
        self.load()
        if isinstance(self.procedures, dict):
            # Try to find matching procedure
            for key, proc in self.procedures.items():
                if task_type.lower() in key.lower():
                    return proc
        return {}

    def save_task_outcome(self, task_summary: dict):
        """Save a completed task outcome for future reference."""
        self.load()
        task_summary["completed_at"] = datetime.now().isoformat()
        self.past_tasks.append(task_summary)
        # Keep only last 50 tasks
        if len(self.past_tasks) > 50:
            self.past_tasks = self.past_tasks[-50:]
        self._save_json("past_tasks.json", self.past_tasks)
        logger.info(f"Task outcome saved: {task_summary.get('task', 'unknown')}")

    def get_team_contacts(self, department: str = "") -> list[dict]:
        """Get team contacts, optionally filtered by department."""
        self.load()
        contacts = self.company_info.get("it_team", [])
        if department:
            contacts = [
                c for c in contacts
                if department.lower() in c.get("role", "").lower()
                or department.lower() in c.get("department", "").lower()
            ]
        return contacts
