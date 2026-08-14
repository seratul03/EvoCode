import os
import sys
import json
import asyncio

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.sandbox import SandboxRunner

def run_docker_sandbox_demo():
    print("--- SWE-bench Docker Sandbox Demo ---")
    
    # 1. Load one of the fetched SWE-bench instances
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    json_files = [f for f in os.listdir(data_dir) if f.endswith(".json")]
    
    if not json_files:
        print("No JSON files found in data/. Did you run fetch_swe_bench.py?")
        return
        
    target_file = json_files[0]
    with open(os.path.join(data_dir, target_file), "r", encoding="utf-8") as f:
        instance = json.load(f)
        
    repo = instance["repo"]
    base_commit = instance["base_commit"]
    instance_id = instance["instance_id"]
    
    print(f"Loaded Instance: {instance_id}")
    print(f"Repository: {repo}")
    print(f"Base Commit: {base_commit}")
    
    # 2. Spin up the Docker SandboxRunner
    print("\nStarting Docker Sandbox (python:3.11-slim)...")
    runner = SandboxRunner(use_docker=True, docker_image="python:3.11-slim")
    
    if not runner.use_docker:
        print("ERROR: Docker is not available or not running. Please start Docker Desktop.")
        return
        
    # 3. Create a setup command to clone the repo inside the container
    setup_cmd = f"git clone https://github.com/{repo}.git . && git checkout {base_commit}"
    
    # We need to install git in the slim container first
    print("\n[Container] Installing git (this might take a minute)...")
    code, out, err = runner.run_command("sh -c 'apt-get update && apt-get install -y git'", timeout=300)
    if code != 0:
        print(f"Failed to install git. Exit Code: {code}")
        print(f"STDOUT:\n{out}")
        print(f"STDERR:\n{err}")
        return
        
    print("\n[Container] Cloning Repository & Checking out Commit...")
    # NOTE: Since SandboxRunner wipes state between calls (it spins up a fresh container each time),
    # in a real harness, you would mount a persistent volume or execute all steps in a single shell script.
    # For this demo, we will combine the clone and a simple verify command into one string!
    
    combined_cmd = (
        "sh -c 'apt-get update && apt-get install -y git && "
        f"git clone https://github.com/{repo}.git repo && "
        f"cd repo && git checkout {base_commit} && "
        "echo \"\\n--- GIT STATUS ---\" && git status && "
        "echo \"\\n--- REPO CONTENTS ---\" && ls -la'"
    )
    
    # Run securely inside Docker
    exit_code, stdout, stderr = runner.run_command(combined_cmd, timeout=300)
    
    print(f"\nExit Code: {exit_code}")
    print("--- STDOUT ---")
    print(stdout)
    
    if stderr:
        print("--- STDERR ---")
        print(stderr)
        
    print("\nSuccess! Your Docker Sandbox can securely clone and interact with real SWE-bench repositories.")

if __name__ == "__main__":
    run_docker_sandbox_demo()
