"""
generalization_gap.py — Analyzes performance on fixed vs ephemeral tests.

For each condition, computes the average pass rate on fixed tests (first 20)
versus ephemeral property-based tests (last 5) to detect overfitting.
Also generates a per-problem heatmap showing which problems each condition solved.

Output: results/plots/generalization_gap.png, results/plots/problem_heatmap.png
"""

import json
import os
import numpy as np
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

COLORS = ["#6c757d", "#dc3545", "#fd7e14", "#0d6efd"]
FIXED_TESTS = 20   # Number of fixed tests per problem
EPHEMERAL_TESTS = 5  # Number of property-based ephemeral tests


def analyze_generalization(data):
    """
    For each problem, find the best evaluation (highest fitness) and analyze
    how it performed on fixed vs ephemeral tests by looking at test_outputs.
    Returns (avg_fixed_rate, avg_ephemeral_rate, per_problem_solved).
    """
    fixed_rates = []
    ephemeral_rates = []
    per_problem_solved = []

    for problem in data.get("problems_evaluated", []):
        best_fitness = -1
        best_eval = None

        for gen in problem.get("generations", []):
            for ev in gen.get("evaluations", []):
                fv = ev.get("fitness", {}).get("fitness_value", 0.0)
                if fv > best_fitness:
                    best_fitness = fv
                    best_eval = ev

        if best_eval is None:
            fixed_rates.append(0.0)
            ephemeral_rates.append(0.0)
            per_problem_solved.append(0)
            continue

        tr = best_eval.get("test_results", {})
        outputs = tr.get("test_outputs", [])
        passed = tr.get("passed_tests", 0)
        total = tr.get("total_tests", 1)

        # If we have detailed test outputs, split by fixed/ephemeral
        if len(outputs) >= FIXED_TESTS + EPHEMERAL_TESTS:
            fixed_passed = sum(1 for o in outputs[:FIXED_TESTS] if o.get("status") == "pass")
            eph_passed = sum(1 for o in outputs[FIXED_TESTS:] if o.get("status") == "pass")
            fixed_rates.append(fixed_passed / FIXED_TESTS)
            ephemeral_rates.append(eph_passed / EPHEMERAL_TESTS)
        else:
            # Fallback: use overall pass rate for both
            rate = passed / max(total, 1)
            fixed_rates.append(rate)
            ephemeral_rates.append(rate)

        per_problem_solved.append(1 if passed == total and total > 0 else 0)

    return (
        np.mean(fixed_rates) if fixed_rates else 0.0,
        np.mean(ephemeral_rates) if ephemeral_rates else 0.0,
        per_problem_solved,
    )


# ─── Compute ──────────────────────────────────────────────────────────
labels = []
fixed_avgs = []
ephemeral_avgs = []
all_solved_maps = []

for label, path in FILES.items():
    if not os.path.exists(path):
        print(f"WARNING: {path} not found, skipping {label}")
        continue
    with open(path, "r") as f:
        data = json.load(f)
    fr, er, solved_map = analyze_generalization(data)
    labels.append(label)
    fixed_avgs.append(fr)
    ephemeral_avgs.append(er)
    all_solved_maps.append(solved_map)


# ─── Chart 1: Generalization Gap (Grouped Bar) ───────────────────────
fig, ax = plt.subplots(figsize=(10, 6))
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#161b22")

x = np.arange(len(labels))
width = 0.3

bars1 = ax.bar(x - width / 2, fixed_avgs, width, label="Fixed Tests",
               color="#58a6ff", edgecolor="#30363d", linewidth=1.2, zorder=3)
bars2 = ax.bar(x + width / 2, ephemeral_avgs, width, label="Ephemeral Tests",
               color="#f0883e", edgecolor="#30363d", linewidth=1.2, zorder=3)

# Value labels
for bar in bars1:
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
            f"{bar.get_height():.0%}", ha="center", va="bottom",
            fontsize=10, color="white", fontweight="bold")
for bar in bars2:
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
            f"{bar.get_height():.0%}", ha="center", va="bottom",
            fontsize=10, color="white", fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=10, color="white")
ax.set_ylabel("Average Pass Rate", fontsize=13, color="white", labelpad=10)
ax.set_title("Generalization: Fixed vs Ephemeral (Property-Based) Tests",
             fontsize=16, fontweight="bold", color="white", pad=15)
ax.set_ylim(0, 1.15)
ax.tick_params(colors="white", labelsize=11)
ax.grid(True, axis="y", alpha=0.15, color="white")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#30363d")
ax.spines["bottom"].set_color("#30363d")

legend = ax.legend(fontsize=11, loc="upper left", framealpha=0.3,
                   edgecolor="#30363d", facecolor="#161b22", labelcolor="white")

output_path = os.path.join(OUTPUT_DIR, "generalization_gap.png")
plt.tight_layout()
plt.savefig(output_path, dpi=200, facecolor=fig.get_facecolor())
plt.close()
print(f"✅ Saved: {output_path}")


# ─── Chart 2: Per-Problem Heatmap ────────────────────────────────────
if all_solved_maps:
    num_problems = len(all_solved_maps[0])
    heatmap_data = np.array(all_solved_maps)  # shape: (conditions, problems)

    fig, ax = plt.subplots(figsize=(14, 4))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    # Custom colormap: dark grey for unsolved, green for solved
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap(["#21262d", "#2ea043"])

    im = ax.imshow(heatmap_data, aspect="auto", cmap=cmap, interpolation="nearest")

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels([l.replace("\n", " ") for l in labels], fontsize=10, color="white")
    ax.set_xticks(range(num_problems))
    ax.set_xticklabels([f"P{i+1}" for i in range(num_problems)], fontsize=7, color="white")
    ax.set_xlabel("Problem ID", fontsize=13, color="white", labelpad=10)
    ax.set_title("Per-Problem Solve Map (Green = Solved, Dark = Unsolved)",
                 fontsize=14, fontweight="bold", color="white", pad=15)
    ax.tick_params(colors="white")

    # Add grid lines between cells
    for i in range(num_problems + 1):
        ax.axvline(i - 0.5, color="#30363d", linewidth=0.5)
    for i in range(len(labels) + 1):
        ax.axhline(i - 0.5, color="#30363d", linewidth=0.5)

    output_path2 = os.path.join(OUTPUT_DIR, "problem_heatmap.png")
    plt.tight_layout()
    plt.savefig(output_path2, dpi=200, facecolor=fig.get_facecolor())
    plt.close()
    print(f"✅ Saved: {output_path2}")
