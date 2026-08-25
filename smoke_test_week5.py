import asyncio
import json
import sys

sys.path.insert(0, '.')
from src.client import EvoClient
from src.sandbox import Sandbox
from src.fitness_scorer import FitnessScorer

from src.agents.generator import GeneratorAgent
from src.agents.code_validator import CodeValidatorAgent
from src.agents.critic import CriticAgent
from src.agents.mutator import MutatorAgent

from src.genome import GeneratorGenome, CriticGenome, MutatorGenome, EvaluatorGenome

async def run_smoke_test():
    print("Initializing EvoFlow Components...")
    client = EvoClient()
    sandbox = Sandbox(timeout_seconds=5)
    fitness_scorer = FitnessScorer()
    
    generator = GeneratorAgent(client)
    validator = CodeValidatorAgent(client)
    critic = CriticAgent()
    mutator = MutatorAgent()
    
    gen_genome = GeneratorGenome()
    crit_genome = CriticGenome()
    mut_genome = MutatorGenome()
    eval_genome = EvaluatorGenome()

    print("Loading first 5 problems from train_problems.json...")
    with open('data/train_problems.json') as f:
        problems = json.load(f)[:5]

    for i, problem in enumerate(problems):
        print(f"\n==========================================")
        print(f"Problem {i+1}/5: {problem['title']}")
        print(f"==========================================")
        
        # 1. Generate
        print("1. Generating code...")
        code = await generator.solve(problem, gen_genome)
        print(f"   Code length: {len(code)} characters")
        
        # 2. Sandbox
        print("2. Running in sandbox...")
        tests = problem.get("tests", [])
        test_results = sandbox.run(code, tests)
        print(f"   Tests: {test_results['passed_tests']}/{test_results['total_tests']} passed")
        if len(test_results['crash_tests']) > 0:
            print(f"   Crashes: {len(test_results['crash_tests'])}")
            
        # 3. Validate
        print("3. Validating code...")
        validation = await validator.validate(code, problem, test_results)
        print(f"   Validator says correct? {validation.get('is_correct')}, confidence: {validation.get('confidence')}")
        
        # 4. Evaluate & 5. Aggregate
        print("4. Calculating fitness...")
        fitness = fitness_scorer.calculate_fitness(code, test_results, eval_genome)
        print(f"   Fitness score: {fitness['fitness_value']:.2f}")
        
        # 6. Critique
        print("5. Critiquing...")
        diagnosis = critic.critique(code, test_results, validation, crit_genome)
        print(f"   Failure type: {diagnosis['failure_type']}, Severity: {diagnosis['severity']:.2f}")
        print(f"   Recommended mutations: {diagnosis['recommended_mutations']}")
        
        # 7. Mutate
        print("6. Mutating genome...")
        new_gen_genome = mutator.propose(diagnosis, gen_genome, mut_genome)
        
        changes = []
        if new_gen_genome.temperature != gen_genome.temperature:
            changes.append(f"Temp {gen_genome.temperature:.2f}->{new_gen_genome.temperature:.2f}")
        if new_gen_genome.system_instruction_variant != gen_genome.system_instruction_variant:
            changes.append(f"Variant {gen_genome.system_instruction_variant}->{new_gen_genome.system_instruction_variant}")
        if new_gen_genome.prompt_style != gen_genome.prompt_style:
            changes.append(f"Style {gen_genome.prompt_style}->{new_gen_genome.prompt_style}")
            
        if changes:
            print(f"   Mutations applied: {', '.join(changes)}")
        else:
            print("   No mutations applied.")
            
    print("\n--- Smoke Test Complete ---")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
