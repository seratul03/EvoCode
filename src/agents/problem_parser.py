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
            "  \"function_signature\": \"def function_name(arg1: type) -> return_type:\",\n"
            "  \"test_strategy\": {\n"
            "    \"input_types\": \"Analyze the exact input types required.\",\n"
            "    \"inferred_ranges\": \"Infer reasonable min/max ranges for normal usage.\",\n"
            "    \"planned_cases\": \"List the planned Edge, Normal, and Boundary cases.\"\n"
            "  },\n"
            "  \"tests\": [\n"
            "    {\n"
            "      \"id\": 0,\n"
            "      \"input\": \"function_name(value1)\",\n"
            "      \"expected\": \"expected_output_value_as_string\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "CRITICAL RULES FOR TESTS:\n"
            "1. You MUST first fill out the `test_strategy` block to explicitly detect input types, infer ranges, and plan cases.\n"
            "2. Using your strategy, generate 5 to 10 distinct test cases categorized as Edge cases (0, negative, empty), Normal cases, and Boundary cases.\n"
            "3. The 'input' field MUST be a function call string with the EXACT SAME NUMBER OF ARGUMENTS as 'function_signature'. "
            "For example, if function_signature is 'def solve(n: int) -> int:', then every test input MUST be 'solve(VALUE)' with exactly 1 argument.\n"
            "4. The 'expected' field MUST be a string representation of the expected Python RETURN value (e.g. \"True\", \"[1, 2, 3]\", \"'hello'\").\n"
            "5. Make sure the function name in 'input' matches the function name in 'function_signature'.\n"
            "6. IMPORTANT: The evaluation sandbox evaluates RETURN values, not standard output. If the user asks to 'print' something, you MUST rewrite the description to say 'return a string' or 'return a list' and generate test cases that expect that returned value.\n"
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
            if "id" not in problem_dict:
                problem_dict["id"] = 999
            if "tests" not in problem_dict:
                problem_dict["tests"] = []

            # --- Arity Guard ---
            # Determine the expected number of arguments from the function_signature.
            # This prevents the LLM from generating test inputs with the wrong arity.
            sig = problem_dict.get("function_signature", "")
            expected_arity = self._parse_arity(sig)
            print(f"[ProblemParser] Detected function arity: {expected_arity} arg(s) from signature: '{sig}'")

            fixed_tests = []
            for tc in problem_dict.get("tests", []):
                inp = str(tc.get("input", ""))
                try:
                    node = __import__('ast').parse(inp, mode='eval')
                    actual_arity = len(node.body.args)
                    if actual_arity != expected_arity:
                        # Trim excess args or this test is malformed — skip it
                        print(f"[ProblemParser] WARNING: Test id={tc.get('id')} has {actual_arity} arg(s), expected {expected_arity}. Discarding.")
                        continue
                except Exception:
                    pass  # If we can't parse the input, pass it through as-is
                fixed_tests.append(tc)

            if not fixed_tests:
                print(f"[ProblemParser] WARNING: All tests were discarded after arity check. Using original tests.")
                fixed_tests = problem_dict.get("tests", [])

            problem_dict["tests"] = fixed_tests
            print(f"[ProblemParser] Final test count after arity validation: {len(fixed_tests)}")
            return problem_dict
        except json.JSONDecodeError as e:
            print(f"[ProblemParser] Failed to parse JSON: {e}")
            print(f"[ProblemParser] Raw content: {content}")
            raise ValueError("LLM failed to return a valid JSON problem definition.")

    def _parse_arity(self, function_signature: str) -> int:
        """Extracts the number of parameters from a Python function signature string."""
        try:
            import ast
            # Handle both 'def foo(a, b):' and 'foo(a, b) -> int' formats
            sig = function_signature.strip()
            if not sig.startswith("def "):
                sig = "def " + sig
            if not sig.endswith(":"):
                # Strip return type annotation if present
                sig = sig.split("->")[0].strip() + ":"
            
            # ast.parse requires a complete function definition, including a body
            sig += "\n    pass"
            
            tree = ast.parse(sig)
            func_def = tree.body[0]
            # Count only positional args (args), not *args, **kwargs, or self
            params = [a for a in func_def.args.args if a.arg != 'self']
            return len(params)
        except Exception:
            return -1  # -1 means "unknown, don't enforce"

