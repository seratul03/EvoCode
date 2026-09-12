# EvoGenesis Algorithm Specification

## 1. Executive Summary
EvoGenesis is a **Recursive Evolutionary AI Engine**. It moves beyond standard single-prompt LLM generation by structuring software development as an evolutionary process. The algorithm merges genetic algorithms, multi-agent debate, continuous learning (memory synthesis), and recursive self-improvement (Meta-Evolution).

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
*   **Correctness (Test Cases):** Percentage of unit tests passed.
*   **AST Complexity:** Static analysis of the Abstract Syntax Tree (cyclomatic complexity, nesting depth).
*   **Execution Time:** Runtime efficiency of the solution.
*   **Memory Usage:** Resource constraints during execution.

### 2.4 Selection & Crossover
After evaluation, the population is ranked.
*   **Elitism:** The top-performing solutions (Elites) are preserved.
*   **Mutation:** The structural details and feedback of the Elites are injected into the prompts for the next generation. The LLM acts as the mutation engine, attempting to cross-pollinate successful strategies into even better code.

---

## 3. Specialized Multi-Agent Collaboration
Instead of relying on a monolithic prompt, the algorithm distributes cognitive load across a pipeline of specialized agents.

1.  **The Architect:** Analyzes the problem and proposes a high-level structural design.
2.  **The Generator:** Takes the Architect's design and writes the initial source code.
3.  **The Reviewer:** Critiques the generated code for edge cases and logic flaws.
4.  **The Optimizer:** Refactors the code for performance and readability.
5.  **The BugFixer:** Triggered *only* if the Sandbox detects a runtime or logical error. It reads the stack trace and patches the code.

---

## 4. Execution & Validation
Safety and determinism are enforced by the **Sandbox Engine**.
*   **Docker Isolation:** All generated code is executed inside temporary, isolated Docker containers to prevent malicious operations or system corruption.
*   **Resource Limits:** Hardcaps on execution time, memory, and CPU usage to prevent infinite loops and resource exhaustion.

---

## 5. Memory & Knowledge Synthesis
EvoGenesis is designed to learn over time across multiple runs.
*   **Structured Reports:** Every generation produces a structured JSON report detailing the problem, the code, the fitness score, and the exact errors encountered.
*   **Memory Historian:** Periodically, the algorithm aggregates all structured reports and synthesizes them into "Insights" (e.g., "The model consistently struggles with dynamic programming array bounds").
*   **Feedback Loop:** These synthesized insights are loaded at runtime and injected into the system prompts of the Generator and Reviewer, effectively giving the algorithm long-term memory without requiring model fine-tuning.

---

## 6. Meta-Evolution (Recursive Self-Improvement)
The most advanced layer of the algorithm is its ability to upgrade its own source code when performance degrades.

### 6.1 The Watcher
Continuously monitors the rolling success rate of specific AI agents (e.g., `generator.py`). If the success rate drops below a defined threshold, Meta-Evolution is triggered.

### 6.2 The CloneBuilder
Rather than blindly rewriting the entire agent, the CloneBuilder extracts specific target methods (using Python `ast`). It spawns parallel LLM "Architect" agents to propose targeted patches to the method, dramatically reducing hallucination risks and generation time.

### 6.3 The SourceJudge
The proposed patches are reviewed by a panel of LLM judges that vote on the best implementation based on prompt engineering best practices and error-handling robustness.

### 6.4 The Referee (Static Safety Gate)
A hardcoded, non-LLM safety layer. The Referee parses the winning patch and blocks it if it contains syntax errors, disallowed imports, or attempts to modify restricted files. This ensures the system cannot irreparably corrupt itself.

### 6.5 The MetaArena (Fast Duel)
The surviving patch (Challenger) is pitted against the original source code (Original) in a lightweight, isolated **Duel**. Both versions attempt to solve a baseline problem. If the Challenger achieves a higher fitness score, it atomically replaces the Original file. The system has successfully evolved itself.