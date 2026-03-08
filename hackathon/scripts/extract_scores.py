#!/usr/bin/env python3
"""Extract final reward scores from evaluation log files.

Usage:
    python3 scripts/extract_scores.py data/law_v1/
    python3 scripts/extract_scores.py data/consulting_v1/
"""
from __future__ import annotations
import re
import sys
from pathlib import Path


def extract_reward(log_path: Path) -> dict | None:
    text = log_path.read_text()

    model_match = re.search(r"Model: (.+)", text)
    model = model_match.group(1).strip() if model_match else "unknown"

    reward_match = re.search(r"Reward: ([\d.]+)", text)
    if not reward_match:
        return None

    reward = float(reward_match.group(1))

    criteria_match = re.search(r"Final: (\d+)/(\d+)", text)
    criteria_met = int(criteria_match.group(1)) if criteria_match else 0
    criteria_total = int(criteria_match.group(2)) if criteria_match else 0

    # Extract process signals
    process_match = re.search(r"Process: tool_use=(\w) tool_composition=(\w) tool_creation=(\w)", text)
    tool_use = process_match.group(1) if process_match else "?"
    tool_comp = process_match.group(2) if process_match else "?"
    tool_create = process_match.group(3) if process_match else "?"

    return {
        "model": model,
        "reward": reward,
        "criteria_met": criteria_met,
        "criteria_total": criteria_total,
        "tool_use": tool_use,
        "tool_comp": tool_comp,
        "tool_create": tool_create,
        "file": log_path.name,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/extract_scores.py <log_dir>")
        sys.exit(1)

    log_dir = Path(sys.argv[1])
    if not log_dir.exists():
        print(f"Directory not found: {log_dir}")
        sys.exit(1)

    results = []
    for log_file in sorted(log_dir.glob("*.log")):
        r = extract_reward(log_file)
        if r:
            results.append(r)
        else:
            print(f"  [INCOMPLETE] {log_file.name}")

    if not results:
        print("No completed results found.")
        return

    # Sort by reward descending
    results.sort(key=lambda x: x["reward"], reverse=True)

    print(f"\n{'Model':<35} {'Use':>4} {'Comp':>5} {'Cre':>4} {'Reward':>8} {'Criteria':>10}")
    print("-" * 75)
    for r in results:
        short = r["model"].split("/")[-1]
        print(f"{short:<35} {r['tool_use']:>4} {r['tool_comp']:>5} {r['tool_create']:>4} {r['reward']:>8.3f} {r['criteria_met']:>4}/{r['criteria_total']}")


if __name__ == "__main__":
    main()
