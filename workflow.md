# 🔄 EvoCode Operational Workflow

This document details the step-by-step operational flow of the **EvoCode** system during an autonomous run. It tracks the journey of problem definitions as they pass through the multi-agent co-evolutionary pipeline (powered by the EvoGenesis algorithm), memory synthesis, and self-improvement phases.

---

## 📑 Contents
1. [Autonomous Execution Mode](#1-autonomous-execution-mode)
2. [Generation Pipeline (EvoFlow)](#2-generation-pipeline-evoflow)
3. [Memory Synthesis Phase](#3-memory-synthesis-phase)
4. [Meta-Evolution Phase](#4-meta-evolution-phase)

---

## 🎬 1. Autonomous Execution Mode

The primary operational mode for EvoCode is autonomous execution, managed by `run_autonomous.py`.

1. **Problem Generation:** The system fetches problems from the LLM based on user settings (e.g., `--runs 5`).
2. **Sequential Processing:** For each generated problem, the `EvoFlowOrchestrator` runs a set number of generations (`--gens 3`).
3. **Pacing:** Between problems, the system performs telemetry saves, memory compilation, and checks for recursive self-improvement triggers.

---

## 🏗️ 2. Generation Pipeline (EvoFlow)

For each specific problem, the core evolutionary loop (EvoFlow) is executed:

1. **Template Phase:** The `TemplateAgent` generates polyglot function scaffolds and signatures for Python, Java, and C++.
2. **Architect Phase:** The `ArchitectAgent` reviews the problem and writes a high-level solution blueprint (algorithmic choice, edge cases, time/space targets).
3. **Generation Phase:** The `GeneratorAgent` translates the architectural design into Python, Java, or C++ source code. Contextual memories matched via semantic vector search are injected into the prompt.
4. **Review Phase:** The `ReviewerAgent` analyzes the code for potential logical errors, off-by-one errors, and constraint violations prior to execution.
5. **Execution (Sandbox):** The code is sent to the Docker Sandbox. It runs against generated test cases and ephemeral property tests. Telemetry (execution time, peak memory, compiler/runtime errors) is recorded.
6. **BugFixing (Conditional):** If the Sandbox throws a runtime error or fails a test, the `BugFixerAgent` reads the compiler/runtime stack trace and attempts a surgical repair.
7. **Optimization (Conditional):** If the code passes 100% of the tests, the `OptimizerAgent` refactors the solution for cyclomatic complexity, memory usage, and runtime without breaking correctness.
8. **Fitness Scoring & Evolution:** The `FitnessScorer` evaluates the final codebase across correctness and quality metrics (using `lizard` for polyglot AST/cyclomatic complexity). Elites are kept, and survivors undergo crossover and mutation for the next generation.

---

## 🧠 3. Memory Synthesis Phase

At the conclusion of the generation cycles, EvoCode compiles its learnings:

1. **Structured Reports:** The entire run's data is dumped into JSON reports in `structured_reports/`.
2. **Historian Agent:** The `MemoryHistorianAgent` reads all unprocessed reports and distills core strategies, common pitfalls, and successful patterns.
3. **Vector Memory Storage:** These insights are appended to `memory/agent_memory.txt`. Future generations retrieve relevant passages via TF-IDF cosine vector search with multi-objective experience prioritization (`balanced`, `successes`, `failures`).

---

## 🤖 4. Meta-Evolution Phase

After memory is synthesized, the system checks if it needs to evolve its own source code:

1. **Watcher:** The `Watcher` reads rolling success rates across any agent (`generator.py`, `architect.py`, `reviewer.py`, `optimizer.py`, `bugfixer.py`, `template.py`). If the success rate is below 50% across the defined window, Meta-Evolution triggers.
2. **CloneBuilder:** The `CloneBuilder` dynamically locates and extracts the target method from the agent's Python file using AST parsing. It spawns two LLM calls to propose targeted patches.
3. **SourceJudge:** LLM Judges vote on the best proposed patch.
4. **Referee:** The winning patch is statically analyzed by the `Referee` to ensure no syntax errors, banned imports, or unauthorized writes exist.
5. **MetaArena Duel:** The original agent and the newly patched challenger compete in isolated subprocesses on the benchmark suite. The winner is decided by normalized duel fitness:
   $$\text{Score} = \text{clamp}_{[0, 1]}\left(0.45 \cdot \text{Mean Fitness} + 0.35 \cdot \text{Max Fitness} + 0.20 \cdot \text{Correctness Rate} - 0.10 \cdot \text{Crash Rate}\right)$$
   If the Challenger achieves a higher normalized fitness score, it atomically overwrites the original source code. If it ties or loses, a strict rollback occurs to guarantee system stability.
