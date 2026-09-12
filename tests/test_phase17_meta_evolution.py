"""
Tests for Phase 17: Meta-Evolution

Tests cover:
  - Watcher: threshold logic, healthy vs. degraded detection
  - Referee: syntax check, import check, path check
  - Integration: full flow with mocked LLM and a known-bad agent
"""

import os
import json
import pytest
import tempfile
import textwrap
from unittest.mock import AsyncMock, MagicMock, patch

from src.meta_evolution.watcher import Watcher, UpgradeTrigger
from src.meta_evolution.referee import Referee, RefereeVerdict


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_report(passed: int, total: int, tmpdir: str, filename: str) -> str:
    """Create a minimal structured report JSON with one problem and one evaluation."""
    report = {
        "start_time": "2026-09-12T00:00:00",
        "problems_evaluated": [
            {
                "problem_id": 1,
                "generations": [
                    {
                        "generation_id": 1,
                        "evaluations": [
                            {
                                "genome_index": 0,
                                "test_results": {
                                    "passed_tests": passed,
                                    "total_tests": total,
                                },
                                "fitness": {"fitness_value": passed / max(1, total)},
                            }
                        ],
                    }
                ],
            }
        ],
    }
    path = os.path.join(tmpdir, filename)
    with open(path, "w") as f:
        json.dump(report, f)
    return path


# ─── Watcher Tests ────────────────────────────────────────────────────────────

class TestWatcher:

    def test_healthy_returns_none(self, tmp_path):
        """If success rate >= threshold, Watcher returns None."""
        d = str(tmp_path)
        # 8 out of 10 problems solved → 80% success rate
        for i in range(8):
            _make_report(5, 5, d, f"report_{i:03d}.json")
        for i in range(8, 10):
            _make_report(0, 5, d, f"report_{i:03d}.json")

        watcher = Watcher(reports_dir=d, threshold=0.50, window=10)
        trigger = watcher.check()
        assert trigger is None

    def test_degraded_returns_trigger(self, tmp_path):
        """If success rate < threshold, Watcher returns an UpgradeTrigger."""
        d = str(tmp_path)
        # 3 out of 10 problems solved → 30% success rate
        for i in range(3):
            _make_report(5, 5, d, f"report_{i:03d}.json")
        for i in range(3, 10):
            _make_report(0, 5, d, f"report_{i:03d}.json")

        watcher = Watcher(reports_dir=d, threshold=0.50, window=10)
        trigger = watcher.check()
        assert trigger is not None
        assert isinstance(trigger, UpgradeTrigger)
        assert trigger.rolling_success_rate == pytest.approx(0.30)
        assert "generator.py" in trigger.agent_file

    def test_no_reports_returns_none(self, tmp_path):
        """With no reports at all, Watcher should not trigger (healthy by default)."""
        watcher = Watcher(reports_dir=str(tmp_path), threshold=0.50)
        assert watcher.check() is None

    def test_max_failures_halts_trigger(self, tmp_path):
        """After max_failures consecutive failures, Watcher stops triggering."""
        d = str(tmp_path)
        for i in range(10):
            _make_report(0, 5, d, f"report_{i:03d}.json")

        watcher = Watcher(reports_dir=d, threshold=0.50, window=10, max_failures=2)
        # Simulate 2 failed upgrades
        watcher._consecutive_failures["generator.py"] = 2

        trigger = watcher.check()
        assert trigger is None

    def test_success_resets_failure_counter(self, tmp_path):
        """A successful upgrade resets the consecutive failure counter."""
        watcher = Watcher(reports_dir=str(tmp_path))
        watcher._consecutive_failures["generator.py"] = 2
        watcher.record_upgrade_result("src/agents/generator.py", succeeded=True)
        assert watcher._consecutive_failures.get("generator.py", 0) == 0

    def test_failure_increments_counter(self, tmp_path):
        """A failed upgrade increments the consecutive failure counter."""
        watcher = Watcher(reports_dir=str(tmp_path))
        watcher.record_upgrade_result("src/agents/generator.py", succeeded=False)
        watcher.record_upgrade_result("src/agents/generator.py", succeeded=False)
        assert watcher._consecutive_failures.get("generator.py", 0) == 2


# ─── Referee Tests ────────────────────────────────────────────────────────────

class TestReferee:

    def setup_method(self):
        self.referee = Referee()

    def test_valid_code_passes(self):
        code = textwrap.dedent("""
            import os
            import json
            from src.client import EvoClient

            class GeneratorAgent:
                def __init__(self, client):
                    self.client = client
        """)
        verdict = self.referee.inspect(code)
        assert verdict.passed, verdict.reason

    def test_syntax_error_fails(self):
        code = "def broken(:\n    pass"
        verdict = self.referee.inspect(code)
        assert not verdict.passed
        assert "Syntax" in verdict.reason or "syntax" in verdict.reason

    def test_forbidden_import_fails(self):
        code = textwrap.dedent("""
            import requests
            import os

            def foo():
                return requests.get("http://evil.com")
        """)
        verdict = self.referee.inspect(code)
        assert not verdict.passed
        assert "Forbidden import" in verdict.reason

    def test_forbidden_from_import_fails(self):
        code = textwrap.dedent("""
            from flask import Flask

            app = Flask(__name__)
        """)
        verdict = self.referee.inspect(code)
        assert not verdict.passed
        assert "Forbidden import" in verdict.reason

    def test_locked_file_reference_fails(self):
        code = textwrap.dedent("""
            import shutil
            shutil.copy('challenger.py', 'src/system_guard.py')
        """)
        verdict = self.referee.inspect(code)
        assert not verdict.passed
        assert "locked" in verdict.reason.lower() or "system_guard" in verdict.reason

    def test_safe_write_passes(self):
        code = textwrap.dedent("""
            import os

            def save_result():
                with open('src/agents/generator.py', 'w') as f:
                    f.write('# upgraded')
        """)
        verdict = self.referee.inspect(code)
        # Writing to src/agents/ is allowed
        assert verdict.passed, verdict.reason

    def test_unsafe_write_fails(self):
        code = textwrap.dedent("""
            import os

            def backdoor():
                with open('C:/Windows/evil.bat', 'w') as f:
                    f.write('malicious code')
        """)
        verdict = self.referee.inspect(code)
        assert not verdict.passed
        assert "Forbidden file write" in verdict.reason
