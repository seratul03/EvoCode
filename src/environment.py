"""
src/environment.py

Phase 12: Adaptive Environmental Pressure.
Adjusts evaluation difficulty based on the strength of the active population.
"""

import json
import os
from dataclasses import dataclass

@dataclass
class EnvironmentProfile:
    """Current evaluation pressure requirements."""
    level: int = 1
    
    @property
    def efficiency_weight(self) -> float:
        # e.g., Level 1 -> 0.1, Level 5 -> 0.5
        return 0.1 * self.level
        
    @property
    def robustness_weight(self) -> float:
        # e.g., Level 1 -> 0.1, Level 5 -> 0.5
        return 0.1 * self.level
        
    @property
    def base_correctness_threshold(self) -> float:
        # Agents must score at least this on base tests to get ANY efficiency/robustness points.
        # Starts at 0.5 for Level 1, maxes at 0.9.
        return min(0.9, 0.4 + (0.1 * self.level))


class EnvironmentManager:
    """
    Tracks population fitness and adjusts the environment pressure level.
    """
    WORKSPACE_ROOT = "workspaces"
    ENV_FILE = os.path.join(WORKSPACE_ROOT, "environment.json")

    def __init__(self):
        self.profile = self._load_profile()

    def _load_profile(self) -> EnvironmentProfile:
        if os.path.exists(self.ENV_FILE):
            try:
                with open(self.ENV_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return EnvironmentProfile(level=data.get("level", 1))
            except json.JSONDecodeError:
                pass
        return EnvironmentProfile(level=1)

    def _save_profile(self):
        os.makedirs(self.WORKSPACE_ROOT, exist_ok=True)
        with open(self.ENV_FILE, "w", encoding="utf-8") as f:
            json.dump({"level": self.profile.level}, f, indent=2)

    def evaluate_pressure(self, population_scores: dict[str, float]) -> EnvironmentProfile:
        """
        Adapts the environment level based on average population fitness.
        Called periodically (e.g., at the end of an evolution cycle).
        """
        if not population_scores:
            return self.profile

        avg_fitness = sum(population_scores.values()) / len(population_scores)
        
        changed = False
        if avg_fitness > 0.85:
            # Population is thriving, increase pressure
            self.profile.level += 1
            changed = True
        elif avg_fitness < 0.40 and self.profile.level > 1:
            # Population is struggling massively, reduce pressure
            self.profile.level -= 1
            changed = True
            
        if changed:
            self._save_profile()
            print(f"  [Environment] Pressure adapted! New Level: {self.profile.level} (Avg Fitness: {avg_fitness:.2f})")
            
        return self.profile
