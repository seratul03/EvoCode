"""
src/system_guard.py

Phase 13: Failure and Recovery Guards.
Protects the evolutionary pipeline from crashing by wrapping the cycle in a safe
execution block with automatic rollback.
"""

import os
import shutil
import time
import json
import traceback

class SystemGuard:
    """
    Wraps the EvoFlow orchestration to provide snapshot and rollback capabilities.
    """
    WORKSPACE_ROOT = "workspaces"
    SNAPSHOT_DIR = os.path.join(WORKSPACE_ROOT, "_snapshots")
    CRASH_LOG_DIR = os.path.join(WORKSPACE_ROOT, "_crashes")

    def __init__(self, population_manager):
        self.population = population_manager
        self.crash_counts = {}
        self.MAX_CRASHES = 3

    def _get_agent_workspace(self, agent_id: str) -> str:
        return os.path.join(self.WORKSPACE_ROOT, agent_id)

    def create_snapshot(self, agent_id: str) -> str:
        """
        Creates a rapid backup of the agent's workspace before evolution starts.
        """
        src = self._get_agent_workspace(agent_id)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Cannot snapshot non-existent agent {agent_id}")

        os.makedirs(self.SNAPSHOT_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        snapshot_path = os.path.join(self.SNAPSHOT_DIR, f"{agent_id}_{timestamp}")
        
        # Copy the whole workspace
        shutil.copytree(src, snapshot_path)
        return snapshot_path

    def rollback(self, agent_id: str, snapshot_path: str):
        """
        Restores the agent's workspace from the given snapshot.
        """
        target = self._get_agent_workspace(agent_id)
        
        # Remove corrupted workspace completely
        if os.path.exists(target):
            shutil.rmtree(target)
            
        # Restore from snapshot
        shutil.copytree(snapshot_path, target)

    def _record_crash(self, agent_id: str, exception: Exception):
        """Logs the crash and increments quarantine counter."""
        os.makedirs(self.CRASH_LOG_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        crash_file = os.path.join(self.CRASH_LOG_DIR, f"{agent_id}_{timestamp}.json")
        
        crash_data = {
            "agent_id": agent_id,
            "timestamp": timestamp,
            "error_type": type(exception).__name__,
            "error_message": str(exception),
            "traceback": traceback.format_exc()
        }
        
        with open(crash_file, "w", encoding="utf-8") as f:
            json.dump(crash_data, f, indent=2)
            
        self.crash_counts[agent_id] = self.crash_counts.get(agent_id, 0) + 1
        
        if self.crash_counts[agent_id] >= self.MAX_CRASHES:
            print(f"[SystemGuard] 🚨 Agent {agent_id} has crashed the system {self.MAX_CRASHES} times. QUARANTINING.")
            self.population.remove_agent(agent_id)

    async def execute_with_guards(self, evoflow, agent_id: str, *args, **kwargs):
        """
        Safely executes the evolution loop for a specific agent.
        """
        snapshot_path = None
        try:
            snapshot_path = self.create_snapshot(agent_id)
            print(f"[SystemGuard] Snapshot created at {snapshot_path}")
            
            # Execute the potentially dangerous evolution cycle
            await evoflow.trigger_evolution(agent_id, *args, **kwargs)
            
            # If successful, we can optionally clean up the snapshot to save space
            if os.path.exists(snapshot_path):
                shutil.rmtree(snapshot_path)
                
        except Exception as e:
            print(f"[SystemGuard] ⚠️ CATASTROPHIC FAILURE during evolution of {agent_id}: {e}")
            if snapshot_path and os.path.exists(snapshot_path):
                print(f"[SystemGuard] Rolling back {agent_id} to {snapshot_path}...")
                self.rollback(agent_id, snapshot_path)
                
            self._record_crash(agent_id, e)
