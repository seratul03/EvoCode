<div align="center">
  <h1>🧬 EvoGenesis</h1>
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

**EvoGenesis** (formerly EvoCode) is an advanced AI code generation system that moves beyond simple zero-shot prompting. By employing a **co-evolutionary multi-agent architecture**, EvoGenesis generates, tests, critiques, and mutates code solutions across multiple programming languages (Python, Java, C++) simultaneously.

Instead of relying on a single LLM call to get it right, EvoGenesis simulates a Darwinian process:
- A **population of specialized agents** plans, writes, and reviews code.
- A **secure Docker Sandbox** executes the code against test cases to evaluate fitness (Correctness, AST Complexity, Time/Memory).
- A **Feedback Loop** allows the algorithm to learn over time by synthesizing memory from past runs.
- **Meta-Evolution:** The system actively monitors its own source code's success rate and can dynamically rewrite, test, and upgrade itself.

EvoGenesis is an engine for discovery, designed to solve complex programming puzzles autonomously.

---

## ✨ Key Features

- 🌐 **Polyglot Code Generation:** Natively supports evaluating and evolving Python, Java, and C++ code within the same population.
- 🛡️ **Secure Docker Sandboxing:** All AI-generated code is executed in an isolated, network-disabled Docker container (`evocode-sandbox`).
- 🧠 **Multi-Agent Pipeline:** Distributes cognitive load across an Architect, Generator, Reviewer, Optimizer, and BugFixer.
- 📚 **Historical Memory Synthesis:** Aggregates run data into long-term Insights to guide future generations.
- 🧬 **Meta-Evolution:** The system can rewrite its own Python source files when performance degrades, validating the changes in an isolated Arena duel.
- 🔄 **3-Tier LLM Fallback Chain:** Robust API handling that tries Groq Cloud (rotating keys), falls back to Ollama (Local LLMs), and ultimately OpenRouter.

---

## 💻 System Requirements

To run EvoGenesis, your system must meet the following prerequisites:

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
The primary way to use EvoGenesis is to let it run autonomously across a series of generated problems, synthesize memory, and trigger meta-evolution.

```bash
python run_autonomous.py --runs 5 --gens 3
```
You can disable specific features if you want a faster, isolated run:
```bash
python run_autonomous.py --disable-memory --skip-meta-evolution
```

### Interactive Chat Mode
For on-the-fly problem solving:
```bash
python chat.py
```

---

## 📁 Project Structure

```text
EvoCode/
├── .env                    # Environment variables (API keys, config)
├── Dockerfile.sandbox      # Dockerfile for the secure execution environment
├── run_autonomous.py       # Main autonomous runner script
├── chat.py                 # Interactive terminal UI entrypoint
├── requirements.txt        # Python dependencies
├── src/                    # Source code directory
│   ├── agents/             # The Co-Evolutionary AI Agents (Architect, Generator, etc)
│   ├── meta_evolution/     # Self-Improvement Engine (Watcher, CloneBuilder, etc)
│   ├── client.py           # 3-Tier Fallback LLM Client
│   ├── evoflow.py          # The Core Orchestrator for the evolutionary pipeline
│   ├── sandbox.py          # Docker execution and test harness injection
│   └── memory_manager.py   # Historical Insight synthesis
├── config/                 # System configuration files
└── structured_reports/     # Generated JSON reports from EvoFlow runs
```

---

## 🏗️ System Architecture Overview
Read the detailed [Algorithm Specification](algorithm.md) and [Architecture Design](architecture.md) for a deep dive into how EvoGenesis works.

---

## 🧬 Evolutionary Agents & Pipeline

Instead of a monolithic prompt, EvoGenesis uses specialized agents:
1. **Architect:** Proposes a high-level solution design.
2. **Generator:** Translates the design into source code.
3. **Reviewer:** Critiques the generated code.
4. **Optimizer:** Refines for performance and readability.
5. **BugFixer:** Patches code based on sandbox runtime traces.
6. **Memory Historian:** Synthesizes insights from past runs.

---

## 🤖 Meta-Evolution (Recursive Self-Improvement)
EvoGenesis can rewrite its own source code when success rates drop below 50%.
- **CloneBuilder:** Extracts the underperforming logic and generates targeted patches via LLMs.
- **SourceJudge:** Selects the best patch.
- **Referee:** Static analysis safety gate to prevent corruption.
- **MetaArena:** Fast Duel validation. The new patch must beat the original in a test run to be saved.

---

## ⚙️ Configuration

| Variable | Description | Example |
|---|---|---|
| `GROQ_API_KEYS` | Comma-separated list of Groq API keys. | `gsk_xxx,gsk_yyy` |
| `GROQ_MODEL` | The LLM model to use on Groq. | `llama-3.1-70b-versatile` |
| `OLLAMA_BASE_URL` | Local endpoint for Ollama (Tier 2). | `http://localhost:11434/v1` |
| `OPENROUTER_API_KEY` | Tier 3 fallback cloud provider key. | `sk-or-v1-xxx` |