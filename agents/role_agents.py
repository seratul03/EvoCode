import logging
from typing import Dict, Any, Optional

from agents.base_agent import BaseAgent
from evoflow.client import EvoClient
from evoflow.genome import Genome

logger = logging.getLogger(__name__)

class AnalyzerAgent(BaseAgent):
    """
    Analyzes bug reports and repo contexts to narrow down the issue root causes.
    """
    async def run(self, issue_title: str, issue_body: str, repo_context: str) -> Dict[str, Any]:
        user_prompt = self.render_template(
            "analyzer.jinja2",
            issue_title=issue_title,
            issue_body=issue_body,
            repo_context=repo_context
        )
        system_prompt = "You are a software bug diagnosis assistant. Summarize suspect files and root causes."
        
        response = await self.execute_call(system_prompt, user_prompt, temperature=0.0)
        raw_content = response["content"]
        parsed_analysis = self.extract_tag(raw_content, "analysis")
        
        return {
            "raw_content": raw_content,
            "analysis": parsed_analysis or raw_content
        }


class PlannerCoderAgent(BaseAgent):
    """
    Generates a patch/code modification. Dynamic based on Genome settings.
    """
    async def run(self, issue_title: str, issue_body: str, analysis: str, genome: Genome) -> Dict[str, Any]:
        # Select prompt variant based on genome configuration
        template_name = f"planner_coder/{genome.planner_prompt_variant}.jinja2"
        
        user_prompt = self.render_template(
            template_name,
            issue_title=issue_title,
            issue_body=issue_body,
            analysis=analysis
        )
        system_prompt = "You are a code synthesis assistant. Output code modifications in search-and-replace format."
        
        # Call client with temperature from genome configuration
        response = await self.execute_call(
            system_prompt,
            user_prompt,
            temperature=genome.planner_temperature
        )
        raw_content = response["content"]
        parsed_patch = self.extract_tag(raw_content, "patch")
        
        return {
            "raw_content": raw_content,
            "patch": parsed_patch
        }


class CriticAgent(BaseAgent):
    """
    Reviews draft patches and identifies missing files, risks, or potential bugs.
    """
    async def run(self, issue_body: str, patch: str) -> Dict[str, Any]:
        user_prompt = self.render_template(
            "critic.jinja2",
            issue_body=issue_body,
            patch=patch
        )
        system_prompt = "You are a code reviewer. Critique the code modifications and raise safety alerts."
        
        response = await self.execute_call(system_prompt, user_prompt, temperature=0.0)
        raw_content = response["content"]
        parsed_critique = self.extract_tag(raw_content, "critique")
        
        return {
            "raw_content": raw_content,
            "critique": parsed_critique or raw_content
        }


class MutatorAgent(BaseAgent):
    """
    Mutates/refines an original patch using critic reviews. Dynamic based on Genome settings.
    """
    async def run(self, original_patch: str, critique: str, genome: Genome) -> Dict[str, Any]:
        # Currently, standard mutator prompt is used
        template_name = f"{genome.mutator_prompt_variant}.jinja2"
        
        user_prompt = self.render_template(
            template_name,
            original_patch=original_patch,
            critique=critique
        )
        system_prompt = "You are a patch revision assistant. Integrate critiques and output corrected patches."
        
        # Call client with temperature from genome configuration
        response = await self.execute_call(
            system_prompt,
            user_prompt,
            temperature=genome.mutator_temperature
        )
        raw_content = response["content"]
        parsed_patch = self.extract_tag(raw_content, "patch")
        
        return {
            "raw_content": raw_content,
            "patch": parsed_patch
        }


class JudgeAgent(BaseAgent):
    """
    Scores patches based on test execution logs and quality rubrics.
    """
    async def run(self, patch: str, test_results: str) -> Dict[str, Any]:
        user_prompt = self.render_template(
            "judge.jinja2",
            patch=patch,
            test_results=test_results
        )
        system_prompt = "You are a QA testing judge. Review execution results and score patch correctess."
        
        response = await self.execute_call(system_prompt, user_prompt, temperature=0.0)
        raw_content = response["content"]
        
        # Extract and parse numeric score
        score_str = self.extract_tag(raw_content, "score")
        try:
            score = int(score_str)
        except ValueError:
            # Fallback if model outputs non-integer or failed to format tag
            score = 1
            logger.warning(f"Could not parse score '{score_str}' to integer. Defaulting to 1.")
            
        return {
            "raw_content": raw_content,
            "score": score
        }
