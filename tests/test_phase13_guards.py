"""
tests/test_phase13_guards.py

Phase 13 spec tests:
  - Simulate agent corruption and verify rollback.
  - Test that repeated crashes cause the agent to be quarantined.
"""

import os
import shutil
import pytest
from src.system_guard import SystemGuard

class MockPopulationManager:
    def __init__(self):
        self.removed_agents = []
        
    def remove_agent(self, agent_id):
        self.removed_agents.append(agent_id)

class MockEvoFlow_Success:
    async def trigger_evolution(self, agent_id):
        # Mutate a file to prove it ran, but don't crash
        with open(os.path.join("workspaces", agent_id, "test.txt"), "w") as f:
            f.write("success")

class MockEvoFlow_Crash:
    async def trigger_evolution(self, agent_id):
        # Mutate a file, THEN crash
        with open(os.path.join("workspaces", agent_id, "test.txt"), "w") as f:
            f.write("corrupted")
        raise RuntimeError("Simulated catastrophic crash")


class TestPhase13Guards:
    
    WORKSPACE_ROOT = "workspaces"
    AGENT_ID = "TEST_GUARD_AGENT"
    
    def setup_method(self):
        if os.path.exists(self.WORKSPACE_ROOT):
            shutil.rmtree(self.WORKSPACE_ROOT)
            
        os.makedirs(os.path.join(self.WORKSPACE_ROOT, self.AGENT_ID))
        with open(os.path.join(self.WORKSPACE_ROOT, self.AGENT_ID, "test.txt"), "w") as f:
            f.write("original")
            
    def teardown_method(self):
        if os.path.exists(self.WORKSPACE_ROOT):
            shutil.rmtree(self.WORKSPACE_ROOT)
            
    @pytest.mark.asyncio
    async def test_successful_evolution_keeps_changes(self):
        pop = MockPopulationManager()
        guard = SystemGuard(pop)
        
        await guard.execute_with_guards(MockEvoFlow_Success(), self.AGENT_ID)
        
        # Verify changes stuck and no rollback happened
        with open(os.path.join(self.WORKSPACE_ROOT, self.AGENT_ID, "test.txt"), "r") as f:
            content = f.read()
            
        assert content == "success"
        
        # Verify snapshot was cleaned up
        assert len(os.listdir(os.path.join(self.WORKSPACE_ROOT, "_snapshots"))) == 0

    @pytest.mark.asyncio
    async def test_crash_triggers_rollback(self):
        pop = MockPopulationManager()
        guard = SystemGuard(pop)
        
        await guard.execute_with_guards(MockEvoFlow_Crash(), self.AGENT_ID)
        
        # Verify rollback restored the original state, discarding "corrupted"
        with open(os.path.join(self.WORKSPACE_ROOT, self.AGENT_ID, "test.txt"), "r") as f:
            content = f.read()
            
        assert content == "original"
        
        # Verify crash was logged
        crashes = os.listdir(os.path.join(self.WORKSPACE_ROOT, "_crashes"))
        assert len(crashes) == 1
        
    @pytest.mark.asyncio
    async def test_repeated_crashes_quarantine_agent(self):
        pop = MockPopulationManager()
        guard = SystemGuard(pop)
        
        # Crash it 3 times (the MAX_CRASHES threshold)
        for _ in range(3):
            await guard.execute_with_guards(MockEvoFlow_Crash(), self.AGENT_ID)
            
        assert self.AGENT_ID in pop.removed_agents
