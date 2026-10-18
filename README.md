<div align="center">
  <h1>🧬 EvoCode</h1>
  <p><strong>A Recursive Evolutionary AI Engine for Code Generation & Self-Improvement</strong></p>
  <p>Multi-agent, multi-language, sandbox-secured code generation powered by genetic algorithms and meta-evolution.</p>
</div>

---

## 📑 Table of Contents
1. [Introduction](#-introduction)
2. [Key Features](#-key-features)
3. [System Requirements](#-system-requirements)
4. [Installation & Setup](#-installation--setup)
5. [Usage Instructions](#-usage-instructions)
    - [Autonomous Mode](#autonomous-mode)
    - [Interactive Chat Mode](#interactive-chat-mode)
6. [Project Structure](#-project-structure)
7. [System Architecture Overview](#-system-architecture-overview)
8. [Evolutionary Agents & Pipeline](#-evolutionary-agents--pipeline)
9. [Meta-Evolution (Recursive Self-Improvement)](#-meta-evolution-recursive-self-improvement)
10. [Configuration (Environment Variables)](#-configuration)
11. [Troubleshooting & Logs](#-troubleshooting--logs)
12. [License](#-license)

---

## 🚀 Introduction

**EvoCode** is an advanced AI code generation system that moves beyond simple zero-shot prompting. By employing a **co-evolutionary multi-agent algorithm (EvoGenesis)**, EvoCode generates, tests, critiques, and mutates code solutions across multiple programming languages (Python, Java, C++) simultaneously.

Instead of relying on a single LLM call to get it right, EvoCode simulates a Darwinian process:
- A **population of specialized agents** plans, writes, and reviews code.
- A **secure Docker Sandbox** executes the code against test cases to evaluate fitness (Correctness, AST Complexity, Time/Memory).
- A **Feedback Loop** allows the algorithm to learn over time by synthesizing memory from past runs.
- **Meta-Evolution:** The system actively monitors its own source code's success rate and can dynamically rewrite, test, and upgrade itself.

EvoCode is an engine for discovery, designed to solve complex programming puzzles autonomously.

---

## ✨ Key Features

- 🌐 **Polyglot Code Generation & Complexity:** Natively generates, tests, and evaluates Python, Java, and C++ code within the same population. Features polyglot cyclomatic complexity calculation using `lizard` with lexical AST branch fallbacks.
- 🛡️ **Secure Docker Sandboxing:** AI-generated code is executed in an isolated, network-disabled Docker container (`evocode-sandbox`). Every candidate runs in a dedicated ephemeral workspace to prevent state leakage.
- 🧠 **Multi-Agent Pipeline (Agency Layer):** Distributes cognitive load across dedicated personas: `ArchitectAgent` (high-level algorithmic plan), `GeneratorAgent` (code generation), `ReviewerAgent` (pre-execution critique), `BugFixerAgent` (stack-trace debugging), and `OptimizerAgent` (post-correctness complexity refactoring).
- 📚 **Semantic Vector Memory Retrieval:** Vector search powered by TF-IDF unigram+bigram representations and cosine similarity over historical memory passages, with experience prioritization for `"balanced"`, `"successes"`, and `"failures"`.
- 🧬 **Generalized Meta-Evolution:** The system actively monitors all its agents (`generator.py`, `architect.py`, `reviewer.py`, `optimizer.py`, `bugfixer.py`, `template.py`). When performance degrades below threshold, it dynamically extracts underperforming methods, proposes patches, verifies safety via static referee gates, and validates them in Fast Duels scored by normalized multi-factor duel fitness.
- 🧪 **Scientific Benchmarking:** Evaluate performance using built-in 100-problem datasets, reproducible random seeds, and population diversity tracking (fitness variance/mean).
- 📊 **Baseline Comparisons:** Built-in flags to compare EvoCode against standard LLM paradigms (Single-Shot, Iterative, and Static Population).
- 🔄 **3-Tier LLM Fallback Chain:** Robust API handling that tries Ollama (Local LLM, Tier 1), falls back to Groq Cloud (rotating keys, Tier 2), and ultimately OpenRouter (Tier 3).
- ✅ **Comprehensive Test Suite:** 107/107 automated unit and integration tests passing across 20 development phases.

---

## 💻 System Requirements

To run EvoCode, your system must meet the following prerequisites:

1. **Operating System:** Windows 10/11, macOS, or Linux.
2. **Python:** Version 3.10 or higher.
3. **Docker Engine:** Docker Desktop (Windows/Mac) or Docker Daemon (Linux) MUST be installed and running.
4. **API Keys:**
   - Groq API Key (Primary LLM provider, extremely fast).
   - OpenRouter API Key (Optional, used as a cloud fallback).
5. **Local LLM (Optional but Recommended):** Ollama installed with a running model.

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/EvoCode.git
cd EvoCode
```

### 2. Create a Virtual Environment
```bash
python -m venv evo_env
```
Activate the environment:
- **Windows:** `evo_env\Scripts\activate`
- **macOS/Linux:** `source evo_env/bin/activate`

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup the Docker Sandbox
Build the image using the provided Dockerfile:
```bash
docker build -t evocode-sandbox -f Dockerfile.sandbox .
```

### 5. Configure Environment Variables
Copy the sample environment file and insert your API keys:
```bash
cp .env.example .env
```

---

## 🎮 Usage Instructions

### Autonomous Mode
The primary way to use EvoCode is to let it run autonomously across a series of generated problems, synthesize memory, and trigger meta-evolution.

```bash
python run_autonomous.py --runs 5 --gens 3 --dataset benchmark_suite.json
```
You can test the performance of the system against standard LLM approaches using the baseline flag:
```bash
python run_autonomous.py --dataset test_dummy2.json --baseline single-shot
# Options: single-shot, iterative, static-pop, none
```
You can enforce strict reproducibility for experiments:
```bash
python run_autonomous.py --dataset test_dummy2.json --seed 42
```
You can disable specific features for ablation studies or isolated runs:
```bash
python run_autonomous.py --disable-memory --disable-critic --disable-mutation --skip-meta-evolution
```

### Interactive Chat Mode
For on-the-fly problem solving:
```bash
python chat.py
```

### Running the Test Suite
Run the full 107-test suite to verify the entire system:
```bash
pytest tests/
```
Or test specific phases:
```bash
pytest tests/test_phase19_agency_layer.py -v       # Agency Layer
pytest tests/test_phase20_polyglot_and_meta.py -v   # Polyglot AST, Vector Memory, Meta-Evolution
```

---

## 📁 Project Structure

```text
EvoCode/
├── .env                    # Environment variables (API keys, config)
├── Dockerfile.sandbox      # Dockerfile for the secure execution environment
├── run_autonomous.py       # Main autonomous runner script
├── chat.py                 # Interactive terminal UI entrypoint
├── requirements.txt        # Python dependencies (lizard, scikit-learn, etc.)
├── src/                    # Source code directory
│   ├── agents/             # The Co-Evolutionary AI Agents
│   │   ├── architect.py    # ArchitectAgent: Solution design & algorithmic planning
│   │   ├── generator.py    # GeneratorAgent: Polyglot code generation with vector memory
│   │   ├── reviewer.py     # ReviewerAgent: Pre-execution critique & flaw detection
│   │   ├── optimizer.py    # OptimizerAgent: Post-correctness complexity refactoring
│   │   ├── bugfixer.py     # BugFixerAgent: Stack-trace diagnosis & targeted patching
│   │   ├── template.py     # TemplateAgent: Multi-language function scaffolding
│   │   ├── evaluators.py   # Polyglot AST/Cyclomatic Complexity & Robustness Evaluators
│   │   ├── memory_agent.py # MemoryHistorianAgent: Vector memory synthesis & retrieval
│   │   └── mutator.py      # MutatorAgent: Targeted failure-driven genetic mutations
│   ├── meta_evolution/     # Self-Improvement Engine
│   │   ├── watcher.py      # Watcher: Multi-agent performance monitoring & triggers
│   │   ├── clone_builder.py# CloneBuilder: Dynamic AST method extraction & rewriting
│   │   ├── source_judge.py # SourceJudge: LLM committee voting on proposed patches
│   │   ├── referee.py      # Referee: AST static safety verification gate
│   │   └── meta_arena.py   # MetaArena: Subprocess Fast Duel with normalized fitness
│   ├── orchestration/      # Evolutionary Orchestration Modules
│   │   ├── evaluator.py    # EvoEvaluator: Population evaluation with agency pipeline
│   │   ├── breeder.py      # EvoBreeder: Selection, crossover & genome breeding
│   │   └── crossover.py    # Cross-language strategy translation
│   ├── client.py           # 3-Tier Fallback LLM Client (Ollama -> Groq -> OpenRouter)
│   ├── evoflow.py          # The Core Orchestrator for the evolutionary pipeline
│   ├── fitness_scorer.py   # Multiplicative Fitness Scorer (Correctness × Quality)
│   └── sandbox.py          # Docker execution and test harness injection
├── config/                 # System configuration files
├── memory/                 # Persistent distilled agent memory passages
├── structured_reports/     # Generated JSON reports from EvoFlow runs
└── tests/                  # Automated pytest test suites (Phases 1-20, 107 tests)
```

---

## 🏗️ System Architecture Overview
Read the detailed [Algorithm Specification](algorithm.md) and [Architecture Design](architecture.md) for a deep dive into how the EvoGenesis algorithm powers EvoCode.

---

## 🧬 Evolutionary Agents & Pipeline

Instead of a monolithic prompt, EvoCode uses specialized collaborating agents structured into a coherent agency lifecycle:
1. **TemplateAgent:** Generates clean polyglot function signatures and scaffolds for Python, Java, and C++.
2. **ArchitectAgent:** Deconstructs the problem statement, time/space constraints, and produces a concrete algorithmic blueprint.
3. **GeneratorAgent:** Translates the Architect's plan and relevant historical vector memory into complete executable source code.
4. **ReviewerAgent:** Pre-execution verification that inspects candidate code for subtle logical errors, edge cases, off-by-one errors, or type mismatches.
5. **Docker Sandbox Execution:** Executes candidates inside ephemeral, network-isolated containers against public and ephemeral tests.
6. **BugFixerAgent:** Triggered *only* when sandbox execution encounters crashes, timeouts, or test failures. Reads the exact stack trace and applies targeted surgical patches.
7. **OptimizerAgent:** Triggered *only* when candidate code passes all test cases. Refactors the solution for cyclomatic complexity, memory usage, and runtime efficiency without altering correctness.
8. **Fitness Scorer:** Evaluates multi-dimensional fitness:
   $$\text{Fitness} = \text{Correctness Rate} \times \left(0.30 \cdot \text{Runtime} + 0.20 \cdot \text{Memory} + 0.20 \cdot \text{Efficiency} + 0.20 \cdot \text{Complexity} + 0.10 \cdot \text{Robustness}\right)$$
9. **Memory Historian:** Distills run reports into memory passages and indexes them for vector search.

---

## 🤖 Meta-Evolution (Recursive Self-Improvement)
EvoCode can rewrite its own Python source files when performance degrades:
- **Watcher:** Monitors rolling success rates of any system agent (`generator`, `architect`, `reviewer`, `optimizer`, `bugfixer`, `template`). If the rate drops below 50%, an `UpgradeTrigger` is emitted.
- **CloneBuilder:** Dynamically parses the target agent source with `ast`, extracts the target method (`plan`, `review`, `optimize`, `fix`, `_build_system_prompt`, `generate`), and generates two concurrent improved candidate patches.
- **SourceJudge:** LLM committee selects the superior proposal.
- **Referee:** Hard static safety gate (AST parsing) that blocks syntax errors, prohibited network imports (`requests`, `urllib`), and unauthorized filesystem access.
- **MetaArena:** Fast Duel validation. The challenger runs against the original in an isolated subprocess on the benchmark suite. Candidates are ranked using normalized duel fitness:
  $$\text{Score} = \text{clamp}_{[0, 1]}\left(0.45 \cdot \text{Mean Fitness} + 0.35 \cdot \text{Max Fitness} + 0.20 \cdot \text{Correctness Rate} - 0.10 \cdot \text{Crash Rate}\right)$$
  If the challenger wins, it is atomically promoted to overwrite the original agent file; otherwise, the original survives and changes are cleanly rolled back.

---

## ⚙️ Configuration

| Variable | Description | Example |
|---|---|---|
| `OLLAMA_BASE_URL` | Local endpoint for Ollama (Tier 1 primary). | `http://localhost:11434/v1` |
| `OLLAMA_MODEL` | The local model name to use. | `llama3` |
| `GROQ_API_KEYS` | Comma-separated list of Groq API keys (Tier 2). | `gsk_xxx,gsk_yyy` |
| `GROQ_MODEL` | The LLM model to use on Groq. | `llama-3.1-70b-versatile` |
| `OPENROUTER_API_KEY` | Tier 3 fallback cloud provider key. | `sk-or-v1-xxx` |
