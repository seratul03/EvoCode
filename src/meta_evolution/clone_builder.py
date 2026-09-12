"""
CloneBuilder: Two LLM "Architect" agents that independently propose rewrites
to a target agent's source file.

Given the contents of e.g. `src/agents/generator.py`, each Architect is
instructed to improve it — better prompt engineering, smarter error handling,
more robust code extraction, etc.

Each proposal is saved to `src/meta_evolution/staging/` for the SourceJudge
to evaluate. Proposals are NEVER written directly to src/agents/.
"""

import os
import asyncio
from src.client import EvoClient
from src.meta_evolution.watcher import UpgradeTrigger

STAGING_DIR = os.path.join("src", "meta_evolution", "staging")

ARCHITECT_SYSTEM_PROMPT = """You are an expert AI systems engineer specialising in LLM agent design.

You will be given the full source code of a Python LLM agent that is part of an
evolutionary coding framework. Your job is to propose a single, targeted improvement
that makes this agent:

  - Generate better LLM prompts (clearer, more structured, fewer edge-case failures)
  - Handle responses more robustly (better parsing, fallback strategies)
  - Use its genome configuration more effectively
  - Recover more gracefully from API errors or malformed outputs

STRICT RULES:
  1. Return ONLY the complete, modified Python source file — no explanations, no markdown.
  2. Do NOT change the class name, method signatures, or constructor parameters.
     The rest of the system depends on these interfaces being stable.
  3. Do NOT add new imports that are not in: os, sys, re, json, ast, copy, asyncio,
     typing, dataclasses, logging, src (project package), openai, tenacity, dotenv.
  4. Do NOT write to any files. Do NOT add subprocess calls.
  5. Your improvement must be substantive — not just adding comments or renaming variables.
"""


class CloneBuilder:
    """
    Generates two independent proposals for upgrading an agent's source file.

    Args:
        client: EvoClient instance for LLM calls.
    """

    def __init__(self, client: EvoClient):
        self.client = client
        os.makedirs(STAGING_DIR, exist_ok=True)

    async def build(self, trigger: UpgradeTrigger) -> tuple[str, str]:
        """
        Reads the target agent file, fires two independent LLM Architect calls,
        saves both proposals to staging/, and returns their file paths.

        Returns:
            (path_to_proposal_a, path_to_proposal_b)
        """
        # Read the current agent source
        with open(trigger.agent_file, "r", encoding="utf-8") as f:
            current_source = f.read()

        user_prompt = self._build_user_prompt(trigger, current_source)

        print(f"[CloneBuilder] Spawning 2 Architect agents for '{trigger.agent_name}'...")

        # Fire both LLM calls concurrently
        results = await asyncio.gather(
            self._call_architect(user_prompt, architect_id=1),
            self._call_architect(user_prompt, architect_id=2),
        )

        proposal_a, proposal_b = results

        # Save proposals to staging
        path_a = os.path.join(STAGING_DIR, f"{trigger.agent_name}_proposal_a.py")
        path_b = os.path.join(STAGING_DIR, f"{trigger.agent_name}_proposal_b.py")

        with open(path_a, "w", encoding="utf-8") as f:
            f.write(proposal_a)
        with open(path_b, "w", encoding="utf-8") as f:
            f.write(proposal_b)

        print(f"[CloneBuilder] Proposals saved → {path_a}, {path_b}")
        return path_a, path_b

    async def _call_architect(self, user_prompt: str, architect_id: int) -> str:
        print(f"[CloneBuilder] Architect {architect_id} thinking...")
        response = await self.client.create_completion(
            messages=[
                {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,  # slightly creative — each architect should diverge
        )
        code = self._extract_python(response["content"])
        print(f"[CloneBuilder] Architect {architect_id} done ({len(code)} chars).")
        return code

    def _build_user_prompt(self, trigger: UpgradeTrigger, current_source: str) -> str:
        return (
            f"The agent '{trigger.agent_name}' has been performing poorly.\n"
            f"Rolling success rate over the last {trigger.window_size} problems: "
            f"{trigger.rolling_success_rate:.1%} (threshold is 50%).\n\n"
            f"Here is the current source code of this agent:\n\n"
            f"```python\n{current_source}\n```\n\n"
            f"Please propose an improved version of this entire file. "
            f"Return ONLY the complete Python source, no markdown fences, no explanations."
        )

    def _extract_python(self, raw: str) -> str:
        """Strip markdown code fences if the LLM wrapped the output."""
        for fence in ("```python", "```"):
            if fence in raw:
                parts = raw.split(fence)
                if len(parts) > 1:
                    return parts[1].split("```")[0].strip()
        return raw.strip()
