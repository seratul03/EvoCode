"""
test_meta_evolution_live.py
===========================
Live integration test for Phase 17: Meta-Evolution.

This script force-triggers the meta-evolution pipeline by setting the Watcher
threshold to 0.99 (impossible to beat naturally), then runs every component
end-to-end with real LLM calls.

What you will see:
  [Stage 1] Watcher:      Reads reports, detects "degraded" performance (forced).
  [Stage 2] CloneBuilder: Two Architect LLMs rewrite src/agents/generator.py.
  [Stage 3] SourceJudge:  Two Judge LLMs vote on the best proposal.
  [Stage 4] Referee:      Hardcoded safety check (syntax, imports, paths).
  [Stage 5] MetaArena:    Fast Duel — Original vs. Challenger on 1 problem.
  [Result]  Winner survives. generator.py is upgraded (or kept if challenger lost).

Usage:
    python test_meta_evolution_live.py

Safety:
  - The original src/agents/generator.py is backed up before the duel.
  - If anything goes wrong, the backup is automatically restored.
  - Nothing outside src/agents/ or staging/ is touched.
"""

import asyncio
import os
import sys
import shutil
import time
import warnings

# Suppress harmless Windows asyncio pipe cleanup warning
warnings.filterwarnings("ignore", category=ResourceWarning)

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.client import EvoClient
from src.meta_evolution.watcher import Watcher, UpgradeTrigger
from src.meta_evolution.clone_builder import CloneBuilder
from src.meta_evolution.source_judge import SourceJudge
from src.meta_evolution.referee import Referee
from src.meta_evolution.meta_arena import MetaArena

# -- Configuration -------------------------------------------------------------

TARGET_AGENT = "src/agents/generator.py"
BACKUP_PATH  = "src/agents/generator.py.test_backup"

# Force-trigger: threshold=0.99 means 99% success rate required.
# No real pipeline achieves this, so Watcher ALWAYS fires.
FORCE_THRESHOLD = 0.99


# -- Display Helpers -----------------------------------------------------------

def banner(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def step(n: int, label: str):
    print(f"\n[Stage {n}] -- {label} {'-'*(50 - len(label))}")


# -- Main Test -----------------------------------------------------------------

async def run_live_test():
    banner("META-EVOLUTION LIVE TEST")
    print("This test force-triggers the full Phase 17 pipeline.")
    print(f"Target agent: {TARGET_AGENT}")
    print(f"Force threshold: {FORCE_THRESHOLD} (always triggers)")
    print("\nA backup of generator.py will be kept. Press Ctrl+C at any time to abort.")
    time.sleep(2)

    # Safety backup before we do anything
    shutil.copy2(TARGET_AGENT, BACKUP_PATH)
    print(f"\n[Safety] Backup saved -> {BACKUP_PATH}")

    client = EvoClient()

    try:
        # -- Stage 1: Watcher --------------------------------------------------
        step(1, "Watcher — Checking rolling success rate")
        watcher = Watcher(
            reports_dir="structured_reports",
            threshold=FORCE_THRESHOLD,
            window=10,
            max_failures=3,
        )
        trigger: UpgradeTrigger | None = watcher.check()

        if trigger is None:
            # If structured_reports is empty, manually create a trigger
            print("[Watcher] No reports found — creating a synthetic trigger.")
            trigger = UpgradeTrigger(
                agent_file=TARGET_AGENT,
                agent_name="generator",
                rolling_success_rate=0.0,
                window_size=0,
                consecutive_upgrade_failures=0,
            )
        else:
            print(f"[Watcher] [PASS] Upgrade triggered! Rate={trigger.rolling_success_rate:.1%}")

        # -- Stage 2: CloneBuilder ---------------------------------------------
        step(2, "CloneBuilder - Generating 2 upgrade proposals")
        builder = CloneBuilder(client)
        path_a, path_b = await builder.build(trigger)
        print(f"[CloneBuilder] [PASS] Proposal A: {path_a}")
        print(f"[CloneBuilder] [PASS] Proposal B: {path_b}")

        # Show a preview of proposal A
        with open(path_a, "r", encoding="utf-8") as f:
            preview = f.read()[:300]
        print(f"\n[Preview - Proposal A (first 300 chars)]:\n{preview}...\n")

        # -- Stage 3: SourceJudge ----------------------------------------------
        step(3, "SourceJudge - Two LLM judges voting on best proposal")
        judge = SourceJudge(client)
        winning_path = await judge.judge(TARGET_AGENT, path_a, path_b)
        print(f"[SourceJudge] [PASS] Winning proposal: {winning_path}")

        # -- Stage 4: Referee --------------------------------------------------
        step(4, "Referee - Running safety checks on winning proposal")
        referee = Referee()
        with open(winning_path, "r", encoding="utf-8") as f:
            winning_code = f.read()

        verdict = referee.inspect(winning_code)
        print(f"[Referee] Result: {verdict}")

        if not verdict.passed:
            print(f"\n[Referee] [FAIL] Challenger DISQUALIFIED: {verdict.reason}")
            print("[Test] The Referee correctly blocked an unsafe proposal.")
            print("[Test] This is the safety system working as designed.")
            watcher.record_upgrade_result(TARGET_AGENT, succeeded=False)
            return

        print(f"[Referee] [PASS] Challenger passed all safety checks.")

        # -- Stage 5: MetaArena ------------------------------------------------
        step(5, "MetaArena - Running the Fast Duel (this takes ~2 minutes)")
        print("[MetaArena] Spinning up Original vs. Challenger subprocesses...")
        print("[MetaArena] Both are given 1 problem, 1 generation each.")

        arena = MetaArena()
        result = await arena.duel(TARGET_AGENT, winning_path)

        watcher.record_upgrade_result(TARGET_AGENT, succeeded=result.challenger_won)

        # -- Final Result ------------------------------------------------------
        banner("RESULT")
        print(f"  Original fitness:    {result.original_fitness:.4f}")
        print(f"  Challenger fitness:  {result.challenger_fitness:.4f}")

        if result.challenger_won:
            print(f"\n  [WIN] CHALLENGER WON - generator.py has been evolved!")
            print(f"  The new, improved generator.py is now active.")
        else:
            print(f"\n  [SHIELD] ORIGINAL SURVIVED - generator.py is unchanged.")
            print(f"  The challenger was not good enough to replace the original.")

        print(f"\n  Backup stored at: {BACKUP_PATH}")
        print(f"  You can restore the original at any time by running:")
        print(f"    copy {BACKUP_PATH} {TARGET_AGENT}")

    except KeyboardInterrupt:
        print("\n\n[Aborted] Restoring original generator.py from backup...")
        shutil.copy2(BACKUP_PATH, TARGET_AGENT)
        print(f"[Restored] {TARGET_AGENT} is back to its original state.")

    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error: {e}")
        print("[Safety] Restoring original generator.py from backup...")
        shutil.copy2(BACKUP_PATH, TARGET_AGENT)
        print(f"[Restored] {TARGET_AGENT} is back to its original state.")
        raise

    finally:
        print(f"\n[Cleanup] Test complete.")


if __name__ == "__main__":
    asyncio.run(run_live_test())
