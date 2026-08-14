import re
import os
from typing import Dict, Any, Optional

from agents.base_agent import BaseAgent

class IterativeAgent(BaseAgent):
    """
    A single monolithic agent for the baseline iterative refinement process.
    It reads the issue and any previous test failures, then generates a patch.
    """
    
    async def run(self, issue_title: str, issue_body: str, repo_context: str, test_failures: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates a patch based on issue context and previous test failures.
        """
        # Render the baseline template
        user_prompt = self.render_template(
            "baseline.jinja2",
            issue_title=issue_title,
            issue_body=issue_body,
            repo_context=repo_context,
            test_failures=test_failures
        )
        
        system_prompt = "You are a senior software developer. Output code modifications in search-and-replace format inside a <patch> tag."
        
        # Call the LLM
        response = await self.execute_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        response_text = response["content"]
        
        # Extract the patch block
        patch_match = re.search(r'<patch>(.*?)</patch>', response_text, re.DOTALL)
        patch = patch_match.group(1).strip() if patch_match else response_text.strip()
        
        return {
            "patch": patch,
            "raw_content": response_text
        }
