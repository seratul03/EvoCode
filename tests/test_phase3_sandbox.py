import os
import shutil
import pytest
from src.sandbox import Sandbox

@pytest.fixture(autouse=True)
def clean_workspaces():
    """Ensure workspaces are clean before and after tests."""
    ws_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspaces")
    if os.path.exists(ws_dir):
        shutil.rmtree(ws_dir)
    yield
    if os.path.exists(ws_dir):
        shutil.rmtree(ws_dir)

def test_sandbox_creates_persistent_workspace():
    sandbox = Sandbox(timeout_seconds=5)
    code = "def solve(x):\n    return x * 2"
    tests = [{"id": 1, "input": "solve(2)", "expected": "4"}]
    
    # Run sandbox targeting EVO_PY workspace
    res = sandbox.run(code, tests, language="Python", agent_id="EVO_PY")
    assert res["passed_tests"] == 1
    
    # Verify workspaces/EVO_PY exists and contains solution.py
    workspace_dir = os.path.abspath(os.path.join("workspaces", "EVO_PY"))
    assert os.path.exists(workspace_dir)
    assert os.path.isdir(workspace_dir)
    
    solution_path = os.path.join(workspace_dir, "solution.py")
    assert os.path.exists(solution_path)
    
    with open(solution_path, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "def solve(x):" in content
        assert "# === INJECTED TEST HARNESS ===" in content

def test_sandbox_cross_agent_isolation():
    sandbox = Sandbox(timeout_seconds=5)
    
    # Run Python code in EVO_PY
    code1 = "def solve(x):\n    return x + 1"
    sandbox.run(code1, [{"id": 1, "input": "solve(1)", "expected": "2"}], language="Python", agent_id="EVO_PY")
    
    # Run Python code in EVO_CPP
    code2 = "def solve(x):\n    return x + 2"
    sandbox.run(code2, [{"id": 1, "input": "solve(1)", "expected": "3"}], language="Python", agent_id="EVO_CPP")
    
    # Verify both workspaces exist
    py_workspace = os.path.abspath(os.path.join("workspaces", "EVO_PY"))
    cpp_workspace = os.path.abspath(os.path.join("workspaces", "EVO_CPP"))
    
    assert os.path.exists(py_workspace)
    assert os.path.exists(cpp_workspace)
    
    # Check isolation (files in py_workspace should have code1, files in cpp_workspace should have code2)
    with open(os.path.join(py_workspace, "solution.py"), 'r', encoding='utf-8') as f:
        assert "x + 1" in f.read()
        
    with open(os.path.join(cpp_workspace, "solution.py"), 'r', encoding='utf-8') as f:
        assert "x + 2" in f.read()
