"""
Dry-run rollout test — run base model through environments WITHOUT training.

Checks:
  1. Environment reset/step/finish loop works
  2. Model generates reasonable bash commands
  3. Reward signals (tool use/composition/creation + correctness) make sense

Usage:
    # Test all domains locally (no GPU needed, uses API)
    python train/test_rollout.py

    # Test specific domain
    python train/test_rollout.py --domain handdraw

    # Use a specific model via API
    python train/test_rollout.py --model gpt-4o-mini --max-turns 8
"""

import argparse
import os
import sys
from pathlib import Path

# Add environment code to path
_server_dir = Path(__file__).resolve().parent.parent / "server_space" / "apex_env" / "server"
sys.path.insert(0, str(_server_dir))


SYSTEM_PROMPT = (
    "You are a professional analyst. You solve tasks by executing bash commands one at a time.\n"
    "You have access to: python3, grep, awk, sed, jq, and standard unix tools.\n"
    "Each response should contain EXACTLY ONE bash command to execute.\n"
    "Do NOT wrap commands in markdown code blocks. Just output the raw command.\n"
    "After seeing the result, decide your next command.\n"
    "When you have completed the task and written your output files, respond with exactly: done"
)


def create_env(domain: str, task_id: str | None = None):
    """Create an environment instance."""
    if domain == "handdraw":
        from handdraw_env import HandDrawEnvironment
        return HandDrawEnvironment(task_id=task_id or "hourglass")
    elif domain == "ib":
        from building_block_env import BuildingBlockEnvironment
        return BuildingBlockEnvironment()
    elif domain == "law":
        from law_env import LawEnvironment
        return LawEnvironment()
    elif domain == "consulting":
        from consulting_env import ConsultingEnvironment
        return ConsultingEnvironment()
    else:
        raise ValueError(f"Unknown domain: {domain}")


def _load_env_file():
    """Load .env.local for API keys."""
    env_path = Path.home() / "Documents" / "lilyzhng" / "2026" / ".env.local"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

_load_env_file()


def call_model(messages: list[dict], model: str) -> str:
    """Call model via OpenRouter API."""
    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_APIKEY"),
    )
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=512,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


def extract_command(text: str) -> str:
    """Extract bash command from model output."""
    command = text.strip()
    lines = command.split("\n")
    code_lines = []
    in_block = False
    for line in lines:
        if line.strip().startswith("```"):
            if in_block:
                break
            in_block = True
            continue
        if in_block:
            code_lines.append(line)
    if code_lines:
        command = "\n".join(code_lines).strip()
    if command.lower() in ("done", '"done"'):
        command = "done"
    return command


def run_episode(env, model: str, max_turns: int = 10, verbose: bool = True):
    """Run a single episode: model ↔ environment interaction loop."""
    result = env.reset()
    observation = result["stdout"]

    if verbose:
        print(f"\n{'='*60}")
        print(f"ENVIRONMENT RESET")
        print(f"{'='*60}")
        print(observation)

    for turn in range(max_turns):
        if result.get("done"):
            break

        # Build messages
        user_content = observation if turn == 0 else f"Command output:\n{observation}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        # Get model's action
        raw_response = call_model(messages, model)
        command = extract_command(raw_response)

        if verbose:
            print(f"\n--- Turn {turn + 1} ---")
            print(f"MODEL: {command}")

        # Step environment
        result = env.step(command)
        observation = result["stdout"]

        if verbose:
            # Truncate long outputs
            display = observation[:500] + "..." if len(observation) > 500 else observation
            print(f"ENV:   {display}")

    # If we hit max turns without done, force finish
    if not result.get("done"):
        if verbose:
            print(f"\n--- Max turns reached, forcing done ---")
        result = env.step("done")
        observation = result["stdout"]

    if verbose:
        print(f"\n{'='*60}")
        print(f"EPISODE RESULT")
        print(f"{'='*60}")
        print(observation)
        print(f"\nReward: {result.get('reward', 'N/A')}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Test rollout quality")
    parser.add_argument("--domain", default="all",
                        choices=["handdraw", "ib", "law", "consulting", "all"])
    parser.add_argument("--task-id", default=None,
                        help="Task ID within domain (e.g., flower, temple, cherry_blossom)")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--episodes", type=int, default=1,
                        help="Number of episodes per domain")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    domains = ["handdraw", "ib", "law", "consulting"] if args.domain == "all" else [args.domain]

    print(f"Testing rollout: model={args.model}, domains={domains}, "
          f"max_turns={args.max_turns}, episodes={args.episodes}")

    results_summary = []

    for domain in domains:
        print(f"\n{'#'*60}")
        print(f"# DOMAIN: {domain}")
        print(f"{'#'*60}")

        for ep in range(args.episodes):
            env = create_env(domain, task_id=args.task_id)
            try:
                result = run_episode(
                    env, args.model,
                    max_turns=args.max_turns,
                    verbose=not args.quiet,
                )
                results_summary.append({
                    "domain": domain,
                    "episode": ep + 1,
                    "reward": result.get("reward", 0),
                    "criteria_met": result.get("criteria_met", 0),
                    "criteria_total": result.get("criteria_total", 0),
                    "steps": result.get("step", 0),
                })
            finally:
                env.close()

    # Summary table
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"{'Domain':<15} {'Ep':<4} {'Reward':<8} {'Criteria':<12} {'Steps':<6}")
    print(f"{'-'*45}")
    for r in results_summary:
        print(f"{r['domain']:<15} {r['episode']:<4} {r['reward']:<8.3f} "
              f"{r['criteria_met']}/{r['criteria_total']:<9} {r['steps']:<6}")


if __name__ == "__main__":
    main()
