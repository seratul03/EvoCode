import sqlite3
import json
from datetime import datetime
import os

class EventLogger:
    def __init__(self, db_path: str = "results/evocode.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self):
        cursor = self.conn.cursor()
        
        # 1. LLM Calls (Generator & Code Validator only)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS llm_calls (
                call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_type TEXT,
                problem_id INTEGER,
                generation_id INTEGER,
                genome_snapshot TEXT,
                prompt TEXT,
                response TEXT,
                tokens_used INTEGER,
                model_used TEXT,
                timestamp DATETIME
            )
        ''')
        
        # 2. Test Results (Sandbox execution)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id INTEGER,
                generation_id INTEGER,
                generator_id INTEGER,
                passed_tests INTEGER,
                total_tests INTEGER,
                failed_test_ids TEXT,
                timeout_tests TEXT,
                crash_tests TEXT,
                execution_time_ms REAL,
                peak_memory_kb REAL,
                timestamp DATETIME
            )
        ''')
        
        # 3. Fitness Scores
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fitness_scores (
                score_id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_type TEXT,
                agent_id INTEGER,
                generation_id INTEGER,
                problem_id INTEGER,
                fitness_value REAL,
                breakdown TEXT,
                timestamp DATETIME
            )
        ''')
        
        # 4. Mutations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mutations (
                mutation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_type TEXT,
                agent_id INTEGER,
                generation_id INTEGER,
                genome_before TEXT,
                genome_after TEXT,
                mutation_type TEXT,
                reason TEXT,
                fitness_before REAL,
                fitness_after REAL,
                timestamp DATETIME
            )
        ''')
        
        # 5. Agent Genomes (Snapshots)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_genomes (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_type TEXT,
                agent_id INTEGER,
                generation_id INTEGER,
                genome_json TEXT,
                parent_id INTEGER,
                timestamp DATETIME
            )
        ''')
        
        # 6. Critic Feedback
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS critic_feedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id INTEGER,
                generation_id INTEGER,
                failure_type TEXT,
                severity REAL,
                code_issues TEXT,
                suggested_mutations TEXT,
                timestamp DATETIME
            )
        ''')
        
        # 7. Validation Results (Code Validator LLM)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS validation_results (
                validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id INTEGER,
                generation_id INTEGER,
                is_correct BOOLEAN,
                confidence REAL,
                issues_found TEXT,
                tokens_used INTEGER,
                timestamp DATETIME
            )
        ''')
        
        # Create composite indices as recommended in evo.md
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_llm_calls_prob_gen ON llm_calls(problem_id, generation_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_results_prob_gen ON test_results(problem_id, generation_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fitness_scores_prob_gen ON fitness_scores(problem_id, generation_id)')
        
        self.conn.commit()

    def log_llm_call(self, agent_type: str, problem_id: int, generation_id: int, genome_snapshot: dict, prompt: str, response: str, tokens_used: int, model_used: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO llm_calls (agent_type, problem_id, generation_id, genome_snapshot, prompt, response, tokens_used, model_used, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (agent_type, problem_id, generation_id, json.dumps(genome_snapshot), prompt, response, tokens_used, model_used, datetime.utcnow()))
        self.conn.commit()

    def log_test_result(self, problem_id: int, generation_id: int, generator_id: int, passed: int, total: int, failed_ids: list, timeout_ids: list, crash_ids: list, exec_ms: float, peak_mem: float):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO test_results (problem_id, generation_id, generator_id, passed_tests, total_tests, failed_test_ids, timeout_tests, crash_tests, execution_time_ms, peak_memory_kb, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (problem_id, generation_id, generator_id, passed, total, json.dumps(failed_ids), json.dumps(timeout_ids), json.dumps(crash_ids), exec_ms, peak_mem, datetime.utcnow()))
        self.conn.commit()

    def log_fitness(self, agent_type: str, agent_id: int, generation_id: int, problem_id: int, fitness_value: float, breakdown: dict):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO fitness_scores (agent_type, agent_id, generation_id, problem_id, fitness_value, breakdown, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (agent_type, agent_id, generation_id, problem_id, fitness_value, json.dumps(breakdown), datetime.utcnow()))
        self.conn.commit()

    def log_mutation(self, agent_type: str, agent_id: int, generation_id: int, genome_before: dict, genome_after: dict, mutation_type: str, reason: str, fitness_before: float, fitness_after: float):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO mutations (agent_type, agent_id, generation_id, genome_before, genome_after, mutation_type, reason, fitness_before, fitness_after, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (agent_type, agent_id, generation_id, json.dumps(genome_before), json.dumps(genome_after), mutation_type, reason, fitness_before, fitness_after, datetime.utcnow()))
        self.conn.commit()

    def log_genome(self, agent_type: str, agent_id: int, generation_id: int, genome_json: dict, parent_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO agent_genomes (agent_type, agent_id, generation_id, genome_json, parent_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (agent_type, agent_id, generation_id, json.dumps(genome_json), parent_id, datetime.utcnow()))
        self.conn.commit()

    def log_critic(self, problem_id: int, generation_id: int, failure_type: str, severity: float, code_issues: list, suggested_mutations: list):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO critic_feedback (problem_id, generation_id, failure_type, severity, code_issues, suggested_mutations, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (problem_id, generation_id, failure_type, severity, json.dumps(code_issues), json.dumps(suggested_mutations), datetime.utcnow()))
        self.conn.commit()

    def log_validation(self, problem_id: int, generation_id: int, is_correct: bool, confidence: float, issues_found: str, tokens_used: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO validation_results (problem_id, generation_id, is_correct, confidence, issues_found, tokens_used, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (problem_id, generation_id, is_correct, confidence, issues_found, tokens_used, datetime.utcnow()))
        self.conn.commit()

    def close(self):
        self.conn.close()
