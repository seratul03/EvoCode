import pytest
import os
import shutil
import json
from src.collaboration import CollaborationManager
from src.memory_manager import MemoryManager, EvolutionEvent

class DummyClient:
    async def create_completion(self, messages, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": "Focus on dynamic programming and breaking down recursive trees."
                }
            }]
        }

@pytest.fixture
def test_workspace():
    # Setup
    workspace = "workspaces"
    os.makedirs(workspace, exist_ok=True)
    
    # Create fake agents
    donor_id = "EVO_CPP"
    target_id = "EVO_PY"
    
    # Seed donor with successful memory
    event = EvolutionEvent.create(
        agent_id=donor_id,
        generation=1,
        trigger_data={"category": "recursion"},
        hypothesis_data={"hypothesis": "Implement bottom-up dynamic programming to avoid recursion limits."},
        selection_decision="PROMOTE"
    )
    MemoryManager.record_event(event)
    
    yield
    
    # Teardown
    if os.path.exists(workspace):
        shutil.rmtree(workspace)

@pytest.mark.asyncio
async def test_collaboration_manager_retrieval(test_workspace):
    client = DummyClient()
    manager = CollaborationManager(client)
    
    # Target agent triggers evolution in recursion category
    trigger_reason = {"category": "recursion", "objective": "Improve recursion depth."}
    
    # Get advice
    advice = await manager.get_crossover_advice("EVO_PY", trigger_reason)
    
    # Assert LLM was called and advice was returned
    assert advice is not None
    assert "dynamic programming" in advice
    
@pytest.mark.asyncio
async def test_collaboration_manager_no_match(test_workspace):
    client = DummyClient()
    manager = CollaborationManager(client)
    
    # Target agent triggers evolution in UNKNOWN category
    trigger_reason = {"category": "string_parsing"}
    
    # Get advice
    advice = await manager.get_crossover_advice("EVO_PY", trigger_reason)
    
    # Assert no advice returned (no successes in string_parsing)
    assert advice is None

@pytest.mark.asyncio
async def test_collaboration_manager_excludes_self(test_workspace):
    client = DummyClient()
    manager = CollaborationManager(client)
    
    # Target agent EVO_CPP triggers evolution. 
    # Even though EVO_CPP has a recursion success, it shouldn't read its own memory.
    trigger_reason = {"category": "recursion"}
    
    # Get advice
    advice = await manager.get_crossover_advice("EVO_CPP", trigger_reason)
    
    # Assert no advice returned
    assert advice is None
