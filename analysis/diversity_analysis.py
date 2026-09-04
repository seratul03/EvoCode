"""
diversity_analysis.py — Generates the "Problems Solved" comparison bar chart.

Creates a grouped bar chart comparing the number of problems perfectly solved
(100% tests passed at least once) across all 4 experimental conditions.

Output: results/plots/problems_solved.png
"""

import json
import os
import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")

# ─── Configuration ────────────────────────────────────────────────────
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "structured_reports")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "plots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FILES = {
    "Baseline A\n(Zero-Shot)":         os.path.join(REPORT_DIR, "04092026_04-05-18.json"),
    "Baseline B\n(Static Reflection)": os.path.join(REPORT_DIR, "04092026_05-10-24.json"),
    "Baseline C\n(Random Mutation)":   os.path.join(REPORT_DIR, "04092026_05-45-26.json"),
    "EvoCode\n(Co-Evolution)":         os.path.join(REPORT_DIR, "04092026_07-26-05.json"),
}

BAR_COLORS = ["#6c757d", "#dc3545", "#fd7e14", "#0d6efd"]


def count_solved(data):
    """Count how many problems had at least one evaluation with 100% tests passed."""
    solved = 0
    total = len(data.get("problems_evaluated", []))
    for problem in data.get("problems_evaluated", []):
        for gen in problem.get("generations", []):
            found = False
            for ev in gen.get("evaluations", []):
                tr = ev.get("test_results", {})
                passed = tr.get("passed_tests", 0)
                total_tests = tr.get("total_tests", 1)
                if passed == total_tests and total_tests > 0:
                    found = True
                    break
            if found:
                solved += 1
                break
    return solved, total


# ─── Compute ──────────────────────────────────────────────────────────
labels = []
solved_counts = []
total_problems = 30

for label, path in FILES.items():
    if not os.path.exists(path):
        print(f"WARNING: {path} not found, skipping {label}")
        continue
    with open(path, "r") as f:
        data = json.load(f)
    solved, total = count_solved(data)
    total_problems = total
    labels.append(label)
    solved_counts.append(solved)

unsolved_counts = [total_problems - s for s in solved_counts]

# ─── Plot ─────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 6))
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#161b22")

x = range(len(labels))
bars = ax.bar(x, solved_counts, color=BAR_COLORS, edgecolor="#30363d",
              linewidth=1.5, width=0.6, zorder=3)

# Add value labels on top of bars
for bar, count in zip(bars, solved_counts):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4,
            f"{count}/{total_problems}",
            ha="center", va="bottom", fontsize=14, fontweight="bold", color="white")

# Add unsolved portion as a faded stacked bar
ax.bar(x, unsolved_counts, bottom=solved_counts, color="#21262d",
       edgecolor="#30363d", linewidth=1.5, width=0.6, zorder=2)

ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=10, color="white")
ax.set_ylabel("Number of Problems", fontsize=13, color="white", labelpad=10)
ax.set_title("Problems Perfectly Solved (100% Tests Passed)",
             fontsize=16, fontweight="bold", color="white", pad=15)
ax.set_ylim(0, total_problems + 3)
ax.tick_params(colors="white", labelsize=11)
ax.grid(True, axis="y", alpha=0.15, color="white")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#30363d")
ax.spines["bottom"].set_color("#30363d")

# Add a horizontal line at the total
ax.axhline(y=total_problems, color="#58a6ff", linestyle="--", alpha=0.4, linewidth=1)
ax.text(len(labels) - 0.5, total_problems + 0.3, f"Total: {total_problems}",
        fontsize=9, color="#58a6ff", alpha=0.6)

output_path = os.path.join(OUTPUT_DIR, "problems_solved.png")
plt.tight_layout()
plt.savefig(output_path, dpi=200, facecolor=fig.get_facecolor())
plt.close()
print(f"✅ Saved: {output_path}")
