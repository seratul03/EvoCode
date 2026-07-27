import asyncio
import os
import sys

# Resolve project root and insert into sys.path to enable relative imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from evoflow.client import EvoClient
from evoflow.genome import Genome
from agents.role_agents import (
    AnalyzerAgent,
    PlannerCoderAgent,
    CriticAgent,
    MutatorAgent,
    JudgeAgent
)

async def run_pipeline_demo():
    print("=" * 60)
    print("EVOCODE DAYS 3-4 AGENT PIPELINE DEMO")
    print("=" * 60)
    
    # Initialize client
    client = EvoClient()
    
    has_groq = client._is_key_valid(client.groq_key)
    has_or = client._is_key_valid(client.openrouter_key)
    
    # If no keys configured, we will mock the LLM responses to simulate pipeline progress
    if not (has_groq or has_or):
        print("\n[NOTE] No real API keys found. Running in SIMULATED mode.")
        print("To run for real, update the keys in your '.env' file.")
        
        from unittest.mock import AsyncMock, MagicMock
        client.groq_client = AsyncMock()
        
        # We will mock create_completion directly on EvoClient for simplicity
        async def mock_create_completion(messages, temperature=0.0, **kwargs):
            system_prompt = messages[0]["content"]
            user_prompt = messages[1]["content"]
            
            # Simple content based routing to simulate agent-specific outputs
            if "diagnosis" in system_prompt or "analyzer" in user_prompt:
                content = "<analysis>\n- Suspect File: src/utils.py\n- Cause: list indexing without size assertion\n- Fix: wrap with bounds checks\n</analysis>"
            elif "synthesis" in system_prompt or "plan" in user_prompt:
                content = "<patch>\n<<<<<<< SEARCH\ndef get_element(arr, idx):\n    return arr[idx]\n=======\ndef get_element(arr, idx):\n    if idx >= len(arr):\n        return None\n    return arr[idx]\n>>>>>>> REPLACE\n</patch>"
            elif "reviewer" in system_prompt or "critic" in user_prompt:
                content = "<critique>\n- Line 3: Need to also handle negative index checks (idx < 0).\n</critique>"
            elif "revision" in system_prompt or "mutator" in user_prompt:
                content = "<patch>\n<<<<<<< SEARCH\ndef get_element(arr, idx):\n    return arr[idx]\n=======\ndef get_element(arr, idx):\n    if idx >= len(arr) or idx < -len(arr):\n        return None\n    return arr[idx]\n>>>>>>> REPLACE\n</patch>"
            elif "judge" in system_prompt:
                content = "Reasoning: Correct bounds validation for positive and negative values. Tests pass.\n<score>9</score>"
            else:
                content = "Default mock reply"
                
            # Log metrics in budget tracker
            client.budget_tracker.record_call(
                provider="openrouter",
                model="meta-llama/llama-3-70b-instruct:free",
                input_tokens=250,
                output_tokens=120
            )
            
            return {
                "provider": "openrouter",
                "model": "meta-llama/llama-3-70b-instruct:free",
                "content": content,
                "input_tokens": 250,
                "output_tokens": 120
            }
            
        client.create_completion = mock_create_completion

    # Setup agents
    analyzer = AnalyzerAgent(client)
    planner = PlannerCoderAgent(client)
    critic = CriticAgent(client)
    mutator = MutatorAgent(client)
    judge = JudgeAgent(client)
    
    # Define Genome configuration
    genome = Genome(
        planner_prompt_variant="plan_then_code",
        planner_temperature=0.0,
        mutator_prompt_variant="mutator",
        mutator_temperature=0.2
    )
    
    print("\n--- Starting Pipeline ---")
    issue_title = "IndexError when querying elements out of range"
    issue_body = "Calling get_element([1, 2], 5) crashes the process instead of returning None."
    repo_context = "src/utils.py: contains def get_element(arr, idx): return arr[idx]"
    
    # 1. Analysis
    print("\n1. Running AnalyzerAgent...")
    analysis_res = await analyzer.run(issue_title, issue_body, repo_context)
    print(f"Parsed Analysis:\n{analysis_res['analysis']}")
    
    # 2. Plan & Code Generation
    print("\n2. Running PlannerCoderAgent...")
    plan_res = await planner.run(issue_title, issue_body, analysis_res["analysis"], genome)
    print(f"Parsed Patch Proposal:\n{plan_res['patch']}")
    
    # 3. Critique
    print("\n3. Running CriticAgent...")
    critic_res = await critic.run(issue_body, plan_res["patch"])
    print(f"Parsed Critique:\n{critic_res['critique']}")
    
    # 4. Mutation / Correction
    print("\n4. Running MutatorAgent...")
    mutate_res = await mutator.run(plan_res["patch"], critic_res["critique"], genome)
    print(f"Parsed Mutated Patch:\n{mutate_res['patch']}")
    
    # 5. Judging
    print("\n5. Running JudgeAgent...")
    # Simulate test execution output (e.g., tests passed)
    simulated_test_output = "test_get_element_valid: PASSED\ntest_get_element_overflow: PASSED\ntest_get_element_negative: PASSED"
    judge_res = await judge.run(mutate_res["patch"], simulated_test_output)
    print(f"Evaluated Quality Score: {judge_res['score']} / 10")
    
    print("\n" + "=" * 60)
    print("BUDGET & USAGE SUMMARY")
    print("=" * 60)
    summary = client.budget_tracker.get_summary()
    print(f"Total Calls Made: {summary['total_calls']} / {summary['max_calls']}")
    print(f"Total Input Tokens: {summary['total_input_tokens']}")
    print(f"Total Output Tokens: {summary['total_output_tokens']}")
    print(f"Total Cost: ${summary['total_cost']:.6f}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_pipeline_demo())
