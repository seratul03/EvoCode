"""
tests/test_phase11_population.py

Phase 11 spec tests:
  - Descendants inherit valid lineage.
  - Descendant genomes are independent workspaces.
  - Population limits are enforced.
  - Duplicate/near-identical agents can be detected.
"""

import json
import os
import shutil
import pytest
from src.population import PopulationManager
from src.clone_manager import CloneManager, CandidateClone
from src.genome import AgentGenome


class TestPhase11Population:
    
    WORKSPACE_ROOT = "workspaces"
    AGENT_ID = "TEST_POP_AGENT"
    
    def setup_method(self):
        if os.path.exists(self.WORKSPACE_ROOT):
            shutil.rmtree(self.WORKSPACE_ROOT)
        os.makedirs(os.path.join(self.WORKSPACE_ROOT, self.AGENT_ID, "candidates", "dummy"), exist_ok=True)
            
    def teardown_method(self):
        if os.path.exists(self.WORKSPACE_ROOT):
            shutil.rmtree(self.WORKSPACE_ROOT)
            
    def _make_dummy_clone(self, temp=0.5):
        genome = AgentGenome(temperature=temp).model_dump()
        c = CandidateClone(
            candidate_id="dummy",
            agent_id=self.AGENT_ID,
            parent_genome=genome,
            candidate_genome=genome,
            diff={},
            parent_hash="hash_p",
            candidate_hash=f"hash_c_{temp}",
            workspace_path=os.path.join(self.WORKSPACE_ROOT, self.AGENT_ID, "candidates", "dummy")
        )
        with open(os.path.join(c.workspace_path, "genome.json"), "w") as f:
            json.dump(genome, f)
        return c
            
    def test_duplicate_detection(self):
        manager = PopulationManager(max_population=5)
        manager.register_agent("A1", "hash123")
        
        assert manager.is_duplicate("hash123") is True
        assert manager.is_duplicate("hash456") is False
        
    def test_fork_to_new_agent(self):
        clone = self._make_dummy_clone()
        new_agent_id = CloneManager.fork_to_new_agent(clone)
        
        # Should create TEST_POP_AGENT_v1 since there are no existing _v versions
        assert new_agent_id == f"{self.AGENT_ID}_v1"
        assert os.path.exists(os.path.join(self.WORKSPACE_ROOT, new_agent_id, "genome.json"))
        
        # A second fork should create _v2
        new_agent_id_2 = CloneManager.fork_to_new_agent(clone)
        assert new_agent_id_2 == f"{self.AGENT_ID}_v2"
        assert os.path.exists(os.path.join(self.WORKSPACE_ROOT, new_agent_id_2, "genome.json"))
        
    def test_enforce_population_limit(self):
        manager = PopulationManager(max_population=2)
        
        # Add 3 agents
        manager.register_agent("A1", "hash1")
        manager.register_agent("A2", "hash2")
        manager.register_agent("A3", "hash3")
        
        # Setup dummy dirs for them so archive can move them
        for a in ["A1", "A2", "A3"]:
            os.makedirs(os.path.join(self.WORKSPACE_ROOT, a))
            
        assert len(manager.active_agents) == 3
        
        # A2 is weakest
        scores = {"A1": 0.9, "A2": 0.2, "A3": 0.8}
        manager.enforce_population_limit(scores)
        
        assert len(manager.active_agents) == 2
        assert "A2" not in manager.active_agents
        assert "A1" in manager.active_agents
        assert "A3" in manager.active_agents
        
        # Verify A2 was moved to archive
        assert not os.path.exists(os.path.join(self.WORKSPACE_ROOT, "A2"))
        assert os.path.exists(os.path.join(self.WORKSPACE_ROOT, "_archive", "A2"))
