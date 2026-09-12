"""
src/clone_manager.py

Phase 6: Clone-Based Self-Modification.

Manages the safe creation, modification, and lifecycle of candidate genome clones.
The CloneManager enforces the access policy from the spec:
  - Candidates may only write inside workspaces/{agent_id}/candidates/
  - The parent workspace and all other agents' workspaces are read-only / untouched.
  - The src/ control plane is never touched.
"""

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.genome import AgentGenome


# ── Control-plane directories that a candidate can never write to ────────────
_FORBIDDEN_PREFIXES = [
    "src",
    "tests",
    "data",
    "analysis",
    "Documentations",
]


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


def _sha256(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _compute_diff(parent: dict, candidate: dict) -> dict:
    """Return only the top-level (and nested) keys that changed."""
    diff = {}
    all_keys = set(parent.keys()) | set(candidate.keys())
    for k in all_keys:
        p_val = parent.get(k)
        c_val = candidate.get(k)
        if p_val != c_val:
            # For nested dicts, recurse one level
            if isinstance(p_val, dict) and isinstance(c_val, dict):
                nested = _compute_diff(p_val, c_val)
                if nested:
                    diff[k] = {"before": p_val, "after": c_val, "nested_diff": nested}
            else:
                diff[k] = {"before": p_val, "after": c_val}
    return diff


def _apply_dotted_path(data: dict, dotted_key: str, value: Any) -> bool:
    """
    Apply a value at a dot-separated path in a nested dict.
    e.g. 'reasoning.planning_strategy' sets data['reasoning']['planning_strategy'] = value.
    Returns True on success, False if the path doesn't exist.
    """
    parts = dotted_key.split(".")
    obj = data
    for part in parts[:-1]:
        if not isinstance(obj, dict) or part not in obj:
            return False
        obj = obj[part]
    if not isinstance(obj, dict) or parts[-1] not in obj:
        return False
    obj[parts[-1]] = value
    return True


class CloneManager:
    """
    Orchestrates the safe lifecycle of candidate clones.

    Usage:
        clone = CloneManager.create_candidate(agent_id, parent_genome, hypothesis)
        # clone is a CandidateClone with diff already computed and files written to disk
        CloneManager.discard_candidate(clone)   # or
        CloneManager.commit_candidate(clone)    # (used in Phase 7)
    """

    WORKSPACE_ROOT = "workspaces"

    @classmethod
    def _candidate_dir(cls, agent_id: str, candidate_id: str) -> str:
        return os.path.join(cls.WORKSPACE_ROOT, agent_id, "candidates", candidate_id)

    @classmethod
    def _parent_genome_path(cls, agent_id: str) -> str:
        return os.path.join(cls.WORKSPACE_ROOT, agent_id, "genome.json")

    @classmethod
    def _enforce_isolation(cls, path: str, agent_id: str):
        """Raise if path escapes the allowed write zone."""
        norm = os.path.normpath(path).replace("\\", "/")
        allowed_prefix = f"{cls.WORKSPACE_ROOT}/{agent_id}/candidates/"
        if not norm.startswith(allowed_prefix.replace("\\", "/")):
            raise PermissionError(
                f"[CloneManager] Access denied: path '{path}' is outside "
                f"the allowed candidate workspace for agent '{agent_id}'."
            )
        for forbidden in _FORBIDDEN_PREFIXES:
            if norm.startswith(forbidden + "/") or norm == forbidden:
                raise PermissionError(
                    f"[CloneManager] Access denied: path '{path}' touches "
                    f"the control-plane directory '{forbidden}'."
                )

    @classmethod
    def create_candidate(
        cls,
        agent_id: str,
        parent_genome: AgentGenome,
        hypothesis: dict,
    ) -> CandidateClone:
        """
        1. Freeze the parent as a JSON snapshot.
        2. Create an isolated candidate workspace.
        3. Apply the hypothesis modification to the candidate genome.
        4. Validate the candidate as a proper AgentGenome.
        5. Write both snapshots to disk.
        6. Compute and return the full CandidateClone record.
        """
        candidate_id = str(uuid.uuid4())[:8]
        parent_snapshot = parent_genome.model_dump()
        candidate_snapshot = parent_genome.model_copy(deep=True).model_dump()

        # ── Step 5: Apply the hypothesis modification ─────────────────────────
        target_component = hypothesis.get("target_component", "")
        modification_applied = False

        if target_component:
            # Determine a sensible default value for the target component
            value = _infer_modification_value(target_component, candidate_snapshot)
            if value is not None:
                modification_applied = _apply_dotted_path(
                    candidate_snapshot, target_component, value
                )

        if not modification_applied:
            # Fallback: bump temperature slightly as a guaranteed-safe change
            current_temp = candidate_snapshot.get("temperature", 0.5)
            candidate_snapshot["temperature"] = round(
                min(1.0, current_temp + 0.15), 4
            )

        # ── Step 8: Structural validation ─────────────────────────────────────
        # Re-parse through Pydantic to confirm it's still a valid AgentGenome
        try:
            AgentGenome(**candidate_snapshot)
        except Exception as e:
            raise ValueError(
                f"[CloneManager] Candidate genome failed structural validation: {e}"
            )

        # ── Compute hashes and diff ───────────────────────────────────────────
        parent_hash = _sha256(parent_snapshot)
        candidate_hash = _sha256(candidate_snapshot)
        diff = _compute_diff(parent_snapshot, candidate_snapshot)

        # ── Write to disk ─────────────────────────────────────────────────────
        candidate_dir = cls._candidate_dir(agent_id, candidate_id)
        cls._enforce_isolation(
            os.path.join(candidate_dir, "genome.json"), agent_id
        )
        os.makedirs(candidate_dir, exist_ok=True)

        # Freeze parent snapshot (written once, never overwritten)
        parent_path = cls._parent_genome_path(agent_id)
        os.makedirs(os.path.dirname(parent_path), exist_ok=True)
        if not os.path.exists(parent_path):
            with open(parent_path, "w", encoding="utf-8") as f:
                json.dump(parent_snapshot, f, indent=2)

        # Write candidate genome
        candidate_path = os.path.join(candidate_dir, "genome.json")
        with open(candidate_path, "w", encoding="utf-8") as f:
            json.dump(candidate_snapshot, f, indent=2)

        # Write metadata (hypothesis + diff + hashes)
        meta_path = os.path.join(candidate_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "candidate_id": candidate_id,
                    "agent_id": agent_id,
                    "hypothesis": hypothesis,
                    "parent_hash": parent_hash,
                    "candidate_hash": candidate_hash,
                    "diff": diff,
                },
                f,
                indent=2,
            )

        return CandidateClone(
            candidate_id=candidate_id,
            agent_id=agent_id,
            parent_genome=parent_snapshot,
            candidate_genome=candidate_snapshot,
            diff=diff,
            parent_hash=parent_hash,
            candidate_hash=candidate_hash,
            hypothesis=hypothesis,
            workspace_path=candidate_dir,
        )

    @classmethod
    def discard_candidate(cls, clone: CandidateClone):
        """Mark a candidate as discarded. Does not delete files (kept for audit trail)."""
        clone.discarded = True
        meta_path = os.path.join(clone.workspace_path, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["discarded"] = True
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

    @classmethod
    def replace_parent(cls, clone: CandidateClone):
        """
        Phase 9 Finalization: Overwrite the parent genome with the candidate genome.
        The candidate workspace is left intact for lineage tracking.
        """
        parent_path = cls._parent_genome_path(clone.agent_id)
        candidate_path = os.path.join(clone.workspace_path, "genome.json")
        
        if not os.path.exists(candidate_path):
            raise FileNotFoundError(f"[CloneManager] Missing candidate genome at {candidate_path}")
            
        import shutil
        shutil.copy2(candidate_path, parent_path)

    @classmethod
    def fork_to_new_agent(cls, clone: CandidateClone) -> str:
        """
        Phase 11: Spawns the candidate as a brand new independent agent in the population.
        """
        # 1. Determine a new sequential agent ID
        existing = [d for d in os.listdir(cls.WORKSPACE_ROOT) if d.startswith(clone.agent_id.split("_v")[0])]
        
        # Simple version bump logic
        base_name = clone.agent_id.split("_v")[0]
        max_v = 0
        for e in existing:
            if "_v" in e:
                try:
                    v = int(e.split("_v")[1])
                    max_v = max(max_v, v)
                except ValueError:
                    pass
        new_agent_id = f"{base_name}_v{max_v + 1}"
        
        # 2. Setup the new workspace
        new_workspace = os.path.join(cls.WORKSPACE_ROOT, new_agent_id)
        os.makedirs(new_workspace, exist_ok=True)
        
        # 3. Copy the candidate genome into the new workspace as its 'parent' genome
        candidate_path = os.path.join(clone.workspace_path, "genome.json")
        if not os.path.exists(candidate_path):
            raise FileNotFoundError(f"[CloneManager] Missing candidate genome at {candidate_path}")
            
        import shutil
        shutil.copy2(candidate_path, os.path.join(new_workspace, "genome.json"))
        
        return new_agent_id

    @classmethod
    def commit_candidate(cls, clone: CandidateClone, verifier=None) -> AgentGenome | None:
        """
        Guarded promotion (Phase 7).

        If a CandidateVerifier is provided, the candidate must pass all 5 stages
        before being promoted.  On failure the candidate is auto-discarded and
        None is returned.  Without a verifier the legacy unguarded path is used
        (useful in tests that only target Phase 6 clone behaviour).
        """
        if verifier is not None:
            from src.candidate_verifier import VerificationResult
            result: VerificationResult = verifier.verify(clone)
            # Persist verification result into the candidate's metadata.json
            meta_path = os.path.join(clone.workspace_path, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["verification"] = result.to_dict()
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

            if not result.passed:
                print(
                    f"  [Verifier] Candidate '{clone.candidate_id}' FAILED "
                    f"Stage {result.failed_stage}: {result.reason}"
                )
                cls.discard_candidate(clone)
                return None

        clone.committed = True
        return AgentGenome(**clone.candidate_genome)


# ── Modification Value Inference ──────────────────────────────────────────────

_PLANNING_STRATEGIES = ["direct", "chain_of_thought", "test_first", "step_by_step"]
_SYSTEM_VARIANTS = ["standard", "expert_coder", "pedantic_reviewer"]


def _infer_modification_value(target_component: str, genome_snapshot: dict) -> Any:
    """
    Given a target_component path (e.g. 'reasoning.planning_strategy'),
    return a sensible mutated value based on the current value.
    Returns None if we don't know how to handle the component.
    """
    # Read current value
    parts = target_component.split(".")
    obj = genome_snapshot
    try:
        for part in parts:
            obj = obj[part]
        current = obj
    except (KeyError, TypeError):
        return None

    # Decide a mutation based on type / known field names
    leaf = parts[-1]

    if leaf == "planning_strategy":
        others = [s for s in _PLANNING_STRATEGIES if s != current]
        return others[0] if others else current

    if leaf == "system_instruction_variant":
        others = [s for s in _SYSTEM_VARIANTS if s != current]
        return others[0] if others else current

    if leaf == "temperature" and isinstance(current, float):
        return round(min(1.0, current + 0.15), 4)

    if leaf == "reasoning_depth" and isinstance(current, int):
        return min(10, current + 1)

    if leaf == "verification_depth" and isinstance(current, int):
        return min(10, current + 2)

    if leaf == "test_generation_policy":
        options = ["none", "edge_cases_only", "comprehensive"]
        others = [s for s in options if s != current]
        return others[-1] if others else current

    if leaf == "experimentation_aggressiveness" and isinstance(current, float):
        return round(min(1.0, current + 0.1), 4)

    # Unknown field — cannot infer safely
    return None
