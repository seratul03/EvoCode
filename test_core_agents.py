import asyncio
import sys

sys.path.insert(0, '.')
from src.client import EvoClient
from src.genome import GeneratorGenome
from src.agents.generator import GeneratorAgent
from src.agents.code_validator import CodeValidatorAgent

async def test_generator_and_validator():
    print("Initializing EvoClient...")
    client = EvoClient()
    
    gen_agent = GeneratorAgent(client)
    val_agent = CodeValidatorAgent(client)
    
    dummy_problem = {
        "id": 0,
        "title": "Add Two Numbers",
        "description": "Write a python function `def add(a, b):` that returns the sum of two integers.",
        "tests": []
    }
    
    genome = GeneratorGenome(
        system_instruction_variant="expert_coder",
        prompt_style="direct",
        temperature=0.0
    )
    
    print("\n--- Testing GeneratorAgent ---")
    try:
        code = await gen_agent.solve(dummy_problem, genome)
        print("Generated Code:")
        print(code)
        if "def add" in code:
            print("=> GeneratorAgent PASS")
        else:
            print("=> GeneratorAgent FAIL (could not find `def add`)")
    except Exception as e:
        print(f"=> GeneratorAgent ERROR: {e}")
        return
        
    print("\n--- Testing CodeValidatorAgent ---")
    dummy_test_results = {
        "passed_tests": 1,
        "total_tests": 1,
        "failed_test_ids": [],
        "crash_tests": 0,
        "timeout_tests": 0
    }
    
    try:
        verdict = await val_agent.validate(code, dummy_problem, dummy_test_results)
        print("Validator Verdict:", str(verdict).encode("ascii", "replace").decode("ascii"))
        if "is_correct" in verdict and "confidence" in verdict:
            print("=> CodeValidatorAgent PASS")
        else:
            print("=> CodeValidatorAgent FAIL (missing expected keys)")
    except Exception as e:
        print(f"=> CodeValidatorAgent ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_generator_and_validator())
