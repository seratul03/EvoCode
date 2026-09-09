import pytest
from src.evolution_trigger import TriggerMonitor

def test_isolated_failure_does_not_trigger():
    monitor = TriggerMonitor(stagnation_window=5, weakness_window=3, threshold=0.45)
    
    # 2 passes, 1 failure in a category
    monitor.add_result("EVO_PY", "algorithmic", 1.0, True)
    monitor.add_result("EVO_PY", "algorithmic", 1.0, True)
    monitor.add_result("EVO_PY", "algorithmic", 0.0, False)
    
    should_trigger, reason = monitor.evaluate("EVO_PY")
    assert not should_trigger
    # fail rate = 1/3 = 0.33, weakness score = 0.33, E = 0.5 * 0.33 = 0.165
    assert reason["score"] < 0.45

def test_repeated_failure_triggers_evolution():
    monitor = TriggerMonitor(stagnation_window=5, weakness_window=3, threshold=0.45)
    
    # 3 failures in a category
    monitor.add_result("EVO_PY", "recursion", 0.0, False)
    monitor.add_result("EVO_PY", "recursion", 0.0, False)
    monitor.add_result("EVO_PY", "recursion", 0.0, False)
    
    should_trigger, reason = monitor.evaluate("EVO_PY")
    assert should_trigger
    assert reason["target_weakness"] == "recursion"
    assert "Improve recursion" in reason["objective"]
    # fail rate = 1.0, E = 0.5 * 1.0 = 0.5 >= 0.45

def test_stagnation_triggers_evolution():
    monitor = TriggerMonitor(stagnation_window=3, weakness_window=5, threshold=0.45)
    
    # First 3 items (previous baseline)
    monitor.add_result("EVO_PY", "general", 0.8, True)
    monitor.add_result("EVO_PY", "general", 0.9, True)
    monitor.add_result("EVO_PY", "general", 0.8, True)
    
    # Next 3 items (recent window, plateaued)
    monitor.add_result("EVO_PY", "general", 0.7, True)
    monitor.add_result("EVO_PY", "general", 0.8, True)
    monitor.add_result("EVO_PY", "general", 0.9, True) # Max is 0.9, which <= previous max 0.9
    
    should_trigger, reason = monitor.evaluate("EVO_PY")
    assert should_trigger
    assert reason["stagnation_score"] == 1.0
    # E = 0.5 * 1.0 = 0.5 >= 0.45

def test_trigger_is_deterministic():
    # Identical history must produce identical output
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
