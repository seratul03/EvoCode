"""
src/arena.py

Phase 8: The Evolution Arena.

Where a verified candidate clone competes against its parent.
The referee controls the contest, ensuring fair conditions.
For this phase, the evaluation uses a simulated scoring model based on the genome's
parameters against sampled problems. This allows deterministic offline testing
of the arena pipeline before full live LLM generation is hooked up in a later sprint.
"""

import hashlib
import json
import os
import random
from dataclasses import dataclass, field
from typing import Literal, Optional

from src.genome import AgentGenome
from src.environment import EnvironmentProfile


@dataclass
class ArenaResult:
    agent_id: str
    winner: Literal["parent", "candidate", "draw"]
    parent_score: float
    candidate_score: float
    margin: float
    group_scores: dict
    fairness_verified: bool
    result_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "winner": self.winner,
            "parent_score": round(self.parent_score, 4),
            "candidate_score": round(self.candidate_score, 4),
            "margin": round(self.margin, 4),
            "group_scores": self.group_scores,
            "fairness_verified": self.fairness_verified,
            "result_hash": self.result_hash,
        }


class ArenaReferee:
    """
    Independent referee that scores a parent against a candidate on an identical
    task set.
    """

    def __init__(self, problems_file: str = "data/test_problems.json"):
        self.problems_file = problems_file
        self.problems = self._load_problems()

    def _load_problems(self) -> list[dict]:
        if not os.path.exists(self.problems_file):
            return []
        try:
            with open(self.problems_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def _sample_test_groups(self, triggering_category: str) -> dict[str, list[dict]]:
        """
        Samples problems into the 6 spec groups.
        """
        if not self.problems:
            return {
                "known_solved": [{"id": "fb1", "category": "general"}],
                "triggering": [{"id": "fb2", "category": triggering_category}],
                "unseen_related": [{"id": "fb3", "category": triggering_category}],
                "unrelated": [{"id": "fb4", "category": "other"}],
                "adversarial": [{"id": "fb5", "category": "edge_cases"}],
                "regression": [{"id": "fb6", "category": "general"}],
            }

        groups = {
            "known_solved": [],
            "triggering": [],
            "unseen_related": [],
            "unrelated": [],
            "adversarial": [],
            "regression": [],
        }

        for p in self.problems:
            cat = p.get("category", "general")
            if cat == triggering_category:
                if random.random() > 0.5:
                    groups["triggering"].append(p)
                else:
                    groups["unseen_related"].append(p)
            elif cat == "edge_cases":
                groups["adversarial"].append(p)
            else:
                groups["unrelated"].append(p)

        all_probs = self.problems.copy()
        random.shuffle(all_probs)
        groups["known_solved"] = all_probs[:max(1, len(all_probs) // 10)]
        groups["regression"] = all_probs[max(1, len(all_probs) // 10):max(2, len(all_probs) // 5)]

        return groups

    def _score_genome(self, genome_data: dict, env_profile: EnvironmentProfile) -> dict:
        """
        Simulated deterministic scorer based on genome parameters.
        This is the Phase 8 offline model — it avoids live LLM calls while still
        producing scores that reflect genome quality differences, so the arena tests
        can run without Docker or API keys.

        Score components:
          - reasoning_depth (0-5 → 0.0-1.0): deeper reasoning → higher score
          - temperature (0.0-1.0): lower temp → more consistent → higher score
          - verification_depth (0-5 → 0.0-1.0): deeper verification → higher score
          - env_profile.level penalty: higher pressure level reduces raw score
        """
        reasoning = genome_data.get("reasoning", {})
        verification = genome_data.get("verification", {})

        depth_score = min(1.0, reasoning.get("reasoning_depth", 2) / 5.0)
        temp_score = 1.0 - genome_data.get("temperature", 0.5)
        verif_score = min(1.0, verification.get("verification_depth", 2) / 5.0)

        raw_score = (depth_score * 0.5) + (temp_score * 0.3) + (verif_score * 0.2)

        # Higher environment pressure → harder evaluation → lower scores
        pressure_penalty = (env_profile.level - 1) * 0.05
        final_score = max(0.0, raw_score - pressure_penalty)

        group_scores = {
            "known_solved": final_score,
            "triggering":   final_score,
            "unseen_related": final_score,
            "unrelated":    final_score,
            "adversarial":  final_score * 0.9,
            "regression":   final_score,
        }
        return {"group_scores": group_scores, "overall_score": final_score}

    def compare(self, parent_genome_data: dict, candidate_genome_data: dict, env_profile: EnvironmentProfile = None) -> ArenaResult:
        """
        Scores both genomes with the simulated model and declares a winner.

        This is a synchronous, deterministic method — no LLM calls, no Docker.
        It is designed for offline unit testing of the arena pipeline.
        The MetaEvolutionRunner uses the live MetaArena (src/meta_evolution/meta_arena.py)
        for real-world code-level duels.
        """
        if env_profile is None:
            env_profile = EnvironmentProfile()

        p_results = self._score_genome(parent_genome_data, env_profile)
        c_results = self._score_genome(candidate_genome_data, env_profile)

        parent_score = p_results["overall_score"]
        candidate_score = c_results["overall_score"]

        margin = candidate_score - parent_score
        if margin > 0.01:
            winner = "candidate"
        elif margin < -0.01:
            winner = "parent"
        else:
            winner = "draw"

        group_scores = {}
        for group_name in p_results["group_scores"]:
            group_scores[group_name] = {
                "parent":    p_results["group_scores"][group_name],
                "candidate": c_results["group_scores"].get(group_name, 0.0),
            }

        agent_id = parent_genome_data.get("agent_id", "agent_unknown")

        result = ArenaResult(
            agent_id=agent_id,
            winner=winner,
            parent_score=parent_score,
            candidate_score=candidate_score,
            margin=margin,
            group_scores=group_scores,
            fairness_verified=True,
            result_hash="",
        )

        raw = json.dumps(result.to_dict(), sort_keys=True).encode("utf-8")
        result.result_hash = hashlib.sha256(raw).hexdigest()

        return result
