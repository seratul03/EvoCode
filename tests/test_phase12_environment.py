"""
tests/test_phase12_environment.py

Phase 12 spec tests:
  - Strong population causes increased difficulty.
  - Weak population does not.
  - The same adaptive policy behaves predictably for identical histories.
"""

import os
import shutil
import pytest
from src.environment import EnvironmentManager, EnvironmentProfile
from src.arena import ArenaReferee
from src.genome import AgentGenome

class TestPhase12Environment:
    
    WORKSPACE_ROOT = "workspaces"
    
    def setup_method(self):
        if os.path.exists(self.WORKSPACE_ROOT):
            shutil.rmtree(self.WORKSPACE_ROOT)
            
    def teardown_method(self):
        if os.path.exists(self.WORKSPACE_ROOT):
            shutil.rmtree(self.WORKSPACE_ROOT)
            
    def test_strong_population_increases_pressure(self):
        env = EnvironmentManager()
        assert env.profile.level == 1
        
        # Super strong population
        scores = {"A1": 0.95, "A2": 0.92, "A3": 0.88}
        env.evaluate_pressure(scores)
        
        assert env.profile.level == 2
        
    def test_weak_population_decreases_pressure(self):
        env = EnvironmentManager()
        env.profile.level = 3 # Force start at level 3
        
        # Weak population
        scores = {"A1": 0.3, "A2": 0.25}
        env.evaluate_pressure(scores)
        
        assert env.profile.level == 2
        
    def test_moderate_population_keeps_pressure(self):
        env = EnvironmentManager()
        env.profile.level = 2
        
        # Moderate
        scores = {"A1": 0.6, "A2": 0.7}
        env.evaluate_pressure(scores)
        
        assert env.profile.level == 2
        
    def test_higher_pressure_lowers_scores(self):
        # We test that identical genomes perform WORSE when evaluated under a higher pressure
        arena = ArenaReferee()
        
        genome = AgentGenome(
            temperature=0.7,      # Suboptimal
            reasoning={"reasoning_depth": 2},      # Low efficiency equivalent
            verification={"verification_depth": 2} # Low robustness equivalent
        ).model_dump()
        
        # Level 1 evaluation
        env1 = EnvironmentProfile(level=1)
        res1 = arena.compare(genome, genome, env1)
        score1 = res1.parent_score
        
        # Level 5 evaluation
        env5 = EnvironmentProfile(level=5)
        res5 = arena.compare(genome, genome, env5)
        score5 = res5.parent_score
        
        # Because the genome lacks efficiency and robustness, and its temperature is off,
        # it will fail to meet the higher correctness threshold in Level 5 and get penalized.
        assert score5 < score1
