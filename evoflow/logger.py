import os
import json
import time
from typing import Dict, Any

class EventLogger:
    def __init__(self, log_dir: str = "logs", filename: str = "run_logs.jsonl"):
        # Ensure we are saving relative to the project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_dir = os.path.join(project_root, log_dir)
        self.filename = filename
        self.log_path = os.path.join(self.log_dir, self.filename)
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
    def _log_event(self, event_type: str, data: dict):
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
            
    def log_agent_action(self, agent_name: str, input_data: str, output_data: str, token_usage: Dict[str, Any] = None):
        self._log_event("agent_action", {
            "agent_name": agent_name,
            "input": input_data,
            "output": output_data,
            "token_usage": token_usage or {}
        })
        
    def log_evaluator_result(self, task_id: str, result: Dict[str, Any]):
        self._log_event("evaluator_result", {
            "task_id": task_id,
            "result": result
        })
        
    def log_pipeline_start(self, task_id: str):
        self._log_event("pipeline_start", {
            "task_id": task_id
        })
        
    def log_pipeline_end(self, task_id: str, final_status: str):
        self._log_event("pipeline_end", {
            "task_id": task_id,
            "final_status": final_status
        })
