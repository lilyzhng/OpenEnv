"""
Batch hand-draw evaluation: run multiple tasks × models × runs.

Usage:
    # Single task, all models, 3 runs each
    python scripts/eval_handdraw_batch.py --task flower --runs 3

    # Single task, single model (quick test)
    python scripts/eval_handdraw_batch.py --task flower --model anthropic/claude-sonnet-4 --runs 1

    # All complex tasks
    python scripts/eval_handdraw_batch.py --task flower,balanced_scale,cherry_blossom,fish,stacking_stones,neural_net --runs 3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "server_space" / "apex_env" / "server"))

from handdraw_env import HandDrawEnvironment

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are an illustrator. You create SVG illustrations using Rough.js by composing basic elements.\n"
    "You solve tasks by executing bash commands one at a time.\n"
    "You have access to: cat, ls, grep, find, and standard unix tools.\n"
    "Each response should contain EXACTLY ONE bash command to execute.\n"
    "Do NOT wrap commands in markdown code blocks. Just output the raw command.\n"
    "Explore your workspace to discover what elements and examples are available.\n"
    "Study the examples to understand how basic elements compose into illustrations.\n"
    "Use the template.html as your starting point.\n"
    "Write your output as a complete HTML file.\n"
    "Pay attention to [Progress] feedback — it tells you how many criteria you've met.\n"
    "When finished, respond with exactly: done"
)

MODELS = [
    "anthropic/claude-sonnet-4",
    "openai/gpt-4.1",
    "openai/gpt-4o-mini",
    "deepseek/deepseek-chat-v3-0324",
    "qwen/qwen3-coder-30b-a3b-instruct",
]


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_APIKEY", "")
    if not key:
        for env_path in [
            Path.home() / "Documents" / "lilyzhng" / "2026" / ".env.local",
            Path.home() / ".env.local",
        ]:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("OPENROUTER_APIKEY="):
                        key = line.split("=", 1)[1].strip()
                        break
            if key:
                break
    return key


def call_model(messages: list[dict], model: str, api_key: str) -> str:
    api_model = model.removeprefix("openrouter/") if model.startswith("openrouter/") else model
    for attempt in range(3):
        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": api_model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 2048,
                },
                timeout=60,
            )
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
                continue
            raise
    raise RuntimeError("Failed after 3 attempts")


def extract_command(response: str) -> str:
    import re

    stripped = response.strip().lower()
    if stripped in ("done", '"done"', "'done'"):
        return "done"

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

    talk_prefixes = (
        "I ", "I'", "Let me", "Now ", "First", "Next", "The ", "This ",
        "Here", "Sure", "OK", "Okay", "Great", "Note", "Since ", "To ",
        "We ", "My ", "After", "Before", "Based", "Looking", "There ",
    )

    cmd_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if any(s.startswith(p) for p in talk_prefixes):
            continue
        if s.endswith(".") and not any(c in s for c in "|>&;$`"):
            continue
        cmd_start = i
        break

    if cmd_start is None:
        return response.strip()

    first_line = lines[cmd_start]

    # Handle heredoc
    heredoc_match = re.search(r"<<\s*'?(\w+)'?", first_line)
    if heredoc_match:
        delimiter = heredoc_match.group(1)
        heredoc_lines = [first_line]
        for line in lines[cmd_start + 1:]:
            heredoc_lines.append(line)
            if line.strip() == delimiter:
                break
        return "\n".join(heredoc_lines)

    # Handle unclosed quotes
    for quote_char in ["'", '"']:
        count = first_line.count(quote_char) - first_line.count("\\" + quote_char)
        if count % 2 == 1:
            multi_lines = [first_line]
            for line in lines[cmd_start + 1:]:
                multi_lines.append(line)
                line_count = line.count(quote_char) - line.count("\\" + quote_char)
                if line_count % 2 == 1:
                    break
            return "\n".join(multi_lines)

    return first_line.strip()


def run_single(task_name: str, model: str, api_key: str, max_turns: int = 30, run_id: int = 0) -> dict:
    """Run a single episode and return results."""
    env = HandDrawEnvironment(task_id=task_name)
    obs = env.reset()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": obs["stdout"]},
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
            obs = env.step("done")
            break

        obs = env.step(command)
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": obs["stdout"][:3000]})
    else:
        obs = env.step("done")

    env.close()

    return {
        "task": task_name,
        "model": model,
        "run_id": run_id,
        "reward": obs.get("reward", 0),
        "criteria_met": obs.get("criteria_met", 0),
        "criteria_total": obs.get("criteria_total", 0),
        "num_turns": len(actions),
        "actions": actions,
    }


def main():
    parser = argparse.ArgumentParser(description="Batch hand-draw eval")
    parser.add_argument("--task", required=True, help="Comma-separated task names (e.g. flower,fish)")
    parser.add_argument("--model", default=None, help="Single model (default: all 5)")
    parser.add_argument("--runs", type=int, default=3, help="Runs per task×model")
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("-o", "--output-dir", default=None)
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("ERROR: Set OPENROUTER_APIKEY")
        sys.exit(1)

    tasks = [t.strip() for t in args.task.split(",")]
    models = [args.model] if args.model else MODELS

    total_evals = len(tasks) * len(models) * args.runs
    print(f"Batch eval: {len(tasks)} tasks × {len(models)} models × {args.runs} runs = {total_evals} evals")
    print(f"Tasks: {tasks}")
    print(f"Models: {[m.split('/')[-1] for m in models]}")
    print("=" * 70)

    output_dir = Path(args.output_dir) if args.output_dir else Path(f"data/handdraw_complex")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    eval_num = 0

    for task_name in tasks:
        print(f"\n{'='*70}")
        print(f"TASK: {task_name}")
        print(f"{'='*70}")

        for model in models:
            model_short = model.split("/")[-1]
            for run in range(args.runs):
                eval_num += 1
                print(f"\n  [{eval_num}/{total_evals}] {model_short} run {run+1}/{args.runs}")

                result = run_single(task_name, model, api_key, args.max_turns, run)
                all_results.append(result)

                print(f"    reward={result['reward']:.3f}  criteria={result['criteria_met']}/{result['criteria_total']}  turns={result['num_turns']}")

                # Save incrementally
                log_path = output_dir / f"{task_name}_{model_short}_run{run}.json"
                with open(log_path, "w") as f:
                    json.dump(result, f, indent=2)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    for task_name in tasks:
        print(f"\n  {task_name}:")
        for model in models:
            model_short = model.split("/")[-1]
            task_model_results = [r for r in all_results if r["task"] == task_name and r["model"] == model]
            rewards = [r["reward"] for r in task_model_results]
            if rewards:
                avg = sum(rewards) / len(rewards)
                print(f"    {model_short:30s}  avg={avg:.3f}  runs={[f'{r:.3f}' for r in rewards]}")

    # Save summary
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "tasks": tasks,
            "models": models,
            "runs_per": args.runs,
            "results": all_results,
        }, f, indent=2)
    print(f"\nSaved to {output_dir}/")


if __name__ == "__main__":
    main()
