import pytest
from src.evolution_trigger import TriggerMonitor

def test_isolated_failure_does_not_trigger():
    monitor = TriggerMonitor(stagnation_window=5, weakness_window=3, threshold=0.45)
    
    monitor.add_result("EVO_PY", "algorithmic", 1.0, True)
    monitor.add_result("EVO_PY", "algorithmic", 1.0, True)
    monitor.add_result("EVO_PY", "algorithmic", 0.0, False)
    
    should_trigger, reason = monitor.evaluate("EVO_PY")
    assert not should_trigger
    assert reason["score"] < 0.45

def test_repeated_failure_triggers_evolution():
    monitor = TriggerMonitor(stagnation_window=5, weakness_window=3, threshold=0.45)
    
    monitor.add_result("EVO_PY", "recursion", 0.0, False)
    monitor.add_result("EVO_PY", "recursion", 0.0, False)
    monitor.add_result("EVO_PY", "recursion", 0.0, False)
    
    should_trigger, reason = monitor.evaluate("EVO_PY")
    assert should_trigger
    assert reason["target_weakness"] == "recursion"
    assert "Improve recursion" in reason["objective"]

def test_stagnation_triggers_evolution():
    monitor = TriggerMonitor(stagnation_window=3, weakness_window=5, threshold=0.45)
    
    monitor.add_result("EVO_PY", "general", 0.8, True)
    monitor.add_result("EVO_PY", "general", 0.9, True)
    monitor.add_result("EVO_PY", "general", 0.8, True)
    
    monitor.add_result("EVO_PY", "general", 0.7, True)
    monitor.add_result("EVO_PY", "general", 0.8, True)
    monitor.add_result("EVO_PY", "general", 0.9, True)
    
    should_trigger, reason = monitor.evaluate("EVO_PY")
    assert should_trigger
    assert reason["stagnation_score"] == 1.0

def test_trigger_is_deterministic():
    monitor1 = TriggerMonitor()
    monitor2 = TriggerMonitor()
    
    for m in (monitor1, monitor2):
        m.add_result("A", "cat1", 0.5, False)
        m.add_result("A", "cat1", 0.5, False)
        m.add_result("A", "cat1", 0.5, False)
        m.add_result("A", "cat2", 1.0, True)
        
    t1, r1 = monitor1.evaluate("A")
    t2, r2 = monitor2.evaluate("A")
    
    assert t1 == t2
    assert r1 == r2
