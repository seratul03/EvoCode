from src.genome import CriticGenome

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
            "priority": "low"
        }

        # 1. Check Sandbox Failures
        if test_results["crash_tests"]:
            diagnosis["failure_type"] = "crash"
            diagnosis["severity"] = min(1.0, 0.8 * genome.strictness_threshold * 2)
            diagnosis["recommended_mutations"].append("add_error_handling")
            diagnosis["priority"] = "high"
        
        elif test_results["timeout_tests"]:
            diagnosis["failure_type"] = "timeout"
            diagnosis["severity"] = min(1.0, 0.7 * genome.strictness_threshold * 2)
            diagnosis["recommended_mutations"].append("simplify_logic")
            diagnosis["priority"] = "high"
            
        elif test_results["failed_test_ids"]:
            diagnosis["failure_type"] = "wrong_output"
            diagnosis["severity"] = min(1.0, 0.5 * genome.strictness_threshold * 2)
            diagnosis["recommended_mutations"].append("increase_reasoning_steps")
            diagnosis["priority"] = "medium"

        # 2. Check Validator Overrides
        if not validation_result.get("is_correct", True):
            # Sandbox might have passed, but validator found issues (e.g. infinite loop risk)
            if diagnosis["failure_type"] == "none":
                diagnosis["failure_type"] = "algorithmic_error"
                diagnosis["severity"] = 0.9 * validation_result.get("confidence", 1.0)
                diagnosis["recommended_mutations"].append("change_prompt_style")
                diagnosis["priority"] = "high"
            
            # Combine issues
            if validation_result.get("issues"):
                diagnosis["recommended_mutations"].append("fix_edge_cases")

        # Fallback to none if perfectly clean
        if diagnosis["failure_type"] == "none":
            diagnosis["severity"] = 0.0
            
        return diagnosis
