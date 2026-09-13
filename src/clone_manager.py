"""
src/clone_manager.py

Phase 6: Clone-Based Self-Modification.

Manages the safe creation, modification, and lifecycle of candidate genome clones.
The CloneManager enforces the access policy from the spec:
  - Candidates may only write inside workspaces/{agent_id}/candidates/
  - The parent workspace and all other agents' workspaces are read-only / untouched.
  - The src/ control plane is never touched.
"""

import json
import os
import uuid
import shutil

from src.genome import AgentGenome
from src.cloning.models import CandidateClone
from src.cloning.utils import (
    sha256,
    compute_diff,
    apply_dotted_path,
    infer_modification_value
)

# ── Control-plane directories that a candidate can never write to ────────────
_FORBIDDEN_PREFIXES = [
    "src",
    "tests",
    "data",
    "analysis",
    "Documentations",
]


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
            value = infer_modification_value(target_component, candidate_snapshot)
            if value is not None:
                modification_applied = apply_dotted_path(
                    candidate_snapshot, target_component, value
                )

        if not modification_applied:
            current_temp = candidate_snapshot.get("temperature", 0.5)
            candidate_snapshot["temperature"] = round(
                min(1.0, current_temp + 0.15), 4
            )

        # ── Step 8: Structural validation ─────────────────────────────────────
        try:
            AgentGenome(**candidate_snapshot)
        except Exception as e:
            raise ValueError(
                f"[CloneManager] Candidate genome failed structural validation: {e}"
            )

        # ── Compute hashes and diff ───────────────────────────────────────────
        parent_hash = sha256(parent_snapshot)
        candidate_hash = sha256(candidate_snapshot)
        diff = compute_diff(parent_snapshot, candidate_snapshot)

        # ── Write to disk ─────────────────────────────────────────────────────
        candidate_dir = cls._candidate_dir(agent_id, candidate_id)
        cls._enforce_isolation(
            os.path.join(candidate_dir, "genome.json"), agent_id
        )
        os.makedirs(candidate_dir, exist_ok=True)

        parent_path = cls._parent_genome_path(agent_id)
        os.makedirs(os.path.dirname(parent_path), exist_ok=True)
        if not os.path.exists(parent_path):
            with open(parent_path, "w", encoding="utf-8") as f:
                json.dump(parent_snapshot, f, indent=2)

        candidate_path = os.path.join(candidate_dir, "genome.json")
        with open(candidate_path, "w", encoding="utf-8") as f:
            json.dump(candidate_snapshot, f, indent=2)

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
            
        shutil.copy2(candidate_path, parent_path)

    @classmethod
    def fork_to_new_agent(cls, clone: CandidateClone) -> str:
        """
        Phase 11: Spawns the candidate as a brand new independent agent in the population.
        """
        existing = [d for d in os.listdir(cls.WORKSPACE_ROOT) if d.startswith(clone.agent_id.split("_v")[0])]
        
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
        
        new_workspace = os.path.join(cls.WORKSPACE_ROOT, new_agent_id)
        os.makedirs(new_workspace, exist_ok=True)
        
        candidate_path = os.path.join(clone.workspace_path, "genome.json")
        if not os.path.exists(candidate_path):
            raise FileNotFoundError(f"[CloneManager] Missing candidate genome at {candidate_path}")
            
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
