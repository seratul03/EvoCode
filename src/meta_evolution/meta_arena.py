"""
MetaArena: Runs the "Fast Duel" between the Original agent and the Challenger.

Both are given the same single problem and run as isolated Python subprocesses
using run_autonomous.py with --runs 1 --gens 1. The subprocess for the Clone
uses a patched import that temporarily replaces the target agent's source with
the challenger file.

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
    def __init__(self, original_fitness: float, challenger_fitness: float, challenger_won: bool):
        self.original_fitness = original_fitness
        self.challenger_fitness = challenger_fitness
        self.challenger_won = challenger_won

    def __repr__(self):
        winner = "CHALLENGER" if self.challenger_won else "ORIGINAL"
        return (
            f"DuelResult(winner={winner}, "
            f"original={self.original_fitness:.4f}, "
            f"challenger={self.challenger_fitness:.4f})"
        )


class MetaArena:
    """
    Conducts the fast duel between the original agent and its challenger.

    The duel runs two isolated subprocesses. Each subprocess:
        1. Runs run_autonomous.py with --runs 1 --gens 1 on a shared problem.
        2. Writes a structured_report JSON to a temporary output directory.
        3. The MetaArena reads both JSON outputs and compares best_fitness.

    If the challenger wins, its file is atomically promoted to replace the original.
    """

    def __init__(self, project_root: str = "."):
        self.project_root = os.path.abspath(project_root)

    async def duel(self, original_path: str, challenger_path: str) -> DuelResult:
        """
        Runs the fast duel between original and challenger.

        Args:
            original_path:    e.g. "src/agents/generator.py"
            challenger_path:  Path to the challenger file in staging/

        Returns:
            DuelResult with fitness scores and a winner flag.
        """
        print(f"\n[MetaArena] [START] FAST DUEL STARTING")
        print(f"[MetaArena] Original:   {original_path}")
        print(f"[MetaArena] Challenger: {challenger_path}")

        # Create two temp dirs for isolated report output
        with tempfile.TemporaryDirectory() as tmpdir_a, \
             tempfile.TemporaryDirectory() as tmpdir_b:

            # Run both processes concurrently
            original_fitness, challenger_fitness = await asyncio.gather(
                self._run_subprocess(
                    label="ORIGINAL",
                    agent_patch=None,  # no patch — use real file
                    original_path=original_path,
                    report_dir=tmpdir_a,
                ),
                self._run_subprocess(
                    label="CHALLENGER",
                    agent_patch=challenger_path,  # patch with challenger
                    original_path=original_path,
                    report_dir=tmpdir_b,
                ),
            )

        challenger_won = challenger_fitness > original_fitness
        result = DuelResult(original_fitness, challenger_fitness, challenger_won)

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
    ) -> float:
        """
        Runs a single EvoCode pipeline in a subprocess.
        If agent_patch is set, the challenger file temporarily replaces
        the original before the subprocess starts.
        """
        # Build environment for the subprocess
        env = os.environ.copy()
        env["EVOCODE_REPORT_DIR"] = report_dir  # Override report output directory

        # Build the command
        python_exe = sys.executable
        cmd = [
            python_exe, "src/meta_evolution/duel_runner.py"
        ]

        if agent_patch:
            # Strategy: copy the challenger into a temp location,
            # then pass its path via env var so we can monkey-patch at import time.
            # For simplicity in Phase 17.0, we do a safe file swap + restore.
            backup_path = original_path + ".meta_backup"
            shutil.copy2(original_path, backup_path)
            shutil.copy2(agent_patch, original_path)
            print(f"[MetaArena] [{label}] Challenger file installed. Running pipeline...")
        else:
            backup_path = None
            print(f"[MetaArena] [{label}] Running with original file...")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)  # 10 min max

            if proc.returncode != 0:
                print(f"[MetaArena] [{label}] Subprocess failed (exit {proc.returncode}).")
                if stderr:
                    print(f"[MetaArena] [{label}] STDERR: {stderr.decode()[:500]}")
                fitness = 0.0
            else:
                fitness = self._extract_best_fitness(report_dir)
                print(f"[MetaArena] [{label}] Best fitness: {fitness:.4f}")

        except asyncio.TimeoutError:
            print(f"[MetaArena] [{label}] Subprocess timed out after 600s. Scoring as 0.")
            fitness = 0.0
        finally:
            # Always restore original file if we swapped it
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, original_path)
                os.remove(backup_path)
                print(f"[MetaArena] [{label}] Original file restored.")

        return fitness

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
