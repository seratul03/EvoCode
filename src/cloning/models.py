from dataclasses import dataclass, field

@dataclass
class CandidateClone:
    """Immutable record of one candidate modification experiment."""
    candidate_id: str
    agent_id: str
    parent_genome: dict
    candidate_genome: dict
    diff: dict
    parent_hash: str
    candidate_hash: str
    hypothesis: dict = field(default_factory=dict)
    workspace_path: str = ""
    committed: bool = False
    discarded: bool = False
