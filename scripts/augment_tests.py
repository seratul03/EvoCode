"""
scripts/augment_tests.py -- Layer 1 one-time runner.

Run from project root:
    python scripts/augment_tests.py

Reads data/train_problems.json and data/test_problems.json,
augments each problem to 20 test cases using TestAugmentor,
and writes the results back in-place.
Creates a backup (.bak) before overwriting.
"""

import json
import os
import sys
import shutil

sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.test_augmentor import TestAugmentor

TARGET_COUNT = 20
FILES = [
    "data/train_problems.json",
    "data/test_problems.json",
]


def augment_file(path: str, augmentor: TestAugmentor, target: int) -> None:
    print(f"\n{'=' * 60}")
    print(f"Processing: {path}")
    print(f"{'=' * 60}")

    with open(path, "r", encoding="utf-8") as f:
        problems = json.load(f)

    # Backup original
    backup_path = path + ".bak"
    shutil.copy2(path, backup_path)
    print(f"  Backup created: {backup_path}")

    augmented_problems = []
    for i, problem in enumerate(problems):
        pid = problem.get("id", i)
        title = problem.get("title", f"Problem {pid}")
        before = len(problem.get("tests", []))

        aug = augmentor.augment_problem(problem, target_count=target)
        after = len(aug.get("tests", []))

        status = "OK" if after >= target else f"WARN only {after}"
        print(f"  [{pid:>3}] {title:<40}  {before:>2} -> {after:>2} tests  {status}")
        augmented_problems.append(aug)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(augmented_problems, f, indent=2, ensure_ascii=False)

    print(f"\n  Written: {path}")


def main():
    augmentor = TestAugmentor()
    print("EvoCode Test Augmentor — Layer 1")
    print(f"Target: {TARGET_COUNT} tests per problem\n")

    for filepath in FILES:
        if not os.path.exists(filepath):
            print(f"  SKIP (not found): {filepath}")
            continue
        augment_file(filepath, augmentor, TARGET_COUNT)

    print("\n\nDone. All problem files augmented successfully.")


if __name__ == "__main__":
    main()
