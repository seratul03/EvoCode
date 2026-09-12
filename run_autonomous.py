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
from src.meta_evolution import Watcher, CloneBuilder, SourceJudge, Referee, MetaArena
from src.meta_evolution.watcher import UpgradeTrigger


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
    Enforces a ratio (e.g., 80% unique, 10% same topic, 10% identical).
    """
    import random
    import copy
    
    print(f"\n[Autonomous] Asking LLM to generate {n} compatible problem(s)...")

    if n >= 3:
        num_identical = max(1, round(n * 0.1))
        num_same_topic = max(1, round(n * 0.1))
    else:
        num_identical = 0
        num_same_topic = 0
    num_unique = max(0, n - num_identical - num_same_topic)
    
    print(f"[Autonomous] Target Plan: {num_unique} Unique, {num_same_topic} Same-Topic, {num_identical} Identical")

    unique_titles = []
    
    async def _gen_one(prompt_suffix: str, attempt_idx: int) -> dict:
        user_prompt = (
            f"Generate exactly 1 programming problem following the rules above. "
            f"Use a difficulty between 1-7. "
            f"Return ONLY a JSON object (not an array) for that single problem.\n"
            f"{prompt_suffix}"
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
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            p = parsed[0] if isinstance(parsed, list) and parsed else parsed
            
            if not all(k in p for k in ("title", "description", "tests", "function_signature")):
                print(f"    [Autonomous] Attempt {attempt_idx} missing required fields. Skipping.")
                return None
            if len(p.get("tests", [])) < 3:
                print(f"    [Autonomous] Attempt {attempt_idx} has too few tests. Skipping.")
                return None
            return p
        except Exception as e:
            print(f"    [Autonomous] Error on attempt {attempt_idx}: {e}")
            return None

    unique_problems = []
    for i in range(num_unique):
        print(f"  -> Generating Unique problem {i + 1}/{num_unique}...")
        avoid_str = ""
        if unique_titles:
            avoid_str = f"CRITICAL: Do NOT generate problems similar to these existing ones: {', '.join(unique_titles[-10:])}"
        p = await _gen_one(f"Use a fresh category. {avoid_str}", i + 1)
        if p:
            unique_problems.append(p)
            unique_titles.append(p.get("title", "Unknown"))
            print(f"    [OK] '{p.get('title')}'")

    same_topic_problems = []
    for i in range(num_same_topic):
        print(f"  -> Generating Same-Topic problem {i + 1}/{num_same_topic}...")
        base_title = random.choice(unique_titles) if unique_titles else "array manipulation"
        prompt = f"CRITICAL: Generate a problem related to the same topic/category as '{base_title}', but it MUST be a completely different problem."
        p = await _gen_one(prompt, i + 1 + num_unique)
        if p:
            same_topic_problems.append(p)
            unique_titles.append(p.get("title", "Unknown"))
            print(f"    [OK] '{p.get('title')}' (Related to: {base_title})")

    final_list = unique_problems + same_topic_problems
    random.shuffle(final_list)
    
    identical_problems = []
    for i in range(num_identical):
        if final_list:
            base_prob = random.choice(final_list)
            dup = copy.deepcopy(base_prob)
            identical_problems.append(dup)

    if identical_problems:
        # Space them out evenly across the final list
        spacing = max(1, len(final_list) // len(identical_problems))
        for i, p in enumerate(identical_problems):
            insert_idx = min(len(final_list), (i * spacing) + (spacing // 2))
            final_list.insert(insert_idx, p)
            print(f"  -> Injected Identical problem (Clone of '{p.get('title')}') at index {insert_idx}")

    # Final ID assignment
    valid_problems = []
    attempt_id = start_id
    for p in final_list:
        new_p = copy.deepcopy(p)
        new_p["id"] = attempt_id
        valid_problems.append(new_p)
        attempt_id += 1

    print(f"[Autonomous] {len(valid_problems)}/{n} valid problem(s) generated.")
    return valid_problems


# ─── Main Pipeline ────────────────────────────────────────────────────────────

async def run_autonomous_pipeline(n_runs: int, n_gens: int, memory_only: bool,
                                  enable_evolution: bool = True,
                                  enable_collaboration: bool = True,
                                  enable_memory: bool = True,
                                  single_agent_mode: bool = False,
                                  skip_meta_evolution: bool = False):
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
            orchestrator = EvoFlowOrchestrator(
                pop_size=3,
                enable_evolution=enable_evolution,
                enable_collaboration=enable_collaboration,
                enable_memory=enable_memory,
                single_agent_mode=single_agent_mode
            )
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
    report_dir = os.environ.get("EVOCODE_REPORT_DIR", "structured_reports")
    print(f"  Reports saved to:  {report_dir}/")
    print(f"  Memory updated at: memory/agent_memory.txt")
    print("=" * 60)

    # ── Meta-Evolution Phase ──────────────────────────────────────────────────
    if not skip_meta_evolution:
        await _run_meta_evolution_phase(client)


# ─── Meta-Evolution Phase Function ───────────────────────────────────────────

async def _run_meta_evolution_phase(client: EvoClient) -> None:
    """
    Runs the Phase 17 Meta-Evolution loop after the main pipeline completes.

    Steps:
      1. Watcher checks rolling success rate.
      2. If below threshold, CloneBuilder proposes two rewrites.
      3. SourceJudge votes on the best proposal.
      4. Referee inspects the winner for safety.
      5. MetaArena runs a fast duel — Original vs. Challenger.
      6. Winner is kept; loser is discarded.
    """
    print(f"\n{'='*60}")
    print("  META-EVOLUTION PHASE")
    print(f"{'='*60}")

    watcher = Watcher(threshold=0.50, window=10, max_failures=3)
    trigger: UpgradeTrigger | None = watcher.check()

    if trigger is None:
        print("[Meta-Evolution] Agents are healthy. No upgrade needed.")
        return

    print(f"\n[Meta-Evolution] ⚠️  Upgrade triggered for: {trigger.agent_file}")
    print(f"[Meta-Evolution] Consecutive failures so far: {trigger.consecutive_upgrade_failures}")

    # Step 1: Generate two proposals
    builder = CloneBuilder(client)
    path_a, path_b = await builder.build(trigger)

    # Step 2: Judge votes
    judge = SourceJudge(client)
    winning_path = await judge.judge(trigger.agent_file, path_a, path_b)

    # Step 3: Referee safety check
    referee = Referee()
    with open(winning_path, "r", encoding="utf-8") as f:
        winning_code = f.read()

    verdict = referee.inspect(winning_code)
    print(f"[Meta-Evolution] Referee verdict: {verdict}")

    if not verdict.passed:
        print(f"[Meta-Evolution] ❌ Challenger DISQUALIFIED by Referee: {verdict.reason}")
        watcher.record_upgrade_result(trigger.agent_file, succeeded=False)
        return

    # Step 4: Fast Duel
    arena = MetaArena()
    result = await arena.duel(trigger.agent_file, winning_path)

    watcher.record_upgrade_result(trigger.agent_file, succeeded=result.challenger_won)

    if result.challenger_won:
        print(f"\n[Meta-Evolution] 🎉 Agent '{trigger.agent_name}' has evolved!")
    else:
        print(f"\n[Meta-Evolution] Original agent survives. No changes made.")

    print(f"{'='*60}")


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

    parser.add_argument(
        "--single-agent",
        action="store_true",
        help="Run in single-agent mode (Python only). Used for ablation."
    )
    parser.add_argument(
        "--disable-evolution",
        action="store_true",
        help="Disable the self-evolution mechanism. Used for ablation."
    )
    parser.add_argument(
        "--disable-memory",
        action="store_true",
        help="Disable injection of historical memory. Used for ablation."
    )
    parser.add_argument(
        "--disable-collaboration",
        action="store_true",
        help="Disable multi-agent knowledge crossover. Used for ablation."
    )
    parser.add_argument(
        "--skip-meta-evolution",
        action="store_true",
        help="Skip the Phase 17 meta-evolution upgrade check after the pipeline."
    )

    args = parser.parse_args()

    asyncio.run(run_autonomous_pipeline(
        n_runs=args.runs,
        n_gens=args.gens,
        memory_only=args.memory_only,
        enable_evolution=not args.disable_evolution,
        enable_collaboration=not args.disable_collaboration,
        enable_memory=not args.disable_memory,
        single_agent_mode=args.single_agent,
        skip_meta_evolution=args.skip_meta_evolution,
    ))
