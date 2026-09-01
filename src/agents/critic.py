from src.genome import CriticGenome

# Error message substrings that indicate the LLM raised instead of returning None
_RAISE_INSTEAD_OF_NONE_PATTERNS = [
    "no two sum solution",
    "no solution found",
    "no valid solution",
    "solution not found",
    "no answer found",
    "valueerror",
]

class CriticAgent:
    """
    Rule-based Critic.
    Classifies failure type from Sandbox output + Code Validator verdict.
    No API calls.
    """
    def __init__(self):
        pass

    def critique(self, code: str, test_results: dict, validation_result: dict, genome: CriticGenome) -> dict:
        """
        Returns diagnosis with severity, recommended mutation types, and priority level.
        """
        diagnosis = {
            "failure_type": "none",
            "severity": 0.0,
            "recommended_mutations": [],
            "priority": "low",
            "code_issues": [],
        }

        total = max(test_results.get("total_tests", 1), 1)
        crash_count = len(test_results.get("crash_tests", []))
        crash_rate = crash_count / total

        # 1. Check Sandbox Failures
        if crash_count > 0:
            diagnosis["failure_type"] = "crash"
            diagnosis["severity"] = min(1.0, 0.8 * genome.strictness_threshold * 2)
            diagnosis["recommended_mutations"].append("add_error_handling")
            diagnosis["priority"] = "high"

            # Detect raise-instead-of-None pattern from error messages
            errors = [
                out.get("error", "").lower()
                for out in test_results.get("test_outputs", [])
                if out.get("status") == "crash" and out.get("error")
            ]
            if any(
                any(pat in err for pat in _RAISE_INSTEAD_OF_NONE_PATTERNS)
                for err in errors
            ):
                diagnosis["recommended_mutations"].append("return_none_on_no_solution")
                diagnosis["code_issues"].append(
                    "The function raises an exception instead of returning None when no solution exists. "
                    "Return None for unsolvable inputs."
                )

            # High crash rate (>50%): systemic issue — also force a prompt style change
            if crash_rate > 0.5:
                if "change_prompt_style" not in diagnosis["recommended_mutations"]:
                    diagnosis["recommended_mutations"].append("change_prompt_style")
                diagnosis["code_issues"].append(
                    f"High crash rate ({crash_count}/{total} tests). "
                    "The current algorithm approach is fundamentally broken for many inputs. "
                    "Try a completely different approach."
                )

        elif test_results.get("timeout_tests"):
            diagnosis["failure_type"] = "timeout"
            diagnosis["severity"] = min(1.0, 0.7 * genome.strictness_threshold * 2)
            diagnosis["recommended_mutations"].append("simplify_logic")
            diagnosis["priority"] = "high"

        elif test_results.get("failed_test_ids"):
            diagnosis["failure_type"] = "wrong_output"
            diagnosis["severity"] = min(1.0, 0.5 * genome.strictness_threshold * 2)
            diagnosis["recommended_mutations"].append("increase_reasoning_steps")
            diagnosis["recommended_mutations"].append("fix_edge_cases")
            diagnosis["priority"] = "medium"

        # 2. Check Validator Overrides
        # Only trust the validator if the sandbox crash rate is LOW (<20%).
        # At high crash rates the validator signal is unreliable (it hallucinates correctness).
        if crash_rate < 0.2 and not validation_result.get("is_correct", True):
            if diagnosis["failure_type"] == "none":
                diagnosis["failure_type"] = "algorithmic_error"
                diagnosis["severity"] = 0.9 * validation_result.get("confidence", 1.0)
                diagnosis["recommended_mutations"].append("change_prompt_style")
                diagnosis["priority"] = "high"

            if validation_result.get("issues"):
                if "fix_edge_cases" not in diagnosis["recommended_mutations"]:
                    diagnosis["recommended_mutations"].append("fix_edge_cases")

        # Fallback
        if diagnosis["failure_type"] == "none":
            diagnosis["severity"] = 0.0

        return diagnosis
