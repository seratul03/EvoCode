"""
src/memory_manager.py

Phase 10: Versioning, Lineage, and Memory.

Records every evolutionary event (successful or failed) and maintains the agent's lineage graph.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class EvolutionEvent:
    """Immutable record of a single evolutionary cycle."""
    event_id: str
    timestamp: str
    agent_id: str
    generation: int
    trigger_data: dict
    hypothesis_data: dict
    parent_hash: str
    candidate_hash: str
    diff: dict
    verification_result: dict
    arena_result: dict
    selection_decision: str
    selection_reason: str

    @classmethod
    def create(cls, agent_id: str, generation: int, **kwargs) -> "EvolutionEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            agent_id=agent_id,
            generation=generation,
            trigger_data=kwargs.get("trigger_data", {}),
            hypothesis_data=kwargs.get("hypothesis_data", {}),
            parent_hash=kwargs.get("parent_hash", ""),
            candidate_hash=kwargs.get("candidate_hash", ""),
            diff=kwargs.get("diff", {}),
            verification_result=kwargs.get("verification_result", {}),
            arena_result=kwargs.get("arena_result", {}),
            selection_decision=kwargs.get("selection_decision", "unknown"),
            selection_reason=kwargs.get("selection_reason", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


class MemoryManager:
    """
    Manages immutable raw event memory and the lineage graph.
    """
    WORKSPACE_ROOT = "workspaces"

    @classmethod
    def _memory_dir(cls, agent_id: str) -> str:
        return os.path.join(cls.WORKSPACE_ROOT, agent_id, "memory")
        
    @classmethod
    def _events_dir(cls, agent_id: str) -> str:
        return os.path.join(cls._memory_dir(agent_id), "events")
        
    @classmethod
    def _lineage_path(cls, agent_id: str) -> str:
        return os.path.join(cls._memory_dir(agent_id), "lineage.json")

    @classmethod
    def record_event(cls, event: EvolutionEvent):
        """
        Record the evolution event in immutable storage and update lineage.
        """
        # 1. Write immutable event JSON
        events_dir = cls._events_dir(event.agent_id)
        os.makedirs(events_dir, exist_ok=True)
        
        event_path = os.path.join(events_dir, f"{event.event_id}.json")
        with open(event_path, "w", encoding="utf-8") as f:
            json.dump(event.to_dict(), f, indent=2)
            
        # 2. Update lineage graph
        cls._update_lineage(event)

    @classmethod
    def _update_lineage(cls, event: EvolutionEvent):
        lineage_path = cls._lineage_path(event.agent_id)
        os.makedirs(os.path.dirname(lineage_path), exist_ok=True)
        
        lineage = {}
        if os.path.exists(lineage_path):
            try:
                with open(lineage_path, "r", encoding="utf-8") as f:
                    lineage = json.load(f)
            except json.JSONDecodeError:
                pass
                
        # Ensure root hash exists if this is the first event
        if "root_hash" not in lineage:
            lineage["root_hash"] = event.parent_hash
            lineage["current_hash"] = event.parent_hash
            lineage["history"] = []
            
        # Record the attempt
        attempt = {
            "event_id": event.event_id,
            "parent_hash": event.parent_hash,
            "candidate_hash": event.candidate_hash,
            "decision": event.selection_decision,
            "timestamp": event.timestamp,
        }
        lineage["history"].append(attempt)
        
        # If promoted, update current head
        if event.selection_decision.lower() == "promote":
            lineage["current_hash"] = event.candidate_hash
            
        with open(lineage_path, "w", encoding="utf-8") as f:
            json.dump(lineage, f, indent=2)
            
    @classmethod
    def get_lineage(cls, agent_id: str) -> dict:
        """Read the current lineage graph."""
        lineage_path = cls._lineage_path(agent_id)
        if os.path.exists(lineage_path):
            with open(lineage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @classmethod
    def get_successful_events(cls, category_filter: str = None, exclude_agent: str = None) -> list[dict]:
        """
        Retrieves a list of successful (PROMOTE) evolution events across all agents.
        Optionally filters by problem category and excludes a specific agent lineage.
        """
        if not os.path.exists(cls.WORKSPACE_ROOT):
            return []
            
        successful_events = []
        
        for agent_dir in os.listdir(cls.WORKSPACE_ROOT):
            if agent_dir == exclude_agent or agent_dir.startswith("_"):
                continue
                
            events_dir = cls._events_dir(agent_dir)
            if not os.path.exists(events_dir):
                continue
                
            for filename in os.listdir(events_dir):
                if not filename.endswith(".json"):
                    continue
                    
                filepath = os.path.join(events_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        event = json.load(f)
                        
                    if event.get("selection_decision") == "PROMOTE":
                        # Check category if provided
                        trigger_data = event.get("trigger_data", {})
                        event_category = trigger_data.get("category", "general")
                        if category_filter and category_filter != event_category:
                            continue
                        successful_events.append(event)
                except Exception:
                    pass
                    
        return successful_events
