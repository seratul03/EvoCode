# EvoGenesis Algorithm Specification

## 1. Executive Summary
EvoGenesis is a **Recursive Evolutionary AI Engine** that powers the EvoCode system. It moves beyond standard single-prompt LLM generation by structuring software development as an evolutionary process. The algorithm merges genetic algorithms, multi-agent debate, continuous learning (memory synthesis), and recursive self-improvement (Meta-Evolution).

The goal of the algorithm is to autonomously discover, optimize, and self-heal software solutions by simulating biological evolution inside an isolated computational environment.

---

## 2. Core Evolutionary Loop (The "Genetic" Algorithm)
The foundation of EvoGenesis is an iterative cycle of generation, evaluation, and mutation.

### 2.1 Initialization
The system spins up a starting **Population** of AI Agents. Each agent is instantiated with a unique `AgentGenome`, defining its internal parameters (e.g., temperature, focus traits like "Performance" or "Readability", and verbosity).

### 2.2 Generation
Each agent in the population attempts to solve the given programming problem. The process is orchestrated through the **Multi-Agent Pipeline** (see Section 3).

### 2.3 Evaluation (Fitness Scoring)
Solutions are not simply graded on a Pass/Fail binary. They are executed inside a secure Docker **Sandbox** and assigned a quantitative **Fitness Score** based on multiple dimensions:
*   **Correctness (Test Cases):** Percentage of unit tests passed (strict multiplicative gate: 0 tests passed = 0.0 fitness).
*   **AST & Cyclomatic Complexity:** Static analysis of the Abstract Syntax Tree using `lizard` across Python, Java, and C++, with lexical decision-point fallback counting branches (`if`, `for`, `while`, `case`, `catch`, `&&`, `||`, `?`).
*   **Defensive Robustness:** Language-tailored defensive programming detection (`try/catch`, `null`, `nullptr`, `NULL`, `empty()`, `isEmpty()`).
*   **Execution Time:** Runtime efficiency relative to population boundaries.
*   **Memory Usage:** Resource constraints and peak memory footprint during execution.

### 2.4 Selection & Crossover
After evaluation, the population is ranked.
*   **Elitism:** The top-performing solutions (Elites) are preserved.
*   **Mutation:** The structural details and feedback of the Elites are injected into the prompts for the next generation. The LLM acts as the mutation engine, attempting to cross-pollinate successful strategies into even better code.

---

## 3. Specialized Multi-Agent Collaboration
Instead of relying on a monolithic prompt, the algorithm distributes cognitive load across a pipeline of specialized agents:

1.  **The TemplateAgent:** Produces clean, polyglot starter scaffolds and entry points for Python, Java, and C++.
2.  **The Architect:** Analyzes problem constraints and time/space complexity to formulate an algorithmic plan.
3.  **The Generator:** Translates the Architect's plan and relevant vector memory passages into executable source code.
4.  **The Reviewer:** Inspects candidate code prior to execution for subtle edge cases, off-by-one errors, or constraint violations.
5.  **The BugFixer:** Triggered *only* when the Sandbox detects a runtime crash, timeout, or failed test. Parses compiler and runtime stack traces to apply surgical patches.
6.  **The Optimizer:** Triggered *only* when code passes 100% of the tests. Refactors for cyclomatic complexity, memory footprint, and execution speed without breaking functional correctness.

---

## 4. Execution & Validation
Safety and determinism are enforced by the **Sandbox Engine**.
*   **Docker Isolation:** All generated code is executed inside temporary, isolated Docker containers to prevent malicious operations or system corruption.
*   **Resource Limits:** Hardcaps on execution time, memory, and CPU usage to prevent infinite loops and resource exhaustion.

---

## 5. Memory & Knowledge Synthesis
EvoGenesis is designed to learn over time across multiple runs without fine-tuning:
*   **Structured Reports:** Every generation produces a structured JSON report detailing the problem, the code, the fitness score, mutations, and the exact errors encountered.
*   **Memory Historian:** Distills reports into structured memory passages and indexes them for vector search.
*   **Semantic Vector Retrieval:** Uses TF-IDF unigram+bigram representations and cosine similarity to match current problem descriptions against historical experiences.
*   **Prioritization Dynamics:**
    - `balanced`: Blends successful implementation strategies with failure warnings.
    - `successes`: High-fitness exemplars prioritized for initial code generation.
    - `failures`: Failure modes and crash patterns prioritized for mutation and debugging.

---

## 6. Meta-Evolution (Recursive Self-Improvement)
The most advanced layer of the algorithm is its ability to upgrade its own source code when performance degrades.

### 6.1 The Watcher
Continuously monitors the rolling success rate across any agent (`generator.py`, `architect.py`, `reviewer.py`, `optimizer.py`, `bugfixer.py`, `template.py`). If the success rate drops below 50%, an `UpgradeTrigger` is emitted.

### 6.2 The CloneBuilder
Rather than blindly rewriting an entire file, the CloneBuilder extracts specific target methods (`plan`, `review`, `optimize`, `fix`, `_build_system_prompt`, `generate`) using Python `ast`. It spawns parallel LLM "Architect" agents to propose targeted patches to the method, dramatically reducing hallucination risks and generation time.

### 6.3 The SourceJudge
The proposed patches are reviewed by a panel of LLM judges that vote on the best implementation based on prompt engineering best practices and error-handling robustness.

### 6.4 The Referee (Static Safety Gate)
A hardcoded, non-LLM safety layer. The Referee parses the winning patch and blocks it if it contains syntax errors, disallowed imports (`requests`, `urllib`), or attempts to modify restricted files (`system_guard.py`, `sandbox.py`, `evoflow.py`). This ensures the system cannot irreparably corrupt itself.

### 6.5 The MetaArena (Rigorous Duel)
The surviving patch (Challenger) is pitted against the original source code (Original) in an isolated subprocess **Fast Duel** on the benchmark suite. Candidates are evaluated on normalized duel fitness:
$$\text{Score} = \text{clamp}_{[0, 1]}\left(0.45 \cdot \text{Mean Fitness} + 0.35 \cdot \text{Max Fitness} + 0.20 \cdot \text{Correctness Rate} - 0.10 \cdot \text{Crash Rate}\right)$$
If the Challenger achieves a higher normalized fitness score, it atomically replaces the Original file. If there is a tie or degradation, the system safely rolls back. The system has successfully evolved itself.