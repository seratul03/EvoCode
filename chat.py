import asyncio
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Ensure the src module can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.client import EvoClient
from src.agents.problem_parser import ProblemParserAgent
from src.evoflow import EvoFlowOrchestrator

import subprocess

async def run_chat():
    print("==================================================")
    print("           EvoCode Terminal Chat System           ")
    print("==================================================")
    
    # 1. Check if Docker is running
    print("[System]: Checking Docker status...")
    try:
        subprocess.run(["docker", "info"], capture_output=True, text=True, check=True)
        print("[System]: Docker is running.\n")
    except Exception:
        print("[Error]: Docker isn't running or isn't accessible.")
        print("[Error]: Please start Docker Desktop/Daemon to run the Sandbox safely.")
        return

    print("Type your programming question below. The evolutionary pipeline will")
    print("generate a problem definition, and run a 3-round competition among")
    print("the agents (Python, Java, C++) to find and evolve the best solution.")
    print("Type 'exit' or 'quit' to stop.\n")

    client = EvoClient()
    
    # 2. Enforce Ollama ONLY (Disable cloud APIs)
    client.groq_clients = []
    client.openrouter_client = None
    
    parser = ProblemParserAgent(client)

    while True:
        try:
            user_query = input("\n[You]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat. Goodbye!")
            break

        if not user_query:
            continue
            
        if user_query.lower() in ['exit', 'quit']:
            print("Exiting chat. Goodbye!")
            break

        print("\n[System]: Analyzing your question and generating problem specification...")
        
        try:
            problem = await parser.parse(user_query)
            print(f"[System]: Created Problem '{problem.get('title')}' with {len(problem.get('tests', []))} test cases.")
            print(f"[System]: Starting EvoFlow Pipeline (3 rounds, Population: 3)...\n")
            
            # Initialize orchestrator
            # Pop Size 3 to align with Python, Java, C++
            orchestrator = EvoFlowOrchestrator(pop_size=3)
            
            # Run the generations. 
            # Note: The logging in evoflow.py will print directly to the terminal, acting as our "live stream"
            await orchestrator.run_generations(num_generations=3, problems=[problem], mode="evolve", disable_circuit_breaker=True)
            
            print("\n==================================================")
            print("Pipeline Complete! The final code and run details ")
            print("have been saved to a JSON file in the ")
            print("'structured_reports/' directory.")
            print("==================================================\n")
            
        except Exception as e:
            print(f"\n[Error]: An error occurred during the pipeline execution: {e}")

if __name__ == "__main__":
    asyncio.run(run_chat())
