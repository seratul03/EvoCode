import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Dict, Any

from harness.sandbox import SandboxRunner
from harness.patch_applier import apply_patch_to_file

@dataclass
class Task:
    """Represents a mock SWE-bench task."""
    instance_id: str
    setup_script: str
    test_command: str
    gold_patch: str
    target_file: str


class Evaluator:
    def __init__(self, use_docker: bool = False):
        self.runner = SandboxRunner(use_docker=use_docker)

    def evaluate(self, task: Task, patch: str) -> Dict[str, Any]:
        """
        Evaluates a proposed patch against a given task.
        
        Steps:
        1. Create a clean workspace.
        2. Run the task setup script to scaffold the repository/code.
        3. Apply the proposed patch.
        4. Run the test suite.
        5. Return the result based on the test command's exit code.
        """
        workspace = tempfile.mkdtemp(prefix=f"evocode_eval_{task.instance_id}_")
        
        try:
            # 1. Setup the environment
            setup_exit_code, setup_stdout, setup_stderr = self.runner.run_command(
                task.setup_script, working_dir=workspace
            )
            
            if setup_exit_code != 0:
                return {
                    "success": False,
                    "error": "Setup failed",
                    "logs": setup_stdout + "\n" + setup_stderr
                }

            # 2. Apply the patch
            target_file_path = os.path.join(workspace, task.target_file)
            if not os.path.exists(target_file_path):
                return {
                    "success": False,
                    "error": f"Target file {task.target_file} not found after setup.",
                    "logs": ""
                }
                
            try:
                apply_patch_to_file(target_file_path, patch)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Patch application failed: {str(e)}",
                    "logs": ""
                }

            # 3. Run the tests
            test_exit_code, test_stdout, test_stderr = self.runner.run_command(
                task.test_command, working_dir=workspace
            )

            is_success = (test_exit_code == 0)

            return {
                "success": is_success,
                "exit_code": test_exit_code,
                "logs": test_stdout + "\n" + test_stderr,
                "error": None
            }

        finally:
            # Cleanup workspace
            if os.path.exists(workspace):
                try:
                    # Windows cleanup can sometimes fail if files are held by antivirus etc.
                    shutil.rmtree(workspace)
                except Exception:
                    pass
