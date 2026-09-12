"""
Phase 17: Meta-Evolution Package

This package implements the second-order evolutionary loop where EvoCode agents
can upgrade their own source files in src/agents/ when their performance degrades.

Components:
    - Watcher:      Monitors success rates and triggers upgrades
    - CloneBuilder: LLM agents that propose rewrites to agent source files
    - SourceJudge:  LLM agents that vote on the best proposal
    - MetaArena:    Runs Original vs. Clone in a fast duel
    - Referee:      Hardcoded safety rules enforcer (non-LLM)
"""

from src.meta_evolution.watcher import Watcher, UpgradeTrigger
from src.meta_evolution.clone_builder import CloneBuilder
from src.meta_evolution.source_judge import SourceJudge
from src.meta_evolution.referee import Referee
from src.meta_evolution.meta_arena import MetaArena

__all__ = [
    "Watcher",
    "UpgradeTrigger",
    "CloneBuilder",
    "SourceJudge",
    "Referee",
    "MetaArena",
]
