"""
fitness_curves.py — Generates the "hero chart" for the EvoCode thesis.

Plots a line chart of Generation vs Best Fitness for each experimental condition,
averaged across all 30 problems. Problems that were solved early (fewer generations)
are forward-filled with their last known fitness so the averages remain meaningful.

Output: results/plots/fitness_curves.png
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for saving to file

# ─── Configuration ────────────────────────────────────────────────────
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "structured_reports")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "plots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FILES = {
    "Baseline A\n(Zero-Shot)":        os.path.join(REPORT_DIR, "04092026_04-05-18.json"),
    "Baseline B\n(Static Reflection)": os.path.join(REPORT_DIR, "04092026_05-10-24.json"),
    "Baseline C\n(Random Mutation)":   os.path.join(REPORT_DIR, "04092026_05-45-26.json"),
    "EvoCode\n(Co-Evolution)":         os.path.join(REPORT_DIR, "04092026_07-26-05.json"),
}

COLORS = {
    "Baseline A\n(Zero-Shot)":        "#6c757d",   # Grey
    "Baseline B\n(Static Reflection)": "#dc3545",   # Red
    "Baseline C\n(Random Mutation)":   "#fd7e14",   # Orange
    "EvoCode\n(Co-Evolution)":         "#0d6efd",   # Blue
}

MAX_GENS = 10  # Maximum generations any run can have


def extract_fitness_curves(data):
    """
    For each problem, extract the best fitness at each generation.
    Returns a list of lists: one per problem, each containing best fitness per generation.
    """
    all_curves = []
    for problem in data.get("problems_evaluated", []):
        curve = []
        for gen in problem.get("generations", []):
            best_fitness = 0.0
            for ev in gen.get("evaluations", []):
                fv = ev.get("fitness", {}).get("fitness_value", 0.0)
                if fv > best_fitness:
                    best_fitness = fv
            curve.append(best_fitness)
        all_curves.append(curve)
    return all_curves


def pad_and_average(curves, max_gens):
    """
    Pad each curve to max_gens by forward-filling the last value (early stopping
    means the problem was solved, so the fitness stays constant).
    Then compute mean and std across all problems at each generation.
    """
    padded = []
    for curve in curves:
        if len(curve) == 0:
            padded.append([0.0] * max_gens)
        else:
            extended = curve + [curve[-1]] * (max_gens - len(curve))
            padded.append(extended[:max_gens])
    arr = np.array(padded)
    return arr.mean(axis=0), arr.std(axis=0)


# ─── Plot ─────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 6))
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#161b22")

for label, path in FILES.items():
    if not os.path.exists(path):
        print(f"WARNING: {path} not found, skipping {label}")
        continue

    with open(path, "r") as f:
        data = json.load(f)

    curves = extract_fitness_curves(data)
    mean, std = pad_and_average(curves, MAX_GENS)
    gens = np.arange(1, MAX_GENS + 1)
    color = COLORS[label]

    ax.plot(gens, mean, color=color, linewidth=2.5, label=label, marker="o",
            markersize=5, zorder=3)
    ax.fill_between(gens, mean - std, mean + std, color=color, alpha=0.15, zorder=2)

ax.set_xlabel("Generation", fontsize=13, color="white", labelpad=10)
ax.set_ylabel("Average Best Fitness", fontsize=13, color="white", labelpad=10)
ax.set_title("Fitness Progression Across Generations",
             fontsize=16, fontweight="bold", color="white", pad=15)
ax.set_xticks(range(1, MAX_GENS + 1))
ax.set_ylim(0, 1.0)
ax.tick_params(colors="white", labelsize=11)
ax.grid(True, alpha=0.15, color="white")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#30363d")
ax.spines["bottom"].set_color("#30363d")

legend = ax.legend(fontsize=9, loc="lower right", framealpha=0.3,
                   edgecolor="#30363d", facecolor="#161b22", labelcolor="white")

output_path = os.path.join(OUTPUT_DIR, "fitness_curves.png")
plt.tight_layout()
plt.savefig(output_path, dpi=200, facecolor=fig.get_facecolor())
plt.close()
print(f"✅ Saved: {output_path}")
