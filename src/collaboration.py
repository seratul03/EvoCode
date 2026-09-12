import json
from src.client import EvoClient
from src.memory_manager import MemoryManager

class CollaborationManager:
    """
    Phase 15: Manages knowledge crossover between different agent lineages.
    """
    def __init__(self, client: EvoClient):
        self.client = client

    async def get_crossover_advice(self, target_agent_id: str, trigger_reason: dict) -> str | None:
        """
        Searches other agents' histories for successful evolutions addressing the same category.
        If found, synthesizes a conceptual crossover strategy using the LLM.
        """
        category = trigger_reason.get("category", "general")
        
        # 1. Fetch successful events from OTHER agents in the same category
        successes = MemoryManager.get_successful_events(category_filter=category, exclude_agent=target_agent_id)
        
        if not successes:
            print(f"      [Collaboration] No relevant crossover knowledge found for category '{category}'.")
            return None
            
        # 2. Pick the most relevant/recent success (for simplicity, we take the most recent one)
        # Assuming timestamps are sortable ISO strings
        best_event = sorted(successes, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
        donor_agent = best_event.get("agent_id", "UNKNOWN")
        
        print(f"      [Collaboration] Found successful strategy from {donor_agent}. Synthesizing crossover...")
        
        # 3. Synthesize the strategy
        sys_prompt = (
            "You are the Collaboration Strategy Synthesizer.\n"
            "An agent has successfully evolved to solve a problem category.\n"
            "Your task is to extract the underlying ALGORITHMIC and CONCEPTUAL strategy from its hypothesis.\n"
            "Do NOT include any language-specific syntax (e.g. do not mention Python dicts or C++ vectors).\n"
            "Provide ONLY a concise, 1-2 sentence instruction that another agent can use as a 'crossover_instruction'."
        )
        
        user_prompt = (
            f"Donor Agent: {donor_agent}\n"
            f"Problem Category: {category}\n"
            f"Donor Hypothesis: {json.dumps(best_event.get('hypothesis_data', {}), indent=2)}\n\n"
            "Extract the conceptual strategy instruction now."
        )
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        fallback = "Consider adjusting structural decomposition and verification thoroughness."
        
        try:
            response = await self.client.create_completion(
                messages=messages,
                temperature=0.2,
                max_tokens=150
            )
            content = response["choices"][0]["message"]["content"].strip()
            return content
        except Exception as e:
            print(f"      [Collaboration] Synthesis failed: {e}. Returning fallback.")
            return fallback
