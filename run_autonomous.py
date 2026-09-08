"""
run_autonomous.py
=================
Autonomous Self-Training Pipeline for EvoCode.

Usage:
    python run_autonomous.py              # defaults to 5 autonomous runs
    python run_autonomous.py --runs 10    # run 10 problems
    python run_autonomous.py --runs 3 --gens 5   # 3 problems, 5 generations each
    python run_autonomous.py --memory-only       # skip execution, just synthesize memory from existing reports

How it works:
    1. An LLM generates `n` novel programming problem statements that are
       compatible with the EvoCode sandbox (correct JSON format, valid tests).
    2. The EvoFlowOrchestrator runs the full evolutionary pipeline on each problem.
       Every run is saved to `structured_reports/` regardless of pass or fail.
    3. After all runs complete, the MemoryHistorianAgent reads the new reports
       and synthesizes them into `memory/agent_memory.txt` — human-readable
       lessons that future agents will automatically inject into their prompts.
"""

import asyncio
import argparse
import json
import os
import sys
import subprocess

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.client import EvoClient
from src.evoflow import EvoFlowOrchestrator
from src.agents.memory_agent import MemoryHistorianAgent


# ─── Problem Generation ───────────────────────────────────────────────────────

PROBLEM_GENERATION_SYSTEM_PROMPT = """You are an expert competitive programming problem designer.
Your job is to generate programming problems that are compatible with an automated evaluation sandbox.

COMPATIBILITY RULES for the sandbox:
- Problems must be solvable with a SINGLE Python function.
- The function signature must take only primitive or standard Python types:
  integers, floats, strings, lists of primitives, or dicts with string/int keys.
- The function must RETURN a value (not print it).
- Problems should range from Easy to Medium difficulty.
- Avoid problems requiring file I/O, network calls, or external libraries.
- Good categories: array manipulation, string processing, math, recursion, dynamic programming,
  sorting, searching, hashmap usage, sliding window, two pointers, stack/queue problems.

You MUST return a JSON array (list) of problems. Each problem MUST follow this exact schema:
[
  {
    "id": <unique integer>,
    "category": "<category>",
    "title": "<short descriptive title>",
    "description": "<full clear problem description>",
    "difficulty": <integer 1-10>,
    "function_signature": "def <name>(<args>) -> <return_type>:",
    "test_strategy": {
      "input_types": "<description>",
      "inferred_ranges": "<description>",
      "planned_cases": "<description>"
    },
    "tests": [
      {"id": 0, "input": "<function_name>(value)", "expected": "<string representation of return value>"}
    ]
  }
]

CRITICAL TEST RULES:
1. Generate 5 to 8 test cases per problem: mix of Normal, Edge (empty, zero, negative), and Boundary cases.
2. The 'input' field MUST be a function call matching the exact function_signature arity.
3. The 'expected' field MUST be the string representation of the Python return value.
   Examples: "42", "True", "[1, 2, 3]", "\\\"hello\\\"", "None"
4. Ensure the function name in 'input' matches 'function_signature'.
5. MUST output perfectly valid JSON. Escape all inner quotes properly. NO trailing commas.

Respond with ONLY the JSON array. No markdown, no explanation."""


def _get_next_problem_id() -> int:
    """
    Scans the structured_reports directory to find the highest problem_id 
    evaluated so far, and returns the next sequential integer.
    """
    reports_dir = "structured_reports"
    if not os.path.exists(reports_dir):
        return 1
    
    max_id = 0
    for filename in os.listdir(reports_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(reports_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                report = json.load(f)
                for prob in report.get("problems_evaluated", []):
                    pid = prob.get("problem_id", 0)
                    if isinstance(pid, int) and pid > max_id:
                        max_id = pid
                    elif isinstance(pid, str) and pid.isdigit() and int(pid) > max_id:
                        max_id = int(pid)
        except Exception:
            pass
    return max_id + 1

async def generate_problems(client: EvoClient, n: int, start_id: int) -> list[dict]:
    """
    Uses the LLM to autonomously generate `n` programming problems.
    Generates ONE problem per API call to avoid token-limit truncation.
    """
    print(f"\n[Autonomous] Asking LLM to generate {n} compatible problem(s) (one at a time)...")

    valid_problems = []
    attempt_id = start_id

    for i in range(n):
        print(f"  -> Generating problem {i + 1}/{n} (ID will be {attempt_id})...")

        user_prompt = (
            f"Generate exactly 1 programming problem following the rules above. "
            f"Use a fresh category and difficulty between 1-7. "
            f"Return ONLY a JSON object (not an array) for that single problem."
        )

        try:
            response = await client.create_completion(
                messages=[
                    {"role": "system", "content": PROBLEM_GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )

            content = response["content"].strip()

            # Strip markdown code blocks if the LLM wrapped the JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # The LLM might return an array with one item or a plain object
            parsed = json.loads(content)
            if isinstance(parsed, list):
                if not parsed:
                    print(f"    [Autonomous] Empty response for problem {i + 1}. Skipping.")
                    continue
                p = parsed[0]
            else:
                p = parsed

            # Validate minimum required fields
            if not all(k in p for k in ("title", "description", "tests", "function_signature")):
                print(f"    [Autonomous] Problem {i + 1} missing required fields. Skipping.")
                continue

            if len(p.get("tests", [])) < 3:
                print(f"    [Autonomous] Problem {i + 1} has too few tests ({len(p.get('tests', []))}). Skipping.")
                continue

            # Assign sequential ID, ignoring whatever the LLM put
            p["id"] = attempt_id
            valid_problems.append(p)
            print(f"    [OK] '{p.get('title')}' -> ID: {attempt_id}")
            attempt_id += 1

        except json.JSONDecodeError as e:
            print(f"    [Autonomous] JSON error for problem {i + 1}: {e}. Skipping.")
            with open(f"failed_problem_{i + 1}.txt", "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"    [Autonomous] Unexpected error for problem {i + 1}: {e}. Skipping.")

    print(f"[Autonomous] {len(valid_problems)}/{n} valid problem(s) generated.")
    return valid_problems


# ─── Main Pipeline ────────────────────────────────────────────────────────────

async def run_autonomous_pipeline(n_runs: int, n_gens: int, memory_only: bool):
    print("=" * 60)
    print("       EvoCode Autonomous Self-Training Pipeline")
    print("=" * 60)

    # 1. Docker health check
    if not memory_only:
        print("\n[System] Checking Docker status...")
        try:
            subprocess.run(["docker", "info"], capture_output=True, text=True, check=True)
            print("[System] Docker is running.")
        except Exception:
            print("[ERROR] Docker is not running. Please start Docker Desktop/Daemon.")
            print("[ERROR] You can still run --memory-only to synthesize memory from existing reports.")
            return

    client = EvoClient()
    memory_agent = MemoryHistorianAgent(client)

    # ── Memory-Only Mode ──────────────────────────────────────────────────────
    if memory_only:
        print("\n[Autonomous] Running in --memory-only mode.")
        print("[Autonomous] Synthesizing memory from ALL un-processed structured reports...")
        await memory_agent.synthesize_latest(n_reports=50)  # Process up to 50 unlogged reports
        print("\n[Autonomous] Memory synthesis complete.")
        return

    # ── Full Autonomous Pipeline ──────────────────────────────────────────────
    # 2. Generate problems
    start_id = _get_next_problem_id()
    problems = await generate_problems(client, n_runs, start_id)
    if not problems:
        print("[Autonomous] No valid problems were generated. Aborting.")
        return

    actual_runs = len(problems)
    print(f"\n[Autonomous] Starting {actual_runs} autonomous run(s) with {n_gens} generation(s) each...")
    print("-" * 60)

    # 3. Run EvoFlow on each problem
    for run_idx, problem in enumerate(problems):
        print(f"\n{'='*60}")
        print(f"  AUTONOMOUS RUN {run_idx + 1}/{actual_runs}: {problem.get('title', 'Unknown')}")
        print(f"{'='*60}")

        try:
            orchestrator = EvoFlowOrchestrator(pop_size=3)
            await orchestrator.run_generations(
                num_generations=n_gens,
                problems=[problem],
                mode="evolve",
                disable_circuit_breaker=False
            )
        except Exception as e:
            print(f"\n[Autonomous] ERROR during run {run_idx + 1}: {e}")
            print("[Autonomous] Continuing with next problem...")

    # 4. Synthesize memory from ALL new reports generated during this session
    print(f"\n{'='*60}")
    print("  MEMORY SYNTHESIS PHASE")
    print(f"{'='*60}")
    print(f"\n[Autonomous] All {actual_runs} run(s) complete.")
    print("[Autonomous] Starting MemoryHistorianAgent to synthesize lessons learned...")

    await memory_agent.synthesize_latest(n_reports=actual_runs)

    print("\n" + "=" * 60)
    print("  Autonomous pipeline finished!")
    print(f"  Reports saved to:  structured_reports/")
    print(f"  Memory updated at: memory/agent_memory.txt")
    print("=" * 60)


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="EvoCode Autonomous Self-Training Pipeline.\n"
                    "Generates programming problems, runs EvoFlow, and synthesizes memory.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--runs", "-n",
        type=int,
        default=5,
        help="Number of autonomous runs (problems) to generate and execute. Default: 5."
    )
    parser.add_argument(
        "--gens", "-g",
        type=int,
        default=3,
        help="Number of evolutionary generations per problem. Default: 3."
    )
    parser.add_argument(
        "--memory-only",
        action="store_true",
        help="Skip problem generation and execution. Only synthesize memory from existing reports."
    )

    args = parser.parse_args()

    asyncio.run(run_autonomous_pipeline(
        n_runs=args.runs,
        n_gens=args.gens,
        memory_only=args.memory_only
    ))
