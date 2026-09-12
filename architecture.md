# 🏛️ EvoGenesis Architecture Deep Dive

This document provides a highly detailed architectural overview of the **EvoGenesis** system. It explores the internal mechanics of the 3-Tier LLM Client, the Secure Docker Sandbox, the Co-Evolutionary Agent framework, the Historical Memory synthesis, and the Meta-Evolution self-improvement engine.

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

EvoGenesis is an orchestration of specialized systems working in tandem to produce, verify, and improve software.

1. **The Intelligence Layer:** Consists of the LLM Client, Rate Limiters, and the API providers (Groq, Ollama, OpenRouter).
2. **The Agency Layer:** Contains the specialized AI personas (`Architect`, `Generator`, `Reviewer`, `Optimizer`, `BugFixer`).
3. **The Execution Layer:** The isolated Docker sandbox and `FitnessScorer`.
4. **The Meta Layer:** `MemoryHistorian` for past learning, and `MetaArena` for recursive self-improvement.

---

## 🗺️ The 4-Layer Evaluation Hierarchy

The system enforces a rigorous 4-layer evaluation protocol to ensure code correctness and robustness:

1. **Layer 1: The Base Tests**
   - The predefined static input/output test cases provided in the JSON problem definition.
2. **Layer 2: Property-Based Ephemeral Tests**
   - Dynamically generated random inputs on the fly.
3. **Layer 3: Multiplicative Fitness & Viability Gate**
   - **Layer 3A (Viability Gate):** Total failures are eliminated from the breeding pool.
   - **Layer 3B (Multiplicative Fitness):** The `FitnessScorer` calculates `Correctness Rate × Quality Score` (evaluating AST complexity, cyclomatic complexity heuristics, execution time, and memory).
4. **Layer 4: Held-Out Evaluation (Validation)**
   - The logical verification of sandbox results to catch unhandled edge cases missed by tests.

---

## 🧬 The Co-Evolutionary Agent Framework

EvoGenesis models a genetic algorithm where the "DNA" is the prompt engineering configuration. Each agent is driven by a Pydantic "Genome".

### Agent Behaviors
- **Architect:** Analyzes the problem and proposes a high-level structural design.
- **Generator:** Translates the design into source code based on genome settings (e.g., if `prompt_style == "chain_of_thought"`).
- **Reviewer:** Critiques the generated code.
- **Optimizer:** Refactors for performance and readability.
- **BugFixer:** Triggered *only* if the Sandbox detects a runtime or logical error. It reads the stack trace and patches the code.

---

## ⚙️ EvoFlow Orchestrator

The `EvoFlowOrchestrator` (`src/evoflow.py`) is the master loop. It manages the lifecycle of the populations.

### Crossover (Knowledge Sharing)
A unique architectural feature is cross-language pollination. The Orchestrator tracks the absolute best fitness across all languages. When breeding a new child, the system can inject successful source code from other languages into the crossover instruction, translating underlying strategies.

---

## 🔒 Secure Sandboxing System

Executing AI-generated code on a host machine is a severe security risk. EvoGenesis utilizes a strict Docker abstraction.

### `sandbox.py` Mechanics
1. **Harness Injection:** The sandbox dynamically builds a JSON-driven testing harness for Python, Java, and C++.
2. **Docker Constraints:**
    - `--network none`: No internet access.
    - `--memory 256m`: Hard memory limit.
    - `--cpus 0.5`: CPU throttling.
    - `timeout=15`: Native subprocess timeout to kill infinite loops.
3. **Telemetry Extraction:** Parses standard output for time elapsed, peak memory allocated, and exception stack traces.

---

## 🧠 Historical Memory Synthesis

EvoGenesis learns over time.
1. **Structured Reports:** Every generation produces a JSON report detailing the code, fitness score, and errors.
2. **Memory Historian:** Aggregates reports and synthesizes them into actionable "Insights".
3. **Feedback Loop:** These synthesized insights are injected into the system prompts of future Generations, effectively giving the algorithm long-term memory without requiring model fine-tuning.

---

## 🤖 Meta-Evolution Engine

EvoGenesis can upgrade its own source code when performance degrades.

1. **The Watcher:** Monitors rolling success rates of agents.
2. **The CloneBuilder:** Extracts specific methods using AST and spawns LLMs to propose targeted patches (minimizing hallucination).
3. **The SourceJudge:** Panel of LLM judges vote on the best patch based on prompt engineering best practices.
4. **The Referee:** Static safety gate that blocks patches with syntax errors, bad imports, or unauthorized file access.
5. **The MetaArena:** A lightweight "Fast Duel" pitting the surviving patch against the original source code on a baseline problem. The winner is atomically promoted.

---

## 🔌 3-Tier Resilient LLM Client

The `EvoClient` (`src/client.py`) is designed for maximum uptime and resilience during long-running evolutionary algorithms where thousands of LLM calls are made.

### The Fallback Strategy
1. **Groq (Primary):** Rotates multiple API keys for high-speed inference.
2. **Ollama (Local Fallback):** Used if cloud limits are hit.
3. **OpenRouter (Cloud Fallback):** Used if local models are unavailable.
