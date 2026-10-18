# 🏛️ EvoCode Architecture Deep Dive

This document provides a highly detailed architectural overview of the **EvoCode** system. It explores the internal mechanics of the 3-Tier LLM Client, the Secure Docker Sandbox, the Co-Evolutionary Agent framework (powered by the EvoGenesis algorithm), the Historical Memory synthesis, and the Meta-Evolution self-improvement engine.

---

## 📑 Contents
1. [High-Level Architecture](#high-level-architecture)
2. [The 4-Layer Evaluation Hierarchy](#the-4-layer-evaluation-hierarchy)
3. [The Co-Evolutionary Agent Framework](#the-co-evolutionary-agent-framework)
4. [EvoFlow Orchestrator (The Engine)](#evoflow-orchestrator)
5. [Secure Sandboxing System](#secure-sandboxing-system)
6. [Historical Memory Synthesis](#historical-memory-synthesis)
7. [Meta-Evolution Engine](#meta-evolution-engine)
8. [3-Tier Resilient LLM Client](#3-tier-resilient-llm-client)

---

## 🏗️ High-Level Architecture

EvoCode is an orchestration of specialized systems working in tandem to produce, verify, and improve software.

1. **The Intelligence Layer:** Consists of the LLM Client, Rate Limiters, and the API providers (Groq, Ollama, OpenRouter).
2. **The Agency Layer:** Contains the specialized AI personas (`Architect`, `Generator`, `Reviewer`, `Optimizer`, `BugFixer`).
3. **The Execution Layer:** The isolated Docker sandbox and `FitnessScorer`.
4. **The Meta Layer:** `MemoryHistorian` for past learning, and `MetaArena` for recursive self-improvement.

---

## 🗺️ The 4-Layer Evaluation Hierarchy

The system enforces a rigorous 4-layer evaluation protocol to ensure code correctness and robustness:

1. **Layer 1: The Base Tests**
   - Predefined static input/output test cases provided in the JSON problem definition.
2. **Layer 2: Property-Based Ephemeral Tests**
   - Dynamically generated random inputs on the fly to test boundaries and prevent overfitting.
3. **Layer 3: Multiplicative Fitness & Viability Gate**
   - **Layer 3A (Viability Gate):** Total failures (zero tests passed) receive an unconditional fitness of `0.0` and are eliminated from breeding.
   - **Layer 3B (Multiplicative Fitness):** The `FitnessScorer` calculates:
     $$\text{Fitness} = \text{Correctness Rate} \times \text{Quality Score}$$
     $$\text{Quality Score} = 0.30 \cdot \text{Runtime} + 0.20 \cdot \text{Memory} + 0.20 \cdot \text{Efficiency} + 0.20 \cdot \text{Complexity} + 0.10 \cdot \text{Robustness}$$
     - **Polyglot Complexity Evaluator:** Uses `lizard` to parse and compute AST/cyclomatic complexity across Python, Java, and C++, with a fallback decision-point counter (`if`, `for`, `while`, `case`, `catch`, `&&`, `||`, `?`).
     - **Polyglot Robustness Evaluator:** Detects defensive error handling and null checks across languages (`try/catch`, `null`, `nullptr`, `NULL`, `empty()`, `isEmpty()`).
4. **Layer 4: Held-Out Evaluation (Validation)**
   - Verification against a separate held-out test suite (`data/test_problems.json`) to quantify the generalization gap between train and test sets.

---

## 🧬 The Co-Evolutionary Agent Framework

The EvoGenesis algorithm models a genetic algorithm where the "DNA" is the prompt engineering configuration. Each agent is driven by a Pydantic `AgentGenome` with tunable hyper-parameters (temperature, prompt styles, reasoning styles, memory retrieval strategies).

### Full Agency Lifecycle
The multi-agent pipeline operates in a sequential, cooperating agency cycle:
1. **TemplateAgent:** Generates clean, language-specific scaffolding for the problem (Python function headers, Java `Solution` classes, C++ headers).
2. **ArchitectAgent:** Examines problem constraints and decomposes requirements into an algorithmic blueprint (data structures, edge case hazards, time/space complexity goals).
3. **GeneratorAgent:** Translates the Architect's plan and relevant historical vector memory into full implementation code.
4. **ReviewerAgent:** Pre-execution critique. Validates syntax, edge cases, loop terminations, and potential off-by-one errors before any execution occurs.
5. **Sandbox Execution:** Runs code in the isolated Docker container.
6. **BugFixerAgent:** Triggered *only* when the Sandbox detects runtime errors, syntax crashes, or test failures. Parses compiler/runtime stack traces and surgically fixes the code.
7. **OptimizerAgent:** Triggered *only* when the code successfully passes 100% of the tests. Refactors the code for reduced cyclomatic complexity, improved runtime, and lower memory footprint without compromising correctness.

---

## ⚙️ EvoFlow Orchestrator

The `EvoFlowOrchestrator` (`src/evoflow.py`) is the master loop. It manages the lifecycle of the populations.

### Crossover (Knowledge Sharing)
A unique architectural feature is cross-language pollination. The Orchestrator tracks the absolute best fitness across all languages. When breeding a new child, the system can inject successful source code from other languages into the crossover instruction, translating underlying strategies.

---

## 🔒 Secure Sandboxing System

Executing AI-generated code on a host machine is a severe security risk. EvoCode utilizes a strict Docker abstraction.

### `sandbox.py` Mechanics
1. **Workspace Isolation:** Every candidate gets its own ephemeral, isolated directory (`workspaces/run_X/candidate_Y`) to prevent state leakage or cross-contamination between parallel evaluations.
2. **Harness Injection:** The sandbox dynamically builds a JSON-driven testing harness for Python, Java, and C++.
3. **Docker Constraints:**
    - `--network none`: No internet access.
    - `--memory 256m`: Hard memory limit.
    - `--cpus 0.5`: CPU throttling.
    - `timeout=15`: Native subprocess timeout to kill infinite loops.
4. **Telemetry Extraction:** Parses standard output for time elapsed, peak memory allocated, and exception stack traces.

---

## 🧠 Historical Memory Synthesis

EvoCode continuously learns from experience without requiring expensive model fine-tuning:
1. **Structured Reports:** Every generation outputs a structured JSON report detailing code, fitness breakdown, mutations, and error logs.
2. **Memory Historian:** Distills raw reports into readable memory entries tagged with problem context, results, and actionable lessons learned.
3. **Semantic Vector Retrieval:** Uses scikit-learn `TfidfVectorizer` (unigrams + bigrams) and cosine similarity to search memory passages by problem context.
4. **Experience Prioritization:**
   - `"balanced"`: Equal distribution of best matching successes and failures.
   - `"successes"`: Prioritizes proven working patterns for code generation.
   - `"failures"`: Prioritizes bug traps and anti-patterns for mutation and debugging.

---

## 🤖 Meta-Evolution Engine

EvoCode can rewrite and evolve its own Python source files when performance degrades:

1. **The Watcher:** Tracks rolling success rates across any agent (`generator.py`, `architect.py`, `reviewer.py`, `optimizer.py`, `bugfixer.py`, `template.py`). If the rate drops below 50%, an `UpgradeTrigger` is emitted.
2. **The CloneBuilder:** Uses Python `ast` to dynamically locate and extract the target method (`plan`, `review`, `optimize`, `fix`, `_build_system_prompt`, `generate`). Spawns parallel LLM calls to propose two alternative rewritten implementations.
3. **The SourceJudge:** Panel of LLM judges evaluates the candidates and votes on the best proposal.
4. **The Referee:** Static analysis AST gate that verifies Python syntax, blocks dangerous imports (`requests`, `urllib`), and prevents modification of locked infrastructure files (`system_guard.py`, `sandbox.py`, `evoflow.py`).
5. **The MetaArena:** Fast Duel validation. The surviving candidate is tested against the original in an isolated subprocess. Winners are decided by normalized duel fitness:
   $$\text{Score} = \text{clamp}_{[0, 1]}\left(0.45 \cdot \text{Mean Fitness} + 0.35 \cdot \text{Max Fitness} + 0.20 \cdot \text{Correctness Rate} - 0.10 \cdot \text{Crash Rate}\right)$$
   If the challenger wins, it is atomically promoted to overwrite the original agent file; otherwise, the original is retained and the staging directory is cleared.

---

## 🔌 3-Tier Resilient LLM Client

The `EvoClient` (`src/client.py`) is designed for maximum uptime and resilience during long-running evolutionary algorithms where thousands of LLM calls are made.

### The Fallback Strategy
1. **Ollama (Tier 1 — Local Primary):** Runs completely locally with no rate limits. Used first if `OLLAMA_MODEL` is set.
2. **Groq (Tier 2 — Cloud Fast-Fallback):** Rotates multiple API keys for high-speed cloud inference.
3. **OpenRouter (Tier 3 — Cloud Safety Net):** Final fallback if Groq limits are exhausted.
