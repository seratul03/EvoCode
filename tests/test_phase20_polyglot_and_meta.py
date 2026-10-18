"""
Tests for Phase 20: Polyglot Complexity Evaluators, Vector Memory Retrieval, and Generalized Meta-Evolution.

Coverage:
  - Step 3: Polyglot Complexity Evaluator (Python, Java, C++) and Robustness Evaluator.
  - Step 4: Semantic Vector Memory Retrieval with TF-IDF cosine similarity and prioritization.
  - Step 5: Multi-agent Meta-Evolution (Watcher, CloneBuilder) and normalized duel fitness in MetaArena.
"""

import os
import json
import pytest
import tempfile
import textwrap
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.evaluators import ComplexityEvaluator, RobustnessEvaluator
from src.fitness_scorer import calculate_fitness, FitnessScorer
from src.genome import AgentGenome, EvaluatorGenome
from src.agents.memory_agent import MemoryHistorianAgent
from src.meta_evolution.watcher import Watcher, UpgradeTrigger, UPGRADEABLE_AGENTS, AGENT_TARGET_METHODS
from src.meta_evolution.clone_builder import CloneBuilder
from src.meta_evolution.meta_arena import MetaArena, DuelResult


# ============================================================================
# Step 3: Polyglot Complexity & Robustness Evaluators
# ============================================================================

class TestPolyglotComplexityEvaluator:
    def setup_method(self):
        self.evaluator = ComplexityEvaluator()

    def test_python_cyclomatic_complexity(self):
        py_simple = textwrap.dedent("""
            def add(a, b):
                return a + b
        """)
        py_complex = textwrap.dedent("""
            def solve(n, arr):
                res = []
                for x in arr:
                    if x > 0:
                        if x % 2 == 0:
                            res.append(x * 2)
                        else:
                            res.append(x)
                    elif x == 0:
                        continue
                    else:
                        while x < -5:
                            x += 1
                        res.append(x)
                return res
        """)
        score_simple = self.evaluator.score(py_simple, language="Python")
        score_complex = self.evaluator.score(py_complex, language="Python")

        assert 0.0 <= score_simple <= 1.0
        assert 0.0 <= score_complex <= 1.0
        # Simpler code has lower cyclomatic complexity, hence higher score
        assert score_simple > score_complex

    def test_java_cyclomatic_complexity(self):
        java_simple = textwrap.dedent("""
            public class Solution {
                public int add(int a, int b) {
                    return a + b;
                }
            }
        """)
        java_complex = textwrap.dedent("""
            public class Solution {
                public int process(int[] nums, boolean flag) {
                    int sum = 0;
                    for (int n : nums) {
                        if (n > 0 && flag) {
                            sum += n;
                        } else if (n < 0 || !flag) {
                            while (n < 0) {
                                n++;
                                sum++;
                            }
                        } else {
                            switch (n) {
                                case 0: sum += 1; break;
                                default: sum += 2; break;
                            }
                        }
                    }
                    return sum;
                }
            }
        """)
        score_simple = self.evaluator.score(java_simple, language="Java")
        score_complex = self.evaluator.score(java_complex, language="Java")

        assert 0.0 <= score_simple <= 1.0
        assert 0.0 <= score_complex <= 1.0
        assert score_simple > score_complex

    def test_cpp_cyclomatic_complexity(self):
        cpp_simple = textwrap.dedent("""
            #include <vector>
            int add(int a, int b) {
                return a + b;
            }
        """)
        cpp_complex = textwrap.dedent("""
            #include <vector>
            int compute(const std::vector<int>& v) {
                int total = 0;
                for (int x : v) {
                    if (x > 10 && x < 100) {
                        total += x;
                    } else if (x <= 10 || x == 0) {
                        total -= x;
                    }
                    while (x > 100) {
                        x /= 2;
                        total++;
                    }
                }
                return total;
            }
        """)
        score_simple = self.evaluator.score(cpp_simple, language="C++")
        score_complex = self.evaluator.score(cpp_complex, language="C++")

        assert 0.0 <= score_simple <= 1.0
        assert 0.0 <= score_complex <= 1.0
        assert score_simple > score_complex

    def test_fallback_cyclomatic_complexity(self):
        # Even if lizard is bypassed, the fallback AST regex works
        code = textwrap.dedent("""
            bool check(int x, int y) {
                if (x > 0 && y > 0) return true;
                while (x < 0) x++;
                for (int i = 0; i < 5; ++i) y++;
                return false;
            }
        """)
        cc = self.evaluator._fallback_cyclomatic_complexity(code)
        assert cc > 1


class TestPolyglotRobustnessEvaluator:
    def setup_method(self):
        self.evaluator = RobustnessEvaluator()

    def test_java_robustness(self):
        java_fragile = "public class Solution { public int calc(int a) { return a / 0; } }"
        java_robust = textwrap.dedent("""
            public class Solution {
                public int calc(String s, int[] arr) {
                    if (s == null || arr.length == 0) {
                        return 0;
                    }
                    try {
                        return arr[0] / (s.length() == 0 ? 1 : s.length());
                    } catch (Exception e) {
                        return -1;
                    }
                }
            }
        """)
        score_fragile = self.evaluator.score(java_fragile, language="Java")
        score_robust = self.evaluator.score(java_robust, language="Java")

        assert 0.0 <= score_fragile <= 1.0
        assert 0.0 <= score_robust <= 1.0
        assert score_robust > score_fragile

    def test_cpp_robustness(self):
        cpp_fragile = "int run(int* p) { return *p; }"
        cpp_robust = textwrap.dedent("""
            #include <vector>
            #include <stdexcept>
            int run(int* ptr, const std::vector<int>& v) {
                if (ptr == nullptr || v.empty()) {
                    return 0;
                }
                try {
                    return *ptr + v.at(0);
                } catch (const std::exception& e) {
                    return -1;
                }
            }
        """)
        score_fragile = self.evaluator.score(cpp_fragile, language="C++")
        score_robust = self.evaluator.score(cpp_robust, language="C++")

        assert 0.0 <= score_fragile <= 1.0
        assert 0.0 <= score_robust <= 1.0
        assert score_robust > score_fragile

    def test_calculate_fitness_polyglot(self):
        test_results = {"passed_tests": 5, "total_tests": 5, "failed_tests": [], "crash_tests": []}
        code_java = "public class Solution { public int add(int a, int b) { return a + b; } }"
        genome = EvaluatorGenome(agent_id="eval_test", generation_id=1)

        fitness_java = calculate_fitness(code=code_java, test_results=test_results, genome=genome, language="Java")
        assert fitness_java["fitness_value"] > 0.0
        assert "complexity" in fitness_java["breakdown"]
        assert "robustness" in fitness_java["breakdown"]

        code_cpp = "int add(int a, int b) { return a + b; }"
        fitness_cpp = calculate_fitness(code=code_cpp, test_results=test_results, genome=genome, language="C++")
        assert fitness_cpp["fitness_value"] > 0.0
        assert "complexity" in fitness_cpp["breakdown"]
        assert "robustness" in fitness_cpp["breakdown"]


# ============================================================================
# Step 4: Vector Memory Retrieval
# ============================================================================

class TestVectorMemoryRetrieval:
    def test_search_memory_semantic_matching(self, tmp_path):
        client = MagicMock()
        memory_file = str(tmp_path / "agent_memory.txt")
        memory_agent = MemoryHistorianAgent(client, memory_file=memory_file)

        # Append diverse experiences
        memory_agent.append_entry(
            "[MEMORY ENTRY - 2026-10-18T10:00:00]\n"
            "Problem: Binary Tree Inorder Traversal | Result: SOLVED | Best Fitness: 0.9500\n"
            "Traverse a binary tree in inorder and return the nodes as an array.\n"
            "LESSON: Recursion or stack works well for trees."
        )
        memory_agent.append_entry(
            "[MEMORY ENTRY - 2026-10-18T10:05:00]\n"
            "Problem: Two Sum with Hash Map | Result: SOLVED | Best Fitness: 0.9800\n"
            "Find two indices that sum to target using dictionary hash map lookup.\n"
            "LESSON: Dict lookup is O(1) average time."
        )
        memory_agent.append_entry(
            "[MEMORY ENTRY - 2026-10-18T10:10:00]\n"
            "Problem: Graph Dijkstra Shortest Path | Result: SOLVED | Best Fitness: 0.9000\n"
            "Compute single-source shortest path in weighted directed graph using min-heap priority queue.\n"
            "LESSON: Heapq keeps minimum distance vertex at the top."
        )

        # Query specifically for trees
        tree_results = memory_agent.search_memory(
            query="tree traversal recursive nodes",
            max_entries=1,
            memory_file=memory_file
        )
        assert len(tree_results) == 1
        assert "Binary Tree Inorder Traversal" in tree_results[0]

        # Query specifically for graph shortest path
        graph_results = memory_agent.search_memory(
            query="graph shortest path priority queue",
            max_entries=1,
            memory_file=memory_file
        )
        assert len(graph_results) == 1
        assert "Graph Dijkstra Shortest Path" in graph_results[0]

    def test_prioritization_successes_vs_failures(self, tmp_path):
        client = MagicMock()
        memory_file = str(tmp_path / "agent_memory.txt")
        memory_agent = MemoryHistorianAgent(client, memory_file=memory_file)

        # Add a high fitness item and a low fitness failure item with overlapping keywords
        memory_agent.append_entry(
            "[MEMORY ENTRY - 2026-10-18T10:15:00]\n"
            "Problem: Sorting Arrays QuickSort | Result: SOLVED | Best Fitness: 0.9500\n"
            "Sort an array of integers using quicksort divide and conquer.\n"
            "LESSON: Random pivot prevents O(n^2) worst case."
        )
        memory_agent.append_entry(
            "[MEMORY ENTRY - 2026-10-18T10:20:00]\n"
            "Problem: Sorting Arrays BubbleSort Failure | Result: UNSOLVED | Best Fitness: 0.2000\n"
            "Sort an array of integers using bubble sort which timed out on large tests.\n"
            "LESSON: Bubble sort is too slow for large inputs."
        )

        # Prioritize successes
        succ_results = memory_agent.search_memory(
            query="sorting array integers",
            max_entries=2,
            prioritization="successes",
            memory_file=memory_file
        )
        assert "QuickSort" in succ_results[0]

        # Prioritize failures (for debugging/mutation lessons)
        fail_results = memory_agent.search_memory(
            query="sorting array integers",
            max_entries=2,
            prioritization="failures",
            memory_file=memory_file
        )
        assert "BubbleSort Failure" in fail_results[0]

    def test_load_memory_vector_and_recent_strategies(self, tmp_path):
        client = MagicMock()
        memory_file = str(tmp_path / "agent_memory.txt")
        memory_agent = MemoryHistorianAgent(client, memory_file=memory_file)

        for i in range(5):
            memory_agent.append_entry(
                f"[MEMORY ENTRY - 2026-10-18T10:{i:02d}:00]\n"
                f"Problem: Task {i} | Result: SOLVED | Best Fitness: 0.8000\n"
                f"Description of problem {i} with unique keyword kw_{i}\n"
                f"LESSON: lesson {i}"
            )

        # Test vector search retrieval
        text_vector = memory_agent.load_memory(
            query="kw_2 specific description",
            strategy="vector",
            max_entries=2,
            memory_file=memory_file
        )
        assert "Task 2" in text_vector

        # Test recent retrieval fallback
        text_recent = memory_agent.load_memory(
            strategy="recent",
            max_entries=2,
            memory_file=memory_file
        )
        assert "Task 4" in text_recent
        assert "Task 3" in text_recent


# ============================================================================
# Step 5: Generalized Meta-Evolution
# ============================================================================

def _make_sample_report(passed: int, total: int, tmpdir: str, filename: str, has_crash: bool = False) -> str:
    report = {
        "start_time": "2026-09-12T00:00:00",
        "problems_evaluated": [
            {
                "problem_id": 1,
                "generations": [
                    {
                        "generation_id": 1,
                        "evaluations": [
                            {
                                "genome_index": 0,
                                "test_results": {
                                    "passed_tests": passed,
                                    "total_tests": total,
                                    "crash_tests": ["crash_1"] if has_crash else [],
                                },
                                "fitness": {
                                    "fitness_value": passed / max(1, total),
                                    "correctness_rate": passed / max(1, total),
                                },
                                "execution_error": "CrashError" if has_crash else None,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    path = os.path.join(tmpdir, filename)
    with open(path, "w") as f:
        json.dump(report, f)
    return path


class TestGeneralizedMetaEvolution:
    def test_watcher_multi_agent_targeting(self, tmp_path):
        d = str(tmp_path)
        for i in range(10):
            _make_sample_report(0, 5, d, f"report_{i:03d}.json")

        watcher = Watcher(reports_dir=d, threshold=0.50, window=10)

        # Target architect
        trig_arch = watcher.check(target_agent="architect.py")
        assert trig_arch is not None
        assert trig_arch.agent_name == "architect"
        assert trig_arch.target_method == AGENT_TARGET_METHODS["architect.py"]

        # Target reviewer
        trig_rev = watcher.check(target_agent="reviewer.py")
        assert trig_rev is not None
        assert trig_rev.agent_name == "reviewer"
        assert trig_rev.target_method == AGENT_TARGET_METHODS["reviewer.py"]

        # Target optimizer
        trig_opt = watcher.check(target_agent="optimizer.py")
        assert trig_opt is not None
        assert trig_opt.agent_name == "optimizer"
        assert trig_opt.target_method == AGENT_TARGET_METHODS["optimizer.py"]

        # Target template
        trig_tmpl = watcher.check(target_agent="template.py")
        assert trig_tmpl is not None
        assert trig_tmpl.agent_name == "template"
        assert trig_tmpl.target_method == AGENT_TARGET_METHODS["template.py"]

    @pytest.mark.asyncio
    async def test_clone_builder_generalized_patching(self):
        client = AsyncMock()
        client.create_completion = AsyncMock(return_value={
            "content": """
```python
    async def plan(self, problem: dict, language: str = "Python") -> dict:
        return {"approach": "optimized multi-step decomposition"}
```
"""
        })
        builder = CloneBuilder(client)
        trigger = UpgradeTrigger(
            agent_name="architect",
            agent_file="src/agents/architect.py",
            target_method="plan",
            rolling_success_rate=0.2,
            window_size=10,
            consecutive_upgrade_failures=0
        )

        with tempfile.TemporaryDirectory() as tmp_staging:
            with patch("src.meta_evolution.clone_builder.STAGING_DIR", tmp_staging):
                path_a, path_b = await builder.build(trigger)
                assert os.path.exists(path_a)
                assert os.path.exists(path_b)
                with open(path_a, "r", encoding="utf-8") as f:
                    content_a = f.read()
                assert "class ArchitectAgent" in content_a
                assert "optimized multi-step decomposition" in content_a

    def test_meta_arena_normalized_duel_fitness(self, tmp_path):
        d = str(tmp_path)
        arena = MetaArena()

        # Create reports:
        # 1. passed=5, total=5 (fitness=1.0, correctness=1.0, crash=0)
        # 2. passed=3, total=5 (fitness=0.6, correctness=0.6, crash=0)
        # 3. passed=0, total=5 (fitness=0.0, correctness=0.0, crash=1)
        _make_sample_report(5, 5, d, "rep1.json", has_crash=False)
        _make_sample_report(3, 5, d, "rep2.json", has_crash=False)
        _make_sample_report(0, 5, d, "rep3.json", has_crash=True)

        score, metrics = arena.extract_normalized_fitness(d)

        # Expected calculations:
        # fitness_values = [1.0, 0.6, 0.0] -> mean = 0.5333, max = 1.0
        # correctness_rates = [1.0, 0.6, 0.0] -> mean = 0.5333
        # crash_rate = 1 / 3 = 0.3333
        # raw_score = 0.45 * 0.5333 + 0.35 * 1.0 + 0.20 * 0.5333 - 0.10 * 0.3333
        # raw_score = 0.2400 + 0.3500 + 0.1067 - 0.0333 = 0.6634
        assert metrics["eval_count"] == 3
        assert pytest.approx(metrics["mean_fitness"], abs=0.05) == 0.5333
        assert metrics["max_fitness"] == 1.0
        assert pytest.approx(metrics["correctness_rate"], abs=0.05) == 0.5333
        assert pytest.approx(metrics["crash_rate"], abs=0.05) == 0.3333
        assert pytest.approx(score, abs=0.05) == 0.6634

    @pytest.mark.asyncio
    async def test_meta_arena_duel_challenger_wins(self, tmp_path):
        arena = MetaArena(project_root=str(tmp_path))

        # Mock _run_subprocess to simulate original (0.50) vs challenger (0.85)
        orig_metrics = {"mean_fitness": 0.5, "max_fitness": 0.6, "correctness_rate": 0.5, "crash_rate": 0.0}
        chal_metrics = {"mean_fitness": 0.85, "max_fitness": 0.95, "correctness_rate": 0.9, "crash_rate": 0.0}

        with patch.object(
            arena,
            "_run_subprocess",
            side_effect=[
                (0.50, orig_metrics),
                (0.85, chal_metrics),
            ],
        ), patch.object(arena, "_promote_challenger") as mock_promote:
            result = await arena.duel("src/agents/generator.py", "staging/chal.py")
            assert isinstance(result, DuelResult)
            assert result.challenger_won is True
            assert result.original_fitness == 0.50
            assert result.challenger_fitness == 0.85
            assert result.original_metrics == orig_metrics
            assert result.challenger_metrics == chal_metrics
            mock_promote.assert_called_once_with("staging/chal.py", "src/agents/generator.py")
