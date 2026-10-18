"""
tests/test_phase19_agency_layer.py

Unit and integration tests for Phase Step 2: Agency Layer Components:
  - ArchitectAgent (src/agents/architect.py)
  - ReviewerAgent (src/agents/reviewer.py)
  - OptimizerAgent (src/agents/optimizer.py)
  - GeneratorAgent plan injection (src/agents/generator.py)
  - EvoEvaluator agency layer pipeline hookup (src/orchestration/evaluator.py)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.architect import ArchitectAgent
from src.agents.reviewer import ReviewerAgent
from src.agents.optimizer import OptimizerAgent
from src.agents.generator import GeneratorAgent
from src.genome import AgentGenome, ReasoningGenes, CodingGenes, VerificationGenes
from src.orchestration.evaluator import EvoEvaluator


# ======================================================================
# ArchitectAgent Tests
# ======================================================================

class TestArchitectAgent:
    @pytest.mark.asyncio
    async def test_plan_success(self):
        client = MagicMock()
        client.create_completion = AsyncMock(return_value={
            "content": "Algorithm: Two Pointers\n1. Sort array\n2. Use left/right pointers"
        })
        architect = ArchitectAgent(client)
        genome = AgentGenome()
        problem = {
            "title": "Two Sum",
            "description": "Find two numbers summing to target",
            "tests": [{"input": "[2, 7, 11, 15], 9", "expected": "[0, 1]"}]
        }

        plan = await architect.plan(problem, genome)
        assert "Two Pointers" in plan
        assert "Sort array" in plan
        client.create_completion.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_plan_graceful_degradation_on_exception(self):
        client = MagicMock()
        client.create_completion = AsyncMock(side_effect=RuntimeError("LLM offline"))
        architect = ArchitectAgent(client)
        genome = AgentGenome()
        problem = {"title": "Problem", "description": "Desc"}

        plan = await architect.plan(problem, genome)
        assert plan == ""  # Never crashes caller

    def test_strategy_hints(self):
        client = MagicMock()
        architect = ArchitectAgent(client)

        g1 = AgentGenome(
            coding=CodingGenes(algorithm_selection_strategy="brute_force_first"),
            reasoning=ReasoningGenes(planning_strategy="step_by_step", reasoning_depth=5)
        )
        hint1 = architect._strategy_hint(g1)
        assert "brute-force" in hint1
        assert "fine-grained numbered steps" in hint1
        assert "detailed complexity analysis" in hint1

        g2 = AgentGenome(
            coding=CodingGenes(algorithm_selection_strategy="optimize_first"),
            reasoning=ReasoningGenes(planning_strategy="tree_of_thought", reasoning_depth=1)
        )
        hint2 = architect._strategy_hint(g2)
        assert "time-efficient" in hint2
        assert "two alternative algorithmic approaches" in hint2
        assert "keep the plan very brief" in hint2


# ======================================================================
# ReviewerAgent Tests
# ======================================================================

class TestReviewerAgent:
    @pytest.mark.asyncio
    async def test_review_no_issues(self):
        client = MagicMock()
        client.create_completion = AsyncMock(return_value={"content": "NO_ISSUES"})
        reviewer = ReviewerAgent(client)
        genome = AgentGenome()
        problem = {"title": "Two Sum", "description": "Find indices"}
        code = "def two_sum(nums, target):\n    return [0, 1]"

        res = await reviewer.review(code, problem, "Python", genome)
        assert res["revised_code"] is None
        assert res["issues"] == []

    @pytest.mark.asyncio
    async def test_review_with_revision(self):
        client = MagicMock()
        client.create_completion = AsyncMock(return_value={
            "content": "```python\ndef two_sum(nums, target):\n    if not nums: return []\n    return [0, 1]\n```"
        })
        reviewer = ReviewerAgent(client)
        genome = AgentGenome()
        problem = {"title": "Two Sum", "description": "Find indices"}
        code = "def two_sum(nums, target):\n    return [0, 1]"

        res = await reviewer.review(code, problem, "Python", genome)
        assert res["revised_code"] is not None
        assert "if not nums: return []" in res["revised_code"]
        assert len(res["issues"]) > 0

    @pytest.mark.asyncio
    async def test_review_skips_unparseable_python_syntax(self):
        client = MagicMock()
        client.create_completion = AsyncMock()
        reviewer = ReviewerAgent(client)
        genome = AgentGenome()
        broken_syntax_code = "def two_sum(: invalid syntax"

        res = await reviewer.review(broken_syntax_code, {}, "Python", genome)
        assert res["revised_code"] is None
        assert "Syntax error" in res["issues"][0]
        client.create_completion.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_review_graceful_degradation_on_exception(self):
        client = MagicMock()
        client.create_completion = AsyncMock(side_effect=RuntimeError("API failure"))
        reviewer = ReviewerAgent(client)
        genome = AgentGenome()
        code = "def solve(): return 42"

        res = await reviewer.review(code, {}, "Python", genome)
        assert res["revised_code"] is None
        assert res["issues"] == []


# ======================================================================
# OptimizerAgent Tests
# ======================================================================

class TestOptimizerAgent:
    @pytest.mark.asyncio
    async def test_optimize_already_optimal(self):
        client = MagicMock()
        client.create_completion = AsyncMock(return_value={"content": "ALREADY_OPTIMAL"})
        optimizer = OptimizerAgent(client)
        genome = AgentGenome()
        code = "def solve(n): return n * 2"

        res = await optimizer.optimize(code, {}, "Python", genome)
        assert res == code

    @pytest.mark.asyncio
    async def test_optimize_returns_improved_code(self):
        client = MagicMock()
        client.create_completion = AsyncMock(return_value={
            "content": "```python\ndef solve(n):\n    return [i * 2 for i in range(n)]\n```"
        })
        optimizer = OptimizerAgent(client)
        genome = AgentGenome()
        original_code = "def solve(n):\n    res = []\n    for i in range(n):\n        res.append(i * 2)\n    return res"

        res = await optimizer.optimize(original_code, {}, "Python", genome)
        assert "return [i * 2 for i in range(n)]" in res

    @pytest.mark.asyncio
    async def test_optimize_graceful_degradation_on_exception(self):
        client = MagicMock()
        client.create_completion = AsyncMock(side_effect=RuntimeError("Provider timeout"))
        optimizer = OptimizerAgent(client)
        genome = AgentGenome()
        code = "def solve(): return 1"

        res = await optimizer.optimize(code, {}, "Python", genome)
        assert res == code


# ======================================================================
# GeneratorAgent Plan Injection Tests
# ======================================================================

class TestGeneratorPlanInjection:
    def test_generator_prompt_includes_architect_plan(self):
        client = MagicMock()
        generator = GeneratorAgent(client, language="Python", enable_memory=False)
        genome = AgentGenome()
        problem = {
            "title": "Search Matrix",
            "description": "Search in 2D sorted matrix",
            "architect_plan": "Use binary search treating 2D as 1D array"
        }

        prompt = generator._build_user_prompt(problem, genome, template=None)
        assert "--- ARCHITECTURAL PLAN ---" in prompt
        assert "Use binary search treating 2D as 1D array" in prompt

    def test_generator_prompt_without_architect_plan(self):
        client = MagicMock()
        generator = GeneratorAgent(client, language="Python", enable_memory=False)
        genome = AgentGenome()
        problem = {
            "title": "Search Matrix",
            "description": "Search in 2D sorted matrix"
        }

        prompt = generator._build_user_prompt(problem, genome, template=None)
        assert "--- ARCHITECTURAL PLAN ---" not in prompt


# ======================================================================
# EvoEvaluator Integration Tests
# ======================================================================

class TestEvoEvaluatorAgencyIntegration:
    @pytest.mark.asyncio
    async def test_architect_plan_cached_on_problem(self):
        mock_orch = MagicMock()
        mock_orch.enable_architect = True
        mock_orch.architect = MagicMock()
        mock_orch.architect.plan = AsyncMock(return_value="Binary Search Strategy")
        mock_orch.template_agent = MagicMock()
        mock_orch.template_agent.generate = AsyncMock(return_value={})
        mock_orch.pop_generator = [AgentGenome()]
        mock_orch.pop_size = 1

        evaluator = EvoEvaluator(mock_orch)
        problem = {"id": 1, "title": "Test Problem", "description": "..."}
        problem_report = {"generations": []}

        with patch.object(evaluator, "_generate_and_test", AsyncMock(return_value=("code", {}, {}, 1, False, None))), \
             patch.object(evaluator, "_score_and_critique", MagicMock(return_value=({}, {}))):
            await evaluator.evaluate_population(0, problem, problem_report)

        assert problem.get("architect_plan") == "Binary Search Strategy"
        mock_orch.architect.plan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reviewer_revises_code_before_sandbox(self):
        mock_orch = MagicMock()
        mock_orch.enable_reviewer = True
        mock_orch.reviewer = MagicMock()
        mock_orch.reviewer.review = AsyncMock(return_value={
            "revised_code": "def solve(): return 'reviewed'",
            "issues": ["Fixed missing base case"]
        })
        mock_orch.enable_optimizer = False
        mock_orch.disable_property_testing = True
        mock_orch.use_validator = False

        generator = MagicMock()
        generator.language = "Python"
        generator.solve = AsyncMock(return_value="def solve(): return 'raw'")
        mock_orch.generators = [generator]
        mock_orch.pop_generator = [AgentGenome()]
        mock_orch.pop_size = 1

        mock_orch.tester = MagicMock()
        mock_orch.tester.evaluate = AsyncMock(return_value=True)

        mock_orch.sandbox = MagicMock()
        mock_orch.sandbox.run = MagicMock(return_value={
            "passed_tests": 1, "total_tests": 1,
            "failed_test_ids": [], "timeout_tests": [], "crash_tests": [],
            "execution_time_ms": 1.0, "peak_memory_kb": 100.0,
            "test_outputs": [{"status": "pass"}]
        })
        mock_orch.logger = MagicMock()

        evaluator = EvoEvaluator(mock_orch)
        problem = {"id": 1, "tests": [{"input": "()", "expected": "'reviewed'"}]}

        code, test_res, val, chash, _, _ = await evaluator._generate_and_test(0, 0, problem, 1)

        mock_orch.reviewer.review.assert_awaited_once()
        assert code == "def solve(): return 'reviewed'"
        # Verify sandbox was invoked with the reviewed code
        sandbox_call_code = mock_orch.sandbox.run.call_args[0][0]
        assert sandbox_call_code == "def solve(): return 'reviewed'"

    @pytest.mark.asyncio
    async def test_optimizer_refines_all_pass_code(self):
        mock_orch = MagicMock()
        mock_orch.enable_reviewer = False
        mock_orch.enable_optimizer = True
        mock_orch.optimizer = MagicMock()
        mock_orch.optimizer.optimize = AsyncMock(return_value="def solve(): return 'optimized'")
        mock_orch.disable_property_testing = True
        mock_orch.use_validator = False

        generator = MagicMock()
        generator.language = "Python"
        generator.solve = AsyncMock(return_value="def solve(): return 'initial'")
        mock_orch.generators = [generator]
        mock_orch.pop_generator = [AgentGenome()]
        mock_orch.pop_size = 1

        mock_orch.tester = MagicMock()
        mock_orch.tester.evaluate = AsyncMock(return_value=True)

        # First sandbox call passes 2/2 tests. Second sandbox call (re-verifying optimized) also passes 2/2 tests.
        mock_orch.sandbox = MagicMock()
        mock_orch.sandbox.run = MagicMock(side_effect=[
            {
                "passed_tests": 2, "total_tests": 2,
                "failed_test_ids": [], "timeout_tests": [], "crash_tests": [],
                "execution_time_ms": 1.0, "peak_memory_kb": 100.0,
                "test_outputs": []
            },
            {
                "passed_tests": 2, "total_tests": 2,
                "failed_test_ids": [], "timeout_tests": [], "crash_tests": [],
                "execution_time_ms": 0.5, "peak_memory_kb": 90.0,
                "test_outputs": []
            }
        ])
        mock_orch.logger = MagicMock()

        evaluator = EvoEvaluator(mock_orch)
        problem = {"id": 1, "tests": [{"input": "1", "expected": "1"}, {"input": "2", "expected": "2"}]}

        code, test_res, val, chash, _, _ = await evaluator._generate_and_test(0, 0, problem, 1)

        mock_orch.optimizer.optimize.assert_awaited_once()
        assert code == "def solve(): return 'optimized'"
        assert mock_orch.sandbox.run.call_count == 2

    @pytest.mark.asyncio
    async def test_optimizer_rejected_when_retest_fails(self):
        mock_orch = MagicMock()
        mock_orch.enable_reviewer = False
        mock_orch.enable_optimizer = True
        mock_orch.optimizer = MagicMock()
        mock_orch.optimizer.optimize = AsyncMock(return_value="def solve(): return 'broken_opt'")
        mock_orch.disable_property_testing = True
        mock_orch.use_validator = False

        generator = MagicMock()
        generator.language = "Python"
        generator.solve = AsyncMock(return_value="def solve(): return 'working_original'")
        mock_orch.generators = [generator]
        mock_orch.pop_generator = [AgentGenome()]
        mock_orch.pop_size = 1

        mock_orch.tester = MagicMock()
        mock_orch.tester.evaluate = AsyncMock(return_value=True)

        # 1st run: 2/2 pass. 2nd run: 1/2 pass (regression).
        mock_orch.sandbox = MagicMock()
        mock_orch.sandbox.run = MagicMock(side_effect=[
            {
                "passed_tests": 2, "total_tests": 2,
                "failed_test_ids": [], "timeout_tests": [], "crash_tests": [],
                "execution_time_ms": 1.0, "peak_memory_kb": 100.0,
                "test_outputs": []
            },
            {
                "passed_tests": 1, "total_tests": 2,
                "failed_test_ids": [1], "timeout_tests": [], "crash_tests": [],
                "execution_time_ms": 0.5, "peak_memory_kb": 90.0,
                "test_outputs": []
            }
        ])
        mock_orch.logger = MagicMock()

        evaluator = EvoEvaluator(mock_orch)
        problem = {"id": 1, "tests": [{"input": "1", "expected": "1"}, {"input": "2", "expected": "2"}]}

        code, test_res, val, chash, _, _ = await evaluator._generate_and_test(0, 0, problem, 1)

        # Should revert to original
        assert code == "def solve(): return 'working_original'"
        assert test_res["passed_tests"] == 2

    @pytest.mark.asyncio
    async def test_ablation_flags_disable_all_three_agents(self):
        mock_orch = MagicMock()
        mock_orch.enable_architect = False
        mock_orch.enable_reviewer = False
        mock_orch.enable_optimizer = False
        mock_orch.architect = MagicMock()
        mock_orch.reviewer = MagicMock()
        mock_orch.optimizer = MagicMock()

        mock_orch.template_agent = MagicMock()
        mock_orch.template_agent.generate = AsyncMock(return_value={})
        mock_orch.pop_generator = [AgentGenome()]
        mock_orch.pop_size = 1

        generator = MagicMock()
        generator.language = "Python"
        generator.solve = AsyncMock(return_value="def solve(): return 42")
        mock_orch.generators = [generator]

        mock_orch.tester = MagicMock()
        mock_orch.tester.evaluate = AsyncMock(return_value=True)
        mock_orch.sandbox = MagicMock()
        mock_orch.sandbox.run = MagicMock(return_value={
            "passed_tests": 1, "total_tests": 1,
            "failed_test_ids": [], "timeout_tests": [], "crash_tests": [],
            "execution_time_ms": 1.0, "peak_memory_kb": 100.0,
            "test_outputs": []
        })
        mock_orch.logger = MagicMock()
        mock_orch.use_validator = False

        evaluator = EvoEvaluator(mock_orch)
        problem = {"id": 1, "tests": [{"input": "()", "expected": "42"}]}
        problem_report = {"generations": []}

        with patch.object(evaluator, "_score_and_critique", MagicMock(return_value=({}, {}))):
            await evaluator.evaluate_population(0, problem, problem_report)

        mock_orch.architect.plan.assert_not_called()
        mock_orch.reviewer.review.assert_not_called()
        mock_orch.optimizer.optimize.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_single_genome(self):
        mock_orch = MagicMock()
        mock_orch.enable_architect = True
        mock_orch.enable_reviewer = False
        mock_orch.enable_optimizer = False
        mock_orch.architect = MagicMock()
        mock_orch.architect.plan = AsyncMock(return_value="Single Genome Plan")
        mock_orch.pop_generator = [AgentGenome()]
        mock_orch.pop_size = 1
        mock_orch.generators = [MagicMock(language="Python", solve=AsyncMock(return_value="code"))]
        mock_orch.tester = MagicMock(evaluate=AsyncMock(return_value=True))
        mock_orch.sandbox = MagicMock(run=MagicMock(return_value={
            "passed_tests": 1, "total_tests": 1,
            "failed_test_ids": [], "timeout_tests": [], "crash_tests": [],
            "execution_time_ms": 1.0, "peak_memory_kb": 100.0, "test_outputs": []
        }))
        mock_orch.logger = MagicMock()
        mock_orch.use_validator = False

        evaluator = EvoEvaluator(mock_orch)
        problem = {"id": 1, "tests": [{"input": "1", "expected": "1"}]}

        with patch.object(evaluator, "_score_and_critique", MagicMock(return_value=({"fitness": 1.0}, {"eval": 1}))):
            result_item, eval_item = await evaluator.evaluate_single_genome(0, 0, problem, 1)

        assert problem.get("architect_plan") == "Single Genome Plan"
        assert result_item == {"fitness": 1.0}

