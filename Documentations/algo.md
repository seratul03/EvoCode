# AIECG: Adaptive Intelligent Evolutionary Code Generation

## Complete Algorithm Specification & Implementation Guide

**Version:** 1.0  
**Date:** September 2026  
**Project:** EvoCode Multi-Objective Extension  
**Status:** Final-Year Implementation (6 months)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Algorithm Overview](#algorithm-overview)
3. [Core Components](#core-components)
4. [System Architecture](#system-architecture)
5. [Data Models](#data-models)
6. [Implementation Details](#implementation-details)
7. [Integration Points](#integration-points)
8. [Configuration & Hyperparameters](#configuration--hyperparameters)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Evaluation & Metrics](#evaluation--metrics)
11. [Appendix: Code Templates](#appendix-code-templates)

---

## Executive Summary

**AIECG** is a novel evolutionary algorithm that combines 10 integrated components to adaptively evolve code genomes while learning from its own evolutionary process.

### Key Innovation
Unlike traditional genetic algorithms that use fixed hyperparameters, AIECG:
- **Adapts** its own parameters based on landscape detection
- **Learns** which mutations are effective
- **Remembers** past solutions via LLM-powered knowledge transfer
- **Specializes** mutations based on failure patterns
- **Rewards** behavioral diversity and novelty
- **Competes** multiple strategies to find the best one
- **Co-evolves** its own agents (Mutator, Critic, Validator)
- **Analyzes** the evolutionary landscape in real-time

### Research Contribution
This is a **meta-learning system** for evolutionary algorithms—not just a solution finder, but a system that learns *how to evolve better* over time.

### Target Scope
- **6-month implementation** (phased across 12 phases)
- **~2,000–3,000 lines of core code**
- **5–7 new Python modules**
- **Integration with existing EvoCode architecture**

---

## Algorithm Overview

### High-Level Flow

```
┌────────────────────────────────────────────────────────────────┐
│                    AIECG Generation Loop                       │
└────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
          [GENERATE]     [EVALUATE]    [SELECT]
                │             │             │
                ↓             ↓             ↓
     ┌─────────────────────────────────────────────────┐
     │ 1. Generate via Multiple Strategies (#10)       │
     │    - Aggressive (high mutation, low selection)  │
     │    - Conservative (low mutation, high selection)│
     │    - Balanced (adaptive)                        │
     └─────────────────────────────────────────────────┘
                              │
     ┌─────────────────────────────────────────────────┐
     │ 2. Mutate using:                                │
     │    - Failure-driven targeting (#6)              │
     │    - Learned mutation weights (#2)              │
     │    - RL-suggested actions (#3)                  │
     │    - Adaptive rates (#1)                        │
     │    - Co-evolved agent parameters (#4)           │
     └─────────────────────────────────────────────────┘
                              │
     ┌─────────────────────────────────────────────────┐
     │ 3. Evaluate Multi-Objective Fitness:            │
     │    - Correctness (minimize errors)              │
     │    - Runtime (minimize ms)                      │
     │    - Complexity (minimize LOC/AST nodes)        │
     │    - Novelty (maximize behavioral distance) (#8)│
     └─────────────────────────────────────────────────┘
                              │
     ┌─────────────────────────────────────────────────┐
     │ 4. Analyze Failures (#6):                       │
     │    - Classify: timeout / wrong output / crash   │
     │    - Track patterns                             │
     │    - Bias future mutations                      │
     └─────────────────────────────────────────────────┘
                              │
     ┌─────────────────────────────────────────────────┐
     │ 5. Compute Behavioral Signatures (#7):          │
     │    - Execution paths, output patterns, AST      │
     │    - Distance to population                     │
     └─────────────────────────────────────────────────┘
                              │
     ┌─────────────────────────────────────────────────┐
     │ 6. Detect Landscape Status (#9):                │
     │    - Stagnation? → Increase exploration         │
     │    - Convergence? → Inject diversity            │
     │    - Query LLM memory if stuck (#5)             │
     └─────────────────────────────────────────────────┘
                              │
     ┌─────────────────────────────────────────────────┐
     │ 7. RL Decision-Making (#3):                     │
     │    - State: fitness, diversity, convergence     │
     │    - Action: mutation rate, selection pressure  │
     │    - Reward: fitness improvement per step       │
     └─────────────────────────────────────────────────┘
                              │
     ┌─────────────────────────────────────────────────┐
     │ 8. Select Survivors via:                        │
     │    - Behavioral diversity clustering (#7)       │
     │    - Novelty scoring (#8)                       │
     │    - Multi-objective optimization               │
     └─────────────────────────────────────────────────┘
                              │
     ┌─────────────────────────────────────────────────┐
     │ 9. Evolve Agents (#4):                          │
     │    - Mutator, Critic, Validator params evolve   │
     │    - Based on population fitness                │
     └─────────────────────────────────────────────────┘
                              │
     ┌─────────────────────────────────────────────────┐
     │ 10. Store Memory (#5):                          │
     │     - Periodically save success/failure logs     │
     │     - Enable future problem transfer learning   │
     └─────────────────────────────────────────────────┘
                              │
                        Next Generation
```

---

## Core Components

### Component #1: Adaptive Evolution

**Purpose:** Monitor population fitness and diversity. Automatically adjust mutation rate and selection pressure.

**Mechanism:**
- Track fitness improvement over last N generations
- If improvement < threshold: **increase mutation** (explore more)
- If improvement > threshold: **decrease mutation** (exploit)
- Track diversity: if variance drops, increase mutation

**Key Equations:**
```
Convergence Score = (fitness[t] - fitness[t-5]) / 5
If Convergence Score < ε (e.g., 0.01):
    mutation_rate = min(0.8, mutation_rate × 1.1)
    selection_pressure = max(0.2, selection_pressure × 0.9)
Else:
    mutation_rate = max(0.2, mutation_rate × 0.95)
    selection_pressure = min(0.9, selection_pressure × 1.05)
```

**Implementation File:** `adaptive_evolution.py`

**Class:** `AdaptiveEvolution`

**Methods:**
- `update_parameters(population)` — Called every generation; adjusts rates
- `get_mutation_rate()` — Returns current mutation rate
- `get_selection_pressure()` — Returns current selection pressure
- `reset()` — Reset to initial state

---

### Component #2: Learning-to-Mutate

**Purpose:** Track which mutation types improve fitness. Bias mutation selection toward effective types.

**Mechanism:**
- Track effectiveness score for each mutation type
- Compute softmax of scores to get normalized probabilities
- Use weighted random sampling to choose mutations
- Update scores after each evaluation

**Key Equations:**
```
For each mutation_type:
    effectiveness[type] = [improvements from using this type]
    avg_effectiveness[type] = mean(effectiveness[type])

mutation_weights = softmax(avg_effectiveness)
selected_mutation = sample(MUTATION_TYPES, weights=mutation_weights)
```

**Implementation File:** `mutation_effectiveness.py`

**Class:** `MutationEffectivenessTracker`

**Methods:**
- `record_mutation(mutation_type, improvement)` — Store result of mutation
- `get_mutation_weights()` — Return normalized weights for sampling
- `get_top_mutations(k)` — Return top-K effective mutations
- `reset_scores(mutation_type)` — Reset history for a specific type

**Supported Mutation Types:**
```
- add_bounds_check
- simplify_logic
- add_early_exit
- reduce_nesting
- add_caching
- vectorize_operations
- refactor_complex_function
- add_comment_hint
- reduce_variable_scope
- optimize_data_structure
```

---

### Component #3: RL-Controlled Evolution

**Purpose:** Learn optimal hyperparameter values (mutation rate, selection pressure, test budget).

**Mechanism:**
- State: fitness, diversity, generations without improvement, current rates
- Actions: increase/decrease mutation, increase/decrease selection, run extra tests, no change
- Reward: fitness improvement per computational step
- Learning: Q-learning or simple policy gradient

**Key Equations:**
```
State = [avg_fitness, diversity, stagnation_counter, mutation_rate, selection_pressure]
Actions = {increase_mutation, decrease_mutation, increase_selection, 
           decrease_selection, run_extra_tests, no_change}

reward = (fitness[t] - fitness[t-1]) / computation_cost
Q-learning update:
Q(s,a) ← Q(s,a) + α[reward + γ max_a' Q(s',a') - Q(s,a)]
```

**Implementation File:** `rl_controller.py`

**Class:** `RLEvolutionaryController`

**Methods:**
- `get_next_action(state)` — RL model predicts best action
- `execute_action(action)` — Apply RL-recommended change
- `update_q_values(state, action, reward, next_state)` — Learn from experience
- `save_model(path)` — Persist trained model
- `load_model(path)` — Load trained model

**Model Type:** Lightweight Q-learning (not deep RL; ~10 state features, 6 actions)

---

### Component #4: Co-Evolution of Agents

**Purpose:** Agent hyperparameters (Mutator, Critic, Validator) evolve alongside code genomes.

**Mechanism:**
- Each agent has a genome of hyperparameters
- Agents reproduce based on how well their code population performs
- Agent genomes mutate (hyperparameters shift slightly)
- Selection pressure: agents producing better code fitness survive

**Agent Genome Structure:**
```json
{
  "mutation_rate": 0.5,          // Probability of applying mutation
  "mutation_diversity": 0.7,     // How extreme mutations are
  "selection_threshold": 0.75,   // Fitness threshold for survival
  "test_budget": 50,             // Num tests to run per evaluation
  "critic_weight": 0.6,          // How much to trust critic feedback
  "timeout_threshold_ms": 5000   // Max execution time
}
```

**Mutation Rule for Agents:**
- Float parameters: mutate with Gaussian noise N(0, 0.1)
- Integer parameters: mutate with Gaussian noise N(0, 5)
- Mutation probability: 0.3 per parameter per generation

**Implementation File:** `agent_population.py`

**Classes:**
- `EvolvableAgent` — Single agent with evolving genome
- `AgentPopulation` — Population of agents

**Methods:**
- `EvolvableAgent.mutate()` — Apply random perturbation to hyperparameters
- `EvolvableAgent.copy()` — Clone agent (for reproduction)
- `AgentPopulation.evolve(code_fitness_scores)` — Evolve agents based on performance
- `AgentPopulation.get_best_agent()` — Return highest-fitness agent

---

### Component #5: Evolutionary Memory (LLM-Powered)

**Purpose:** Store solutions from previous problems. Use LLM to query memory when stuck. Enable transfer learning.

**Mechanism:**
- After solving a problem, save success/failure patterns
- When stuck on a new problem, query LLM with context from memory
- LLM identifies similar past problems and suggests mutations
- Bias mutation pool toward LLM-suggested types

**Memory Entry Structure:**
```json
{
  "problem_id": "sorting_algorithm_v2",
  "language": "python",
  "timestamp": "2026-09-15T10:30:00Z",
  "successful_genomes": [
    {
      "id": 127,
      "prompt_config": {...},
      "fitness": 0.95,
      "behaviors": ["uses_merge_sort", "handles_edge_cases"]
    }
  ],
  "failure_log": [
    {
      "test_case": "large_input",
      "error_type": "timeout",
      "frequency": 15,
      "mutation_attempts": ["reduce_nesting", "add_early_exit"]
    }
  ],
  "mutation_effectiveness": {
    "add_bounds_check": 0.7,
    "simplify_logic": 0.5,
    "add_early_exit": 0.8
  },
  "evolutionary_timeline": [
    {"generation": 1, "avg_fitness": 0.65, "diversity": 0.8},
    {"generation": 10, "avg_fitness": 0.88, "diversity": 0.5}
  ],
  "final_metrics": {
    "generations": 50,
    "total_evaluations": 5000,
    "peak_fitness": 0.99,
    "convergence_gen": 35
  }
}
```

**LLM Query Prompt Template:**
```
You are an evolutionary algorithm strategist. A code generation system is stuck.

CURRENT PROBLEM:
- Description: {problem_description}
- Language: {language}
- Stuck on error: {error_type}
- Attempts: {attempts_count}

SIMILAR PROBLEMS SOLVED BEFORE:
{format_memory_entries(similar_problems)}

Based on these past successes, suggest (JSON format):
1. Top 3 mutation types most likely to work
2. Code patterns that fixed this before
3. Exploration level (0-1): should we explore more or exploit?
4. Confidence (0-1): how sure are you?

Examples of successful mutations for similar errors:
{format_mutation_examples(similar_problems)}

Respond ONLY with valid JSON:
{
  "recommended_mutations": ["mutation_1", "mutation_2", "mutation_3"],
  "code_patterns": ["pattern_1", "pattern_2"],
  "exploration_level": 0.7,
  "confidence": 0.85,
  "reasoning": "Short explanation"
}
```

**Implementation File:** `evolutionary_memory.py`

**Class:** `EvolutionaryMemory`

**Methods:**
- `store_problem_solution(problem_id, success_data)` — Save problem memory
- `query_for_strategy(problem, error_type, attempts)` — Ask LLM for help
- `find_similar_problems(query, error_type, k=3)` — Semantic search
- `apply_mutation_bias(mutations)` — Update mutation weights
- `get_memory_summary()` — Statistics on stored problems

**LLM Configuration:**
- Model: `claude-3-5-sonnet-20241022` (or your preferred model)
- Max tokens: 1000
- Temperature: 0.3 (deterministic)
- Timeout: 30s

---

### Component #6: Failure-Driven Evolution

**Purpose:** Classify failure types. Bias mutations to fix specific failures.

**Mechanism:**
- Classify each failure into category: timeout, wrong_output, crash, memory_limit
- Track which mutation types help for each failure category
- When population has failures of type X, increase weight of effective mutations for X

**Failure Classification Rules:**
```
if test_result.timeout:
    return "timeout"
elif test_result.wrong_output:
    return "wrong_output"
elif test_result.crash or test_result.exception:
    return "crash"
elif test_result.memory_exceeded:
    return "memory_limit"
else:
    return "unknown"
```

**Mutation Effectiveness Mapping:**
```python
MUTATION_EFFECTIVENESS_PER_FAILURE = {
    "timeout": {
        "reduce_nesting": 0.9,
        "add_early_exit": 0.85,
        "add_caching": 0.7,
        "simplify_logic": 0.8,
        "vectorize_operations": 0.6
    },
    "wrong_output": {
        "add_bounds_check": 0.85,
        "fix_edge_cases": 0.9,
        "add_validation": 0.8,
        "simplify_logic": 0.7,
        "add_comment_hint": 0.6
    },
    "crash": {
        "add_bounds_check": 0.9,
        "add_validation": 0.85,
        "reduce_variable_scope": 0.8,
        "simplify_logic": 0.7,
        "add_error_handling": 0.85
    },
    "memory_limit": {
        "add_caching": 0.8,
        "optimize_data_structure": 0.9,
        "reduce_nesting": 0.7,
        "vectorize_operations": 0.85
    }
}
```

**Implementation File:** `failure_analysis.py`

**Class:** `FailureDrivenMutation`

**Methods:**
- `classify_failure(test_result)` — Categorize failure type
- `record_failure(code, failure_type)` — Store failure info
- `get_targeted_mutations(failure_type)` — Return mutations effective for this failure
- `get_failure_statistics()` — Summary of failure distribution
- `update_effectiveness(failure_type, mutation, was_successful)` — Learn from experience

---

### Component #7: Behavioral Diversity

**Purpose:** Keep solutions with different code behaviors, not just different fitness.

**Mechanism:**
- Compute behavior signature for each code: execution paths, output patterns, AST structure
- Measure behavioral distance between individuals
- Use in selection: prefer solutions with novel behaviors

**Behavior Signature Computation:**
```python
def compute_behavior_signature(code, test_results):
    signature = {
        "execution_paths": len(set(test_results.execution_traces)),
        "output_hash": hash(tuple(test_results.outputs)),
        "ast_structure": compute_ast_hash(code),
        "complexity_profile": code.cyclomatic_complexity,
        "recursion_depth": max_recursion_depth(code),
        "loop_count": count_loops(code),
        "conditional_count": count_conditionals(code)
    }
    return signature
```

**Behavioral Distance:**
```
distance = sqrt(
    (paths_diff / max_paths)^2 +
    (output_hash_diff)^2 +
    (ast_diff / max_ast)^2 +
    (complexity_diff / max_complexity)^2
)
```

**Implementation File:** `behavioral_diversity.py`

**Class:** `BehavioralDiversity`

**Methods:**
- `compute_behavior_signature(code, test_results)` — Generate signature
- `behavior_distance(code1, code2)` — Distance between two behaviors
- `novelty_score(code, population)` — How novel is this code?
- `get_behavior_cluster(population, k=5)` — Cluster by behavior

---

### Component #8: Novelty-Driven Evolution

**Purpose:** Explicitly reward exploration. Add novelty as an objective.

**Mechanism:**
- Compute novelty as minimum distance to K-nearest neighbors in behavior space
- Archive novel solutions (solutions exceeding novelty threshold)
- Add novelty as 4th objective in multi-objective fitness

**Key Equations:**
```
novelty(x) = mean(distance(x, k_nearest_neighbors(x, k=15)))

fitness = (correctness × 0.6) + (novelty × 0.4)

If novelty(x) > NOVELTY_THRESHOLD (e.g., 0.5):
    add to novelty_archive
```

**Implementation File:** `novelty_evolution.py`

**Class:** `NoveltyDrivenEvolution`

**Methods:**
- `compute_novelty(individual, population)` — K-NN novelty score
- `add_to_archive(individual)` — Store novel solution
- `fitness_with_novelty(individual, population)` — Multi-objective fitness
- `get_archive()` — Return all archived novel solutions

---

### Component #9: Evolutionary Landscape Detection

**Purpose:** Detect stagnation, convergence, improvement. Trigger adaptive responses.

**Mechanism:**
- Monitor fitness trend: is it improving?
- Monitor diversity: is population converging?
- If stagnation detected: increase mutation, inject diversity
- If convergence detected: bring back archived solutions

**Detection Thresholds:**
```python
STAGNATION_WINDOW = 10  # generations to check
CONVERGENCE_THRESHOLD = 0.01  # fitness improvement threshold
DIVERSITY_THRESHOLD = 0.1  # minimum population diversity
STAGNATION_TRIGGER = 0.01  # no improvement over window
```

**Adaptive Responses:**
```python
if detect_stagnation():
    return {
        "action": "increase_exploration",
        "mutation_rate_multiplier": 1.3,
        "diversity_shock": True  # Randomly mutate 20% of population
    }
elif detect_convergence():
    return {
        "action": "inject_novelty",
        "sample_from_archive": True,  # Bring back archived solutions
        "archive_sample_size": 0.2  # 20% of population
    }
else:
    return {
        "action": "continue",
        "no_change": True
    }
```

**Implementation File:** `landscape_detector.py`

**Class:** `LandscapeDetector`

**Methods:**
- `detect_stagnation()` — Is fitness plateaued?
- `detect_convergence()` — Is population converged?
- `detect_improvement()` — Is fitness increasing?
- `trigger_adaptive_response()` — Return action dict
- `get_landscape_status()` — Return summary (stagnant/improving/converging)

---

### Component #10: Population of Strategies

**Purpose:** Run multiple evolutionary strategies in parallel. Best strategy gets more resources.

**Mechanism:**
- Define 3 strategies: aggressive, conservative, balanced
- Each strategy maintains a sub-population
- Track fitness trend for each strategy
- Allocate population slots based on fitness improvement rate

**Strategy Definitions:**
```python
STRATEGIES = {
    "aggressive": {
        "mutation_rate": 0.7,
        "selection_pressure": 0.2,
        "exploration_bias": 0.8,
        "test_budget": 100
    },
    "conservative": {
        "mutation_rate": 0.2,
        "selection_pressure": 0.8,
        "exploration_bias": 0.1,
        "test_budget": 50
    },
    "balanced": {
        "mutation_rate": 0.5,
        "selection_pressure": 0.5,
        "exploration_bias": 0.5,
        "test_budget": 75
    }
}
```

**Resource Allocation:**
```
For each strategy S:
    fitness_trend = (fitness[t] - fitness[t-5]) / 5
    
total_trend = sum(fitness_trend for all strategies)

if total_trend > 0:
    population_size[S] = (fitness_trend[S] / total_trend) × total_population
else:
    population_size[S] = total_population / num_strategies
```

**Implementation File:** `strategy_competition.py`

**Classes:**
- `EvolutionaryStrategy` — Single strategy with sub-population
- `StrategyCompetition` — Manages multiple strategies

**Methods:**
- `EvolutionaryStrategy.run_generation()` — Evolve this strategy's population
- `EvolutionaryStrategy.get_fitness_trend()` — Trend of fitness improvements
- `StrategyCompetition.allocate_resources()` — Update population sizes
- `StrategyCompetition.run_generation()` — Run all strategies
- `StrategyCompetition.get_strategy_stats()` — Performance summary

---

## System Architecture

### Main Evolution Loop

```python
class AIECG:
    """Adaptive Intelligent Evolutionary Code Generation"""
    
    def __init__(self, problem, llm_api_key, num_generations=100):
        # Initialize all 10 components
        self.adaptive_evolution = AdaptiveEvolution()
        self.mutation_tracker = MutationEffectivenessTracker()
        self.rl_controller = RLEvolutionaryController()
        self.agent_population = AgentPopulation()
        self.memory = EvolutionaryMemory(llm_api_key)
        self.failure_driven = FailureDrivenMutation()
        self.behavior_diversity = BehavioralDiversity()
        self.novelty_evolution = NoveltyDrivenEvolution()
        self.landscape = LandscapeDetector()
        self.strategy_competition = StrategyCompetition()
        
        self.problem = problem
        self.num_generations = num_generations
        self.generation = 0
        
    def run(self):
        """Main evolution loop"""
        for self.generation in range(self.num_generations):
            # Phase 1: Generate
            offspring = self.generate_offspring()
            
            # Phase 2: Evaluate
            self.evaluate_population(offspring)
            
            # Phase 3: Analyze
            self.analyze_failures(offspring)
            self.compute_behaviors(offspring)
            self.compute_novelty(offspring)
            
            # Phase 4: Detect Landscape
            adaptive_response = self.landscape_detection()
            self.apply_adaptive_response(adaptive_response)
            
            # Phase 5: Decision Making
            rl_action = self.rl_decision_making()
            self.apply_rl_action(rl_action)
            
            # Phase 6: Adaptive Parameters
            self.adaptive_evolution.update_parameters(offspring)
            
            # Phase 7: Check Memory
            if self.landscape.detect_stagnation():
                self.query_llm_memory()
            
            # Phase 8: Selection
            survivors = self.select_survivors(offspring)
            
            # Phase 9: Agent Evolution
            self.agent_population.evolve_agents([s.fitness for s in survivors])
            
            # Phase 10: Strategy Allocation
            self.strategy_competition.allocate_resources()
            
            # Phase 11: Store Memory
            if self.generation % 20 == 0:
                self.memory.store_problem_solution(self.problem.id, self.get_state())
            
            # Phase 12: Logging
            self.log_generation()
```

### Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    AIECG Core Loop                          │
└─────────────────────────────────────────────────────────────┘
    │
    ├─→ Generate Offspring
    │   └─→ Strategy Competition (#10) picks strategy
    │   └─→ Mutator (possibly co-evolved #4) applies mutations
    │
    ├─→ Evaluate Fitness
    │   └─→ Multi-objective: correctness, runtime, complexity, novelty
    │
    ├─→ Failure Analysis
    │   └─→ Failure-Driven (#6) classifies errors
    │   └─→ Updates mutation effectiveness (#2)
    │
    ├─→ Compute Behaviors
    │   └─→ Behavioral Diversity (#7) generates signatures
    │   └─→ Novelty-Driven (#8) scores novelty
    │
    ├─→ Landscape Detection
    │   └─→ Landscape Detector (#9) checks stagnation/convergence
    │   └─→ Triggers adaptive responses
    │   └─→ If stuck, query LLM Memory (#5)
    │
    ├─→ RL Decision
    │   └─→ RL Controller (#3) recommends hyperparameter changes
    │
    ├─→ Adaptive Parameters
    │   └─→ Adaptive Evolution (#1) adjusts mutation_rate, selection_pressure
    │
    ├─→ Selection
    │   └─→ Use Behavioral Diversity (#7) + Novelty (#8) + Multi-objective
    │   └─→ Cluster by behavior, select top from each cluster
    │
    ├─→ Agent Evolution
    │   └─→ Co-Evolution (#4) evolves Mutator/Critic/Validator parameters
    │
    ├─→ Store Memory
    │   └─→ Every N generations, save problem state for future transfer
    │
    └─→ Repeat
```

---

## Data Models

### ObjectiveVector

Represents multi-dimensional fitness (4 objectives).

```python
from dataclasses import dataclass

@dataclass
class ObjectiveVector:
    correctness: float      # [0, 1], higher is better
    runtime: float          # [0, 1], lower is better (normalized)
    complexity: float       # [0, 1], lower is better (normalized)
    novelty: float          # [0, 1], higher is better
    
    def weighted_fitness(self, weights=None):
        """Scalarize to single fitness value"""
        if weights is None:
            weights = [0.6, 0.15, 0.15, 0.1]
        return sum(w * obj for w, obj in zip(weights, 
            [self.correctness, 1-self.runtime, 1-self.complexity, self.novelty]))
    
    def as_vector(self):
        """Return as list for clustering/distance"""
        return [self.correctness, self.runtime, self.complexity, self.novelty]
```

### BehaviorSignature

Captures code's execution behavior.

```python
from dataclasses import dataclass

@dataclass
class BehaviorSignature:
    execution_paths: int            # Number of unique execution paths
    output_hash: int                # Hash of outputs across tests
    ast_structure: int              # Hash of AST
    complexity_profile: int         # Cyclomatic complexity
    recursion_depth: int            # Max recursion depth
    loop_count: int                 # Number of loops
    conditional_count: int          # Number of conditionals
    
    def distance_to(self, other):
        """Euclidean distance to another signature"""
        deltas = [
            (self.execution_paths - other.execution_paths) ** 2,
            (self.output_hash - other.output_hash) ** 2,
            (self.ast_structure - other.ast_structure) ** 2,
            (self.complexity_profile - other.complexity_profile) ** 2,
            (self.recursion_depth - other.recursion_depth) ** 2,
            (self.loop_count - other.loop_count) ** 2,
            (self.conditional_count - other.conditional_count) ** 2
        ]
        return sum(deltas) ** 0.5
```

### Individual Genome

Extended from EvoCode's existing genome to include new fields.

```python
from dataclasses import dataclass, field

@dataclass
class Individual:
    # Existing fields
    id: str
    prompt_config: dict
    code: str
    language: str
    generation: int
    
    # New: Multi-objective
    objectives: ObjectiveVector = None
    
    # New: Behavior
    behavior_signature: BehaviorSignature = None
    novelty_score: float = 0.0
    
    # New: Failure tracking
    test_result: dict = None
    failure_type: str = None  # timeout, wrong_output, crash, memory_limit
    
    # New: Mutation tracking
    mutation_type: str = None
    parent_id: str = None
    parent_fitness: float = None
    
    # New: Diversity
    cluster_id: int = None
    behavioral_distance_to_nearest: float = None
    
    def fitness(self):
        """Convenience method for overall fitness"""
        if self.objectives:
            return self.objectives.weighted_fitness()
        return 0.0
```

### ProblemState

Snapshot of evolution state for memory storage.

```python
from dataclasses import dataclass

@dataclass
class ProblemState:
    problem_id: str
    language: str
    generation: int
    timestamp: str
    
    # Population stats
    avg_fitness: float
    best_fitness: float
    population_diversity: float
    
    # Success examples
    successful_genomes: list
    
    # Failure distribution
    failure_log: dict  # failure_type -> count
    
    # Mutation effectiveness
    mutation_effectiveness: dict
    
    # Strategy performance
    strategy_stats: dict
    
    # Evolutionary timeline
    fitness_history: list
    diversity_history: list
```

---

## Implementation Details

### Phase 1: Failure Classification (#6) — Weeks 1–2

**Goal:** Classify failures into 4 types; track patterns.

**Files to Create:**
- `failure_analysis.py` (main module)

**Key Methods:**
```python
class FailureDrivenMutation:
    def classify_failure(self, test_result):
        if test_result.timeout:
            return "timeout"
        elif test_result.wrong_output:
            return "wrong_output"
        elif test_result.crash:
            return "crash"
        elif test_result.memory_exceeded:
            return "memory_limit"
        return "unknown"
```

**Integration:**
- Call in `fitness_scorer.py` after test execution
- Store `Individual.failure_type`

**Testing:**
- Unit test: 10 mock test results → correct classification
- Integration test: run on existing EvoCode problems → verify categories

---

### Phase 2: Behavioral Diversity (#7) & Landscape Detection (#9) — Weeks 3–4

**Goal:** Compute behavior signatures; detect stagnation.

**Files to Create:**
- `behavioral_diversity.py`
- `landscape_detector.py`

**Key Methods:**
```python
# behavioral_diversity.py
def compute_behavior_signature(code, test_results):
    return BehaviorSignature(
        execution_paths=len(set(test_results.traces)),
        output_hash=hash(tuple(test_results.outputs)),
        ast_structure=compute_ast_hash(code),
        complexity_profile=code.cyclomatic_complexity,
        ...
    )

# landscape_detector.py
def detect_stagnation():
    if len(fitness_history) < STAGNATION_WINDOW:
        return False
    improvement = fitness_history[-1] - fitness_history[-STAGNATION_WINDOW]
    return improvement < CONVERGENCE_THRESHOLD
```

**Integration:**
- In `evoflow.py`: call after evaluation
- Update `Individual.behavior_signature`

---

### Phase 3: Adaptive Evolution (#1) & Mutation Tracking (#2) — Weeks 5–6

**Goal:** Auto-adjust parameters based on convergence; learn effective mutations.

**Files to Create:**
- `adaptive_evolution.py`
- `mutation_effectiveness.py`

**Key Methods:**
```python
# adaptive_evolution.py
def update_parameters(population):
    avg_fitness = mean([ind.fitness() for ind in population])
    if not improving:
        mutation_rate *= 1.1
        selection_pressure *= 0.9

# mutation_effectiveness.py
def record_mutation(mutation_type, improvement):
    effectiveness[mutation_type].append(improvement)

def get_mutation_weights():
    scores = {t: mean(effectiveness[t]) for t in MUTATION_TYPES}
    return softmax(scores)
```

**Integration:**
- In `mutator.py`: use weighted sampling
- Call `record_mutation()` after evaluation

---

### Phase 4: Novelty-Driven Evolution (#8) & Multi-Objective — Weeks 7–8

**Goal:** Add novelty as objective; K-means clustering for selection.

**Files to Create:**
- `novelty_evolution.py`

**Key Methods:**
```python
def compute_novelty(individual, population):
    k = 15
    distances = [behavior_distance(individual, other) for other in population]
    distances.sort()
    return mean(distances[:k])
```

**Integration:**
- Update `ObjectiveVector` to include novelty
- Selection: K-means clustering on objective space

---

### Phase 5: LLM Memory Integration (#5) — Weeks 9–10

**Goal:** Store/retrieve problem solutions via LLM.

**Files to Create:**
- `evolutionary_memory.py`

**Key Methods:**
```python
def store_problem_solution(problem_id, state):
    entry = {
        "problem_id": problem_id,
        "successful_genomes": state.best_individuals,
        "failure_log": state.failures,
        "mutation_effectiveness": state.mutations,
        "evolutionary_timeline": state.fitness_history
    }
    self.memory.append(entry)

def query_for_strategy(problem, error_type, attempts):
    similar = find_similar_problems(problem, error_type)
    prompt = build_prompt(problem, similar)
    response = llm.call(prompt)
    return parse_json_response(response)
```

**LLM Setup:**
```python
from anthropic import Anthropic

self.client = Anthropic(api_key=llm_api_key)
response = self.client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1000,
    messages=[{"role": "user", "content": prompt}]
)
```

---

### Phase 6: Co-Evolution of Agents (#4) — Weeks 11–12

**Goal:** Mutator/Critic/Validator hyperparameters evolve.

**Files to Create:**
- `agent_population.py`

**Key Methods:**
```python
class EvolvableAgent:
    def mutate(self):
        for key in self.genome:
            if random.random() < 0.3:
                if isinstance(self.genome[key], float):
                    self.genome[key] += random.gauss(0, 0.1)
                    self.genome[key] = clip(0, 1)

class AgentPopulation:
    def evolve_agents(self, code_population_fitness):
        for agent in self.agents:
            agent.fitness = mean(code_population_fitness)
        top = sorted(agents, key=lambda a: a.fitness, reverse=True)[:3]
        self.agents = top + [a.mutate() for a in top]
```

---

### Phase 7: Strategy Competition (#10) — Weeks 13–14

**Goal:** Multiple strategies compete; best grows.

**Files to Create:**
- `strategy_competition.py`

**Key Methods:**
```python
class StrategyCompetition:
    def allocate_resources(self):
        trends = [s.fitness_trend for s in self.strategies]
        total_trend = sum(max(0, t) for t in trends)
        for strategy in self.strategies:
            if total_trend > 0:
                strategy.population_size = int(
                    (strategy.fitness_trend / total_trend) * self.total_population
                )
```

---

### Phase 8: RL-Controlled Evolution (#3) — Weeks 15–16

**Goal:** Lightweight RL agent learns optimal hyperparameters.

**Files to Create:**
- `rl_controller.py`

**Model Type:** Simple Q-learning (not deep)

**Key Methods:**
```python
class RLEvolutionaryController:
    def get_next_action(self):
        state_vector = [self.state["avg_fitness"], self.state["diversity"], ...]
        action = self.model.predict(state_vector)
        return action
    
    def update_q_values(self, state, action, reward, next_state):
        current_q = self.Q[(state, action)]
        max_next_q = max(self.Q.get((next_state, a), 0) for a in ACTIONS)
        self.Q[(state, action)] = current_q + LR * (reward + GAMMA * max_next_q - current_q)
```

---

### Phase 9–12: Integration, Testing, Visualization, Documentation — Weeks 17–24

**Phase 9 (Weeks 17–18): Integration Testing**
- Unit test each component
- Integration test all 10 components together
- Regression test: does AIECG beat baseline?

**Phase 10 (Weeks 19–20): Visualization Dashboard**
- 2D/3D scatter plots (objectives, clusters)
- Fitness trend lines
- Strategy performance comparison
- Failure distribution charts

**Phase 11 (Weeks 21–22): Benchmarking & Analysis**
- Compare AIECG vs. scalar fitness baseline
- Measure diversity metrics
- Document convergence speed
- Analyze which components matter most

**Phase 12 (Weeks 23–24): Final Documentation**
- Update README
- Document all 10 components
- Write usage guide
- Prepare defense presentation

---

## Integration Points

### Modified Files

#### `fitness_scorer.py`

**Change 1:** Return `ObjectiveVector` instead of scalar

```python
def score_genome(self, code, test_results):
    # Before:
    # return correctness_rate * quality_score
    
    # After:
    correctness = len([t for t in test_results if t.passed]) / len(test_results)
    runtime = median([t.execution_time for t in test_results])
    complexity = compute_complexity(code)
    novelty = 0.0  # Will be set later by novelty_evolution
    
    return ObjectiveVector(
        correctness=correctness,
        runtime=runtime / MAX_RUNTIME,
        complexity=complexity / MAX_COMPLEXITY,
        novelty=novelty
    )
```

#### `genome.py`

**Change 1:** Add new fields to Individual

```python
@dataclass
class Individual:
    # ... existing fields ...
    
    # New multi-objective fields
    objectives: ObjectiveVector = None
    
    # New behavior fields
    behavior_signature: BehaviorSignature = None
    novelty_score: float = 0.0
    
    # New failure tracking
    failure_type: str = None
    test_result: dict = None
    
    # New mutation tracking
    mutation_type: str = None
    parent_id: str = None
    
    # New diversity fields
    cluster_id: int = None
```

#### `evoflow.py`

**Change 1:** Integrate all 10 components into main loop

```python
class EvoFlow:
    def __init__(self, problem, config):
        # ... existing init ...
        
        # NEW: Initialize all 10 components
        self.adaptive_evolution = AdaptiveEvolution()
        self.mutation_tracker = MutationEffectivenessTracker()
        self.rl_controller = RLEvolutionaryController()
        self.agent_population = AgentPopulation()
        self.memory = EvolutionaryMemory(config.llm_api_key)
        self.failure_driven = FailureDrivenMutation()
        self.behavior_diversity = BehavioralDiversity()
        self.novelty_evolution = NoveltyDrivenEvolution()
        self.landscape = LandscapeDetector()
        self.strategy_competition = StrategyCompetition()
    
    def run_generation(self):
        # 1. Generate
        offspring = self.strategy_competition.run_generation()
        
        # 2. Evaluate
        for ind in offspring:
            ind.objectives = self.fitness_scorer.score_genome(ind.code, ind.test_result)
        
        # 3. Analyze failures
        for ind in offspring:
            ind.failure_type = self.failure_driven.classify_failure(ind.test_result)
            self.failure_driven.record_failure(ind, ind.failure_type)
        
        # 4. Compute behaviors & novelty
        for ind in offspring:
            ind.behavior_signature = self.behavior_diversity.compute_behavior_signature(ind)
            ind.novelty_score = self.novelty_evolution.compute_novelty(ind, offspring)
            ind.objectives.novelty = ind.novelty_score
        
        # 5. Detect landscape
        adaptive_response = self.landscape.trigger_adaptive_response()
        if adaptive_response["action"] == "diversity_shock":
            self.inject_diversity_shock(offspring)
        
        # 6. RL decision
        rl_action = self.rl_controller.get_next_action()
        self.rl_controller.execute_action(rl_action)
        
        # 7. Adaptive parameters
        self.adaptive_evolution.update_parameters(offspring)
        
        # 8. Query LLM if stuck
        if self.landscape.detect_stagnation():
            error_type = self.get_dominant_failure_type()
            llm_suggestion = self.memory.query_for_strategy(self.problem, error_type, self.generation)
            self.apply_llm_mutation_bias(llm_suggestion)
        
        # 9. Selection
        survivors = self.select_with_diversity_and_novelty(offspring)
        
        # 10. Evolve agents
        self.agent_population.evolve_agents([s.objectives.weighted_fitness() for s in survivors])
        
        # 11. Allocate to strategies
        self.strategy_competition.allocate_resources()
        
        # 12. Store memory
        if self.generation % 20 == 0:
            self.memory.store_problem_solution(self.problem.id, self.get_state())
        
        return survivors
```

#### `mutator.py`

**Change 1:** Use learned mutation weights

```python
class Mutator:
    def apply_mutation(self, genome, mutation_tracker):
        # Before: random mutation type
        # mutation_type = random.choice(MUTATION_TYPES)
        
        # After: weighted by effectiveness
        weights = mutation_tracker.get_mutation_weights()
        mutation_type = random.choices(MUTATION_TYPES, weights=weights)[0]
        
        # Apply mutation based on failure type (if available)
        if genome.failure_type:
            targeted_mutations = self.failure_driven.get_targeted_mutations(genome.failure_type)
            if random.random() < 0.7:  # 70% chance to use targeted mutation
                mutation_type = random.choice(targeted_mutations)
        
        return self.apply_mutation_of_type(genome, mutation_type)
```

#### `event_logger.py`

**Change 1:** Log objectives instead of single fitness

```python
def log_generation(self, generation, population):
    # Before:
    # avg_fitness = mean([ind.fitness for ind in population])
    # logger.info(f"Gen {generation}: avg fitness={avg_fitness}")
    
    # After:
    objectives_list = [ind.objectives.as_vector() for ind in population]
    avg_objectives = [mean(col) for col in zip(*objectives_list)]
    
    logger.info(f"""
    Generation {generation}:
      Correctness: {avg_objectives[0]:.3f}
      Runtime: {avg_objectives[1]:.3f}
      Complexity: {avg_objectives[2]:.3f}
      Novelty: {avg_objectives[3]:.3f}
      Stagnation: {self.landscape.detect_stagnation()}
      Diversity: {self.compute_diversity():.3f}
    """)
```

### New Files to Create

```
evocode/
├── aiecg/
│   ├── __init__.py
│   ├── adaptive_evolution.py          # Component #1
│   ├── mutation_effectiveness.py      # Component #2
│   ├── rl_controller.py               # Component #3
│   ├── agent_population.py            # Component #4
│   ├── evolutionary_memory.py         # Component #5
│   ├── failure_analysis.py            # Component #6
│   ├── behavioral_diversity.py        # Component #7
│   ├── novelty_evolution.py           # Component #8
│   ├── landscape_detector.py          # Component #9
│   ├── strategy_competition.py        # Component #10
│   ├── data_models.py                 # ObjectiveVector, BehaviorSignature, etc.
│   └── aiecg_main.py                  # Main AIECG class
```

---

## Configuration & Hyperparameters

### Global Configuration File: `aiecg_config.yaml`

```yaml
# AIECG Configuration

# Core
num_generations: 100
population_size: 300
problem: "sorting_algorithm"
language: "python"

# LLM
llm_api_key: ${LLM_API_KEY}
llm_model: "claude-3-5-sonnet-20241022"
llm_query_frequency: 10  # Query memory every N generations if stuck

# Component #1: Adaptive Evolution
adaptive_evolution:
  enabled: true
  stagnation_window: 10
  convergence_threshold: 0.01
  mutation_rate_bounds: [0.2, 0.8]
  selection_pressure_bounds: [0.2, 0.9]

# Component #2: Learning-to-Mutate
mutation_learning:
  enabled: true
  mutation_types:
    - add_bounds_check
    - simplify_logic
    - add_early_exit
    - reduce_nesting
    - add_caching
    - vectorize_operations

# Component #3: RL Controller
rl_controller:
  enabled: true
  model_type: "q_learning"  # lightweight
  learning_rate: 0.1
  discount_factor: 0.9
  epsilon: 0.1  # exploration rate

# Component #4: Co-Evolution of Agents
agent_coevolution:
  enabled: true
  num_agents: 5
  agent_types: ["mutator", "critic", "validator"]
  mutation_std: 0.1  # gaussian std for hyperparameter mutation

# Component #5: Evolutionary Memory
evolutionary_memory:
  enabled: true
  storage_path: "./memory/"
  query_similarity_threshold: 0.7
  top_k_similar_problems: 3
  llm_timeout_seconds: 30

# Component #6: Failure-Driven Evolution
failure_driven:
  enabled: true
  failure_types: ["timeout", "wrong_output", "crash", "memory_limit"]
  update_frequency: 5  # Update effectiveness tracking every N generations

# Component #7: Behavioral Diversity
behavioral_diversity:
  enabled: true
  signature_features:
    - execution_paths
    - output_hash
    - ast_structure
    - complexity_profile
    - recursion_depth
    - loop_count
    - conditional_count

# Component #8: Novelty-Driven
novelty_driven:
  enabled: true
  k_neighbors: 15
  novelty_threshold: 0.5
  novelty_weight: 0.4  # in fitness

# Component #9: Landscape Detection
landscape_detection:
  enabled: true
  stagnation_window: 10
  convergence_diversity_threshold: 0.1
  diversity_shock_percentage: 0.2  # 20% of population

# Component #10: Strategy Competition
strategy_competition:
  enabled: true
  strategies:
    - name: "aggressive"
      mutation_rate: 0.7
      selection_pressure: 0.2
    - name: "conservative"
      mutation_rate: 0.2
      selection_pressure: 0.8
    - name: "balanced"
      mutation_rate: 0.5
      selection_pressure: 0.5

# Multi-objective Fitness Weights
fitness_weights:
  correctness: 0.6
  runtime: 0.15
  complexity: 0.15
  novelty: 0.1

# Logging
logging:
  level: "INFO"
  log_file: "./logs/aiecg.log"
  event_log_file: "./logs/events.json"
  log_frequency: 5  # Log every N generations
```

### Runtime Configuration

```python
from dataclasses import dataclass
import yaml

@dataclass
class AIECGConfig:
    num_generations: int
    population_size: int
    llm_api_key: str
    problem: str
    language: str
    
    @classmethod
    def from_yaml(cls, path):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)
```

---

## Implementation Roadmap

### Timeline: 24 Weeks (6 months)

| Phase | Weeks | Component(s) | Tasks | Deliverable |
|---|---|---|---|---|
| **1** | 1–2 | #6, #7 | Failure classification, behavior signatures | `failure_analysis.py`, `behavioral_diversity.py` |
| **2** | 3–4 | #9 | Landscape detection, stagnation checking | `landscape_detector.py` |
| **3** | 5–6 | #1, #2 | Adaptive evolution, mutation tracking | `adaptive_evolution.py`, `mutation_effectiveness.py` |
| **4** | 7–8 | #8 | Novelty computation, multi-objective fitness | `novelty_evolution.py`, update `ObjectiveVector` |
| **5** | 9–10 | #5 | LLM memory integration, prompt engineering | `evolutionary_memory.py` |
| **6** | 11–12 | #4 | Co-evolution of agents | `agent_population.py` |
| **7** | 13–14 | #10 | Strategy competition, resource allocation | `strategy_competition.py` |
| **8** | 15–16 | #3 | RL controller (Q-learning) | `rl_controller.py` |
| **9** | 17–18 | All | Integration, unit/integration testing | All tests passing |
| **10** | 19–20 | All | Visualization dashboard | HTML/React dashboard |
| **11** | 21–22 | All | Benchmarking, comparative analysis | Benchmark results |
| **12** | 23–24 | All | Documentation, defense prep | Final documentation |

### Dependency Graph

```
Phase 1: #6, #7 (foundation)
    ↓
Phase 2: #9 (uses #6, #7)
    ↓
Phase 3: #1, #2 (uses #6, #7, #9)
    ↓
Phase 4: #8 (uses #7)
    ↓
Phase 5: #5 (uses #1-#4, #6-#9)
    ↓
Phase 6: #4 (independent)
    ↓
Phase 7: #10 (independent)
    ↓
Phase 8: #3 (uses #1, #9, #10)
    ↓
Phase 9: Integration
    ↓
Phase 10: Visualization
    ↓
Phase 11: Benchmarking
    ↓
Phase 12: Documentation
```

---

## Evaluation & Metrics

### Metrics to Track

#### 1. Fitness Metrics
- **Peak Fitness:** Best fitness value found
- **Average Fitness:** Mean of population fitness
- **Fitness Trend:** Rate of improvement over last N generations
- **Convergence Generation:** Generation when fitness plateaus

#### 2. Diversity Metrics
- **Behavioral Diversity:** Mean distance between individuals
- **Novelty Archive Size:** Number of novel solutions found
- **Population Variance:** Variance of objectives
- **Cluster Distribution:** How evenly population spreads across clusters

#### 3. Component Effectiveness
- **Mutation Effectiveness:** Which mutation types help most
- **Failure Type Distribution:** Percentage of each failure type
- **Strategy Performance:** Fitness trend for each strategy
- **Agent Evolution Impact:** Fitness change after agent evolution
- **Memory Query Success:** % of queries that help

#### 4. Adaptive Control
- **Mutation Rate Evolution:** How it changes over time
- **Selection Pressure Evolution:** How it changes over time
- **Stagnation Detections:** Number of times stagnation detected
- **Diversity Shocks Triggered:** Number of diversity injections
- **RL Action Success Rate:** % of RL actions that improved fitness

### Comparison Baseline: Scalar Fitness

Run same problems with old scalar fitness (`fitness = correctness × quality`), then compare:
- Peak fitness: AIECG vs. Baseline
- Convergence speed: AIECG vs. Baseline
- Solution diversity: AIECG vs. Baseline
- Robustness: AIECG vs. Baseline on new problems

### Success Criteria

✅ **AIECG finds 100%-correct solutions** for all test problems  
✅ **Converges 20% faster** than scalar fitness baseline  
✅ **Maintains 30% higher diversity** than scalar baseline  
✅ **LLM memory queries** reduce convergence time by 15% on transfer problems  
✅ **All 10 components** integrate without errors  
✅ **Visualization** clearly shows objective space and clusters  

---

## Appendix: Code Templates

### Template 1: Component Base Class

```python
# aiecg/component_base.py

from abc import ABC, abstractmethod

class AIECGComponent(ABC):
    """Base class for all AIECG components"""
    
    def __init__(self, config):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.stats = {}
    
    @abstractmethod
    def initialize(self):
        """Initialize component"""
        pass
    
    @abstractmethod
    def update(self, population):
        """Update component based on current population"""
        pass
    
    def get_stats(self):
        """Return component statistics"""
        return self.stats
    
    def reset(self):
        """Reset component state"""
        self.stats = {}
```

### Template 2: Main AIECG Class

```python
# aiecg/aiecg_main.py

from .adaptive_evolution import AdaptiveEvolution
from .mutation_effectiveness import MutationEffectivenessTracker
from .rl_controller import RLEvolutionaryController
from .agent_population import AgentPopulation
from .evolutionary_memory import EvolutionaryMemory
from .failure_analysis import FailureDrivenMutation
from .behavioral_diversity import BehavioralDiversity
from .novelty_evolution import NoveltyDrivenEvolution
from .landscape_detector import LandscapeDetector
from .strategy_competition import StrategyCompetition

class AIECG:
    """Adaptive Intelligent Evolutionary Code Generation"""
    
    def __init__(self, problem, config):
        self.problem = problem
        self.config = config
        self.generation = 0
        
        # Initialize all 10 components
        self.adaptive_evolution = AdaptiveEvolution(config.adaptive_evolution)
        self.mutation_tracker = MutationEffectivenessTracker(config.mutation_learning)
        self.rl_controller = RLEvolutionaryController(config.rl_controller)
        self.agent_population = AgentPopulation(config.agent_coevolution)
        self.memory = EvolutionaryMemory(config.evolutionary_memory)
        self.failure_driven = FailureDrivenMutation(config.failure_driven)
        self.behavior_diversity = BehavioralDiversity(config.behavioral_diversity)
        self.novelty_evolution = NoveltyDrivenEvolution(config.novelty_driven)
        self.landscape = LandscapeDetector(config.landscape_detection)
        self.strategy_competition = StrategyCompetition(config.strategy_competition)
        
        # Metrics
        self.metrics = {
            "fitness_history": [],
            "diversity_history": [],
            "failure_distribution": {},
            "component_stats": {}
        }
    
    def run(self):
        """Main evolution loop"""
        for self.generation in range(self.config.num_generations):
            print(f"Generation {self.generation + 1}/{self.config.num_generations}")
            
            # Phase 1: Generate
            offspring = self._generate_offspring()
            
            # Phase 2: Evaluate
            self._evaluate_population(offspring)
            
            # Phase 3–10: All analysis and adaptation
            self._analyze_and_adapt(offspring)
            
            # Phase 11: Selection
            survivors = self._select_survivors(offspring)
            
            # Phase 12: Logging
            self._log_generation(survivors)
        
        return self._finalize_results()
    
    def _generate_offspring(self):
        """Phase 1: Generate via strategies"""
        return self.strategy_competition.run_generation()
    
    def _evaluate_population(self, offspring):
        """Phase 2: Evaluate multi-objective fitness"""
        for ind in offspring:
            ind.objectives = compute_objectives(ind)
    
    def _analyze_and_adapt(self, offspring):
        """Phases 3–10: Analysis and adaptation"""
        # Implement as per main loop in overview
        pass
    
    def _select_survivors(self, offspring):
        """Phase 11: Selection via diversity + novelty"""
        clusters = self.behavior_diversity.get_behavior_cluster(offspring, k=5)
        survivors = []
        for cluster in clusters:
            cluster.sort(
                key=lambda i: (i.objectives.correctness, i.novelty_score),
                reverse=True
            )
            survivors.extend(cluster[:len(cluster) // 5])
        return survivors
    
    def _log_generation(self, survivors):
        """Phase 12: Logging"""
        avg_fitness = mean([s.objectives.weighted_fitness() for s in survivors])
        self.metrics["fitness_history"].append(avg_fitness)
        print(f"  Avg Fitness: {avg_fitness:.3f}")
    
    def _finalize_results(self):
        """After all generations, return results"""
        return {
            "best_individuals": self.novelty_evolution.novelty_archive,
            "metrics": self.metrics,
            "memory": self.memory.memory
        }
```

### Template 3: Unit Test

```python
# tests/test_adaptive_evolution.py

import pytest
from aiecg.adaptive_evolution import AdaptiveEvolution
from aiecg.data_models import Individual, ObjectiveVector

def test_detect_stagnation():
    ae = AdaptiveEvolution({"stagnation_window": 5, "convergence_threshold": 0.01})
    
    # Simulate fitness history
    ae.fitness_history = [0.5, 0.55, 0.56, 0.565, 0.568, 0.569]
    
    # Last 5 gens improved by < 0.01, so stagnation
    is_stagnant = ae.detect_stagnation()
    assert is_stagnant == False  # Recent improvement still
    
    ae.fitness_history.extend([0.569, 0.569, 0.5691])
    assert ae.detect_stagnation() == True

def test_mutation_rate_increase():
    ae = AdaptiveEvolution({"stagnation_window": 5})
    ae.mutation_rate = 0.5
    ae.fitness_history = [0.5, 0.51, 0.51, 0.51, 0.51, 0.51]  # Stagnant
    
    ae.update_parameters([])
    assert ae.mutation_rate > 0.5  # Should increase

def test_mutation_rate_decrease():
    ae = AdaptiveEvolution({"stagnation_window": 5})
    ae.mutation_rate = 0.5
    ae.fitness_history = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]  # Improving
    
    ae.update_parameters([])
    assert ae.mutation_rate < 0.5  # Should decrease (exploit)
```

---

## Appendix: LLM Prompt Template

### Default Prompt for Memory Query

```
You are an evolutionary algorithm strategist. A code generation system is stuck.

CURRENT PROBLEM:
- Name: {problem.name}
- Description: {problem.description}
- Language: {language}
- Stuck on: {error_type}
- Failed attempts: {attempts_count}

SIMILAR PROBLEMS SOLVED BEFORE:
{format_memory_entries(similar_problems, top_k=3)}

FAILURE PATTERNS IN PAST SOLUTIONS:
{format_failure_patterns(similar_problems)}

SUCCESSFUL MUTATION STRATEGIES:
{format_mutation_success(similar_problems)}

Based on these past successes, suggest:
1. Top 3 mutation types most likely to work for this {error_type} error
2. Code patterns that fixed similar errors before
3. Exploration level (0-1): should we explore more or exploit current strategy?
4. Confidence (0-1): how sure are you about these recommendations?

Respond ONLY with valid JSON (no other text):
{
  "recommended_mutations": ["mutation_1", "mutation_2", "mutation_3"],
  "reasoning": "Brief explanation of why these mutations work",
  "code_patterns": ["pattern_1", "pattern_2"],
  "exploration_level": 0.7,
  "confidence": 0.85
}
```

---

## Final Notes

### Defense Argument

> "AIECG is a meta-learning evolutionary system for code generation. Unlike traditional GAs that use fixed hyperparameters, AIECG adapts in real-time by:
>
> 1. **Monitoring its own progress** (landscape detection)
> 2. **Learning effective strategies** (mutation tracking, RL control)
> 3. **Maintaining diversity** (behavioral + novelty)
> 4. **Targeting weaknesses** (failure-driven mutation)
> 5. **Leveraging past experience** (LLM memory)
> 6. **Co-evolving its components** (agent evolution)
> 7. **Competing strategies** (strategy competition)
>
> The result is an algorithm that doesn't just find solutions—it learns how to evolve better solutions, achieving higher quality, faster convergence, and greater diversity than fixed-parameter approaches."

### Success Indicators

✅ All 10 components implemented and integrated  
✅ AIECG finds 100%-correct solutions consistently  
✅ 20%+ faster convergence than baseline  
✅ 30%+ higher behavioral diversity  
✅ Clear visualization of objective space  
✅ LLM memory enables transfer learning  
✅ Comprehensive evaluation metrics  

---
