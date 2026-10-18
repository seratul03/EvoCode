"""
MetaArena: Runs the "Fast Duel" between the Original agent and the Challenger.

Both are given the same single problem and run sequentially as isolated Python
subprocesses using duel_runner.py with --runs 1 --gens 1. The subprocess for the
challenger temporarily replaces the target agent's source with the challenger file.

Winner selection:
    - Parse the structured_reports/*.json produced by each run
    - The run with the higher best_fitness wins
    - In case of a tie, the Original is kept (safety-first)

If the Challenger wins, its source file is atomically moved to overwrite the
original in src/agents/. The staging/ directory is then cleared.
"""

import os
import sys
import json
import glob
import shutil
import asyncio
import subprocess
import tempfile
from pathlib import Path

STAGING_DIR = os.path.join("src", "meta_evolution", "staging")


class DuelResult:
    def __init__(
        self,
        original_fitness: float,
        challenger_fitness: float,
        challenger_won: bool,
        original_metrics: dict | None = None,
        challenger_metrics: dict | None = None,
    ):
        self.original_fitness = original_fitness
        self.challenger_fitness = challenger_fitness
        self.challenger_won = challenger_won
        self.original_metrics = original_metrics or {}
        self.challenger_metrics = challenger_metrics or {}

    def __repr__(self):
        winner = "CHALLENGER" if self.challenger_won else "ORIGINAL"
        return (
            f"DuelResult(winner={winner}, "
            f"original={self.original_fitness:.4f}, "
            f"challenger={self.challenger_fitness:.4f}, "
            f"orig_metrics={self.original_metrics}, "
            f"chal_metrics={self.challenger_metrics})"
        )


class MetaArena:
    """
    Conducts the fast duel between the original agent and its challenger sequentially.

    The duel runs two isolated subprocesses one after another. Each subprocess:
        1. Runs duel_runner.py with --runs 1 --gens 1 on a shared problem.
        2. Writes a structured_report JSON to a temporary output directory.
        3. The MetaArena reads both JSON outputs and compares normalized duel fitness.

    If the challenger wins, its file is atomically promoted to replace the original.
    """

    def __init__(self, project_root: str = "."):
        self.project_root = os.path.abspath(project_root)

    async def duel(self, original_path: str, challenger_path: str) -> DuelResult:
        """
        Runs the fast duel between original and challenger sequentially.

        Args:
            original_path:    e.g. "src/agents/generator.py"
            challenger_path:  Path to the challenger file in staging/

        Returns:
            DuelResult with normalized fitness scores, metrics, and a winner flag.
        """
        print(f"\n[MetaArena] [START] FAST DUEL STARTING")
        print(f"[MetaArena] Original:   {original_path}")
        print(f"[MetaArena] Challenger: {challenger_path}")

        with tempfile.TemporaryDirectory() as tmpdir_a:
            original_fitness, orig_metrics = await self._run_subprocess(
                label="ORIGINAL",
                agent_patch=None,
                original_path=original_path,
                report_dir=tmpdir_a,
            )

        with tempfile.TemporaryDirectory() as tmpdir_b:
            challenger_fitness, chal_metrics = await self._run_subprocess(
                label="CHALLENGER",
                agent_patch=challenger_path,
                original_path=original_path,
                report_dir=tmpdir_b,
            )

        challenger_won = challenger_fitness > original_fitness
        result = DuelResult(
            original_fitness=original_fitness,
            challenger_fitness=challenger_fitness,
            challenger_won=challenger_won,
            original_metrics=orig_metrics,
            challenger_metrics=chal_metrics,
        )

        print(f"\n[MetaArena] [RESULT] DUEL RESULT: {result}")

        if challenger_won:
            self._promote_challenger(challenger_path, original_path)
        else:
            self._clear_staging()
            print("[MetaArena] Original survives. Staging cleared.")

        return result

    async def _run_subprocess(
        self,
        label: str,
        agent_patch: str | None,
        original_path: str,
        report_dir: str,
    ) -> tuple[float, dict]:
        """
        Runs a single EvoCode pipeline in a subprocess.
        If agent_patch is set, the challenger file temporarily replaces
        the original before the subprocess starts.
        Returns:
            (normalized_score, metrics_dict)
        """
        env = os.environ.copy()
        env["EVOCODE_REPORT_DIR"] = report_dir

        python_exe = sys.executable
        cmd = [
            python_exe, "run_autonomous.py",
            "--dataset", "benchmark_suite.json",
            "--runs", "3",
            "--skip-meta-evolution"
        ]

        if agent_patch:
            backup_path = original_path + ".meta_backup"
            shutil.copy2(original_path, backup_path)
            shutil.copy2(agent_patch, original_path)
            print(f"[MetaArena] [{label}] Challenger file installed. Running pipeline...")
        else:
            backup_path = None
            print(f"[MetaArena] [{label}] Running with original file...")

        fitness = 0.0
        metrics = {
            "mean_fitness": 0.0,
            "max_fitness": 0.0,
            "correctness_rate": 0.0,
            "crash_rate": 1.0,
            "normalized_score": 0.0,
            "eval_count": 0,
        }

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)

            if proc.returncode != 0:
                print(f"[MetaArena] [{label}] Subprocess failed (exit {proc.returncode}).")
                if stderr:
                    print(f"[MetaArena] [{label}] STDERR: {stderr.decode()[:500]}")
            else:
                fitness, metrics = self._extract_normalized_fitness(report_dir)
                print(
                    f"[MetaArena] [{label}] Normalized duel fitness: {fitness:.4f} "
                    f"(mean={metrics.get('mean_fitness', 0.0):.4f}, "
                    f"max={metrics.get('max_fitness', 0.0):.4f}, "
                    f"corr={metrics.get('correctness_rate', 0.0):.4f}, "
                    f"crash={metrics.get('crash_rate', 0.0):.4f})"
                )

        except asyncio.TimeoutError:
            print(f"[MetaArena] [{label}] Subprocess timed out after 600s. Scoring as 0.")
            fitness = 0.0
        finally:
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, original_path)
                os.remove(backup_path)
                print(f"[MetaArena] [{label}] Original file restored.")

        return fitness, metrics

    def extract_normalized_fitness(self, report_dir: str) -> tuple[float, dict]:
        """Public helper to compute normalized duel fitness from structured reports."""
        return self._extract_normalized_fitness(report_dir)

    def _extract_normalized_fitness(self, report_dir: str) -> tuple[float, dict]:
        """
        Reads all JSON reports in report_dir and computes a normalized duel fitness score.
        Formula:
            normalized_score = 0.45 * mean_fitness + 0.35 * max_fitness + 0.20 * correctness_rate - 0.10 * crash_rate
            clamped to [0.0, 1.0].
        """
        fitness_values: list[float] = []
        correctness_rates: list[float] = []
        crashes: int = 0
        total_evals: int = 0

        for path in glob.glob(os.path.join(report_dir, "*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    report = json.load(f)
                for problem in report.get("problems_evaluated", []):
                    for gen in problem.get("generations", []):
                        for ev in gen.get("evaluations", []):
                            total_evals += 1
                            fit_val = float(ev.get("fitness", {}).get("fitness_value", 0.0))
                            fitness_values.append(fit_val)

                            test_results = ev.get("test_results", {})
                            if "correctness_rate" in ev.get("fitness", {}):
                                corr = float(ev["fitness"]["correctness_rate"])
                            else:
                                passed = test_results.get("passed_tests", 0)
                                total = test_results.get("total_tests", 0)
                                corr = passed / max(1, total) if total > 0 else 0.0
                            correctness_rates.append(corr)

                            crash_tests = test_results.get("crash_tests", [])
                            has_crash = len(crash_tests) > 0 or bool(ev.get("execution_error"))
                            if has_crash:
                                crashes += 1
            except Exception:
                pass

        if not fitness_values:
            return 0.0, {
                "mean_fitness": 0.0,
                "max_fitness": 0.0,
                "correctness_rate": 0.0,
                "crash_rate": 0.0,
                "normalized_score": 0.0,
                "eval_count": 0,
            }

        mean_fitness = sum(fitness_values) / len(fitness_values)
        max_fitness = max(fitness_values)
        mean_correctness = sum(correctness_rates) / len(correctness_rates)
        crash_rate = crashes / max(1, total_evals)

        raw_score = (
            0.45 * mean_fitness
            + 0.35 * max_fitness
            + 0.20 * mean_correctness
            - 0.10 * crash_rate
        )
        normalized_score = max(0.0, min(1.0, raw_score))

        metrics = {
            "mean_fitness": round(mean_fitness, 4),
            "max_fitness": round(max_fitness, 4),
            "correctness_rate": round(mean_correctness, 4),
            "crash_rate": round(crash_rate, 4),
            "normalized_score": round(normalized_score, 4),
            "eval_count": total_evals,
        }
        return normalized_score, metrics

    def _extract_best_fitness(self, report_dir: str) -> float:
        """Reads all JSON reports in report_dir and returns the highest best_fitness found."""
        best = 0.0
        for path in glob.glob(os.path.join(report_dir, "*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    report = json.load(f)
                for problem in report.get("problems_evaluated", []):
                    for gen in problem.get("generations", []):
                        for ev in gen.get("evaluations", []):
                            fit = ev.get("fitness", {}).get("fitness_value", 0.0)
                            best = max(best, fit)
            except Exception:
                pass
        return best

    def _promote_challenger(self, challenger_path: str, original_path: str) -> None:
        """Atomically replaces the original with the challenger."""
        print(f"[MetaArena] [WIN] Promoting challenger -> {original_path}")
        shutil.copy2(challenger_path, original_path)
        self._clear_staging()
        print(f"[MetaArena] [PASS] Upgrade complete. {original_path} has been evolved.")

    def _clear_staging(self) -> None:
        """Removes all files from the staging directory."""
        for f in glob.glob(os.path.join(STAGING_DIR, "*.py")):
            try:
                os.remove(f)
            except Exception:
                pass
