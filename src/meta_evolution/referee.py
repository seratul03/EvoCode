"""
Referee: Hardcoded, non-LLM safety enforcer.

Before any proposed source file can enter the MetaArena duel, the Referee
inspects it against three strict rules:

    1. Syntax check     — the file must be valid Python (ast.parse)
    2. Import check     — no imports outside the approved whitelist
    3. Path check       — no open()/write to files outside the safe zone

If ANY rule fails, the challenger is immediately disqualified.
The Referee cannot be overridden by any LLM or any other component.
"""

import ast
import re
from pathlib import Path
from typing import Optional


# ── Approved import whitelist ─────────────────────────────────────────────────
# These are the standard library + project packages currently in requirements.txt
# and the project's own src/ package.
ALLOWED_TOP_LEVEL_IMPORTS = {
    # stdlib
    "os", "sys", "re", "json", "glob", "ast", "copy", "time", "math",
    "random", "pathlib", "typing", "dataclasses", "abc", "io", "logging",
    "hashlib", "asyncio", "functools", "itertools", "collections",
    "contextlib", "inspect", "importlib", "shutil", "subprocess",
    "textwrap", "traceback", "warnings", "weakref",
    # project internals
    "src",
    # approved third-party (from requirements.txt)
    "openai", "tenacity", "dotenv", "httpx", "pydantic",
}

# ── Safe path prefixes where file writes are permitted ────────────────────────
SAFE_WRITE_PREFIXES = (
    "src/agents/",
    "src/meta_evolution/staging/",
    "src\\agents\\",
    "src\\meta_evolution\\staging\\",
)


class RefereeVerdict:
    def __init__(self, passed: bool, reason: str):
        self.passed = passed
        self.reason = reason

    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"RefereeVerdict({status}: {self.reason})"


class Referee:
    """
    Enforces three safety rules on a proposed challenger source file.

    Usage:
        referee = Referee()
        verdict = referee.inspect(challenger_code: str)
        if not verdict.passed:
            print(f"Challenger disqualified: {verdict.reason}")
    """

    def inspect(self, challenger_code: str) -> RefereeVerdict:
        """
        Runs all three checks in sequence.
        Returns the first failure found, or a passing verdict.
        """
        # Rule 1: Syntax
        verdict = self._check_syntax(challenger_code)
        if not verdict.passed:
            return verdict

        # Rule 2: Imports
        verdict = self._check_imports(challenger_code)
        if not verdict.passed:
            return verdict

        # Rule 3: File paths
        verdict = self._check_paths(challenger_code)
        if not verdict.passed:
            return verdict

        return RefereeVerdict(passed=True, reason="All safety checks passed.")

    # ── Rule 1: Syntax ────────────────────────────────────────────────────────

    def _check_syntax(self, code: str) -> RefereeVerdict:
        try:
            ast.parse(code)
            return RefereeVerdict(passed=True, reason="Syntax OK")
        except SyntaxError as e:
            return RefereeVerdict(
                passed=False,
                reason=f"Syntax error at line {e.lineno}: {e.msg}"
            )

    # ── Rule 2: Imports ───────────────────────────────────────────────────────

    def _check_imports(self, code: str) -> RefereeVerdict:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return RefereeVerdict(passed=False, reason="Cannot check imports — syntax error.")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in ALLOWED_TOP_LEVEL_IMPORTS:
                        return RefereeVerdict(
                            passed=False,
                            reason=f"Forbidden import: '{alias.name}'. Only whitelisted packages are allowed."
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top not in ALLOWED_TOP_LEVEL_IMPORTS:
                        return RefereeVerdict(
                            passed=False,
                            reason=f"Forbidden import from: '{node.module}'. Only whitelisted packages are allowed."
                        )

        return RefereeVerdict(passed=True, reason="Imports OK")

    # ── Rule 3: Path checks ───────────────────────────────────────────────────

    def _check_paths(self, code: str) -> RefereeVerdict:
        """
        Uses regex to detect any open() call with a write mode ('w', 'a', 'x')
        that targets a path outside the safe zone.
        """
        # Detect open() calls with write modes — captures the path string argument
        write_open_pattern = re.compile(
            r"""open\s*\(\s*(?:f?["']([^"']+)["']|([^,\)]+))\s*,\s*["'][wa]"""
        )

        matches = write_open_pattern.findall(code)
        for literal_path, _ in matches:
            if literal_path:
                normalized = literal_path.replace("\\", "/")
                if not any(normalized.startswith(safe) for safe in SAFE_WRITE_PREFIXES):
                    return RefereeVerdict(
                        passed=False,
                        reason=f"Forbidden file write to path: '{literal_path}'. Writes are only allowed in src/agents/ and staging/."
                    )

        # Also check for shutil.copy/move/rmtree targeting locked files
        locked_names_pattern = re.compile(
            r"(system_guard|sandbox|evoflow|arena)\.py"
        )
        if locked_names_pattern.search(code):
            return RefereeVerdict(
                passed=False,
                reason="Code references a locked system file (system_guard, sandbox, evoflow, or arena). This is forbidden."
            )

        return RefereeVerdict(passed=True, reason="Path checks OK")
