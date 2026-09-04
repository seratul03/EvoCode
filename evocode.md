# EvoCode — Project Overview (As-Built)

**Author:** Final-Year Project (BCSE-AIML)
**Status:** Phase 2 Complete — Experiment Runs Done on 10-Problem Dev Set
**Last Updated:** September 2026

---

## 1. What EvoCode Actually Is

EvoCode is a **Co-Evolutionary Multi-Agent Code Generation System**. It investigates whether applying evolutionary pressure — selection, mutation, and generational replacement — to a **population** of LLM-based code generators produces better and more generalizable solutions than a single agent iterating alone, at the same total number of LLM calls.

The short version: given a programming problem, multiple AI agents compete to write the best code. The bad ones are eliminated. The good ones breed and mutate. Over generations, the population converges toward a correct, high-quality solution.

---

## 2. Core Research Question

> Does an evolutionary multi-agent system solve programming problems better than a single LLM agent iterating alone — when given the same number of total LLM calls?

### The 4 Experimental Conditions

| Condition | What It Does | Purpose |
|---|---|---|
| **Baseline A** | Single generator, up to 10 generations, no population | Simplest possible baseline |
| **Baseline B** | Single generator, more iterations per problem (matched budget) | "Does just trying more times help?" |
| **Baseline C** | Population + random mutation, no Critic or Mutator guidance | "Does mutation alone help, without direction?" |
| **Evolved Pop** | Full system: population + Critic + Mutator + selection | The main hypothesis under test |

---

## 3. System Architecture

### 3.1 The Two Types of Agents

**Only ONE agent makes LLM API calls:**

| Agent | Type | What It Does |
|---|---|---|
| **Generator** | LLM-based | Writes the Python code for each problem |
| **Critic** | Rule-based | Diagnoses *why* code failed (crashes, wrong output, timeouts, edge cases) |
| **Mutator** | Rule-based | Decides *how* to change the Generator's strategy based on the Critic's diagnosis |
| **Code Validator** | Rule-based | Final correctness check, guards against sandbox blind spots |
| **Evaluators x5** | Rule-based | Score code on runtime, memory, efficiency, complexity, robustness |

This is intentional: only the Generator costs API tokens. Everything else is free computation.

### 3.2 The Genome System

Each Generator in the population carries a **Genome** — a set of parameters that defines *how* it prompts the LLM:

```
GeneratorGenome:
  prompt_style               -> "direct" | "chain_of_thought" | "test_first" | "step_by_step"
  temperature                -> 0.0 to 1.0 (creativity/randomness of the LLM)
  reasoning_steps            -> How many explicit thinking steps to require before coding
  system_instruction_variant -> "standard" | "expert_coder" | "pedantic_reviewer"
  past_code                  -> Previous failing attempt (for reflection-based prompting)
  critic_feedback            -> Critic's diagnosis of the previous attempt
```

The Genome is what *evolves*. The LLM model weights never change.

### 3.3 The Fitness Function

```
fitness_value = correctness_rate x quality_score

Where:
  correctness_rate = passed_tests / total_tests   (THE GATE - must be > 0)
  quality_score    = weighted blend of:
    runtime efficiency     (30%)
    memory efficiency      (20%)
    code efficiency        (20%)
    cyclomatic complexity  (20%)
    robustness             (10%)
```

**Critical rule:** If 0 tests pass, fitness = 0.0 regardless of code quality. Clean but wrong code scores zero.

---

## 4. How One Full Generation Works

```
For each genome in the population (5 genomes):

  1. [Generator]        -> Sends prompt to LLM, receives Python code
  2. [Cache Check]      -> If this exact code was seen before, inject break_cache_loop signal
  3. [Sandbox]          -> Executes code against 25 test cases (subprocess, 5s timeout)
  4. [Code Validator]   -> Rule-based final correctness check
  5. [Evaluators x5]    -> Score runtime, memory, efficiency, complexity, robustness
  6. [FitnessScorer]    -> Combine into single fitness_value (0.0 to 1.0)
  7. [Critic]           -> Diagnose failure: crash / timeout / wrong_output / edge_case_miss
  8. [Mutator]          -> Propose genome changes based on Critic's diagnosis

After all 5 genomes evaluated:

  9.  [Selection]       -> Rank by fitness, keep top 2 (survivors), kill bottom 3
  10. [Breeding]        -> Mutate 3 killed genomes from survivors to create next generation
  11. [Circuit Breaker] -> If any genome hits 1.0 correctness -> stop early (problem solved)
```

---

## 5. The Mutator's Strategies (How Genomes Evolve)

| Critic Diagnosis | Mutator Response |
|---|---|
| **Crash detected** | Switch to pedantic_reviewer, use test_first style, boost reasoning steps |
| **LLM raised exception instead of returning None** | Switch to pedantic_reviewer, inject return_none hint |
| **Wrong output / edge case miss** | Switch to chain_of_thought, increase reasoning steps |
| **Timeout** | Switch to step_by_step, reduce temperature |
| **Cache loop** (same code repeated) | Force different prompt style, boost temperature, warn to try different approach |
| **High crash rate (>50% tests)** | Rotate prompt style entirely — current approach is fundamentally broken |
| **Random jolt** (10% chance) | Random temperature change, random prompt style — maintains diversity |

---

## 6. Infrastructure and API Stack

### 6.1 The 3-Tier Fallback Chain

```
Tier 1 (Primary):    Ollama Local   -> qwen2.5-coder:7b -> localhost:11434
                     No cost, no rate limits, ~5-10 tokens/sec

Tier 2 (Fallback):   Groq Cloud     -> openai/gpt-oss-120b -> 4 rotating API keys
                     Very fast (~500 t/s), rate-limited

Tier 3 (Safety net): OpenRouter     -> nvidia/nemotron-3-ultra-550b -> 1 key
                     Last resort, never lets the run crash
```

Every call goes to Tier 1 first. If Ollama fails, auto-fallback to Groq. If all Groq keys are rate-limited, fallback to OpenRouter. The experiment **never crashes due to API issues.**

### 6.2 Key Files

```
EvoCode/
├── .env                       <- API keys and model config (all 3 tiers)
├── data/
│   ├── train_problems.json    <- 30 training problems (5 categories)
│   └── test_problems.json     <- 10 held-out test problems (never seen during training)
├── src/
│   ├── client.py              <- 3-tier API client (Ollama -> Groq -> OpenRouter)
│   ├── evoflow.py             <- Main orchestrator (runs all generations)
│   ├── genome.py              <- Genome dataclasses (Generator, Critic, Mutator, Evaluator)
│   ├── fitness_scorer.py      <- Correctness x Quality fitness function
│   ├── sandbox.py             <- Safe code execution via subprocess (never exec())
│   ├── event_logger.py        <- Logs everything to SQLite + structured JSON reports
│   └── agents/
│       ├── generator.py       <- LLM-based: writes the code
│       ├── critic.py          <- Rule-based: diagnoses failures
│       ├── mutator.py         <- Rule-based: mutates genomes
│       ├── code_validator.py  <- Rule-based: final correctness check
│       └── evaluators.py      <- Rule-based: 5 quality scorers
├── run_baseline_a.py          <- Runner: Baseline A
├── run_baseline_b.py          <- Runner: Baseline B
├── run_baseline_c.py          <- Runner: Baseline C
├── run_evolved_pop.py         <- Runner: Full Evolved Population
├── run_test_eval.py           <- Runner: Held-out test evaluation
├── structured_reports/        <- All experiment outputs (JSON, one file per run)
└── analysis/                  <- Phase 4 analysis scripts
```

---

## 7. Dataset

| | Train Set | Test Set |
|---|---|---|
| **Total Problems** | 30 | 10 |
| **Algorithmic** | 7 | 3 |
| **Data Structures** | 6 | 2 |
| **String/Parsing** | 6 | 2 |
| **System-style** | 5 | 1 |
| **Edge Cases** | 6 | 2 |

> **Development note:** All experiments so far were run on a **10-problem subset** for speed. The full 30-problem train set is ready and will be used for final runs.

---

## 8. Results So Far (10-Problem Dev Set)

| Condition | Solved | Avg Best Correctness | Model |
|---|---|---|---|
| Baseline A | 8 / 10 | 90.8% | Groq 120B |
| Evolved Pop | 9 / 10 | **96.4%** | Qwen 7B Local |

### Key Findings
- **P1 (Two Sum):** Fixed. Critic detects raise-instead-of-None, Mutator corrects it in Gen 2.
- **P6 (Climbing Stairs):** Universally hard. Stuck across all conditions — a legitimate hard problem.
- **P7 (Reverse Integer):** Evolved Pop solved in Gen 3 after Mutator intervention — direct proof of the loop working.
- **Qwen 7B matched Groq 120B:** A local 7B model inside the evolved framework matched a 120B cloud model. Architecture beats raw model size.

---

## 9. Current Status and Next Steps

### Done
- Full problem dataset (30 train + 10 test)
- Complete agent pipeline (Generator -> Sandbox -> Critic -> Mutator -> Selection -> Breeding)
- 3-tier API fallback (Ollama Local -> Groq -> OpenRouter)
- Dev-set runs for all conditions on 10 problems
- Cache-loop breaker, crash-rate gating, edge-case fixes all verified

### Next Steps
1. Run all 4 conditions on the full 30-problem train set
2. Held-out test evaluation (run_test_eval.py) — measure generalization gap
3. Phase 4 Analysis — fitness curves, mutation matrix, co-evolution dynamics plots
4. Phase 5 Write-Up — methods, results, discussion, defense prep

---

*This document reflects the actual as-built state of EvoCode as of September 2026.*
*The original design documents (evo.md, roadmap.md) remain for historical reference.*
