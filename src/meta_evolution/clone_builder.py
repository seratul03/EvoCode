"""
CloneBuilder: Two LLM "Architect" agents that independently propose targeted
improvements to a specific method in a target agent's source file.

Instead of rewriting the entire file (slow, risky), each Architect is asked
to improve ONE specific method. The result is a small patch that is surgically
applied to the original file. This produces a valid, testable challenger file
in ~15-30 seconds instead of 3-5 minutes.
"""

import os
import ast
import asyncio
import textwrap
from src.client import EvoClient
from src.meta_evolution.watcher import UpgradeTrigger

STAGING_DIR = os.path.join("src", "meta_evolution", "staging")

# The specific method to target for improvement in generator.py
TARGET_METHOD = "_build_system_prompt"

ARCHITECT_SYSTEM_PROMPT = """You are an expert AI systems engineer specialising in LLM prompt engineering.

You will be given one Python method from an AI coding agent. Your job is to
propose a single targeted improvement to make the prompts it generates more
effective — clearer structure, better edge-case handling, smarter use of the
agent's genome configuration.

STRICT RULES:
  1. Return ONLY the complete, improved Python method — no explanations, no markdown fences.
  2. Do NOT change the method signature (name, parameters, return type).
  3. Do NOT add new imports.
  4. Your improvement must be substantive — not just adding comments.
  5. Keep the indentation exactly as in the original (4 spaces).
"""


class CloneBuilder:
    """
    Generates two independent proposals for upgrading a specific method
    in an agent's source file. Each proposal is a patched version of the
    original file with the target method replaced.

    Args:
        client: EvoClient instance for LLM calls.
    """

    def __init__(self, client: EvoClient):
        self.client = client
        os.makedirs(STAGING_DIR, exist_ok=True)

    async def build(self, trigger: UpgradeTrigger) -> tuple[str, str]:
        """
        Reads the target agent file, extracts the target method, fires two
        concurrent LLM calls to improve it, applies the patches, saves both
        patched files to staging/, and returns their paths.

        Returns:
            (path_to_proposal_a, path_to_proposal_b)
        """
        self._original_path = trigger.agent_file
        with open(trigger.agent_file, "r", encoding="utf-8") as f:
            original_source = f.read()

        # Extract just the target method to send to the LLM (much smaller prompt)
        target_method_source = self._extract_method(original_source, TARGET_METHOD)
        if not target_method_source:
            print(f"[CloneBuilder] WARNING: Could not extract '{TARGET_METHOD}'. Using full file approach.")
            target_method_source = original_source

        user_prompt = self._build_user_prompt(trigger, target_method_source)

        print(f"[CloneBuilder] Spawning 2 Architect agents for '{trigger.agent_name}.{TARGET_METHOD}'...")
        print(f"[CloneBuilder] Sending {len(target_method_source)} chars to each architect (~15-30s)...")

        # Fire both LLM calls concurrently
        proposal_a_method, proposal_b_method = await asyncio.gather(
            self._call_architect(user_prompt, architect_id=1),
            self._call_architect(user_prompt, architect_id=2),
        )

        # Apply each proposed method back into the full original file
        patched_a = self._apply_patch(original_source, TARGET_METHOD, proposal_a_method)
        patched_b = self._apply_patch(original_source, TARGET_METHOD, proposal_b_method)

        # Save proposals to staging
        path_a = os.path.join(STAGING_DIR, f"{trigger.agent_name}_proposal_a.py")
        path_b = os.path.join(STAGING_DIR, f"{trigger.agent_name}_proposal_b.py")

        with open(path_a, "w", encoding="utf-8") as f:
            f.write(patched_a)
        with open(path_b, "w", encoding="utf-8") as f:
            f.write(patched_b)

        print(f"[CloneBuilder] Proposals saved -> {path_a}, {path_b}")
        return path_a, path_b

    async def _call_architect(self, user_prompt: str, architect_id: int) -> str:
        print(f"[CloneBuilder] Architect {architect_id} thinking...")
        try:
            response = await asyncio.wait_for(
                self.client.create_completion(
                    messages=[
                        {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                ),
                timeout=120,  # 2 min max — method-level output is small
            )
        except asyncio.TimeoutError:
            print(f"[CloneBuilder] Architect {architect_id} timed out. Using original method.")
            return self._extract_method(
                open(self._original_path).read(), TARGET_METHOD
            ) or ""
        code = self._clean_output(response["content"])
        print(f"[CloneBuilder] Architect {architect_id} done ({len(code)} chars).")
        return code

    def _build_user_prompt(self, trigger: UpgradeTrigger, method_source: str) -> str:
        return (
            f"The agent '{trigger.agent_name}' has a rolling success rate of "
            f"{trigger.rolling_success_rate:.1%} — it needs improvement.\n\n"
            f"Here is the '{TARGET_METHOD}' method you must improve:\n\n"
            f"{method_source}\n\n"
            f"Return ONLY the improved method body with the same def signature. "
            f"No markdown, no explanations."
        )

    def _extract_method(self, source: str, method_name: str) -> str | None:
        """Extract a single method's full source text using AST."""
        try:
            tree = ast.parse(source)
            lines = source.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == method_name:
                        start = node.lineno - 1
                        end = node.end_lineno
                        return "\n".join(lines[start:end])
        except Exception:
            pass
        return None

    def _apply_patch(self, original_source: str, method_name: str, new_method: str) -> str:
        """Replace the target method in the original source with the new method."""
        if not new_method or not new_method.strip():
            return original_source  # Fallback: keep original

        try:
            tree = ast.parse(original_source)
            lines = original_source.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == method_name:
                        start = node.lineno - 1
                        end = node.end_lineno
                        new_lines = lines[:start] + new_method.splitlines() + lines[end:]
                        return "\n".join(new_lines)
        except Exception:
            pass
        return original_source  # Fallback: keep original

    def _clean_output(self, raw: str) -> str:
        """Strip markdown fences if present."""
        for fence in ("```python", "```"):
            if fence in raw:
                parts = raw.split(fence)
                if len(parts) > 1:
                    return parts[1].split("```")[0].strip()
        return raw.strip()


