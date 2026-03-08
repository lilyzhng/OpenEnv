"""
Difficulty-tiered evaluation: run eval per tier (easy/medium/hard) to validate
that performance gap exists across difficulty levels.

This is the key validation for RecomposeRL's curriculum learning hypothesis:
if agents score well on easy tasks but poorly on hard tasks, curriculum is justified.

Uses APEX-v1-extended (trainable, 100 tasks) since it has richer rubrics for
difficulty scoring. Groups tasks by tier, runs N per tier, compares.

Usage:
    # Quick validation (2 per tier, 6 total, cheap model)
    python scripts/tiered_eval.py --per-tier 2 --model openai/gpt-4o-mini

    # Full validation (5 per tier, 15 total)
    python scripts/tiered_eval.py --per-tier 5 --model qwen/qwen3-coder-30b-a3b-instruct
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

# Direct imports to bypass openenv dependency
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "server_space" / "apex_env" / "server"))
sys.path.insert(0, str(_project_root / "server_space" / "apex_env" / "server" / "sandbox"))
# Also try the old path
sys.path.insert(0, str(_project_root / "apex_env" / "server"))

from task_loader import TaskLoader, compute_difficulty_score, get_difficulty_tier
from reward import compute_reward
from bash_executor import BashExecutor


# ---------------------------------------------------------------------------
# OpenRouter API (same as baseline_eval.py)
# ---------------------------------------------------------------------------

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a professional analyst. You solve tasks by executing bash commands one at a time.\n"
    "You have access to: python3, grep, awk, sed, jq, and standard unix tools.\n"
    "Each response should contain EXACTLY ONE bash command to execute.\n"
    "Do NOT wrap commands in markdown code blocks. Just output the raw command.\n"
    "After seeing the result, decide your next command.\n"
    "When you have completed the task and written your output files, respond with exactly: done"
)


def call_model(messages: list[dict], model: str, api_key: str) -> str:
    for attempt in range(3):
        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
                timeout=60,
            )
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"    rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
                continue
            raise
    raise RuntimeError("Failed after 3 attempts")


def extract_command(response: str) -> str:
    """Extract bash command from model response (simplified)."""
    import re

    stripped = response.strip().lower()
    if stripped in ("done", '"done"', "'done'"):
        return "done"

    # Code block
    lines = response.strip().split("\n")
    in_block = False
    code_lines = []
    for line in lines:
        if line.strip().startswith("```"):
            if in_block:
                break
            in_block = True
            continue
        if in_block:
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines).strip()

    # Filter talk, take first command-like line
    talk_prefixes = (
        "I ", "I'", "Let me", "Now ", "First", "Next", "The ", "This ",
        "Here", "Sure", "OK", "Okay", "Great", "Note", "Since ", "To ",
        "We ", "My ", "After", "Before", "Based", "Looking", "There ",
    )
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if any(s.startswith(p) for p in talk_prefixes):
            continue
        if s.endswith(".") and not any(c in s for c in "|>&;$`"):
            continue
        return s

    return response.strip()


def run_episode(task: dict, executor: BashExecutor, model: str, api_key: str, max_turns: int = 5) -> dict:
    """Run one episode and return results."""
    import shutil
    import tempfile

    domain = task.get("Domain", task.get("domain", "unknown"))
    task_id = task.get("Task ID", task.get("task_id", "unknown"))
    prompt = task.get("Prompt", task.get("prompt", ""))

    workspace = Path(tempfile.mkdtemp(prefix=f"apex_tier_{task_id}_"))

    # Download file attachments if any
    files_raw = task.get("File Attachments", "")
    input_files = []
    if files_raw and files_raw.strip():
        from huggingface_hub import hf_hub_download
        for fpath in files_raw.strip().split("\n"):
            fpath = fpath.strip()
            if not fpath:
                continue
            try:
                local = hf_hub_download("mercor/APEX-v1-extended", fpath, repo_type="dataset")
                fname = Path(fpath).name
                dest = workspace / fname
                import shutil as _sh
                _sh.copy2(local, dest)
                input_files.append(fname)
            except Exception:
                pass

    files_note = ""
    if input_files:
        files_list = "\n".join(f"  - {f}" for f in input_files)
        files_note = f"\nAvailable input files in your workspace:\n{files_list}\n"

    task_prompt = (
        f"# Task: {task_id}\n"
        f"# Domain: {domain}\n\n"
        f"{prompt}\n\n"
        f"Your workspace is: {workspace}\n"
        f"{files_note}"
        f"Create your output files in the workspace directory.\n"
        f"When finished, send the command: done"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task_prompt},
    ]

    actions = []
    for turn in range(max_turns):
        try:
            response = call_model(messages, model, api_key)
        except Exception as e:
            print(f"      API error turn {turn}: {e}")
            break

        command = extract_command(response)
        actions.append(command)

        if command.strip().lower() == "done":
            break

        result = executor.run(command, cwd=workspace, timeout_s=30.0)
        obs = ""
        if result.stdout:
            obs += result.stdout[:2000] + "\n"
        if result.stderr:
            obs += f"STDERR: {result.stderr[:500]}\n"
        if result.exit_code != 0:
            obs += f"EXIT CODE: {result.exit_code}\n"
        if not obs:
            obs = "(no output)"

        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": obs})

    # Compute reward — need to adapt task format for compute_reward
    # compute_reward expects 'rubric' key as list, but v1-extended has 'Rubric JSON' as dict
    eval_task = dict(task)
    rubric_str = task.get("Rubric JSON", "{}")
    try:
        rubric_parsed = json.loads(rubric_str) if isinstance(rubric_str, str) else rubric_str
        if isinstance(rubric_parsed, dict):
            # Convert dict rubric to list format expected by compute_reward
            eval_task["rubric"] = [
                {"criteria": v.get("description", ""), "description": v.get("description", "")}
                for v in rubric_parsed.values()
            ]
        else:
            eval_task["rubric"] = rubric_parsed
    except Exception:
        eval_task["rubric"] = []

    reward = compute_reward(eval_task, workspace)
    shutil.rmtree(workspace, ignore_errors=True)

    return {
        "task_id": task_id,
        "domain": domain,
        "tier": get_difficulty_tier(task),
        "difficulty_score": compute_difficulty_score(task),
        "reward": reward,
        "num_turns": len(actions),
        "actions": actions,
    }


def main():
    parser = argparse.ArgumentParser(description="Tiered eval: easy vs hard")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--per-tier", type=int, default=3, help="Tasks per tier")
    parser.add_argument("--max-turns", type=int, default=5)
    parser.add_argument("--sandbox", action="store_true", help="Run commands in Docker sandbox")
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_APIKEY", "")
    if not api_key:
        for env_path in [
            Path.home() / "Documents" / "lilyzhng" / "2026" / ".env.local",
            Path(__file__).resolve().parent.parent.parent.parent / "2026" / ".env.local",
            Path.home() / ".env.local",
        ]:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("OPENROUTER_APIKEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
            if api_key:
                break
    if not api_key:
        print("ERROR: Set OPENROUTER_APIKEY")
        sys.exit(1)

    print(f"Loading APEX-v1-extended...")
    loader = TaskLoader(dataset_name="mercor/APEX-v1-extended")
    tiers = loader.get_tasks_by_tier()

    for tier in ["easy", "hard"]:
        print(f"  {tier}: {len(tiers[tier])} tasks")

    # Select tasks per tier (spread across domains)
    selected = {}
    for tier in ["easy", "hard"]:
        pool = tiers[tier]
        # Sort by domain for diversity
        by_domain = defaultdict(list)
        for t in pool:
            by_domain[t.get("Domain", "unknown")].append(t)
        picked = []
        # Round-robin across domains
        domain_iters = {d: iter(tasks) for d, tasks in by_domain.items()}
        while len(picked) < args.per_tier:
            added = False
            for d in sorted(domain_iters.keys()):
                if len(picked) >= args.per_tier:
                    break
                try:
                    picked.append(next(domain_iters[d]))
                    added = True
                except StopIteration:
                    continue
            if not added:
                break
        selected[tier] = picked

    total = sum(len(v) for v in selected.values())
    print(f"\nRunning {total} tasks ({args.per_tier}/tier), model={args.model}, max_turns={args.max_turns}")
    print("=" * 70)

    if args.sandbox:
        from docker_executor import DockerBashExecutor
        executor = DockerBashExecutor()
        print("Using Docker sandbox executor")
    else:
        executor = BashExecutor()
    all_results = []

    for tier in ["easy", "hard"]:
        tasks = selected[tier]
        print(f"\n--- {tier.upper()} TIER ({len(tasks)} tasks) ---")

        for i, task in enumerate(tasks):
            task_id = task.get("Task ID", "?")
            domain = task.get("Domain", "?")
            score = compute_difficulty_score(task)
            print(f"  [{i+1}/{len(tasks)}] {domain} task {task_id} (score={score:.1f})")

            result = run_episode(task, executor, args.model, api_key, args.max_turns)
            all_results.append(result)

            print(f"    reward={result['reward']:.3f}  turns={result['num_turns']}")

    # Report
    print("\n" + "=" * 70)
    print(f"TIERED EVAL RESULTS — {args.model}")
    print("=" * 70)

    for tier in ["easy", "hard"]:
        tier_results = [r for r in all_results if r["tier"] == tier]
        if not tier_results:
            continue
        rewards = [r["reward"] for r in tier_results]
        avg_turns = sum(r["num_turns"] for r in tier_results) / len(tier_results)
        avg_score = sum(r["difficulty_score"] for r in tier_results) / len(tier_results)
        print(f"\n  {tier.upper():8s}  n={len(tier_results)}  "
              f"avg_reward={sum(rewards)/len(rewards):.3f}  "
              f"avg_turns={avg_turns:.1f}  "
              f"avg_difficulty={avg_score:.1f}")
        for r in tier_results:
            print(f"    task {r['task_id']:>5} ({r['domain']:>12})  "
                  f"reward={r['reward']:.3f}  turns={r['num_turns']}  "
                  f"difficulty={r['difficulty_score']:.1f}")

    # Summary comparison
    print("\n" + "-" * 70)
    print("PERFORMANCE GAP SUMMARY:")
    tier_avgs = {}
    for tier in ["easy", "hard"]:
        rewards = [r["reward"] for r in all_results if r["tier"] == tier]
        if rewards:
            tier_avgs[tier] = sum(rewards) / len(rewards)
            print(f"  {tier:8s}: {tier_avgs[tier]:.3f}")

    if "easy" in tier_avgs and "hard" in tier_avgs:
        gap = tier_avgs["easy"] - tier_avgs["hard"]
        print(f"\n  Gap (easy - hard): {gap:+.3f}")
        if gap > 0.05:
            print("  → Performance gap EXISTS — curriculum learning is justified!")
        elif gap > 0:
            print("  → Small gap — curriculum may help but signal is weak")
        else:
            print("  → No gap — difficulty tiers may need refinement")

    # Save
    model_short = args.model.split("/")[-1].replace(":", "-")
    output_path = args.output or f"data/tiered_eval_{model_short}.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "model": args.model,
            "per_tier": args.per_tier,
            "results": all_results,
            "tier_averages": tier_avgs,
        }, f, indent=2)
    print(f"\nSaved to {output_path}")

    # Cleanup sandbox containers
    if args.sandbox and hasattr(executor, 'cleanup_all'):
        executor.cleanup_all()


if __name__ == "__main__":
    main()
