"""
SourceJudge: Two independent LLM judges that vote on which of the two
CloneBuilder proposals is the better agent upgrade.

Both judges read the original source file and both proposals, then cast a
vote ("A" or "B"). The proposal with more votes becomes the challenger.
In case of a tie (which can only happen in odd-judge setups, but for safety),
Proposal A wins by default as the conservative choice.

The winner's path is returned for the Referee to inspect and the MetaArena
to use in the duel.
"""

import asyncio
import re
from src.client import EvoClient

JUDGE_SYSTEM_PROMPT = """You are a senior AI systems architect conducting a code review.

You will be given two proposed rewrites (Proposal A and Proposal B) of a Python
LLM agent. Your job is to judge which proposal is the superior improvement.

Evaluate based on:
  1. Quality of the LLM prompt engineering (clarity, structure, completeness)
  2. Robustness of response parsing and error handling
  3. Correctness — the proposal must not break any existing method signatures
  4. Subtlety — small targeted improvements beat large risky rewrites

At the end of your response, output EXACTLY one line in this format:
  VERDICT: A
or
  VERDICT: B

Do not output anything after the VERDICT line.
"""


class SourceJudge:
    """
    Runs two independent LLM judges to vote on the best proposal.

    Args:
        client: EvoClient instance for LLM calls.
    """

    def __init__(self, client: EvoClient):
        self.client = client

    async def judge(
        self,
        original_path: str,
        proposal_a_path: str,
        proposal_b_path: str,
    ) -> str:
        """
        Reads the original and both proposals, fires two concurrent judge calls,
        tallies votes, and returns the path of the winning proposal.

        Returns:
            Path to the winning proposal file.
        """
        with open(original_path, "r", encoding="utf-8") as f:
            original_source = f.read()
        with open(proposal_a_path, "r", encoding="utf-8") as f:
            proposal_a = f.read()
        with open(proposal_b_path, "r", encoding="utf-8") as f:
            proposal_b = f.read()

        user_prompt = self._build_prompt(original_source, proposal_a, proposal_b)

        print("[SourceJudge] Spawning 2 judge agents...")
        verdicts = await asyncio.gather(
            self._call_judge(user_prompt, judge_id=1),
            self._call_judge(user_prompt, judge_id=2),
        )

        votes = {"A": 0, "B": 0}
        for verdict in verdicts:
            if verdict in votes:
                votes[verdict] += 1
            else:
                votes["A"] += 1  # Malformed verdict → conservative default

        winner = "A" if votes["A"] >= votes["B"] else "B"
        winning_path = proposal_a_path if winner == "A" else proposal_b_path

        print(
            f"[SourceJudge] Votes — A: {votes['A']}, B: {votes['B']}. "
            f"Winner: Proposal {winner} → {winning_path}"
        )
        return winning_path

    async def _call_judge(self, user_prompt: str, judge_id: int) -> str:
        print(f"[SourceJudge] Judge {judge_id} reviewing proposals...")
        response = await self.client.create_completion(
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,  # deterministic — we want principled judgement, not creativity
        )
        verdict = self._extract_verdict(response["content"])
        print(f"[SourceJudge] Judge {judge_id} voted: {verdict}")
        return verdict

    def _build_prompt(self, original: str, proposal_a: str, proposal_b: str) -> str:
        return (
            "Here is the ORIGINAL agent source code:\n"
            f"```python\n{original}\n```\n\n"
            "--- PROPOSAL A ---\n"
            f"```python\n{proposal_a}\n```\n\n"
            "--- PROPOSAL B ---\n"
            f"```python\n{proposal_b}\n```\n\n"
            "Which proposal is the better improvement? Output VERDICT: A or VERDICT: B."
        )

    def _extract_verdict(self, response: str) -> str:
        match = re.search(r"VERDICT:\s*([AB])", response, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return "A"  # Default to conservative choice if parsing fails
