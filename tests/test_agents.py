import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from evoflow.client import EvoClient
from evoflow.genome import Genome
from agents.base_agent import BaseAgent
from agents.role_agents import (
    AnalyzerAgent,
    PlannerCoderAgent,
    CriticAgent,
    MutatorAgent,
    JudgeAgent
)

def test_xml_tag_extraction():
    # Instantiate BaseAgent with mock client to test tag extraction
    mock_client = MagicMock()
    agent = BaseAgent(client=mock_client)
    
    # 1. Standard multiline extraction
    text = "Some text <analysis>File: main.py\nBug: IndexError</analysis> trailing text"
    assert agent.extract_tag(text, "analysis") == "File: main.py\nBug: IndexError"
    
    # 2. Case insensitivity matching
    text_case = "Some text <ANALYSIS>File: main.py</analysis> trailing text"
    assert agent.extract_tag(text_case, "analysis") == "File: main.py"
    
    # 3. Missing tags output empty string
    assert agent.extract_tag("No tags here", "analysis") == ""
    
    # 4. Search and Replace symbols inside blocks
    text_nested = "hello <patch><<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE</patch>"
    assert agent.extract_tag(text_nested, "patch") == "<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE"

def test_template_rendering():
    mock_client = MagicMock()
    agent = BaseAgent(client=mock_client)
    
    rendered = agent.render_template(
        "analyzer.jinja2",
        issue_title="List index out of range",
        issue_body="Occurs on list slice",
        repo_context="main.py"
    )
    assert "List index out of range" in rendered
    assert "Occurs on list slice" in rendered
    assert "main.py" in rendered

@pytest.mark.asyncio
async def test_planner_agent_genome_binding():
    mock_client = MagicMock()
    mock_client.create_completion = AsyncMock(return_value={
        "content": "<patch>modified code</patch>",
        "provider": "groq",
        "model": "llama3-70b-8192"
    })
    
    agent = PlannerCoderAgent(client=mock_client)
    # Configure genome with non-default variant and temperature
    genome = Genome(
        planner_prompt_variant="search_then_edit",
        planner_temperature=0.85
    )
    
    res = await agent.run(
        issue_title="IndexError",
        issue_body="slice error",
        repo_context="main.py",
        analysis="Validate slice ranges",
        genome=genome
    )
    
    assert res["patch"] == "modified code"
    
    # Check that temperature parameters were correctly parsed and bound to EvoClient
    mock_client.create_completion.assert_called_once()
    called_kwargs = mock_client.create_completion.call_args[1]
    assert called_kwargs["temperature"] == 0.85
