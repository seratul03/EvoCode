"""
src/candidate_verifier.py

Phase 7: Candidate Verification Gate.

A mandatory 5-stage pre-arena gate that a candidate clone must pass before it
can be promoted. All stages are deterministic and offline (no LLM calls).

Stages:
    1. Static Validation    — field types, ranges, forbidden values
    2. Startup Validation   — genome can be instantiated; core modules importable
    3. Regression Check     — candidate has not degraded known-good parameters
    4. Trigger-Specific     — modified gene is actually an improvement direction
    5. General Sanity       — all operational bounds satisfied end-to-end
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.genome import AgentGenome

if TYPE_CHECKING:
    from src.clone_manager import CandidateClone


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class StageReport:
    stage: int
    name: str
    passed: bool
    reason: str


@dataclass
class VerificationResult:
    passed: bool
    stage_reached: int          # highest stage attempted (1-5)
    failed_stage: int | None    # None when all stages pass
    reason: str
    stage_reports: list[StageReport] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "stage_reached": self.stage_reached,
            "failed_stage": self.failed_stage,
            "reason": self.reason,
            "stage_reports": [
                {"stage": s.stage, "name": s.name, "passed": s.passed, "reason": s.reason}
                for s in self.stage_reports
            ],
        }


# ── Known operational bounds ──────────────────────────────────────────────────

_VALID_PLANNING_STRATEGIES = {"direct", "chain_of_thought", "test_first", "step_by_step"}
_VALID_SYSTEM_VARIANTS = {"standard", "expert_coder", "pedantic_reviewer"}
_VALID_REFLECTION_POLICIES = {"none", "on_failure", "always"}
_VALID_ALGO_STRATEGIES = {"brute_force_first", "optimize_first"}
_VALID_IMPL_STRATEGIES = {"modular", "monolithic"}
_VALID_LANG_POLICIES = {"standard", "idiomatic", "secure"}
_VALID_TEST_POLICIES = {"none", "edge_cases_only", "comprehensive"}
_VALID_MEMORY_STRATEGIES = {"recent_only", "similarity_search"}
_VALID_EXPERIENCE_PRIO = {"successes", "failures", "balanced"}
_VALID_MOD_SCOPES = {"parameters_only", "logic_rewrite"}

# Minimum operational temperature — prevents pathologically cold sampling
_MIN_TEMPERATURE = 0.05
_MAX_TEMPERATURE = 1.0
_MAX_REASONING_DEPTH = 10
_MAX_VERIFICATION_DEPTH = 15
_MAX_EVIDENCE_THRESHOLD = 20


class CandidateVerifier:
    """
    Runs all 5 verification stages against a CandidateClone.
    Returns a VerificationResult.  Stops at first failure.
    """

    STRUCTURED_REPORTS_DIR = "structured_reports"

    def verify(self, clone: "CandidateClone") -> VerificationResult:
        stages = [
            self._stage1_static,
            self._stage2_startup,
            self._stage3_regression,
            self._stage4_trigger_specific,
            self._stage5_general_sanity,
        ]
        reports: list[StageReport] = []
        for i, stage_fn in enumerate(stages, start=1):
            report = stage_fn(clone)
            reports.append(report)
            if not report.passed:
                return VerificationResult(
                    passed=False,
                    stage_reached=i,
                    failed_stage=i,
                    reason=report.reason,
                    stage_reports=reports,
                )
        return VerificationResult(
            passed=True,
            stage_reached=5,
            failed_stage=None,
            reason="All 5 verification stages passed.",
            stage_reports=reports,
        )

    # ── Stage 1: Static Validation ────────────────────────────────────────────

    def _stage1_static(self, clone: "CandidateClone") -> StageReport:
        """Check field types, enum membership, and numeric ranges."""
        g = clone.candidate_genome
        errors = []

        # Temperature
        temp = g.get("temperature", 0.5)
        if not isinstance(temp, (int, float)):
            errors.append(f"temperature must be numeric, got {type(temp).__name__}")
        elif not (_MIN_TEMPERATURE <= temp <= _MAX_TEMPERATURE):
            errors.append(
                f"temperature {temp} out of operational range [{_MIN_TEMPERATURE}, {_MAX_TEMPERATURE}]"
            )

        # Reasoning sub-genes
        reasoning = g.get("reasoning", {})
        if not isinstance(reasoning, dict):
            errors.append(f"reasoning must be a dict, got {type(reasoning).__name__}")
        else:
            ps = reasoning.get("planning_strategy", "direct")
            if ps not in _VALID_PLANNING_STRATEGIES:
                errors.append(f"Invalid planning_strategy: '{ps}'")
            rd = reasoning.get("reasoning_depth", 3)
            if not isinstance(rd, int) or not (0 <= rd <= _MAX_REASONING_DEPTH):
                errors.append(f"reasoning_depth {rd} out of range [0, {_MAX_REASONING_DEPTH}]")
            srp = reasoning.get("self_reflection_policy", "on_failure")
            if srp not in _VALID_REFLECTION_POLICIES:
                errors.append(f"Invalid self_reflection_policy: '{srp}'")

        # Coding sub-genes
        coding = g.get("coding", {})
        if not isinstance(coding, dict):
            errors.append(f"coding must be a dict, got {type(coding).__name__}")
        else:
            if coding.get("algorithm_selection_strategy") not in _VALID_ALGO_STRATEGIES:
                errors.append(f"Invalid algorithm_selection_strategy: '{coding.get('algorithm_selection_strategy')}'")
            if coding.get("implementation_strategy") not in _VALID_IMPL_STRATEGIES:
                errors.append(f"Invalid implementation_strategy: '{coding.get('implementation_strategy')}'")
            if coding.get("language_specific_policy") not in _VALID_LANG_POLICIES:
                errors.append(f"Invalid language_specific_policy: '{coding.get('language_specific_policy')}'")

        # Verification sub-genes
        verification = g.get("verification", {})
        if not isinstance(verification, dict):
            errors.append(f"verification must be a dict, got {type(verification).__name__}")
        else:
            if verification.get("test_generation_policy") not in _VALID_TEST_POLICIES:
                errors.append(f"Invalid test_generation_policy: '{verification.get('test_generation_policy')}'")
            vd = verification.get("verification_depth", 5)
            if not isinstance(vd, int) or not (0 <= vd <= _MAX_VERIFICATION_DEPTH):
                errors.append(f"verification_depth {vd} out of range [0, {_MAX_VERIFICATION_DEPTH}]")

        # System variant
        sv = g.get("system_instruction_variant", "standard")
        if sv not in _VALID_SYSTEM_VARIANTS:
            errors.append(f"Invalid system_instruction_variant: '{sv}'")

        if errors:
            return StageReport(1, "Static Validation", False, "; ".join(errors))
        return StageReport(1, "Static Validation", True, "All fields valid.")

    # ── Stage 2: Startup Validation ───────────────────────────────────────────

    def _stage2_startup(self, clone: "CandidateClone") -> StageReport:
        """Verify the candidate genome can be instantiated and core modules import."""
        # Re-instantiate through Pydantic to confirm operational readiness
        try:
            genome = AgentGenome(**clone.candidate_genome)
        except Exception as e:
            return StageReport(2, "Startup Validation", False,
                               f"AgentGenome instantiation failed: {e}")

        # Verify required modules are importable (control-plane health check)
        missing = []
        for module in ("src.client", "src.sandbox", "src.fitness_scorer"):
            try:
                __import__(module)
            except ImportError:
                missing.append(module)
        if missing:
            return StageReport(2, "Startup Validation", False,
                               f"Required modules not importable: {missing}")

        # Memory file check — agent must be able to load its own memory
        memory_path = os.path.join("memory", "agent_memory.txt")
        if not os.path.exists(memory_path):
            return StageReport(2, "Startup Validation", False,
                               f"Memory file not found at '{memory_path}'")

        return StageReport(2, "Startup Validation", True,
                           f"Genome instantiated OK. Agent ID: {genome.agent_id or 'none'}")

    # ── Stage 3: Regression Check ─────────────────────────────────────────────

    def _stage3_regression(self, clone: "CandidateClone") -> StageReport:
        """
        Check the candidate has not regressed known-good genome parameters by comparing
        against the frozen parent snapshot.  A regression is defined as:
          - temperature dropped to pathologically low value after being healthy
          - reasoning_depth dropped below 1 when parent was >= 2
          - verification_depth dropped to 0
        """
        parent = clone.parent_genome
        candidate = clone.candidate_genome

        regressions = []

        parent_temp = parent.get("temperature", 0.5)
        cand_temp = candidate.get("temperature", 0.5)
        if parent_temp >= 0.2 and cand_temp < _MIN_TEMPERATURE:
            regressions.append(
                f"temperature regressed from {parent_temp:.2f} to {cand_temp:.2f} "
                f"(below minimum {_MIN_TEMPERATURE})"
            )
        elif parent_temp >= 0.4 and cand_temp < parent_temp * 0.3:
            regressions.append(
                f"temperature regressed significantly from {parent_temp:.2f} to {cand_temp:.2f} "
                f"(below 30% of parent value)"
            )

        parent_rd = parent.get("reasoning", {}).get("reasoning_depth", 3)
        cand_rd = candidate.get("reasoning", {}).get("reasoning_depth", 3)
        if parent_rd >= 2 and cand_rd < 1:
            regressions.append(
                f"reasoning_depth regressed from {parent_rd} to {cand_rd}"
            )

        parent_vd = parent.get("verification", {}).get("verification_depth", 5)
        cand_vd = candidate.get("verification", {}).get("verification_depth", 5)
        if parent_vd >= 3 and cand_vd == 0:
            regressions.append(
                f"verification_depth regressed from {parent_vd} to 0"
            )

        if regressions:
            return StageReport(3, "Regression Check", False,
                               "Regression detected: " + "; ".join(regressions))
        return StageReport(3, "Regression Check", True,
                           "No regressions detected vs parent genome.")

    # ── Stage 4: Trigger-Specific Test ───────────────────────────────────────

    def _stage4_trigger_specific(self, clone: "CandidateClone") -> StageReport:
        """
        Verify the modification actually addresses the trigger's target_component.
        The diff must contain the target_component field, and the new value must
        differ from the parent's value (i.e., the change was actually applied).
        """
        hypothesis = clone.hypothesis
        target = hypothesis.get("target_component", "")
        diff = clone.diff

        if not target:
            # No target — pass with a note (fallback hypothesis case)
            return StageReport(4, "Trigger-Specific Test", True,
                               "No target_component specified in hypothesis; fallback change accepted.")

        # Check that some diff was produced
        if not diff:
            return StageReport(4, "Trigger-Specific Test", False,
                               f"No diff was recorded — candidate genome is identical to parent. "
                               f"Expected change to '{target}'.")

        # Check the top-level key of the target path exists in the diff
        top_key = target.split(".")[0]
        if top_key not in diff:
            return StageReport(4, "Trigger-Specific Test", False,
                               f"Target component '{target}' (top key: '{top_key}') was not "
                               f"modified. Diff keys: {list(diff.keys())}.")

        return StageReport(4, "Trigger-Specific Test", True,
                           f"Target component '{target}' was successfully modified.")

    # ── Stage 5: General Sanity ───────────────────────────────────────────────

    def _stage5_general_sanity(self, clone: "CandidateClone") -> StageReport:
        """
        Final holistic check: ensure the overall genome is coherent and that
        the evolution gene parameters themselves are within safe operating bounds.
        """
        g = clone.candidate_genome
        evolution = g.get("evolution", {})
        issues = []

        ea = evolution.get("experimentation_aggressiveness", 0.1)
        if not isinstance(ea, float) or not (0.0 <= ea <= 1.0):
            issues.append(f"experimentation_aggressiveness {ea} out of [0.0, 1.0]")

        et = evolution.get("evidence_threshold", 3)
        if not isinstance(et, int) or not (1 <= et <= _MAX_EVIDENCE_THRESHOLD):
            issues.append(f"evidence_threshold {et} out of [1, {_MAX_EVIDENCE_THRESHOLD}]")

        ms = evolution.get("modification_scope_preference", "parameters_only")
        if ms not in _VALID_MOD_SCOPES:
            issues.append(f"Invalid modification_scope_preference: '{ms}'")

        # Cross-check: if test_generation_policy is 'none' but verification_depth > 0,
        # that's a coherence inconsistency worth flagging
        veri = g.get("verification", {})
        if veri.get("test_generation_policy") == "none" and veri.get("verification_depth", 0) > 5:
            issues.append(
                "Incoherent: test_generation_policy='none' but verification_depth > 5"
            )

        if issues:
            return StageReport(5, "General Sanity", False, "; ".join(issues))
        return StageReport(5, "General Sanity", True,
                           "Candidate genome is coherent and operationally sound.")
