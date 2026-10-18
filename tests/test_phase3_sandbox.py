import os
import shutil
import subprocess
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


def _docker_available() -> bool:
    """Return True if Docker daemon is reachable and the sandbox image exists."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "evocode-sandbox"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


DOCKER_AVAILABLE = _docker_available()
DOCKER_SKIP_REASON = "evocode-sandbox Docker image not available"


def test_sandbox_creates_persistent_workspace():
    """
    Phase 3 spec: Every sandbox.run() must write the solution file to a
    named persistent workspace (workspaces/<agent_id>/) regardless of whether
    Docker execution succeeds.
    """
    sandbox = Sandbox(timeout_seconds=15)
    code = "def solve(x):\n    return x * 2"
    tests = [{"id": 1, "input": "solve(2)", "expected": "4"}]

    res = sandbox.run(code, tests, language="Python", agent_id="EVO_PY")

    # Workspace + file must exist even if Docker isn't running
    workspace_dir = os.path.abspath(os.path.join("workspaces", "EVO_PY"))
    assert os.path.exists(workspace_dir), "Named workspace directory was not created"
    assert os.path.isdir(workspace_dir)

    solution_path = os.path.join(workspace_dir, "solution.py")
    assert os.path.exists(solution_path), "solution.py was not written to named workspace"

    with open(solution_path, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "def solve(x):" in content
        assert "# === INJECTED TEST HARNESS ===" in content

    # Test execution result only verified when Docker image is available
    if DOCKER_AVAILABLE:
        assert res["passed_tests"] == 1, "Expected 1 passing test when Docker is available"


def test_sandbox_cross_agent_isolation():
    """
    Phase 3 spec: Each agent_id gets its own isolated workspace directory.
    Workspaces must not share files across agents.
    """
    sandbox = Sandbox(timeout_seconds=15)

    code1 = "def solve(x):\n    return x + 1"
    sandbox.run(code1, [{"id": 1, "input": "solve(1)", "expected": "2"}], language="Python", agent_id="EVO_PY")

    code2 = "def solve(x):\n    return x + 2"
    sandbox.run(code2, [{"id": 1, "input": "solve(1)", "expected": "3"}], language="Python", agent_id="EVO_CPP")

    py_workspace = os.path.abspath(os.path.join("workspaces", "EVO_PY"))
    cpp_workspace = os.path.abspath(os.path.join("workspaces", "EVO_CPP"))

    assert os.path.exists(py_workspace), "EVO_PY workspace not created"
    assert os.path.exists(cpp_workspace), "EVO_CPP workspace not created"

    with open(os.path.join(py_workspace, "solution.py"), 'r', encoding='utf-8') as f:
        assert "x + 1" in f.read(), "EVO_PY workspace contains wrong code"

    with open(os.path.join(cpp_workspace, "solution.py"), 'r', encoding='utf-8') as f:
        assert "x + 2" in f.read(), "EVO_CPP workspace contains wrong code"
