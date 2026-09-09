import collections

class TriggerMonitor:
    def __init__(self, stagnation_window=5, weakness_window=3, threshold=0.45):
        # agent_id -> list of overall scores (fitness or task pass rate)
        self.history = collections.defaultdict(list)
        # agent_id -> category -> list of booleans (passed=True, failed=False)
        self.category_history = collections.defaultdict(lambda: collections.defaultdict(list))
        
        self.stagnation_window = stagnation_window
        self.weakness_window = weakness_window
        self.threshold = threshold
        
        # Weights
        self.w_stagnation = 0.5
        self.w_weakness = 0.5
        self.w_competitive = 0.0

    def add_result(self, agent_id: str, category: str, score: float, passed: bool):
        self.history[agent_id].append(score)
        self.category_history[agent_id][category].append(passed)

    def evaluate(self, agent_id: str) -> tuple[bool, dict]:
        """
        Returns (should_trigger, reason_dict)
        """
        stagnation = 0.0
        weakness = 0.0
        
        # Calculate Stagnation
        h = self.history[agent_id]
        if len(h) >= self.stagnation_window:
            recent = h[-self.stagnation_window:]
            previous = h[:-self.stagnation_window]
            
            if previous:
                prev_max = max(previous)
                recent_max = max(recent)
                # If we haven't beaten the previous max, and we aren't at perfect 1.0 score
                if recent_max <= prev_max and recent_max < 1.0:
                    stagnation = 1.0
                elif recent_max < 1.0:
                    stagnation = 0.2 # Some progress, but still not perfect
            else:
                # If we have exactly 'stagnation_window' items, and no previous baseline
                # Check if the recent window is completely flat and sub-optimal
                if max(recent) == min(recent) and max(recent) < 1.0:
                    stagnation = 1.0
        
        # Calculate Weakness
        worst_category = None
        highest_weakness_score = 0.0
        
        for cat, results in self.category_history[agent_id].items():
            if len(results) >= self.weakness_window:
                recent_cat = results[-self.weakness_window:]
                fail_rate = 1.0 - (sum(recent_cat) / len(recent_cat))
                if fail_rate > highest_weakness_score:
                    highest_weakness_score = fail_rate
                    worst_category = cat
                    
        weakness = highest_weakness_score
        
        E = (self.w_stagnation * stagnation) + (self.w_weakness * weakness)
        
        reason = {
            "score": E,
            "stagnation_score": stagnation,
            "weakness_score": weakness,
        }
        
        if E >= self.threshold:
            reason["target_weakness"] = worst_category if worst_category else "general stagnation"
            reason["objective"] = f"Improve {worst_category if worst_category else 'general'} performance without regressing."
            return True, reason
            
        return False, reason
