"""
run_test_eval.py -- Layer 4: Held-Out Test Evaluation.

Run after completing all training conditions:
    python run_test_eval.py

Loads the 4 most recent structured reports (one per mode: baseline_a, baseline_b,
baseline_c, evolve), extracts the best genome configuration from each condition's
final generation, then evaluates each best genome against the held-out
data/test_problems.json.

Results are saved to structured_reports/test_eval_<timestamp>.json.
"""

import asyncio
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from src.evoflow import EvoFlowOrchestrator


REPORT_DIR = "structured_reports"
TEST_PROBLEMS_PATH = "data/test_problems.json"
CONDITIONS = ["baseline_a", "baseline_b", "baseline_c", "evolve"]


def find_latest_report(condition_mode: str) -> dict | None:
    """Find the most recently written structured report for a given mode."""
    if not os.path.exists(REPORT_DIR):
        return None

    matching = []
    for fname in os.listdir(REPORT_DIR):
        if not fname.endswith(".json") or "test_eval" in fname:
            continue
        fpath = os.path.join(REPORT_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("mode") == condition_mode:
                matching.append((fpath, data))
        except Exception:
            continue

    if not matching:
        return None

    # Sort by end_time descending and pick the most recent
    matching.sort(key=lambda x: x[1].get("end_time", ""), reverse=True)
    return matching[0][1]


def extract_best_genome(report: dict) -> dict | None:
    """
    Extract the genome config of the best-performing candidate
    across all problems and generations in a training report.
    """
    best_fitness = -1.0
    best_genome_snapshot = None

    for problem in report.get("problems_evaluated", []):
        for gen in problem.get("generations", []):
            for ev in gen.get("evaluations", []):
                fit_obj = ev.get("fitness", {})
                fit_val = fit_obj.get("fitness_value", 0.0) if isinstance(fit_obj, dict) else 0.0
                if fit_val > best_fitness:
                    best_fitness = fit_val
                    best_genome_snapshot = ev.get("gen_genome_snapshot")

    return best_genome_snapshot


async def main():
    print("=" * 70)
    print("EvoCode -- Layer 4: Held-Out Test Evaluation")
    print("=" * 70)

    # Load test problems
    if not os.path.exists(TEST_PROBLEMS_PATH):
        print(f"ERROR: {TEST_PROBLEMS_PATH} not found.")
        return

    with open(TEST_PROBLEMS_PATH, "r", encoding="utf-8") as f:
        test_problems = json.load(f)
    print(f"\nLoaded {len(test_problems)} held-out test problems.")

    all_results = []

    for condition in CONDITIONS:
        print(f"\n{'=' * 70}")
        print(f"Evaluating condition: {condition.upper()}")
        print(f"{'=' * 70}")

        report = find_latest_report(condition)
        if report is None:
            print(f"  SKIP: No structured report found for mode '{condition}'.")
            continue

        genome_config = extract_best_genome(report)
        if genome_config is None:
            print(f"  SKIP: Could not extract genome from report for '{condition}'.")
            continue

        print(f"  Best genome found: {genome_config}")

        # Determine pop_size from the report
        pop_size = report.get("pop_size", 1)

        orchestrator = EvoFlowOrchestrator(pop_size=pop_size)
        eval_result = await orchestrator.run_eval_only(
            problems=test_problems,
            genome_config=genome_config,
            condition_name=condition,
        )

        summary = eval_result.get("summary", {})
        print(f"\n  Condition '{condition}' Test Results:")
        print(f"    Solved:     {summary.get('solved')}/{summary.get('total_problems')}")
        print(f"    Solve Rate: {summary.get('solve_rate', 0):.1%}")

        all_results.append(eval_result)

    # Save combined test eval report
    os.makedirs(REPORT_DIR, exist_ok=True)
    now = datetime.now()
    filename = now.strftime("test_eval_%d%m%Y_%H-%M-%S.json")
    filepath = os.path.join(REPORT_DIR, filename)

    combined = {
        "evaluation_type": "held_out_test_eval",
        "test_problems_path": TEST_PROBLEMS_PATH,
        "evaluated_at": datetime.utcnow().isoformat(),
        "conditions": all_results,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"\n\n{'=' * 70}")
    print(f"Test evaluation saved to: {filepath}")
    print("\nFINAL SUMMARY:")
    for r in all_results:
        s = r.get("summary", {})
        print(f"  {r['condition']:<15} Solved: {s.get('solved')}/{s.get('total_problems')}  ({s.get('solve_rate', 0):.1%})")


if __name__ == "__main__":
    asyncio.run(main())
