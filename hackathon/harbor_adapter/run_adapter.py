"""
Generate Harbor tasks from mercor/apex-agents (480 eval tasks).

Usage:
    # Generate all 480 tasks
    python harbor_adapter/run_adapter.py

    # Generate 20 tasks (stratified by domain)
    python harbor_adapter/run_adapter.py --limit 20

    # Generate specific domains
    python harbor_adapter/run_adapter.py --domains "Investment Banking" "Law"

    # Custom output directory
    python harbor_adapter/run_adapter.py --output-dir datasets/apex-agents
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset

from adapter import ApexAgentsAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "datasets" / "apex-agents"


def main():
    parser = argparse.ArgumentParser(description="Generate Harbor tasks from apex-agents")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None,
                        help="Max tasks to generate (stratified by domain)")
    parser.add_argument("--domains", nargs="*", default=None,
                        help="Filter to specific domains")
    parser.add_argument("--dataset", default="mercor/apex-agents")
    args = parser.parse_args()

    logger.info(f"Loading {args.dataset}...")
    ds = load_dataset(args.dataset, split="train")
    logger.info(f"Loaded {len(ds)} tasks, columns: {ds.column_names}")

    # Group by domain
    domain_indices = defaultdict(list)
    for i in range(len(ds)):
        domain = ds[i].get("domain", "unknown")
        if args.domains is None or domain in args.domains:
            domain_indices[domain].append(i)

    # Stratified selection if --limit
    selected = []
    if args.limit:
        per_domain = max(1, args.limit // len(domain_indices))
        for domain, indices in sorted(domain_indices.items()):
            take = min(per_domain, len(indices))
            selected.extend(indices[:take])
            logger.info(f"  {domain}: {take}/{len(indices)} tasks")
        selected = selected[:args.limit]
    else:
        for domain, indices in sorted(domain_indices.items()):
            selected.extend(indices)
            logger.info(f"  {domain}: {len(indices)} tasks")

    logger.info(f"Generating {len(selected)} Harbor tasks...")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    adapter = ApexAgentsAdapter(task_dir=args.output_dir, dataset=ds)

    generated = 0
    for idx in selected:
        domain = ds[idx].get("domain", "unknown")
        local_id = ApexAgentsAdapter.make_local_task_id(domain, idx)
        try:
            adapter.generate_task(idx, local_id)
            generated += 1
        except Exception as e:
            logger.error(f"Failed task {idx} ({domain}): {e}")

    logger.info(f"Generated {generated} tasks in {args.output_dir}")
    logger.info("Run with Harbor:")
    logger.info(f"  harbor run --dataset {args.output_dir} --agent claude-code --model <model>")


if __name__ == "__main__":
    main()
