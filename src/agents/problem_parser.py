import json
import re
from src.client import EvoClient

class ProblemParserAgent:
    """
    Takes a natural language programming question and converts it into a
    structured JSON problem dictionary (including tests) required by the EvoFlow pipeline.
    """
    def __init__(self, client: EvoClient):
        self.client = client

    async def parse(self, user_query: str) -> dict:
        """
        Parses the user query into a problem dictionary.
        """
        system_prompt = (
            "You are an expert technical product manager and test engineer. "
            "Your job is to take a natural language programming question from a user and "
            "convert it into a strict JSON format required for an automated evaluation pipeline.\n\n"
            "You MUST return ONLY valid JSON. No markdown formatting, no explanations.\n\n"
            "The JSON MUST follow this exact schema:\n"
            "{\n"
            "  \"id\": 999,\n"
            "  \"category\": \"chatbot_query\",\n"
            "  \"title\": \"A short title for the problem\",\n"
            "  \"description\": \"A clear, complete description of the problem.\",\n"
            "  \"difficulty\": 5,\n"
            "  \"function_signature\": \"def function_name(arg_name: type) -> return_type:\",\n"
            "  \"tests\": [\n"
            "    {\n"
            "      \"id\": 0,\n"
            "      \"input\": \"function_name(arg1, arg2)\",\n"
            "      \"expected\": \"expected_output_value_as_string\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "CRITICAL RULES FOR TESTS:\n"
            "1. Generate at least 5 distinct test cases, including edge cases.\n"
            "2. The 'input' field MUST be a string representing the EXACT Python function call (e.g. \"my_func([1, 2], 'a')\").\n"
            "3. The 'expected' field MUST be a string representation of the expected Python output (e.g. \"True\", \"[1, 2, 3]\", \"'hello'\").\n"
            "4. Make sure the function name in 'input' matches the function name in 'function_signature'.\n"
        )

        user_prompt = f"Convert this query into the required problem JSON format:\n\n{user_query}"
        print(f"[ProblemParser] Sending request to LLM client to parse problem definition...")

        response = await self.client.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        
        print(f"[ProblemParser] Received response from LLM client.")
        content = response["content"]
        
        # Clean up in case the LLM wrapped it in markdown code blocks despite instructions
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        try:
            problem_dict = json.loads(content)
            # Ensure it has the correct structure
            if "id" not in problem_dict:
                problem_dict["id"] = 999
            if "tests" not in problem_dict:
                problem_dict["tests"] = []
                
            return problem_dict
        except json.JSONDecodeError as e:
            print(f"[ProblemParser] Failed to parse JSON: {e}")
            print(f"[ProblemParser] Raw content: {content}")
            raise ValueError("LLM failed to return a valid JSON problem definition.")
