from pydantic import BaseModel, Field

class Genome(BaseModel):
    """
    Represents the evolvable configuration genome of a single agent individual.
    These parameters will vary across individuals in a population and mutate
    over generations.
    """
    # Prompt template choices
    planner_prompt_variant: str = Field(
        default="plan_then_code",
        description="The variant of prompt template used by the PlannerCoderAgent (e.g., 'plan_then_code', 'search_then_edit')."
    )
    mutator_prompt_variant: str = Field(
        default="standard",
        description="The variant of prompt template used by the MutatorAgent (e.g., 'standard')."
    )
    
    # Model parameters
    planner_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="LLM temperature setting for the PlannerCoderAgent (usually low for code generation)."
    )
    mutator_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="LLM temperature setting for the MutatorAgent (higher values introduce variation/creativity)."
    )
    
    # Orchestration / behavior flags
    debate_enabled: bool = Field(
        default=False,
        description="Flag indicating whether to run a peer-review round (Critic reviews patch before finalization)."
    )
    use_memory_retrieval: bool = Field(
        default=False,
        description="Flag indicating whether the agent should consult the SQLite SQLite memory store for previous fixes."
    )
