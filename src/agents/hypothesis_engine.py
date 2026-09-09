import json
from src.client import EvoClient
from src.genome import AgentGenome

class HypothesisEngine:
    """
    Formulates a scientific hypothesis for self-evolution based on the agent's failure mode.
    """
    def __init__(self, client: EvoClient):
        self.client = client

    async def generate_hypothesis(self, agent_id: str, trigger_reason: dict, current_genome: AgentGenome) -> dict:
        sys_prompt = (
            "You are the Evolutionary Hypothesis Engine.\n"
            "An AI agent has triggered a self-evolution protocol due to performance issues.\n"
            "Your task is to analyze its current genome parameters and the trigger reason, then formulate a structured hypothesis for an evolutionary change.\n"
            "You must respond ONLY with a valid JSON object. Do not include markdown code blocks or any other text.\n"
            "The JSON must have the exact following keys:\n"
            "- 'hypothesis': (string) A clear statement of what should change and why.\n"
            "- 'expected_improvement': (string) What metric or capability is expected to improve.\n"
            "- 'target_component': (string) The specific part of the genome or system to modify (e.g., 'temperature', 'reasoning.planning_strategy', 'system_instruction_variant')."
        )
        
        user_prompt = (
            f"Agent ID: {agent_id}\n"
            f"Trigger Reason:\n{json.dumps(trigger_reason, indent=2)}\n\n"
            f"Current Genome:\n{current_genome.model_dump_json(indent=2)}\n\n"
            "Generate the JSON hypothesis now."
        )
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        fallback = {
            "hypothesis": "Adjust temperature and planning strategy to escape local minima.",
            "expected_improvement": "general robustness across multiple tasks",
            "target_component": "reasoning.planning_strategy"
        }
        
        try:
            response = await self.client.create_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=300
            )
            content = response["choices"][0]["message"]["content"].strip()
            
            # Clean up potential markdown JSON wrapping
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            parsed = json.loads(content.strip())
            
            # Validate keys
            if "hypothesis" in parsed and "expected_improvement" in parsed and "target_component" in parsed:
                return parsed
            else:
                print(f"      [HypothesisEngine] LLM returned invalid keys. Using fallback.")
                return fallback
        except Exception as e:
            print(f"      [HypothesisEngine] Failed to generate hypothesis: {e}. Using fallback.")
            return fallback
