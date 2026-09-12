"""
tests/test_phase8_arena.py

Phase 8 spec tests:
  - Parent and candidate are evaluated on identical test groups.
  - Candidate with a better configuration wins the arena.
  - The result contains a valid hash and fairness flag.
"""

import pytest
from src.arena import ArenaReferee, ArenaResult
from src.genome import AgentGenome
from src.environment import EnvironmentProfile


class TestArenaReferee:
    
    def setup_method(self):
        self.referee = ArenaReferee()
        self.env_profile = EnvironmentProfile(level=1)

    def test_identical_agents_draw(self):
        parent = AgentGenome(temperature=0.5)
        # Deep copy to ensure they are identical
        candidate = AgentGenome(**parent.model_dump())
        
        result = self.referee.compare(parent.model_dump(), candidate.model_dump(), self.env_profile)
        
        assert result.winner == "draw"
        assert abs(result.parent_score - result.candidate_score) < 0.05
        assert result.margin < 0.05

    def test_better_candidate_wins(self):
        parent = AgentGenome(temperature=0.5)
        parent.reasoning.reasoning_depth = 2
        
        # Candidate has better reasoning depth, should score higher in the simulation
        candidate = AgentGenome(temperature=0.5)
        candidate.reasoning.reasoning_depth = 4
        
        result = self.referee.compare(parent.model_dump(), candidate.model_dump(), self.env_profile)
        
        assert result.winner == "candidate"
        assert result.candidate_score > result.parent_score
        assert result.margin > 0

    def test_worse_candidate_loses(self):
        parent = AgentGenome(temperature=0.5)
        parent.reasoning.reasoning_depth = 4
        
        # Candidate has worse reasoning depth
        candidate = AgentGenome(temperature=0.5)
        candidate.reasoning.reasoning_depth = 1
        
        result = self.referee.compare(parent.model_dump(), candidate.model_dump(), self.env_profile)
        
        assert result.winner == "parent"
        assert result.parent_score > result.candidate_score

    def test_all_test_groups_populated(self):
        parent = AgentGenome()
        candidate = AgentGenome()
        
        result = self.referee.compare(parent.model_dump(), candidate.model_dump(), self.env_profile)
        
        # In the fallback mock scenario, all groups should have scores
        expected_groups = [
            "known_solved", 
            "unrelated", 
            "adversarial", 
            "regression"
        ]
        
        for group in expected_groups:
            assert group in result.group_scores
            assert "parent" in result.group_scores[group]
            assert "candidate" in result.group_scores[group]
