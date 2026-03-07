"""Baseline evaluation: run a model through ApexEnvironment via OpenRouter API.

Usage:
    # Eval 5 tasks (quick sanity check)
    python -m apex_env.eval.baseline_eval --limit 5

    # Eval all 100 tasks with a specific model
    python -m apex_env.eval.baseline_eval --model qwen/qwen3-coder-next-instruct

    # Resume from a previous run
    python -m apex_env.eval.baseline_eval --resume eval/results/baseline_20260307_143022.jsonl

Requires:
    OPENROUTER_API_KEY env var (or .env file in project root)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Add parent paths so we can import apex_env modules
APEX_ENV_DIR = Path(__file__).resolve().parent.parent
ENVS_DIR = APEX_ENV_DIR.parent
if str(ENVS_DIR) not in sys.path:
    sys.path.insert(0, str(ENVS_DIR))

from apex_env.server.apex_environment import ApexEnvironment
from apex_env.models import BashAction


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """\
You are a professional analyst agent. You solve tasks by executing bash commands in a Linux workspace.

Rules:
- You have access to: bash, python3, grep, sed, awk, curl, wget, jq, git, cat, echo, etc.
- Create output files in your workspace directory using bash commands.
- When you are done with the task, send exactly: done
- Be efficient — use as few steps as possible.
- Each response should contain exactly ONE bash command to execute. No explanations needed, just the command."""


def call_openrouter(
    messages: list[dict],
    model: str,
    api_key: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """Call OpenRouter API and return the assistant's response text."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/lilyzhng/apex-env",
        "X-Title": "APEX Baseline Eval",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    for attempt in range(3):
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            wait = 2 ** (attempt + 1)
            print(f"  Connection error: {e}, retrying in {wait}s...")
            time.sleep(wait)
            continue

    return "done"  # fallback: end episode if API keeps failing


def extract_command(response: str) -> str:
    """Extract a bash command from the model's response.

    Handles cases where the model wraps the command in ```bash ... ``` blocks,
    or adds explanations before/after the command.
    """
    # Try to extract from code block first
    import re
    code_blocks = re.findall(r"```(?:bash|sh)?\n(.*?)```", response, re.DOTALL)
    if code_blocks:
        # Use the first code block, take the full content
        return code_blocks[0].strip()

    # If response is short and looks like a command, use as-is
    lines = [l for l in response.strip().split("\n") if l.strip() and not l.startswith("#")]
    if lines:
        # If first non-comment line looks like a command, return it
        first = lines[0].strip()
        if first.lower() == "done" or not first.startswith(("I ", "Let ", "The ", "This ", "Here ", "Now ")):
            return first

    # Fallback: return the whole thing, let bash deal with it
    return response.strip()


def run_episode(
    env: ApexEnvironment,
    task_id: str,
    model: str,
    api_key: str,
    max_steps: int = 20,
    verbose: bool = False,
) -> dict:
    """Run a single evaluation episode. Returns result dict."""
    # Reset environment with specific task
    obs = env.reset(task_id=task_id)
    instruction = obs.stdout
    task_domain = obs.metadata.get("domain", "unknown")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": instruction},
    ]

    steps = []
    total_tokens_est = 0
    start_time = time.time()

    for step_num in range(1, max_steps + 1):
        # Get model's response
        response = call_openrouter(messages, model, api_key)
        command = extract_command(response)
        total_tokens_est += len(response.split()) * 2  # rough estimate

        if verbose:
            cmd_preview = command[:80] + "..." if len(command) > 80 else command
            print(f"  Step {step_num}: {cmd_preview}")

        # Execute in environment
        obs = env.step(BashAction(command=command))

        steps.append({
            "step": step_num,
            "command": command,
            "stdout": obs.stdout[:500],
            "stderr": obs.stderr[:200],
            "exit_code": obs.exit_code,
        })

        if obs.done:
            if verbose:
                print(f"  -> Done! Reward: {obs.reward:.3f}")
            break

        # Add observation to conversation
        output = ""
        if obs.stdout:
            output += obs.stdout[:2000]
        if obs.stderr:
            output += f"\nSTDERR: {obs.stderr[:500]}"
        if not output:
            output = f"(exit code {obs.exit_code}, no output)"

        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": f"Output:\n{output}"})

    elapsed = time.time() - start_time

    return {
        "task_id": task_id,
        "domain": task_domain,
        "model": model,
        "reward": obs.reward if obs.reward is not None else 0.0,
        "steps_taken": len(steps),
        "done_signal": obs.done,
        "elapsed_s": round(elapsed, 1),
        "steps": steps,
    }


def load_completed_tasks(resume_path: str) -> set[str]:
    """Load task IDs already completed from a previous run."""
    completed = set()
    path = Path(resume_path)
    if path.exists():
        with open(path) as f:
            for line in f:
                if line.strip():
                    result = json.loads(line)
                    completed.add(str(result["task_id"]))
    return completed


def main():
    parser = argparse.ArgumentParser(description="APEX Baseline Evaluation via OpenRouter")
    parser.add_argument("--model", default="qwen/qwen3-coder-next",
                        help="OpenRouter model ID")
    parser.add_argument("--limit", type=int, default=0,
                        help="Number of tasks to evaluate (0 = all)")
    parser.add_argument("--max-steps", type=int, default=20,
                        help="Max steps per episode")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to previous JSONL to resume from")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory (default: eval/results/)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print step-by-step output")
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()

    # API key
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        # Try loading from .env
        env_file = APEX_ENV_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not api_key:
            print("Error: OPENROUTER_API_KEY not set. Export it or add to .env")
            sys.exit(1)

    # Output path
    output_dir = Path(args.output_dir) if args.output_dir else APEX_ENV_DIR / "eval" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_slug = args.model.replace("/", "_")
    output_path = output_dir / f"baseline_{model_slug}_{timestamp}.jsonl"

    # Resume support
    completed_tasks = set()
    if args.resume:
        completed_tasks = load_completed_tasks(args.resume)
        output_path = Path(args.resume)  # append to same file
        print(f"Resuming from {args.resume}, {len(completed_tasks)} tasks already done")

    # Load tasks
    env = ApexEnvironment()
    env._task_loader._load()
    all_tasks = env._task_loader._tasks
    assert all_tasks is not None

    # Dataset uses capitalized keys: "Task ID", "Domain", "Prompt", "Rubric JSON"
    task_ids = [str(t.get("task_id") or t.get("Task ID") or i) for i, t in enumerate(all_tasks)]
    task_ids = [tid for tid in task_ids if tid not in completed_tasks]

    if args.limit > 0:
        task_ids = task_ids[: args.limit]

    print(f"APEX Baseline Evaluation")
    print(f"  Model: {args.model}")
    print(f"  Tasks: {len(task_ids)} (of {len(all_tasks)} total)")
    print(f"  Max steps: {args.max_steps}")
    print(f"  Output: {output_path}")
    print()

    # Run evaluation
    rewards = []
    domain_rewards: dict[str, list[float]] = {}

    for i, task_id in enumerate(task_ids):
        print(f"[{i+1}/{len(task_ids)}] Task {task_id}...", end=" ", flush=True)

        try:
            result = run_episode(
                env, task_id, args.model, api_key,
                max_steps=args.max_steps,
                verbose=args.verbose,
            )

            rewards.append(result["reward"])
            domain = result["domain"]
            domain_rewards.setdefault(domain, []).append(result["reward"])

            if not args.verbose:
                print(f"reward={result['reward']:.3f}  steps={result['steps_taken']}  "
                      f"({result['elapsed_s']}s)")

            # Write result immediately (crash-safe)
            with open(output_path, "a") as f:
                f.write(json.dumps(result) + "\n")

        except Exception as e:
            print(f"ERROR: {e}")
            continue
        finally:
            env.close()

    # Print summary
    print()
    print("=" * 60)
    print(f"BASELINE RESULTS: {args.model}")
    print("=" * 60)

    if rewards:
        avg = sum(rewards) / len(rewards)
        print(f"  Overall:  {avg:.3f}  (n={len(rewards)})")

        for domain, dr in sorted(domain_rewards.items()):
            davg = sum(dr) / len(dr)
            print(f"  {domain:12s}: {davg:.3f}  (n={len(dr)})")

        print(f"\n  Min: {min(rewards):.3f}  Max: {max(rewards):.3f}")
        non_zero = sum(1 for r in rewards if r > 0)
        print(f"  Non-zero rewards: {non_zero}/{len(rewards)} ({100*non_zero/len(rewards):.0f}%)")
    else:
        print("  No results collected.")

    print(f"\n  Results saved to: {output_path}")

    # Also write a summary JSON
    if rewards:
        summary = {
            "model": args.model,
            "timestamp": timestamp,
            "n_tasks": len(rewards),
            "mean_reward": round(sum(rewards) / len(rewards), 4),
            "min_reward": round(min(rewards), 4),
            "max_reward": round(max(rewards), 4),
            "non_zero_pct": round(100 * non_zero / len(rewards), 1),
            "domain_means": {
                d: round(sum(dr) / len(dr), 4)
                for d, dr in sorted(domain_rewards.items())
            },
        }
        summary_path = output_path.with_suffix(".summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"  Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
