from pydantic import BaseModel, Field

class BaseGenome(BaseModel):
    """Base class for all evolving genomes."""
    parent_id: int | None = Field(default=None, description="Lineage tracking: ID of the parent genome.")
    parent_fitness: float = Field(default=0.0, description="Fitness of the parent genome.")
    generation_id: int = Field(default=0, description="The generation in which this genome was created.")

class ReasoningGenes(BaseModel):
    planning_strategy: str = Field(default="direct", description="e.g., 'direct', 'step_by_step', 'tree_of_thought'")
    reasoning_depth: int = Field(default=3, ge=0, description="Number of explicit reasoning steps.")
    self_reflection_policy: str = Field(default="on_failure", description="e.g., 'none', 'on_failure', 'always'")

class CodingGenes(BaseModel):
    algorithm_selection_strategy: str = Field(default="optimize_first", description="e.g., 'brute_force_first', 'optimize_first'")
    implementation_strategy: str = Field(default="modular", description="e.g., 'modular', 'monolithic'")
    language_specific_policy: str = Field(default="standard", description="e.g., 'standard', 'idiomatic', 'secure'")

class VerificationGenes(BaseModel):
    test_generation_policy: str = Field(default="comprehensive", description="e.g., 'none', 'edge_cases_only', 'comprehensive'")
    verification_depth: int = Field(default=5, ge=0, description="Number of test cases to generate or depth of verification.")
    failure_diagnosis_strategy: str = Field(default="logical_trace", description="e.g., 'syntax_only', 'logical_trace'")

class LearningGenes(BaseModel):
    memory_retrieval_strategy: str = Field(default="recent_only", description="e.g., 'recent_only', 'similarity_search'")
    experience_prioritization: str = Field(default="balanced", description="e.g., 'successes', 'failures', 'balanced'")

class EvolutionGenes(BaseModel):
    experimentation_aggressiveness: float = Field(default=0.1, ge=0.0, le=1.0, description="Probability or degree of mutation during self-evolution.")
    evidence_threshold: int = Field(default=3, ge=1, description="Number of failures required to trigger evolution.")
    modification_scope_preference: str = Field(default="parameters_only", description="e.g., 'parameters_only', 'logic_rewrite'")

class AgentGenome(BaseGenome):
    """
    The new, multi-domain genome representing the agent's true evolvable intelligence.
    """
    agent_id: str | None = Field(default=None, description="Unique identifier for the agent lineage (e.g., 'EVO_PY').")
    version: str = Field(default="v1.0", description="Version identifier of the agent.")
    
    # The 5 Gene Groups
    reasoning: ReasoningGenes = Field(default_factory=ReasoningGenes)
    coding: CodingGenes = Field(default_factory=CodingGenes)
    verification: VerificationGenes = Field(default_factory=VerificationGenes)
    learning: LearningGenes = Field(default_factory=LearningGenes)
    evolution: EvolutionGenes = Field(default_factory=EvolutionGenes)
    
    # Retained fields from legacy GeneratorGenome that are still needed for EvoFlow integration temporarily,
    # or that can be migrated into memory properly later.
    system_instruction_variant: str = Field(default="standard", description="Variant of the system instruction: 'standard', 'expert_coder', 'pedantic_reviewer'.")
    temperature: float = Field(default=0.5, ge=0.0, le=1.0, description="LLM temperature setting.")
    past_code: str | None = Field(default=None, description="Previous code attempt (for reflection).")
    critic_feedback: str | None = Field(default=None, description="Critic's diagnosis of the previous attempt (for reflection).")
    crossover_instruction: str | None = Field(default=None, description="Instruction containing the successful logic from a winning agent in another language.")

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
