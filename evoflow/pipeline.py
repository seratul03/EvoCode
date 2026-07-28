import logging
from typing import Dict, Any

from agents.role_agents import AnalyzerAgent, PlannerCoderAgent, CriticAgent, MutatorAgent, JudgeAgent
from harness.evaluator import Evaluator, Task
from evoflow.genome import Genome
from evoflow.logger import EventLogger

logger = logging.getLogger(__name__)

class SequentialPipeline:
    def __init__(self, use_docker: bool = False):
        from evoflow.client import EvoClient
        self.client = EvoClient()
        self.analyzer = AnalyzerAgent(self.client)
        self.planner = PlannerCoderAgent(self.client)
        self.critic = CriticAgent(self.client)
        self.mutator = MutatorAgent(self.client)
        self.judge = JudgeAgent(self.client)
        self.evaluator = Evaluator(use_docker=use_docker)
        self.event_logger = EventLogger()
        self.genome = Genome(mutator_prompt_variant="mutator") # matches mutator.jinja2

    async def run(self, task: Task, issue_title: str, issue_body: str, repo_context: str) -> Dict[str, Any]:
        self.event_logger.log_pipeline_start(task.instance_id)
        
        # 1. Analyzer
        print("[Pipeline] Running Analyzer...")
        analyzer_res = await self.analyzer.run(issue_title, issue_body, repo_context)
        self.event_logger.log_agent_action("Analyzer", issue_body, analyzer_res["raw_content"])
        analysis = analyzer_res["analysis"]
        
        # 2. Planner
        print("[Pipeline] Running Planner...")
        planner_res = await self.planner.run(issue_title, issue_body, analysis, self.genome)
        self.event_logger.log_agent_action("Planner", analysis, planner_res["raw_content"])
        draft_patch = planner_res["patch"]
        
        if not draft_patch:
            # Fallback if parsing fails
            draft_patch = ""
            
        # 3. First Evaluation
        print("[Pipeline] Running First Evaluation...")
        eval_1_res = self.evaluator.evaluate(task, draft_patch)
        self.event_logger.log_evaluator_result(task.instance_id, eval_1_res)
        
        if eval_1_res["success"]:
            # Passed on first try
            print("[Pipeline] Success on first draft!")
            self.event_logger.log_pipeline_end(task.instance_id, "PASS_DRAFT")
            return {"status": "PASS", "patch": draft_patch, "eval": eval_1_res}
            
        # 4. Critic
        print("[Pipeline] Running Critic (first draft failed)...")
        critic_input = f"{issue_body}\n\n[Test Failure Logs]\n{eval_1_res['logs']}"
        critic_res = await self.critic.run(critic_input, draft_patch)
        self.event_logger.log_agent_action("Critic", critic_input, critic_res["raw_content"])
        critique = critic_res["critique"]
        
        # 5. Mutator
        print("[Pipeline] Running Mutator...")
        mutator_res = await self.mutator.run(draft_patch, critique, self.genome)
        self.event_logger.log_agent_action("Mutator", critique, mutator_res["raw_content"])
        mutated_patch = mutator_res["patch"]
        
        if not mutated_patch:
            mutated_patch = ""
            
        # 6. Second Evaluation
        print("[Pipeline] Running Second Evaluation...")
        eval_2_res = self.evaluator.evaluate(task, mutated_patch)
        self.event_logger.log_evaluator_result(task.instance_id, eval_2_res)
        
        # 7. Judge
        print("[Pipeline] Running Judge...")
        judge_res = await self.judge.run(mutated_patch, eval_2_res["logs"])
        self.event_logger.log_agent_action("Judge", mutated_patch, judge_res["raw_content"])
        score = judge_res["score"]
        
        final_status = "PASS_MUTATED" if eval_2_res["success"] else "FAIL"
        self.event_logger.log_pipeline_end(task.instance_id, final_status)
        print(f"[Pipeline] Final status: {final_status} (Judge Score: {score})")
        
        return {
            "status": final_status,
            "patch": mutated_patch,
            "eval_1": eval_1_res,
            "eval_2": eval_2_res,
            "score": score
        }
