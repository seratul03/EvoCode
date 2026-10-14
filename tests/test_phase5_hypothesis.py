import pytest
import asyncio
from src.agents.hypothesis_engine import HypothesisEngine
from src.client import EvoClient
from src.genome import AgentGenome

class MockSuccessClient:
    async def create_completion(self, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": "```json\n{\n  \"hypothesis\": \"Test hypothesis\",\n  \"expected_improvement\": \"Test improvement\",\n  \"target_component\": \"temperature\"\n}\n```"
                }
            }]
        }

class MockFailClient:
    async def create_completion(self, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": "This is just some text, not JSON."
                }
            }]
        }

class MockMissingKeysClient:
    async def create_completion(self, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": "{\"wrong_key\": \"value\"}"
                }
            }]
        }

@pytest.mark.asyncio
async def test_hypothesis_engine_success():
    client = MockSuccessClient()
    engine = HypothesisEngine(client)
    genome = AgentGenome()
    reason = {"objective": "Fix recursion"}
    
    result = await engine.generate_hypothesis("EVO_PY", reason, genome)
    
    assert result["hypothesis"] == "Test hypothesis"
    assert result["expected_improvement"] == "Test improvement"
    assert result["target_component"] == "temperature"

@pytest.mark.asyncio
async def test_hypothesis_engine_invalid_json_fallback():
    client = MockFailClient()
    engine = HypothesisEngine(client)
    genome = AgentGenome()
    reason = {"objective": "Fix recursion"}
    
    result = await engine.generate_hypothesis("EVO_PY", reason, genome)
    
    assert "Adjust temperature" in result["hypothesis"]
    assert result["target_component"] == "reasoning.planning_strategy"

@pytest.mark.asyncio
async def test_hypothesis_engine_missing_keys_fallback():
    client = MockMissingKeysClient()
    engine = HypothesisEngine(client)
    genome = AgentGenome()
    reason = {"objective": "Fix recursion"}
    
    result = await engine.generate_hypothesis("EVO_PY", reason, genome)
    
    assert "Adjust temperature" in result["hypothesis"]
    assert result["target_component"] == "reasoning.planning_strategy"
