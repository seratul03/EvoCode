"""
src/population.py

Phase 11: Reproduction and Population Evolution.

Manages the active population of agents, ensuring diversity and enforcing size limits.
"""

import json
import os
import shutil

class PopulationManager:
    """
    Oversees all active agents.
    """
    WORKSPACE_ROOT = "workspaces"
    POPULATION_FILE = os.path.join(WORKSPACE_ROOT, "population.json")

    def __init__(self, max_population: int = 5):
        self.max_population = max_population
        self.active_agents = self._load_population()

    def _load_population(self) -> dict[str, str]:
        """Returns mapping of agent_id -> genome_hash"""
        if not os.path.exists(self.POPULATION_FILE):
            # Seed the initial population with the default agent if it exists
            default_agent = "EVO_PY"
            default_genome = os.path.join(self.WORKSPACE_ROOT, default_agent, "genome.json")
            if os.path.exists(default_genome):
                from src.clone_manager import _sha256
                with open(default_genome, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {default_agent: _sha256(data)}
            return {}
            
        try:
            with open(self.POPULATION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def _save_population(self):
        os.makedirs(self.WORKSPACE_ROOT, exist_ok=True)
        with open(self.POPULATION_FILE, "w", encoding="utf-8") as f:
            json.dump(self.active_agents, f, indent=2)

    def register_agent(self, agent_id: str, genome_hash: str):
        """Adds a new agent to the active population."""
        self.active_agents[agent_id] = genome_hash
        self._save_population()

    def remove_agent(self, agent_id: str):
        """Removes an agent from active duty (archives workspace)."""
        if agent_id in self.active_agents:
            del self.active_agents[agent_id]
            self._save_population()
            
            # Move to archive to preserve memory/history
            src_dir = os.path.join(self.WORKSPACE_ROOT, agent_id)
            archive_dir = os.path.join(self.WORKSPACE_ROOT, "_archive", agent_id)
            if os.path.exists(src_dir):
                os.makedirs(os.path.dirname(archive_dir), exist_ok=True)
                shutil.move(src_dir, archive_dir)

    def is_duplicate(self, candidate_hash: str) -> bool:
        """Checks if this exact genome already exists in the active population."""
        return candidate_hash in self.active_agents.values()

    def enforce_population_limit(self, fitness_scores: dict[str, float]):
        """
        If active agents > max_population, cull the weakest agent(s).
        fitness_scores: mapping of agent_id -> rolling_average_score
        """
        while len(self.active_agents) > self.max_population:
            # Find the weakest agent that is currently in the active population
            weakest_agent = None
            lowest_score = float('inf')
            
            for agent_id in self.active_agents:
                score = fitness_scores.get(agent_id, 0.0) # Assume 0.0 if not scored yet
                if score < lowest_score:
                    lowest_score = score
                    weakest_agent = agent_id
                    
            if weakest_agent:
                self.remove_agent(weakest_agent)
            else:
                # Fallback if somehow no agents were found
                break
