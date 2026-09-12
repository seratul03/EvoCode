"""
tests/test_phase9_selection.py

Phase 9 spec tests:
  - Better candidate replaces parent (promoted).
  - Worse candidate is destroyed.
  - Candidate with higher task-specific score but major regression is rejected.
  - Draw keeps parent.
  - Invalid fairness flag rejects candidate.
"""

import pytest
from src.arena import ArenaResult
from src.guarded_selection import GuardedSelector, SelectionDecision


class TestGuardedSelection:

    def setup_method(self):
        self.selector = GuardedSelector(regression_tolerance=0.05)
        
    def _mock_result(self, winner, margin, fairness=True, result_hash="abc", groups=None):
        return ArenaResult(
            agent_id="test",
            winner=winner,
            parent_score=0.5,
            candidate_score=0.5 + margin,
            margin=margin,
            group_scores=groups or {},
            fairness_verified=fairness,
            result_hash=result_hash
        )

    def test_better_candidate_promoted(self):
        result = self._mock_result(
            winner="candidate", 
            margin=0.05,
            groups={"known_solved": {"parent": 0.9, "candidate": 0.92}}
        )
        decision, _ = self.selector.evaluate(result)
        assert decision == SelectionDecision.PROMOTE

    def test_worse_candidate_discarded(self):
        result = self._mock_result(
            winner="parent", 
            margin=-0.05,
            groups={"known_solved": {"parent": 0.9, "candidate": 0.8}}
        )
        decision, _ = self.selector.evaluate(result)
        assert decision == SelectionDecision.DISCARD

    def test_draw_keeps_parent(self):
        result = self._mock_result(
            winner="draw", 
            margin=0.00,
            groups={"known_solved": {"parent": 0.9, "candidate": 0.9}}
        )
        decision, _ = self.selector.evaluate(result)
        assert decision == SelectionDecision.KEEP_PARENT

    def test_major_regression_blocks_promotion(self):
        # Candidate wins overall...
        result = self._mock_result(
            winner="candidate", 
            margin=0.05,
            # ...but bombs the regression set heavily (0.9 down to 0.7)
            groups={
                "triggering": {"parent": 0.1, "candidate": 0.9}, # Massive gain here
                "regression": {"parent": 0.9, "candidate": 0.7}  # But massive drop here
            }
        )
        decision, reason = self.selector.evaluate(result)
        assert decision == SelectionDecision.DISCARD
        assert "unacceptable regression" in reason

    def test_invalid_fairness_discarded(self):
        result = self._mock_result(winner="candidate", margin=0.1, fairness=False)
        decision, reason = self.selector.evaluate(result)
        assert decision == SelectionDecision.DISCARD
        assert "fairness could not be verified" in reason
        
    def test_missing_hash_discarded(self):
        result = self._mock_result(winner="candidate", margin=0.1, result_hash="")
        decision, reason = self.selector.evaluate(result)
        assert decision == SelectionDecision.DISCARD
        assert "missing security hash" in reason
