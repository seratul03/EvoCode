"""
src/guarded_selection.py

Phase 9: Guarded Selection.

Evaluates an ArenaResult and makes the authoritative decision on whether
to promote the candidate (replace the parent) or discard it.
"""

from enum import Enum
from src.arena import ArenaResult


class SelectionDecision(Enum):
    PROMOTE = "promote"
    DISCARD = "discard"
    KEEP_PARENT = "keep_parent"


class GuardedSelector:
    """
    Evaluates arena results to protect agent capability and prevent regression.
    """

    def __init__(self, regression_tolerance: float = 0.05):
        # How much regression is acceptable on a specific group before rejecting?
        self.regression_tolerance = regression_tolerance

    def evaluate(self, result: ArenaResult) -> tuple[SelectionDecision, str]:
        """
        Evaluate the ArenaResult and return a decision and a reason.
        """
        if not result.fairness_verified:
            return SelectionDecision.DISCARD, "Candidate discarded: arena fairness could not be verified."
            
        if not result.result_hash:
            return SelectionDecision.DISCARD, "Candidate discarded: arena result is missing security hash."

        # Check for major regressions on core test groups
        # If candidate wins overall but bombs known_solved or unrelated tasks, it's a regression.
        regressions = []
        for group in ["known_solved", "unrelated", "regression"]:
            if group in result.group_scores:
                scores = result.group_scores[group]
                parent_score = scores.get("parent", 0.0)
                cand_score = scores.get("candidate", 0.0)
                if parent_score - cand_score > self.regression_tolerance:
                    regressions.append(
                        f"{group} (parent: {parent_score:.4f}, cand: {cand_score:.4f})"
                    )

        if regressions:
            reason = "Candidate discarded: unacceptable regression on core tasks -> " + "; ".join(regressions)
            return SelectionDecision.DISCARD, reason

        if result.winner == "candidate":
            return SelectionDecision.PROMOTE, f"Candidate promoted: clearly better (margin +{result.margin:.4f})."
            
        if result.winner == "parent":
            return SelectionDecision.DISCARD, f"Candidate discarded: parent clearly better (margin {result.margin:.4f})."
            
        return SelectionDecision.KEEP_PARENT, "Parent kept: results were equivalent (draw)."
