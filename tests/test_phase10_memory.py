"""
tests/test_phase10_memory.py

Phase 10 spec tests:
  - Every evolution produces an immutable event JSON.
  - Parent-child links are correct in lineage.json.
"""

import json
import os
import shutil
import pytest
from src.memory_manager import EvolutionEvent, MemoryManager


class TestPhase10Memory:
    
    AGENT_ID = "TEST_MEM_AGENT"
    
    def setup_method(self):
        self.mem_dir = os.path.join("workspaces", self.AGENT_ID, "memory")
        if os.path.exists(self.mem_dir):
            shutil.rmtree(self.mem_dir)

    def teardown_method(self):
        if os.path.exists(self.mem_dir):
            shutil.rmtree(self.mem_dir)
            
    def test_record_event_writes_json(self):
        event = EvolutionEvent.create(
            agent_id=self.AGENT_ID,
            generation=1,
            trigger_data={"error": "oom"},
            hypothesis_data={"target": "memory"},
            parent_hash="hash_p",
            candidate_hash="hash_c",
            selection_decision="PROMOTE"
        )
        
        MemoryManager.record_event(event)
        
        event_path = os.path.join(self.mem_dir, "events", f"{event.event_id}.json")
        assert os.path.exists(event_path)
        
        with open(event_path) as f:
            data = json.load(f)
            
        assert data["event_id"] == event.event_id
        assert data["agent_id"] == self.AGENT_ID
        assert data["parent_hash"] == "hash_p"
        assert data["selection_decision"] == "PROMOTE"
        
    def test_lineage_tracks_history(self):
        # 1. First event: Rejected
        ev1 = EvolutionEvent.create(
            agent_id=self.AGENT_ID,
            generation=1,
            parent_hash="hash_v1",
            candidate_hash="hash_v2_bad",
            selection_decision="DISCARD"
        )
        MemoryManager.record_event(ev1)
        
        lineage = MemoryManager.get_lineage(self.AGENT_ID)
        assert lineage["root_hash"] == "hash_v1"
        assert lineage["current_hash"] == "hash_v1" # Did not advance
        assert len(lineage["history"]) == 1
        
        # 2. Second event: Promoted
        ev2 = EvolutionEvent.create(
            agent_id=self.AGENT_ID,
            generation=1,
            parent_hash="hash_v1",
            candidate_hash="hash_v2_good",
            selection_decision="PROMOTE"
        )
        MemoryManager.record_event(ev2)
        
        lineage = MemoryManager.get_lineage(self.AGENT_ID)
        assert lineage["current_hash"] == "hash_v2_good" # Advanced
        assert len(lineage["history"]) == 2
        
        last_attempt = lineage["history"][-1]
        assert last_attempt["parent_hash"] == "hash_v1"
        assert last_attempt["candidate_hash"] == "hash_v2_good"
        assert last_attempt["decision"] == "PROMOTE"
