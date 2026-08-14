import asyncio
from typing import Dict, Any

from evoflow.client import EvoClient
from evoflow.logger import EventLogger
from harness.evaluator import Evaluator, Task
from baseline.iterative_agent import IterativeAgent

class BaselinePipeline:
    """
    Executes the Single-Agent iterative refinement process.
    """
    def __init__(self, max_iterations: int = 5, event_logger: EventLogger = None):
        self.max_iterations = max_iterations
        self.client = EvoClient()
        self.agent = IterativeAgent(self.client)
        self.evaluator = Evaluator()
        self.event_logger = event_logger or EventLogger("logs/baseline_logs.jsonl")
        
    async def run_task(self, task: Task, issue_title: str, issue_body: str, repo_context: str) -> Dict[str, Any]:
        """
        Runs the iterative refinement loop for a single task.
        """
        self.event_logger.log_pipeline_start(task.instance_id)
        print(f"\n[Baseline] Starting Task: {task.instance_id}")
        
        test_failures = None
        best_patch = None
        
        for iteration in range(self.max_iterations):
            print(f"[Baseline] Iteration {iteration + 1}/{self.max_iterations}")
            
            # Generate Patch
            agent_res = await self.agent.run(issue_title, issue_body, repo_context, test_failures)
            self.event_logger.log_agent_action(f"IterativeAgent_iter{iteration+1}", "Generated patch", agent_res["raw_content"])
            
            patch = agent_res["patch"]
            best_patch = patch
            
            # Evaluate
            print(f"[Baseline] Evaluating patch...")
            eval_res = self.evaluator.evaluate(task, patch)
            self.event_logger.log_evaluator_result(task.instance_id, eval_res)
            
            if eval_res.get("success", False):
                print(f"[Baseline] Success on iteration {iteration + 1}!")
                self.event_logger.log_pipeline_end(task.instance_id, "PASS")
                return {"status": "PASS", "patch": patch, "iterations": iteration + 1}
            else:
                print(f"[Baseline] Evaluation failed. Capturing logs for next iteration.")
                # Pass the error logs back for the next iteration
                test_failures = eval_res.get("log", eval_res.get("logs", ""))
                
        print(f"[Baseline] Max iterations reached. Failing task.")
        self.event_logger.log_pipeline_end(task.instance_id, "FAIL")
        return {"status": "FAIL", "patch": best_patch, "iterations": self.max_iterations}
