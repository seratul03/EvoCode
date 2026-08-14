import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from baseline.baseline_pipeline import BaselinePipeline
from harness.evaluator import Task

@pytest.fixture
def mock_task():
    return Task(
        instance_id="test-1",
        setup_script="echo setup",
        test_command="pytest",
        gold_patch="",
        target_file="test.py"
    )

@pytest.mark.asyncio
async def test_baseline_pass_first_try(mock_task):
    pipeline = BaselinePipeline(max_iterations=3)
    pipeline.agent.run = AsyncMock(return_value={"patch": "patch1", "raw_content": "raw1"})
    
    # Mock evaluator to pass immediately
    pipeline.evaluator.evaluate = MagicMock(return_value={"success": True, "log": "OK"})
    
    result = await pipeline.run_task(mock_task, "Title", "Body", "Context")
    
    assert result["status"] == "PASS"
    assert result["iterations"] == 1
    assert pipeline.agent.run.call_count == 1

@pytest.mark.asyncio
async def test_baseline_fail_max_iterations(mock_task):
    pipeline = BaselinePipeline(max_iterations=3)
    pipeline.agent.run = AsyncMock(return_value={"patch": "patch1", "raw_content": "raw1"})
    
    # Mock evaluator to always fail
    pipeline.evaluator.evaluate = MagicMock(return_value={"success": False, "log": "ERROR"})
    
    result = await pipeline.run_task(mock_task, "Title", "Body", "Context")
    
    assert result["status"] == "FAIL"
    assert result["iterations"] == 3
    assert pipeline.agent.run.call_count == 3
