"""
duel_runner.py — Lightweight standalone duel script for MetaArena.

This script is called as a subprocess by MetaArena. It runs a single
EvoFlow generation on a fixed hardcoded problem, then exits.

It is intentionally minimal:
  - No problem generation (LLM call avoided)
  - No memory synthesis
  - No collaboration
  - No meta-evolution (obviously)
  - Writes ONE structured report to EVOCODE_REPORT_DIR

Usage (by MetaArena only):
    python src/meta_evolution/duel_runner.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.client import EvoClient
from src.evoflow import EvoFlowOrchestrator

# ── Fixed duel problem — simple, fast, deterministic ─────────────────────────
# Using a simple problem so one generation is enough to get a meaningful signal.

DUEL_PROBLEM = {
    "title": "Sum of Two Numbers",
    "description": (
        "Write a Python function called `solution` that takes two integers "
        "`a` and `b` and returns their sum."
    ),
    "function_signature": "def solution(a: int, b: int) -> int:",
    "test_cases": [
        {"input": {"a": 1, "b": 2}, "expected_output": 3},
        {"input": {"a": -1, "b": 1}, "expected_output": 0},
        {"input": {"a": 0, "b": 0}, "expected_output": 0},
        {"input": {"a": 100, "b": 200}, "expected_output": 300},
        {"input": {"a": -50, "b": -50}, "expected_output": -100},
    ],
    "difficulty": "Easy",
    "category": "math",
}


async def run_duel():
    orchestrator = EvoFlowOrchestrator(
        pop_size=3,
        enable_evolution=False,       # No evolution during duel
        enable_memory=False,          # No memory injection
        enable_collaboration=False,   # No collaboration
    )
    await orchestrator.run_generations(
        num_generations=1,
        problems=[DUEL_PROBLEM],
        mode="evolve",
        disable_circuit_breaker=True
    )


if __name__ == "__main__":
    asyncio.run(run_duel())
