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
    workspace = "workspaces"
    os.makedirs(workspace, exist_ok=True)
    
    donor_id = "EVO_CPP"
    target_id = "EVO_PY"
    
    event = EvolutionEvent.create(
        agent_id=donor_id,
        generation=1,
        trigger_data={"category": "recursion"},
        hypothesis_data={"hypothesis": "Implement bottom-up dynamic programming to avoid recursion limits."},
        selection_decision="PROMOTE"
    )
    MemoryManager.record_event(event)
    
    yield
    
    if os.path.exists(workspace):
        shutil.rmtree(workspace)

@pytest.mark.asyncio
async def test_collaboration_manager_retrieval(test_workspace):
    client = DummyClient()
    manager = CollaborationManager(client)
    
    trigger_reason = {"category": "recursion", "objective": "Improve recursion depth."}
    
    advice = await manager.get_crossover_advice("EVO_PY", trigger_reason)
    
    assert advice is not None
    assert "dynamic programming" in advice
    
@pytest.mark.asyncio
async def test_collaboration_manager_no_match(test_workspace):
    client = DummyClient()
    manager = CollaborationManager(client)
    
    trigger_reason = {"category": "string_parsing"}
    
    advice = await manager.get_crossover_advice("EVO_PY", trigger_reason)
    
    assert advice is None

@pytest.mark.asyncio
async def test_collaboration_manager_excludes_self(test_workspace):
    client = DummyClient()
    manager = CollaborationManager(client)
    
    trigger_reason = {"category": "recursion"}
    
    advice = await manager.get_crossover_advice("EVO_CPP", trigger_reason)
    
    assert advice is None
