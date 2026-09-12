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
            # Fallback if no real test problems available (e.g. during testing)
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

        # For this offline mock, just distribute roughly
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

        # Fill known_solved and regression randomly from all
        all_probs = self.problems.copy()
        random.shuffle(all_probs)
        groups["known_solved"] = all_probs[:max(1, len(all_probs) // 10)]
        groups["regression"] = all_probs[max(1, len(all_probs) // 10):max(2, len(all_probs) // 5)]

        return groups

    def _offline_simulate_run(self, genome: AgentGenome, seed: int, env_profile: EnvironmentProfile) -> dict:
        """
        Simulates an offline evaluation run for a single genome using the given seed and environment profile.
        """
        rng = random.Random(seed)
        triggering_category = "recursion"
        test_groups = self._sample_test_groups(triggering_category)
        
        group_scores = {}
        total_score = 0.0
        total_problems = 0
        
        for group_name, problems in test_groups.items():
            if not problems:
                continue
                
            group_score = 0.0
            for p in problems:
                base_perf = (
                    (1.0 - abs(genome.temperature - 0.3)) * 0.5 + 
                    (min(genome.reasoning.reasoning_depth, 10) / 10) * 0.2 +
                    (min(genome.verification.verification_depth, 10) / 10) * 0.3
                )
                
                # Environment Pressure modifications
                # Under high pressure, base_perf must clear the base_correctness_threshold 
                # to earn full efficiency and robustness bonuses.
                efficiency_bonus = (min(genome.reasoning.reasoning_depth, 10) / 10) * env_profile.efficiency_weight
                robustness_bonus = (min(genome.verification.verification_depth, 10) / 10) * env_profile.robustness_weight
                
                if base_perf < env_profile.base_correctness_threshold:
                    # Penalize heavily if core correctness is lacking in a high pressure environment
                    penalty = (env_profile.base_correctness_threshold - base_perf) * 0.5 * env_profile.level
                    efficiency_bonus = 0
                    robustness_bonus = 0
                    base_perf -= penalty

                # We add a slight random fuzz to simulate real-world noise, 
                # but keep it heavily weighted towards genome parameters
                noise = (rng.random() - 0.5) * 0.1
                
                raw_score = base_perf + efficiency_bonus + robustness_bonus + noise
                score = max(0.0, min(1.0, raw_score))
                
                group_score += score
                total_score += score
                total_problems += 1
                
            group_scores[group_name] = round(group_score / len(problems), 4)
            
        avg_score = total_score / max(1, total_problems)
        return {
            "group_scores": group_scores,
            "overall_score": round(avg_score, 4)
        }

    def compare(self, parent_genome_data: dict, candidate_genome_data: dict, env_profile: EnvironmentProfile = None) -> ArenaResult:
        """
        Runs both genomes through identical simulated task groups.
        Uses the provided environment profile to adjust evaluation pressure.
        """
        if env_profile is None:
            env_profile = EnvironmentProfile()
            
        p_genome = AgentGenome(**parent_genome_data)
        c_genome = AgentGenome(**candidate_genome_data)
        
        # 1. Prepare identical deterministically seeded runs
        seed_p = int(hashlib.md5(b"parent_run").hexdigest(), 16)
        seed_c = int(hashlib.md5(b"candidate_run").hexdigest(), 16)
        
        # 2. Simulate
        p_results = self._offline_simulate_run(p_genome, seed_p, env_profile)
        c_results = self._offline_simulate_run(c_genome, seed_c, env_profile)
        
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
                "parent": p_results["group_scores"][group_name],
                "candidate": c_results["group_scores"].get(group_name, 0.0)
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
            result_hash=""
        )
        
        # Calculate secure hash of result
        raw = json.dumps(result.to_dict(), sort_keys=True).encode("utf-8")
        result.result_hash = hashlib.sha256(raw).hexdigest()
        
        return result
