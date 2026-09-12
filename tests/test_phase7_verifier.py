"""
tests/test_phase7_verifier.py

Phase 7 spec tests:
  - Intentionally broken syntax (invalid field) must be rejected (Stage 1).
  - Unauthorized field values must be rejected (Stage 1).
  - Genome with invalid type is rejected at Stage 2.
  - Temperature regression must block promotion (Stage 3).
  - Candidate where target_component was not actually modified fails Stage 4.
  - A valid candidate clears all 5 stages and commit_candidate returns an AgentGenome.
  - Failed verification auto-discards cleanly.
"""

import shutil
import os
import pytest

from src.genome import AgentGenome
from src.clone_manager import CloneManager, CandidateClone
from src.candidate_verifier import CandidateVerifier

WORKSPACE_ROOT = "workspaces"
_VERIFIER = CandidateVerifier()


def _cleanup(*agent_ids):
    for aid in agent_ids:
        p = os.path.join(WORKSPACE_ROOT, aid)
        if os.path.exists(p):
            shutil.rmtree(p)


def _make_clone(agent_id: str, parent: AgentGenome, hypothesis: dict) -> CandidateClone:
    return CloneManager.create_candidate(agent_id, parent, hypothesis)


# ── Stage 1: Static Validation ────────────────────────────────────────────────

class TestStage1Static:

    def test_invalid_planning_strategy_rejected(self):
        agent_id = "V7_S1_BAD_STRATEGY"
        parent = AgentGenome()
        # Force a bad value directly into the candidate snapshot post-creation
        hypothesis = {"hypothesis": "test", "expected_improvement": "x", "target_component": "temperature"}
        try:
            clone = _make_clone(agent_id, parent, hypothesis)
            # Manually corrupt the candidate genome (simulating a bad mutation)
            clone.candidate_genome["reasoning"]["planning_strategy"] = "INVALID_VALUE"
            result = _VERIFIER.verify(clone)
            assert not result.passed
            assert result.failed_stage == 1
            assert "planning_strategy" in result.reason
        finally:
            _cleanup(agent_id)

    def test_temperature_below_minimum_rejected(self):
        agent_id = "V7_S1_TEMP_LOW"
        parent = AgentGenome()
        hypothesis = {"hypothesis": "test", "expected_improvement": "x", "target_component": "temperature"}
        try:
            clone = _make_clone(agent_id, parent, hypothesis)
            clone.candidate_genome["temperature"] = 0.0   # below _MIN_TEMPERATURE
            result = _VERIFIER.verify(clone)
            assert not result.passed
            assert result.failed_stage == 1
            assert "temperature" in result.reason
        finally:
            _cleanup(agent_id)

    def test_invalid_system_variant_rejected(self):
        agent_id = "V7_S1_BAD_SYS"
        parent = AgentGenome()
        hypothesis = {"hypothesis": "test", "expected_improvement": "x", "target_component": "temperature"}
        try:
            clone = _make_clone(agent_id, parent, hypothesis)
            clone.candidate_genome["system_instruction_variant"] = "hacker_mode"
            result = _VERIFIER.verify(clone)
            assert not result.passed
            assert result.failed_stage == 1
        finally:
            _cleanup(agent_id)


# ── Stage 2: Startup Validation ───────────────────────────────────────────────

class TestStage2Startup:

    def test_non_instantiable_genome_rejected(self):
        agent_id = "V7_S2_BAD_TYPE"
        parent = AgentGenome()
        hypothesis = {"hypothesis": "test", "expected_improvement": "x", "target_component": "temperature"}
        try:
            clone = _make_clone(agent_id, parent, hypothesis)
            # Corrupt to a type that will pass Stage 1 range checks but fail Pydantic instantiation
            clone.candidate_genome["reasoning"] = "not_a_dict_at_all"
            result = _VERIFIER.verify(clone)
            # Stage 1 may or may not catch this depending on dict traversal;
            # Stage 2 definitely will — check it fails at stage <= 2
            assert not result.passed
            assert result.failed_stage <= 2
        finally:
            _cleanup(agent_id)


# ── Stage 3: Regression Check ─────────────────────────────────────────────────

class TestStage3Regression:

    def test_temperature_regression_blocks_promotion(self):
        agent_id = "V7_S3_TEMP_REGRESS"
        parent = AgentGenome(temperature=0.6)
        hypothesis = {"hypothesis": "test", "expected_improvement": "x", "target_component": "temperature"}
        try:
            clone = _make_clone(agent_id, parent, hypothesis)
            # Simulate regression: parent was 0.6 but candidate drops below min
            clone.parent_genome["temperature"] = 0.6
            clone.candidate_genome["temperature"] = 0.06   # passes Stage 1 (>= 0.05) but regresses from parent 0.6
            result = _VERIFIER.verify(clone)
            assert not result.passed
            assert result.failed_stage == 3
            assert "temperature" in result.reason
        finally:
            _cleanup(agent_id)


# ── Stage 4: Trigger-Specific ────────────────────────────────────────────────

class TestStage4TriggerSpecific:

    def test_unmodified_target_component_rejected(self):
        agent_id = "V7_S4_NO_DIFF"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "test",
            "expected_improvement": "x",
            "target_component": "reasoning.planning_strategy"
        }
        try:
            clone = _make_clone(agent_id, parent, hypothesis)
            # Wipe the diff to simulate no change being applied
            clone.diff = {}
            result = _VERIFIER.verify(clone)
            assert not result.passed
            assert result.failed_stage == 4
            assert "No diff" in result.reason
        finally:
            _cleanup(agent_id)


# ── Full Pass ─────────────────────────────────────────────────────────────────

class TestFullVerification:

    def test_valid_candidate_passes_all_stages(self):
        agent_id = "V7_FULL_PASS"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "Switch planning_strategy to step_by_step for better recursion.",
            "expected_improvement": "Higher pass rate on recursive tasks.",
            "target_component": "reasoning.planning_strategy"
        }
        try:
            clone = _make_clone(agent_id, parent, hypothesis)
            result = _VERIFIER.verify(clone)
            assert result.passed, f"Failed at stage {result.failed_stage}: {result.reason}"
            assert result.stage_reached == 5
            assert result.failed_stage is None
            assert len(result.stage_reports) == 5
        finally:
            _cleanup(agent_id)

    def test_commit_with_verifier_returns_agentgenome(self):
        agent_id = "V7_COMMIT_PASS"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "Raise temperature.",
            "expected_improvement": "More diverse solutions.",
            "target_component": "temperature"
        }
        try:
            clone = _make_clone(agent_id, parent, hypothesis)
            promoted = CloneManager.commit_candidate(clone, verifier=_VERIFIER)
            assert isinstance(promoted, AgentGenome)
            assert clone.committed is True
        finally:
            _cleanup(agent_id)

    def test_failed_verification_auto_discards_candidate(self):
        agent_id = "V7_AUTO_DISCARD"
        parent = AgentGenome()
        hypothesis = {
            "hypothesis": "test",
            "expected_improvement": "x",
            "target_component": "temperature"
        }
        try:
            clone = _make_clone(agent_id, parent, hypothesis)
            # Inject a failure: wipe diff so Stage 4 fails
            clone.diff = {}
            promoted = CloneManager.commit_candidate(clone, verifier=_VERIFIER)
            assert promoted is None
            assert clone.discarded is True
        finally:
            _cleanup(agent_id)
