# 🔄 EvoGenesis Operational Workflow

This document details the step-by-step operational flow of the **EvoGenesis** system during an autonomous run. It tracks the journey of problem definitions as they pass through the multi-agent co-evolutionary pipeline, memory synthesis, and self-improvement phases.

---

## 📑 Contents
1. [Autonomous Execution Mode](#1-autonomous-execution-mode)
2. [Generation Pipeline (EvoFlow)](#2-generation-pipeline-evoflow)
3. [Memory Synthesis Phase](#3-memory-synthesis-phase)
4. [Meta-Evolution Phase](#4-meta-evolution-phase)

---

## 🎬 1. Autonomous Execution Mode

The primary operational mode for EvoGenesis is autonomous execution, managed by `run_autonomous.py`.

1. **Problem Generation:** The system fetches problems from the LLM based on user settings (e.g., `--runs 5`).
2. **Sequential Processing:** For each generated problem, the `EvoFlowOrchestrator` runs a set number of generations (`--gens 3`).
3. **Pacing:** Between problems, the system performs telemetry saves, memory compilation, and checks for recursive self-improvement triggers.

---

## 🏗️ 2. Generation Pipeline (EvoFlow)

For each specific problem, the core evolutionary loop (EvoFlow) is executed:

1. **Architect Phase:** The `ArchitectAgent` reviews the problem and writes a high-level solution design.
2. **Generation Phase:** The `GeneratorAgent` translates the architectural design into Python, Java, or C++ source code based on its Genome parameters. Memory Insights from past successful runs are injected into the prompt.
3. **Review Phase:** The `ReviewerAgent` analyzes the code for logical errors before execution.
4. **Optimization Phase:** The `OptimizerAgent` refines the code for peak efficiency and readability.
5. **Execution (Sandbox):** The code is sent to the Docker Sandbox. It runs against generated test cases and ephemeral property tests. Telemetry (execution time, memory peak, AST complexity) is recorded.
6. **BugFixing (Conditional):** If the Sandbox throws a runtime error or fails a test, the `BugFixerAgent` reads the stack trace and attempts a patch.
7. **Fitness Scoring & Evolution:** The `FitnessScorer` evaluates the final codebase. Elites are kept, and lower performers are replaced via crossover and mutation for the next generation.

---

## 🧠 3. Memory Synthesis Phase

At the conclusion of the generation cycles, EvoGenesis compiles its learnings.

1. **Structured Reports:** The entire run's data is dumped into JSON reports.
2. **Historian Agent:** The `MemoryHistorianAgent` reads all unprocessed reports and extracts core strategies, common pitfalls, and successful patterns.
3. **Vector Storage:** These insights are appended to the `agent_memory.md` file, acting as long-term memory for future generations.

---

## 🤖 4. Meta-Evolution Phase

After memory is synthesized, the system checks if it needs to evolve its own source code.

1. **Watcher:** The `Watcher` reads the rolling success rates of core agents (e.g., `generator.py`). If the success rate is below 50% across the defined window, Meta-Evolution triggers.
2. **CloneBuilder:** The `CloneBuilder` uses AST parsing to extract the failing method from the agent's Python file. It spawns two LLM Architects to propose targeted patches.
3. **SourceJudge:** Two LLM Judges vote on the best proposed patch.
4. **Referee:** The winning patch is statically analyzed by the `Referee` to ensure no syntax errors or unauthorized imports exist.
5. **MetaArena Duel:** The original agent and the newly patched agent fight in a lightweight `duel_runner.py` environment on a baseline problem. If the Challenger wins, it atomically overwrites the original source code.
