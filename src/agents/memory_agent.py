import json
import os
import glob
from src.client import EvoClient


MEMORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "memory", "agent_memory.txt"
)


class MemoryHistorianAgent:
    """
    The Memory Historian.

    This agent reads the raw structured JSON reports from `structured_reports/`,
    distils the key lessons learned (both from failures and successes) using an
    LLM, and appends a human-readable 'memory passage' to `memory/agent_memory.txt`.

    Both the agents and the user can read this file to understand what EvoCode has
    learned over time without having to wade through thousands of lines of JSON.
    """

    SYSTEM_PROMPT = (
        "You are a concise technical historian for an AI code-evolution system called EvoCode. "
        "Your job is to read a structured execution log summary and write a compact, insightful memory passage.\n\n"
        "The passage MUST:\n"
        "1. Start with a single-line summary: 'Problem: <title> | Result: <SOLVED/UNSOLVED> | Best Fitness: <score>'\n"
        "2. Describe what strategies WORKED (genome parameters, prompt styles, mutations that improved fitness).\n"
        "3. Describe what strategies FAILED and WHY (crashes, timeouts, wrong edge cases).\n"
        "4. Note any cross-language insights (e.g. 'The Java solution hashmap approach was successfully ported to Python').\n"
        "5. End with 1-2 actionable 'LESSON' lines that future agents should remember for similar problems.\n\n"
        "Format:\n"
        "---\n"
        "[MEMORY ENTRY - <timestamp>]\n"
        "Problem: <title> | Result: <SOLVED/UNSOLVED> | Best Fitness: <score>\n"
        "<2-4 paragraphs of insights>\n"
        "LESSON: <key takeaway>\n"
        "LESSON: <another key takeaway if needed>\n"
        "---\n\n"
        "Be concise. Each entry must be under 300 words. Do NOT include raw JSON or code blocks."
    )

    def __init__(self, client: EvoClient, memory_file: str = MEMORY_FILE, **kwargs):
        self.client = client
        self.memory_file = kwargs.get("memory_path", kwargs.get("db_path", memory_file))

    async def synthesize_latest(self, n_reports: int = 3) -> str:
        """
        Reads the `n_reports` most recent structured JSON reports, synthesizes
        memory passages for each, and appends them to `agent_memory.txt`.

        Returns the combined new memory text that was appended.
        """
        reports_dir = "structured_reports"
        report_files = sorted(
            glob.glob(os.path.join(reports_dir, "*.json")),
            key=os.path.getmtime,
            reverse=True
        )

        if not report_files:
            print("[MemoryHistorian] No structured reports found. Nothing to synthesize.")
            return ""

        already_logged = self._get_already_logged_files()
        new_files = [f for f in report_files if os.path.basename(f) not in already_logged]

        if not new_files:
            print("[MemoryHistorian] All recent reports have already been synthesized. Memory is up to date.")
            return ""

        files_to_process = new_files[:n_reports]
        print(f"[MemoryHistorian] Synthesizing {len(files_to_process)} new report(s)...")

        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)

        all_new_text = []
        for filepath in files_to_process:
            print(f"  -> Processing: {os.path.basename(filepath)}")
            try:
                entry_text = await self._synthesize_single_report(filepath)
                if entry_text:
                    all_new_text.append(entry_text)
                    self._append_to_memory_file(entry_text, os.path.basename(filepath))
            except Exception as e:
                print(f"  [MemoryHistorian] ERROR processing {os.path.basename(filepath)}: {e}")

        combined = "\n\n".join(all_new_text)
        print(f"[MemoryHistorian] Done. Memory file updated at: {MEMORY_FILE}")
        return combined

    async def _synthesize_single_report(self, filepath: str) -> str:
        """
        Loads a single JSON report, strips it down to its essentials to fit in the
        LLM context window, then generates a memory passage.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            report = json.load(f)

        summary = self._build_report_summary(report, filepath)

        user_prompt = (
            "Here is a compact summary of an EvoCode execution log. "
            f"Please synthesize a memory passage from it:\n\n{summary}"
        )

        response = await self.client.create_completion(
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )

        return response["content"].strip()

    def _build_report_summary(self, report: dict, filepath: str) -> str:
        """
        Extracts the most informative fields from the report JSON into a compact
        text summary suitable for sending to the LLM.
        """
        lines = []
        lines.append(f"Report File: {os.path.basename(filepath)}")
        lines.append(f"Mode: {report.get('mode', 'unknown')}")
        lines.append(f"Population Size: {report.get('pop_size', '?')}")
        lines.append(f"Run Start: {report.get('start_time', '?')}")
        lines.append(f"Run End: {report.get('end_time', '?')}")
        lines.append("")

        for prob in report.get("problems_evaluated", []):
            prob_id = prob.get("problem_id", "?")
            lines.append(f"=== Problem ID: {prob_id} ===")

            generations = prob.get("generations", [])
            lines.append(f"Generations Run: {len(generations)}")

            best_fitness_overall = 0.0
            circuit_broken = False

            for gen in generations:
                gen_id = gen.get("generation_id", "?")
                if gen.get("circuit_breaker_triggered"):
                    circuit_broken = True

                for ev in gen.get("evaluations", []):
                    fitness_val = ev.get("fitness", {}).get("fitness_value", 0.0)
                    if fitness_val > best_fitness_overall:
                        best_fitness_overall = fitness_val

                    genome = ev.get("gen_genome_snapshot", {})
                    tr = ev.get("test_results", {})
                    diag = ev.get("critic_diagnosis", {})
                    passed = tr.get("passed_tests", 0)
                    total = tr.get("total_tests", 0)
                    crashes = len(tr.get("crash_tests", []))
                    timeouts = len(tr.get("timeout_tests", []))

                    lines.append(
                        f"  Gen {gen_id} | Genome {ev.get('genome_index', '?')} | "
                        f"Style: {genome.get('prompt_style')} | Temp: {genome.get('temperature')} | "
                        f"Variant: {genome.get('system_instruction_variant')} | "
                        f"Pass: {passed}/{total} | Crashes: {crashes} | Timeouts: {timeouts} | "
                        f"Fitness: {fitness_val:.4f} | Failure: {diag.get('primary_failure', 'none')} | "
                        f"Mutations: {diag.get('recommended_mutations', [])}"
                    )

                sb = gen.get("selection_and_breeding", {})
                if sb:
                    lines.append(
                        f"  Gen {gen_id} Selection -> Survivors: {sb.get('survivors')} | "
                        f"Killed: {sb.get('killed')}"
                    )
                    for mut in sb.get("mutations", []):
                        pg = mut.get("parent_genome", {})
                        cg = mut.get("child_genome", {})
                        lines.append(
                            f"    Mutation: parent(style={pg.get('prompt_style')}, temp={pg.get('temperature')}) "
                            f"-> child(style={cg.get('prompt_style')}, temp={cg.get('temperature')}, "
                            f"variant={cg.get('system_instruction_variant')})"
                        )

            result_str = "SOLVED" if circuit_broken or best_fitness_overall >= 1.0 else "UNSOLVED"
            idx = next(
                (i for i, l in enumerate(lines) if l == f"=== Problem ID: {prob_id} ==="),
                len(lines) - 1
            )
            lines.insert(idx + 2, f"Result: {result_str} | Best Fitness: {best_fitness_overall:.4f}")
            lines.append("")

        return "\n".join(lines)

    def _get_already_logged_files(self) -> set:
        """
        Reads memory/agent_memory.txt and returns the set of report filenames
        that have already been processed (tracked via hidden sentinel lines).
        """
        if not os.path.exists(MEMORY_FILE):
            return set()
        logged = set()
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("# SOURCE_REPORT:"):
                    logged.add(line.split(":", 1)[-1].strip())
        return logged

    def _append_to_memory_file(self, entry_text: str, source_filename: str = "", memory_file: str | None = None):
        """
        Appends a synthesized memory entry to the memory file,
        along with a hidden sentinel line for tracking which reports have been logged.
        """
        target = memory_file or getattr(self, "memory_file", MEMORY_FILE)
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(f"\n---\n{entry_text.strip()}\n---\n")
            if source_filename:
                f.write(f"# SOURCE_REPORT:{source_filename}\n\n")

    def append_entry(self, entry_text: str, source_filename: str = ""):
        """Convenience method to append an entry to the agent's memory file."""
        self._append_to_memory_file(entry_text, source_filename)

    @classmethod
    def parse_memory_entries(cls, memory_file: str = MEMORY_FILE) -> list[str]:
        """Parses all memory entries from the specified memory file."""
        if not os.path.exists(memory_file):
            return []
        with open(memory_file, "r", encoding="utf-8") as f:
            lines = [line for line in f.readlines() if not line.startswith("# SOURCE_REPORT:")]
        full_text = "".join(lines).strip()
        if not full_text:
            return []
        raw_segments = full_text.split("---")
        return [seg.strip() for seg in raw_segments if seg.strip()]

    @classmethod
    def search_memory(
        cls,
        query: str,
        max_entries: int = 5,
        prioritization: str = "balanced",
        memory_file: str = MEMORY_FILE
    ) -> list[str]:
        """
        Performs semantic vector search across historical memory passages
        using TF-IDF cosine similarity with prioritization weighting.

        Args:
            query: Problem description or keywords to match against.
            max_entries: Maximum entries to return.
            prioritization: 'balanced', 'successes', or 'failures'.
            memory_file: Path to memory file to search.
        """
        entries = cls.parse_memory_entries(memory_file=memory_file)
        if not entries:
            return []
        if not query or not query.strip():
            return entries[-max_entries:]

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                token_pattern=r"(?u)\b\w+\b"
            )
            corpus = entries + [query]
            tfidf_matrix = vectorizer.fit_transform(corpus)

            doc_vectors = tfidf_matrix[:-1]
            query_vector = tfidf_matrix[-1:]

            similarities = cosine_similarity(query_vector, doc_vectors)[0]

            scored_entries = []
            for idx, entry in enumerate(entries):
                sim = float(similarities[idx])
                is_solved = "Result: SOLVED" in entry or "RESULT: SOLVED" in entry or "Result: Solved" in entry
                
                # Apply prioritization bonuses
                if prioritization == "successes" and is_solved:
                    sim += 0.25
                elif prioritization == "failures" and not is_solved:
                    sim += 0.25

                scored_entries.append((sim, idx, entry, is_solved))

            if prioritization == "balanced" and max_entries >= 2:
                # Select a balanced mix of best-matching successes and best-matching failures
                successes = sorted([e for e in scored_entries if e[3]], key=lambda x: x[0], reverse=True)
                failures = sorted([e for e in scored_entries if not e[3]], key=lambda x: x[0], reverse=True)

                half = max_entries // 2
                chosen = successes[:half] + failures[:(max_entries - half)]
                # If one category doesn't have enough entries, fill with the other
                if len(chosen) < max_entries:
                    remaining = [e for e in sorted(scored_entries, key=lambda x: x[0], reverse=True) if e not in chosen]
                    chosen += remaining[:(max_entries - len(chosen))]
                chosen.sort(key=lambda x: x[0], reverse=True)
                return [c[2] for c in chosen[:max_entries]]

            # Standard similarity rank
            scored_entries.sort(key=lambda x: x[0], reverse=True)
            return [e[2] for e in scored_entries[:max_entries]]

        except Exception as e:
            # Fallback to recent entries if vectorization fails
            return entries[-max_entries:]

    @classmethod
    def load_memory(
        cls,
        max_entries: int = 5,
        query: str | None = None,
        strategy: str = "similarity_search",
        prioritization: str = "balanced",
        memory_file: str = MEMORY_FILE
    ) -> str:
        """
        Retrieves relevant memory passages.
        If query is provided and strategy in ('similarity_search', 'vector', 'failure_focused'),
        uses semantic vector search. Otherwise falls back to recent entries.
        """
        if not os.path.exists(memory_file):
            return ""

        strat = (strategy or "").lower()
        if query and strat in ("similarity_search", "vector", "failure_focused"):
            selected = cls.search_memory(
                query,
                max_entries=max_entries,
                prioritization=prioritization,
                memory_file=memory_file
            )
        else:
            entries = cls.parse_memory_entries(memory_file=memory_file)
            if not entries or max_entries == 0:
                return "\n---\n".join(entries)
            selected = entries[-max_entries:]

        return "\n---\n".join(selected)

