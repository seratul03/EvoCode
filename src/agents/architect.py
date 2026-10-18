"""
src/agents/architect.py

ArchitectAgent — Pre-generation problem decomposition.

Called ONCE per problem (before any GeneratorAgent call) to produce a
structured algorithmic plan.  The plan is injected into every
GeneratorAgent's user prompt so the LLM starts with a clear strategy
instead of approaching the raw description cold.

Design rules:
  - One LLM call per problem; result cached in problem["architect_plan"].
  - Never blocks the pipeline: if the call fails the plan falls back to "".
  - Respects genome.reasoning.planning_strategy and
    genome.coding.algorithm_selection_strategy.
"""

from src.client import EvoClient
from src.genome import AgentGenome


class ArchitectAgent:
    """
    Decomposes a competitive-programming problem into an algorithmic
    plan that GeneratorAgents use to guide code production.

    The agent is language-agnostic — the plan it returns is a concise
    pseudocode/strategy block that is valid for all target languages.
    """

    SYSTEM_PROMPT = (
        "You are a senior algorithm architect specialising in competitive programming. "
        "Your sole job is to analyse a problem and produce a concise, actionable "
        "algorithmic plan for a code-generation agent to follow.\n\n"
        "Rules:\n"
        "1. Output ONLY the plan — no code, no preamble.\n"
        "2. Structure: Algorithm Choice → Data Structures → Step-by-step Logic → "
        "   Edge Cases to Handle.\n"
        "3. Be concrete and specific (e.g., 'Use a two-pointer approach on a sorted "
        "   array, O(n log n)'), not vague ('use a good algorithm').\n"
        "4. Maximum 15 lines.\n"
    )

    def __init__(self, client: EvoClient):
        self.client = client

    async def plan(self, problem: dict, genome: AgentGenome) -> str:
        """
        Produce an algorithmic plan for *problem* guided by *genome* strategy genes.

        Returns a plain-text plan string.  Returns "" on any failure so the
        calling pipeline can proceed without a plan.
        """
        strategy_hint = self._strategy_hint(genome)
        user_prompt = self._build_prompt(problem, strategy_hint)

        try:
            response = await self.client.create_completion(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.0,   # planning is deterministic
                max_tokens=400,
            )
            plan_text = response.get("content", "").strip()
            return plan_text
        except Exception as e:
            # Graceful degradation — pipeline continues without a plan
            print(f"      [Architect] Plan generation failed ({e}). Continuing without plan.")
            return ""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _strategy_hint(self, genome: AgentGenome) -> str:
        """
        Translates genome strategy genes into a natural-language hint
        that biases the Architect toward the genome's preferred approach.
        """
        hints = []

        coding = getattr(genome, "coding", None)
        algo = getattr(coding, "algorithm_selection_strategy", None) if coding else None
        if algo == "brute_force_first":
            hints.append("prefer a simple brute-force approach first for correctness")
        elif algo == "optimize_first":
            hints.append("prefer the most time-efficient algorithm even if more complex")

        reasoning = getattr(genome, "reasoning", None)
        plan = getattr(reasoning, "planning_strategy", None) if reasoning else None
        if plan == "step_by_step":
            hints.append("break the plan into fine-grained numbered steps")
        elif plan == "tree_of_thought":
            hints.append("explore two alternative algorithmic approaches then pick the best")

        depth = getattr(reasoning, "reasoning_depth", 3) if reasoning else 3
        if depth >= 4:
            hints.append("include detailed complexity analysis")
        elif depth <= 1:
            hints.append("keep the plan very brief")

        return "; ".join(hints) if hints else ""

    def _build_prompt(self, problem: dict, strategy_hint: str) -> str:
        title = problem.get("title", "Unknown Problem")
        description = problem.get("description", "")

        tests = problem.get("tests", [])
        examples = ""
        if tests:
            sample = tests[:3]
            lines = [
                f"  Input: {t.get('input', '')}  →  Expected: {t.get('expected', '')}"
                for t in sample
            ]
            examples = "Example I/O:\n" + "\n".join(lines)

        prompt = f"Problem: {title}\n\n{description}\n\n{examples}\n"
        if strategy_hint:
            prompt += f"\nStrategy hint from genome: {strategy_hint}\n"
        prompt += "\nProduce the algorithmic plan:"
        return prompt
