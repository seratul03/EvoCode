from dataclasses import dataclass, field

@dataclass
class CandidateClone:
    """Immutable record of one candidate modification experiment."""
    candidate_id: str
    agent_id: str
    parent_genome: dict                    # frozen snapshot of the parent
    candidate_genome: dict                 # modified candidate snapshot
    diff: dict                             # only the changed fields
    parent_hash: str                       # sha256 of the parent JSON
    candidate_hash: str                    # sha256 of the candidate JSON
    hypothesis: dict = field(default_factory=dict)
    workspace_path: str = ""               # path to workspaces/{agent_id}/candidates/{id}/
    committed: bool = False
    discarded: bool = False
