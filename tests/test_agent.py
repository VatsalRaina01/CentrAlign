"""
Basic tests for the Nexus agent system.
"""

import pytest
import asyncio
import json
import os

# Test tool imports
from app.tools.base import ToolResult, RiskLevel
from app.tools.file_tool import FileTool
from app.tools.api_tool import APITool
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.memory.execution_log import ExecutionLog
from app.agent.recovery import RecoveryManager
from app.agent.approval import ApprovalGate


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_success_result(self):
        result = ToolResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_failure_result(self):
        result = ToolResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_to_dict(self):
        result = ToolResult(success=True, data="test data")
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == "test data"

    def test_summary(self):
        success = ToolResult(success=True, data="worked")
        assert "✅" in success.summary()

        failure = ToolResult(success=False, error="broken")
        assert "❌" in failure.summary()


class TestFileTool:
    """Test file operations tool."""

    @pytest.mark.asyncio
    async def test_list_directory(self):
        tool = FileTool()
        result = await tool.execute(action="list", path=".")
        assert result.success is True
        assert isinstance(result.data, list)

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        tool = FileTool()
        result = await tool.execute(action="read", path="nonexistent_file.txt")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_write_and_read(self):
        tool = FileTool()
        test_path = "execution_logs/test_file.txt"
        
        # Write
        write_result = await tool.execute(
            action="write", path=test_path, content="Hello Nexus"
        )
        assert write_result.success is True
        
        # Read back
        read_result = await tool.execute(action="read", path=test_path)
        assert read_result.success is True
        assert "Hello Nexus" in read_result.data
        
        # Cleanup
        os.remove(test_path)

    def test_schema(self):
        tool = FileTool()
        schema = tool.get_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "file_operations"

    def test_risk_level(self):
        tool = FileTool()
        assert tool.risk_level == RiskLevel.LOW


class TestShortTermMemory:
    """Test short-term memory."""

    def test_reset(self):
        mem = ShortTermMemory()
        mem.reset("test-123", "Check services")
        assert mem.task_id == "test-123"
        assert mem.original_input == "Check services"
        assert mem.status == "planning"

    def test_add_step_result(self):
        mem = ShortTermMemory()
        mem.reset("test-123", "Test task")
        mem.add_step_result(
            step_id=0,
            description="Navigate to portal",
            tool="browser",
            params={"url": "http://localhost:5001"},
            success=True,
            data={"title": "Dashboard"},
        )
        assert len(mem.executed_steps) == 1
        assert mem.executed_steps[0].result_success is True

    def test_context_variables(self):
        mem = ShortTermMemory()
        mem.reset("test-123", "Test")
        mem.update_variable("vpn_status", "down")
        mem.update_variable("crm_status", "degraded")
        assert mem.context_variables["vpn_status"] == "down"
        assert len(mem.context_variables) == 2

    def test_context_summary(self):
        mem = ShortTermMemory()
        mem.reset("test-123", "Check services")
        summary = mem.get_context_summary()
        assert "Check services" in summary

    def test_to_dict(self):
        mem = ShortTermMemory()
        mem.reset("test-123", "Test")
        d = mem.to_dict()
        assert d["task_id"] == "test-123"


class TestLongTermMemory:
    """Test long-term memory."""

    def test_load(self):
        mem = LongTermMemory()
        mem.load()
        # Should load without error even if files don't exist
        assert mem._loaded is True

    def test_company_context(self):
        mem = LongTermMemory()
        mem.load()
        context = mem.get_company_context()
        assert isinstance(context, str)
        # Should have some content if knowledge files exist
        if os.path.exists("company_knowledge/company_info.json"):
            assert "Acme Corp" in context


class TestExecutionLog:
    """Test execution log."""

    def test_log_events(self):
        log = ExecutionLog()
        log.reset("test-123")
        log.log("TEST_EVENT", "Something happened")
        assert len(log.entries) == 1
        assert log.entries[0]["event_type"] == "TEST_EVENT"

    def test_tool_call_logging(self):
        log = ExecutionLog()
        log.reset("test-123")
        log.log_tool_call("browser", {"url": "http://example.com"}, True, "OK")
        assert len(log.entries) == 1
        assert log.entries[0]["details"]["tool"] == "browser"

    def test_summary(self):
        log = ExecutionLog()
        log.reset("test-123")
        log.log("EVENT_1", "First")
        log.log("EVENT_2", "Second")
        summary = log.get_summary()
        assert "2 entries" in summary


class TestRecoveryManager:
    """Test recovery manager."""

    def test_first_failure_retries(self):
        rm = RecoveryManager()
        rm.reset()
        result = rm.handle_failure(
            {"step_id": 0, "description": "Navigate"}, "Connection timeout"
        )
        assert result["action"] == "retry"

    def test_max_retries_exceeded(self):
        rm = RecoveryManager()
        rm.reset()
        # Exhaust retries
        for _ in range(4):
            result = rm.handle_failure(
                {"step_id": 0, "description": "Navigate", "failure_alternative": ""},
                "Error"
            )
        assert result["action"] == "ask_human"

    def test_alternative_after_retries(self):
        rm = RecoveryManager()
        rm.reset()
        step = {
            "step_id": 0,
            "description": "Navigate",
            "failure_alternative": "Use API instead",
        }
        for _ in range(4):
            result = rm.handle_failure(step, "Error")
        assert result["action"] == "alternative"


class TestApprovalGate:
    """Test approval gate."""

    def test_auto_approve_low_risk(self):
        gate = ApprovalGate()
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            gate.check_approval({"step_id": 0, "description": "Read file"}, RiskLevel.LOW)
        )
        loop.close()
        assert result[0] is True  # approved

    def test_risk_level_detection(self):
        gate = ApprovalGate()
        
        # Email should be HIGH
        risk = gate.get_risk_level_for_step(
            {"tool": "send_email"}, RiskLevel.MEDIUM
        )
        assert risk == RiskLevel.HIGH
        
        # Browser submit should be HIGH
        risk = gate.get_risk_level_for_step(
            {"tool": "browser", "action": "click", "description": "Submit the form"},
            RiskLevel.MEDIUM
        )
        assert risk == RiskLevel.HIGH


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
