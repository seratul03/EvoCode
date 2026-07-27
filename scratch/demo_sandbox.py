import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.patch_applier import apply_patch_to_file
from harness.sandbox import SandboxRunner
import shutil
import tempfile

def run_demo():
    print("--- Docker Sandbox & Patch Applier Demo ---")
    
    # 1. Setup a dummy project directory
    demo_dir = tempfile.mkdtemp(prefix="evocode_demo_")
    print(f"\n[1] Setting up dummy project in {demo_dir}")
    
    file_path = os.path.join(demo_dir, "calculator.py")
    with open(file_path, "w") as f:
        f.write("def multiply(a, b):\n    return a + b\n\nprint(f'2 * 3 = {multiply(2, 3)}')\n")
        
    print("Created calculator.py with a deliberate bug (+ instead of *).")
    
    # 2. Run the buggy code via Sandbox
    runner = SandboxRunner(use_docker=False) # Fallback to local subprocess for demo simplicity
    print("\n[2] Executing buggy code via Sandbox...")
    exit_code, stdout, stderr = runner.run_command("python calculator.py", working_dir=demo_dir)
    print(f"Exit Code: {exit_code}")
    print(f"Output: {stdout.strip()}")
    
    # 3. Apply a patch
    print("\n[3] Applying Patch...")
    patch = "<<<<<<< SEARCH\n    return a + b\n=======\n    return a * b\n>>>>>>> REPLACE"
    print("Patch content:")
    print(patch)
    apply_patch_to_file(file_path, patch)
    print("Patch applied successfully.")
    
    # 4. Run the fixed code via Sandbox
    print("\n[4] Executing patched code via Sandbox...")
    exit_code, stdout, stderr = runner.run_command("python calculator.py", working_dir=demo_dir)
    print(f"Exit Code: {exit_code}")
    print(f"Output: {stdout.strip()}")
    
    # Cleanup
    shutil.rmtree(demo_dir)
    print("\n[5] Cleanup complete.")

if __name__ == "__main__":
    run_demo()
