import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.bugfixer import EvoFixerAgent

def test_extract_crash_context():
    client = MagicMock()
    fixer = EvoFixerAgent(client)
    
    test_results = {
        "crash_tests": [1],
        "test_outputs": [
            {"id": 0, "status": "pass", "error": None},
            {"id": 1, "status": "crash", "error": "IndexError: list index out of range at line 4"}
        ]
    }
    problem_tests = [
        {"id": 0, "input": [1, 2], "expected": 3},
        {"id": 1, "input": [], "expected": 0}
    ]
    
    ctx = fixer._extract_crash_context(test_results, problem_tests)
    assert "[Test 1]" in ctx
    assert "Input: []" in ctx
    assert "IndexError: list index out of range at line 4" in ctx

def test_extract_code_from_markdown():
    client = MagicMock()
    fixer = EvoFixerAgent(client)
    
    py_response = "Here is the fix:\n```python\ndef solve():\n    return 42\n```\nHope it helps!"
    extracted = fixer._extract_code_from_response(py_response, "Python")
    assert extracted == "def solve():\n    return 42"

    raw_response = "def solve():\n    return 42"
    extracted_raw = fixer._extract_code_from_response(raw_response, "Python")
    assert extracted_raw == "def solve():\n    return 42"

@pytest.mark.asyncio
async def test_fix_no_crashes_returns_none():
    client = MagicMock()
    fixer = EvoFixerAgent(client)
    
    test_results = {"crash_tests": []}
    res = await fixer.fix("code", test_results, {}, "Python")
    assert res is None

@pytest.mark.asyncio
async def test_fix_success():
    client = MagicMock()
    client.create_completion = AsyncMock(return_value={
        "content": "```python\ndef two_sum(nums, target):\n    if not nums: return []\n    return [0, 1]\n```"
    })
    fixer = EvoFixerAgent(client)
    
    broken_code = "def two_sum(nums, target):\n    return nums[10]"
    test_results = {
        "crash_tests": [0],
        "test_outputs": [{"id": 0, "status": "crash", "error": "IndexError: list index out of range"}]
    }
    problem = {
        "title": "Two Sum",
        "function_signature": "def two_sum(nums: list[int], target: int) -> list[int]:",
        "tests": [{"id": 0, "input": [1], "expected": []}]
    }
    
    fixed = await fixer.fix(broken_code, test_results, problem, "Python")
    assert fixed is not None
    assert "if not nums: return []" in fixed
    client.create_completion.assert_awaited_once()

@pytest.mark.asyncio
async def test_fix_identical_code_returns_none():
    client = MagicMock()
    broken_code = "def two_sum(nums, target):\n    return nums[10]"
    client.create_completion = AsyncMock(return_value={
        "content": broken_code
    })
    fixer = EvoFixerAgent(client)
    test_results = {
        "crash_tests": [0],
        "test_outputs": [{"id": 0, "status": "crash", "error": "IndexError"}]
    }
    fixed = await fixer.fix(broken_code, test_results, {"tests": []}, "Python")
    assert fixed is None
