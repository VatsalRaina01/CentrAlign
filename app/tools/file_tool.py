"""
File Tool - Local file system operations.

Allows the agent to:
- Read file contents
- Write/create files
- List directory contents
- Search for files by name or content
"""

import os
import logging
from pathlib import Path
from app.tools.base import BaseTool, ToolResult, RiskLevel

logger = logging.getLogger(__name__)

# Restrict file operations to safe directories
ALLOWED_DIRECTORIES = [
    os.path.abspath("company_knowledge"),
    os.path.abspath("execution_logs"),
    os.path.abspath("screenshots"),
    os.path.abspath("workspace"),
]


class FileTool(BaseTool):
    """File system operations tool."""

    @property
    def name(self) -> str:
        return "file_operations"

    @property
    def description(self) -> str:
        return (
            "Read, write, list, and search files on the local system. "
            "Restricted to safe directories (company_knowledge, execution_logs, workspace)."
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "file_operations",
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["read", "write", "list", "search"],
                            "description": "The file operation to perform.",
                        },
                        "path": {
                            "type": "string",
                            "description": "File or directory path (relative to project root).",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write (for 'write' action).",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query for file names or content (for 'search' action).",
                        },
                    },
                    "required": ["action"],
                },
            },
        }

    def _is_safe_path(self, path: str) -> bool:
        """Check if the path is within allowed directories."""
        abs_path = os.path.abspath(path)
        return any(abs_path.startswith(d) for d in ALLOWED_DIRECTORIES)

    async def execute(self, **kwargs) -> ToolResult:
        """Execute a file operation."""
        action = kwargs.get("action")

        action_map = {
            "read": self._read,
            "write": self._write,
            "list": self._list,
            "search": self._search,
        }

        handler = action_map.get(action)
        if not handler:
            return ToolResult(success=False, error=f"Unknown action: {action}")

        return await handler(**kwargs)

    async def _read(self, **kwargs) -> ToolResult:
        """Read file contents."""
        path = kwargs.get("path")
        if not path:
            return ToolResult(success=False, error="No path provided")

        try:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                return ToolResult(success=False, error=f"File not found: {path}")

            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Truncate very large files
            if len(content) > 10000:
                content = content[:10000] + "\n... [truncated]"

            return ToolResult(
                success=True,
                data=content,
                metadata={"path": abs_path, "size": os.path.getsize(abs_path)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Read failed: {str(e)}")

    async def _write(self, **kwargs) -> ToolResult:
        """Write content to a file."""
        path = kwargs.get("path")
        content = kwargs.get("content", "")

        if not path:
            return ToolResult(success=False, error="No path provided")

        try:
            abs_path = os.path.abspath(path)

            # Create parent directories if needed
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                success=True,
                data={"written_to": abs_path, "bytes": len(content)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Write failed: {str(e)}")

    async def _list(self, **kwargs) -> ToolResult:
        """List directory contents."""
        path = kwargs.get("path", ".")

        try:
            abs_path = os.path.abspath(path)
            if not os.path.isdir(abs_path):
                return ToolResult(success=False, error=f"Not a directory: {path}")

            entries = []
            for entry in os.listdir(abs_path):
                full_path = os.path.join(abs_path, entry)
                entries.append({
                    "name": entry,
                    "type": "directory" if os.path.isdir(full_path) else "file",
                    "size": os.path.getsize(full_path) if os.path.isfile(full_path) else None,
                })

            return ToolResult(
                success=True,
                data=entries,
                metadata={"directory": abs_path, "count": len(entries)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"List failed: {str(e)}")

    async def _search(self, **kwargs) -> ToolResult:
        """Search for files by name or content."""
        query = kwargs.get("query", "")
        path = kwargs.get("path", ".")

        if not query:
            return ToolResult(success=False, error="No search query provided")

        try:
            abs_path = os.path.abspath(path)
            results = []

            for root, dirs, files in os.walk(abs_path):
                for file in files:
                    filepath = os.path.join(root, file)
                    # Search in filename
                    if query.lower() in file.lower():
                        results.append({
                            "path": filepath,
                            "match_type": "filename",
                        })
                    # Search in content for text files
                    elif file.endswith((".json", ".txt", ".md", ".csv", ".log")):
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                content = f.read()
                                if query.lower() in content.lower():
                                    results.append({
                                        "path": filepath,
                                        "match_type": "content",
                                    })
                        except (UnicodeDecodeError, PermissionError):
                            pass

                    if len(results) >= 20:
                        break

            return ToolResult(
                success=True,
                data=results,
                metadata={"query": query, "matches": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Search failed: {str(e)}")
