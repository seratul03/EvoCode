"""
Watcher: Monitors rolling problem success rate from structured_reports/ and
emits UpgradeTrigger events when a specific agent's performance drops below
the configured threshold.

Defaults:
    - window:    Last 10 problems
    - threshold: 50% success rate
    - target:    generator.py (the code-writing brain)

The Watcher is purely deterministic — it makes no LLM calls.
It only reads structured_reports/*.json and never writes to any file.
"""

import os
import json
import glob
from dataclasses import dataclass, field
from typing import Optional


# ── Locked files that meta-evolution can NEVER touch ─────────────────────────
LOCKED_FILES = {
    "system_guard.py",
    "sandbox.py",
    "evoflow.py",
    "arena.py",
}

# ── Agents eligible for meta-evolution upgrades ───────────────────────────────
UPGRADEABLE_AGENTS = [
    "generator.py",
]


@dataclass
class UpgradeTrigger:
    """Emitted by the Watcher when an agent must upgrade itself."""
    agent_file: str                    # e.g. "src/agents/generator.py"
    agent_name: str                    # e.g. "generator"
    rolling_success_rate: float        # e.g. 0.30
    window_size: int                   # how many problems were analysed
    consecutive_upgrade_failures: int  # how many times the upgrade has already failed


class Watcher:
    """
    Monitors the structured_reports/ directory.

    Reads the last `window` JSON reports, computes the rolling success rate,
    and emits an UpgradeTrigger if performance is below `threshold`.

    Args:
        reports_dir:     Path to structured_reports/ (default: "structured_reports")
        threshold:       Failure rate that triggers an upgrade (default: 0.50)
        window:          Number of recent problems to consider (default: 10)
        max_failures:    Consecutive failed upgrade attempts before halting (default: 3)
    """

    def __init__(
        self,
        reports_dir: str = "structured_reports",
        threshold: float = 0.50,
        window: int = 10,
        max_failures: int = 3,
    ):
        self.reports_dir = reports_dir
        self.threshold = threshold
        self.window = window
        self.max_failures = max_failures
        self._consecutive_failures: dict[str, int] = {}

    def _load_recent_reports(self) -> list[dict]:
        """Load and sort the most recent N reports chronologically."""
        pattern = os.path.join(self.reports_dir, "*.json")
        files = sorted(glob.glob(pattern))  # alphabetical ≈ chronological by filename
        files = files[-self.window:]        # take only the last N

        reports = []
        for path in files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    reports.append(json.load(f))
            except Exception:
                pass
        return reports

    def _compute_success_rate(self, reports: list[dict]) -> float:
        """
        Computes problem-level success rate.
        A problem is 'solved' if ANY genome achieves perfect correctness in ANY generation.
        """
        total = 0
        solved = 0

        for report in reports:
            for problem in report.get("problems_evaluated", []):
                total += 1
                for gen in problem.get("generations", []):
                    for evaluation in gen.get("evaluations", []):
                        tr = evaluation.get("test_results", {})
                        passed = tr.get("passed_tests", 0)
                        total_tests = tr.get("total_tests", 0)
                        if total_tests > 0 and passed == total_tests:
                            solved += 1
                            break  # Problem is solved — move to next problem
                    else:
                        continue
                    break

        if total == 0:
            return 1.0  # No data → assume healthy, don't trigger
        return solved / total

    def check(self) -> Optional[UpgradeTrigger]:
        """
        Run a health check. Returns an UpgradeTrigger if performance is below
        threshold, or None if everything is fine.

        Also returns None if the agent has already failed max_failures consecutive
        upgrade attempts (to avoid infinite loops — requires human intervention).
        """
        reports = self._load_recent_reports()
        if not reports:
            return None  # No data yet

        rate = self._compute_success_rate(reports)
        print(f"[Watcher] Rolling success rate (last {len(reports)} reports): {rate:.1%}")

        for agent_file in UPGRADEABLE_AGENTS:
            failures = self._consecutive_failures.get(agent_file, 0)

            if failures >= self.max_failures:
                print(
                    f"[Watcher] ALERT: '{agent_file}' has failed {failures} consecutive "
                    f"upgrade attempts. Manual intervention required. Halting meta-evolution."
                )
                return None

            if rate < self.threshold:
                agent_name = agent_file.replace(".py", "")
                full_path = os.path.join("src", "agents", agent_file)

                print(
                    f"[Watcher] SUCCESS RATE {rate:.1%} < THRESHOLD {self.threshold:.1%}. "
                    f"Triggering upgrade for: {full_path}"
                )
                return UpgradeTrigger(
                    agent_file=full_path,
                    agent_name=agent_name,
                    rolling_success_rate=rate,
                    window_size=len(reports),
                    consecutive_upgrade_failures=failures,
                )

        return None  # All agents healthy

    def record_upgrade_result(self, agent_file: str, succeeded: bool) -> None:
        """
        Called by MetaArena after the duel to update the failure counter.
        """
        base = os.path.basename(agent_file)
        if succeeded:
            self._consecutive_failures[base] = 0
            print(f"[Watcher] Upgrade succeeded for '{base}'. Failure counter reset.")
        else:
            self._consecutive_failures[base] = self._consecutive_failures.get(base, 0) + 1
            count = self._consecutive_failures[base]
            print(f"[Watcher] Upgrade failed for '{base}'. Consecutive failures: {count}/{self.max_failures}")
