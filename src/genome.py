from pydantic import BaseModel, Field

class BaseGenome(BaseModel):
    """Base class for all evolving genomes."""
    parent_id: int | None = Field(default=None, description="Lineage tracking: ID of the parent genome.")
    generation_id: int = Field(default=0, description="The generation in which this genome was created.")

class GeneratorGenome(BaseGenome):
    """
    Genome for the LLM-based Generator agent.
    Mutates to find the optimal code generation strategy.
    """
    prompt_style: str = Field(
        default="direct",
        description="The style of the prompt: 'direct', 'chain_of_thought', 'test_first', 'step_by_step'."
    )
    temperature: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="LLM temperature setting."
    )
    reasoning_steps: int = Field(
        default=3,
        ge=0,
        description="Number of explicit reasoning steps to require before coding."
    )
    system_instruction_variant: str = Field(
        default="standard",
        description="Variant of the system instruction: 'standard', 'expert_coder', 'pedantic_reviewer'."
    )
    past_code: str | None = Field(
        default=None,
        description="Previous code attempt (for reflection)."
    )
    critic_feedback: str | None = Field(
        default=None,
        description="Critic's diagnosis of the previous attempt (for reflection)."
    )
    crossover_instruction: str | None = Field(
        default=None,
        description="Instruction containing the successful logic from a winning agent in another language."
    )

class CriticGenome(BaseGenome):
    """
    Genome for the rule-based Critic agent.
    Adapts based on how well its outputs correlate with real outcomes.
    """
    strictness_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Threshold above which to flag an issue as high severity."
    )
    heuristic_weights: dict[str, float] = Field(
        default_factory=lambda: {"complexity": 1.0, "nesting": 1.0, "edge_cases": 1.0},
        description="Weights applied to various static analysis heuristics."
    )

class MutatorGenome(BaseGenome):
    """
    Genome for the rule-based Mutator agent.
    Mutates to decide how genomes should change in response to diagnoses.
    """
    mutation_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Base probability of applying a random mutation vs a targeted one."
    )
    strategy_preference: str = Field(
        default="balanced",
        description="Mutation strategy: 'aggressive', 'conservative', 'balanced'."
    )

class EvaluatorGenome(BaseGenome):
    """
    Genome for the rule-based Evaluators.
    Adapts to maximize correlation with overall observed code fitness.
    """
    sensitivity: float = Field(
        default=1.0,
        ge=0.1,
        description="Sensitivity multiplier for the specific evaluation metric."
    )
    penalty_curve: str = Field(
        default="linear",
        description="Shape of the penalty curve: 'linear', 'exponential', 'step'."
    )
