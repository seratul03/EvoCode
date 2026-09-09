import pytest
import json
import os
import shutil
from src.clone_manager import CloneManager, CandidateClone
from src.genome import AgentGenome

# ── Helpers ───────────────────────────────────────────────────────────────────

WORKSPACE_ROOT = "workspaces"

def _cleanup(*agent_ids):
    """Remove test workspace directories after each test."""
    for agent_id in agent_ids:
        path = os.path.join(WORKSPACE_ROOT, agent_id)
        if os.path.exists(path):
            shutil.rmtree(path)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCloneCreation:

    def test_candidate_is_created_and_differs_from_parent(self):
        agent_id = "TEST_PY_CLONE_CREATE"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "Switch to step_by_step to handle recursion better.",
            "expected_improvement": "Better recursion pass rate.",
            "target_component": "reasoning.planning_strategy"
        }
        try:
            clone = CloneManager.create_candidate(agent_id, parent, hypothesis)
            # Candidate must be a valid dataclass
            assert isinstance(clone, CandidateClone)
            assert clone.agent_id == agent_id
            # The modification must be reflected
            assert clone.candidate_genome["reasoning"]["planning_strategy"] != clone.parent_genome["reasoning"]["planning_strategy"]
            # Diff must capture the change
            assert "reasoning" in clone.diff or "planning_strategy" in str(clone.diff)
        finally:
            _cleanup(agent_id)

    def test_parent_genome_is_byte_for_byte_unchanged(self):
        agent_id = "TEST_PY_CLONE_UNCHANGED"
        parent = AgentGenome(temperature=0.5)
        hypothesis = {
            "hypothesis": "Raise temperature.",
            "expected_improvement": "More diverse solutions.",
            "target_component": "temperature"
        }
        parent_snapshot_before = parent.model_dump()
        try:
            clone = CloneManager.create_candidate(agent_id, parent, hypothesis)
            # The parent Python object must be unchanged
            assert parent.model_dump() == parent_snapshot_before
            # The parent snapshot stored in the clone must equal the pre-mutation snapshot
            assert clone.parent_genome == parent_snapshot_before
        finally:
            _cleanup(agent_id)

    def test_candidate_hashes_differ_from_parent(self):
        agent_id = "TEST_PY_CLONE_HASH"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "Test hash divergence.",
            "expected_improvement": "n/a",
            "target_component": "reasoning.planning_strategy"
        }
        try:
            clone = CloneManager.create_candidate(agent_id, parent, hypothesis)
            assert clone.parent_hash != clone.candidate_hash
            assert len(clone.parent_hash) == 64   # sha256 hex
        finally:
            _cleanup(agent_id)

    def test_candidate_genome_is_structurally_valid_agentgenome(self):
        agent_id = "TEST_PY_CLONE_VALID"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "Increase verification depth.",
            "expected_improvement": "Fewer missed edge cases.",
            "target_component": "verification.verification_depth"
        }
        try:
            clone = CloneManager.create_candidate(agent_id, parent, hypothesis)
            # Must be re-parseable as an AgentGenome without error
            reconstructed = AgentGenome(**clone.candidate_genome)
            assert reconstructed is not None
        finally:
            _cleanup(agent_id)


class TestAccessPolicy:

    def test_cross_agent_isolation(self):
        """CloneManager must not write into another agent's workspace."""
        my_agent = "TEST_PY_ISOLATION_A"
        other_agent = "TEST_PY_ISOLATION_B"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "test",
            "expected_improvement": "test",
            "target_component": "temperature"
        }
        try:
            clone = CloneManager.create_candidate(my_agent, parent, hypothesis)
            # The candidate workspace must be inside my_agent's folder, not other_agent's
            assert my_agent in clone.workspace_path
            assert other_agent not in clone.workspace_path
        finally:
            _cleanup(my_agent, other_agent)

    def test_candidate_files_written_inside_agent_workspace(self):
        """Candidate genome.json and metadata.json must live under workspaces/{agent_id}/candidates/"""
        agent_id = "TEST_PY_CLONE_FILES"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "test",
            "expected_improvement": "test",
            "target_component": "temperature"
        }
        try:
            clone = CloneManager.create_candidate(agent_id, parent, hypothesis)
            genome_path = os.path.join(clone.workspace_path, "genome.json")
            meta_path = os.path.join(clone.workspace_path, "metadata.json")
            assert os.path.exists(genome_path)
            assert os.path.exists(meta_path)
            # Verify the genome.json contains valid JSON matching the candidate
            with open(genome_path) as f:
                on_disk = json.load(f)
            assert on_disk == clone.candidate_genome
        finally:
            _cleanup(agent_id)


class TestCandidateLifecycle:

    def test_discard_marks_metadata(self):
        agent_id = "TEST_PY_CLONE_DISCARD"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "test",
            "expected_improvement": "test",
            "target_component": "temperature"
        }
        try:
            clone = CloneManager.create_candidate(agent_id, parent, hypothesis)
            CloneManager.discard_candidate(clone)
            assert clone.discarded is True
            meta_path = os.path.join(clone.workspace_path, "metadata.json")
            with open(meta_path) as f:
                meta = json.load(f)
            assert meta.get("discarded") is True
        finally:
            _cleanup(agent_id)

    def test_commit_returns_valid_agentgenome(self):
        agent_id = "TEST_PY_CLONE_COMMIT"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "test",
            "expected_improvement": "test",
            "target_component": "temperature"
        }
        try:
            clone = CloneManager.create_candidate(agent_id, parent, hypothesis)
            promoted = CloneManager.commit_candidate(clone)
            assert isinstance(promoted, AgentGenome)
            assert clone.committed is True
        finally:
            _cleanup(agent_id)

    def test_parent_workspace_genome_is_never_overwritten(self):
        """If the parent genome.json already exists, it must not be overwritten."""
        agent_id = "TEST_PY_CLONE_PERSIST"
        parent = AgentGenome(temperature=0.3)
        hypothesis = {
            "hypothesis": "test",
            "expected_improvement": "test",
            "target_component": "temperature"
        }
        try:
            # First call — writes parent genome.json
            clone1 = CloneManager.create_candidate(agent_id, parent, hypothesis)
            parent_path = CloneManager._parent_genome_path(agent_id)
            with open(parent_path) as f:
                first_write = json.load(f)

            # Second call — parent genome.json must remain unchanged
            parent2 = AgentGenome(temperature=0.9)   # different object
            clone2 = CloneManager.create_candidate(agent_id, parent2, hypothesis)
            with open(parent_path) as f:
                second_write = json.load(f)

            assert first_write == second_write, "Parent genome.json was overwritten!"
        finally:
            _cleanup(agent_id)
