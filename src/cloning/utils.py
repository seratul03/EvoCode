import hashlib
import json
from typing import Any

# ── Modification Value Inference ──────────────────────────────────────────────
_PLANNING_STRATEGIES = ["direct", "chain_of_thought", "test_first", "step_by_step"]
_SYSTEM_VARIANTS = ["standard", "expert_coder", "pedantic_reviewer"]

def sha256(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def compute_diff(parent: dict, candidate: dict) -> dict:
    """Return only the top-level (and nested) keys that changed."""
    diff = {}
    all_keys = set(parent.keys()) | set(candidate.keys())
    for k in all_keys:
        p_val = parent.get(k)
        c_val = candidate.get(k)
        if p_val != c_val:
            if isinstance(p_val, dict) and isinstance(c_val, dict):
                nested = compute_diff(p_val, c_val)
                if nested:
                    diff[k] = {"before": p_val, "after": c_val, "nested_diff": nested}
            else:
                diff[k] = {"before": p_val, "after": c_val}
    return diff

def apply_dotted_path(data: dict, dotted_key: str, value: Any) -> bool:
    """
    Apply a value at a dot-separated path in a nested dict.
    Returns True on success, False if the path doesn't exist.
    """
    parts = dotted_key.split(".")
    obj = data
    for part in parts[:-1]:
        if not isinstance(obj, dict) or part not in obj:
            return False
        obj = obj[part]
    if not isinstance(obj, dict) or parts[-1] not in obj:
        return False
    obj[parts[-1]] = value
    return True

def infer_modification_value(target_component: str, genome_snapshot: dict) -> Any:
    """
    Given a target_component path (e.g. 'reasoning.planning_strategy'),
    return a sensible mutated value based on the current value.
    Returns None if we don't know how to handle the component.
    """
    parts = target_component.split(".")
    obj = genome_snapshot
    try:
        for part in parts:
            obj = obj[part]
        current = obj
    except (KeyError, TypeError):
        return None

    leaf = parts[-1]

    if leaf == "planning_strategy":
        others = [s for s in _PLANNING_STRATEGIES if s != current]
        return others[0] if others else current

    if leaf == "system_instruction_variant":
        others = [s for s in _SYSTEM_VARIANTS if s != current]
        return others[0] if others else current

    if leaf == "temperature" and isinstance(current, float):
        return round(min(1.0, current + 0.15), 4)

    if leaf == "reasoning_depth" and isinstance(current, int):
        return min(10, current + 1)

    if leaf == "verification_depth" and isinstance(current, int):
        return min(10, current + 2)

    if leaf == "test_generation_policy":
        options = ["none", "edge_cases_only", "comprehensive"]
        others = [s for s in options if s != current]
        return others[-1] if others else current

    if leaf == "experimentation_aggressiveness" and isinstance(current, float):
        return round(min(1.0, current + 0.1), 4)

    return None
