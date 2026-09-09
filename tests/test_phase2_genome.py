import pytest
from pydantic import ValidationError
from src.genome import AgentGenome, ReasoningGenes, EvolutionGenes

def test_serialize_deserialize():
    genome = AgentGenome(agent_id="EVO_PY", version="v1.0")
    
    # Serialize to JSON string
    json_str = genome.model_dump_json()
    assert "EVO_PY" in json_str
    
    # Deserialize back
    restored = AgentGenome.model_validate_json(json_str)
    assert restored.agent_id == "EVO_PY"
    assert restored.reasoning.reasoning_depth == 3

def test_invalid_genome_values_rejected():
    with pytest.raises(ValidationError):
        # reasoning_depth must be >= 0
        AgentGenome(reasoning=ReasoningGenes(reasoning_depth=-1))
        
    with pytest.raises(ValidationError):
        # experimentation_aggressiveness must be <= 1.0
        AgentGenome(evolution=EvolutionGenes(experimentation_aggressiveness=1.5))

def test_lineage_fields_survive_cloning():
    parent = AgentGenome(agent_id="EVO_PY", generation_id=1)
    
    # Deep copy clone
    child = parent.model_copy(deep=True)
    child.generation_id = 2
    child.parent_id = 123
    
    assert child.agent_id == "EVO_PY"
    assert child.generation_id == 2
    assert child.parent_id == 123

def test_clone_independence():
    parent = AgentGenome(agent_id="EVO_PY")
    child = parent.model_copy(deep=True)
    
    # Modify child
    child.reasoning.planning_strategy = "tree_of_thought"
    
    # Parent should be unaffected
    assert parent.reasoning.planning_strategy == "direct"

def test_control_plane_separation():
    genome = AgentGenome()
    # Verify genome does not have fields related to docker, host, or referee
    fields = genome.model_dump().keys()
    assert "docker" not in fields
    assert "evaluator" not in fields
    assert "referee" not in fields
