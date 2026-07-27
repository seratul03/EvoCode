import os
import pytest
from harness.patch_applier import apply_patch, apply_patch_to_file
from harness.sandbox import SandboxRunner
import tempfile

def test_apply_patch_success():
    original = "def add(a, b):\n    return a - b\n"
    patch = "<<<<<<< SEARCH\n    return a - b\n=======\n    return a + b\n>>>>>>> REPLACE"
    patched = apply_patch(original, patch)
    assert patched == "def add(a, b):\n    return a + b\n"

def test_apply_patch_failure_no_match():
    original = "def add(a, b):\n    return a - b\n"
    patch = "<<<<<<< SEARCH\n    return a * b\n=======\n    return a + b\n>>>>>>> REPLACE"
    with pytest.raises(ValueError):
        apply_patch(original, patch)

def test_apply_patch_failure_no_blocks():
    original = "def add(a, b):\n    return a - b\n"
    patch = "Just some text without search and replace block"
    with pytest.raises(ValueError):
        apply_patch(original, patch)

def test_sandbox_local_execution():
    runner = SandboxRunner(use_docker=False)
    exit_code, stdout, stderr = runner.run_command("echo hello")
    assert exit_code == 0
    assert "hello" in stdout

def test_sandbox_local_timeout():
    runner = SandboxRunner(use_docker=False)
    # This should time out
    exit_code, stdout, stderr = runner.run_command("python -c \"import time; time.sleep(3)\"", timeout=1)
    assert exit_code == -1
    assert "timed out" in stderr.lower()

def test_patch_applier_file_integration():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("def sub(a, b):\n    return a + b\n")
        temp_file_name = f.name
    
    try:
        patch = "<<<<<<< SEARCH\n    return a + b\n=======\n    return a - b\n>>>>>>> REPLACE"
        apply_patch_to_file(temp_file_name, patch)
        
        with open(temp_file_name, 'r') as f:
            content = f.read()
        assert content == "def sub(a, b):\n    return a - b\n"
    finally:
        os.remove(temp_file_name)
