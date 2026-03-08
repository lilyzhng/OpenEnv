"""Run an agent through the phased KatNip environment and see what happens.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --model openai/gpt-4o-mini
    python scripts/run_demo.py --sandbox  # run in Docker
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

from building_block_env import BuildingBlockEnvironment


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are an IB analyst. You solve tasks by executing bash commands one at a time.\n"
    "You have access to: python3, numpy, grep, find, cat, and standard unix tools.\n"
    "Each response should contain EXACTLY ONE bash command to execute.\n"
    "Do NOT wrap commands in markdown code blocks. Just output the raw command.\n"
    "For Python code, write a .py file first, then run it with python3 IN A SEPARATE STEP.\n"
    "IMPORTANT: numpy.irr is removed. For IRR, use scipy.optimize.brentq or Newton's method.\n"
    "IMPORTANT: After writing ANY file, you MUST run it — unexecuted scripts produce nothing.\n"
    "Explore your workspace to find the data you need — not everything is relevant.\n"
    "Check the tools/ directory for utility scripts that may help.\n"
    "Pay attention to [Progress] feedback — it tells you how many criteria you've met.\n"
    "Write all final answers to analysis.txt with the actual computed numbers.\n"
    "When finished, respond with exactly: done"
)


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
    stripped = response.strip().lower()
    if stripped in ("done", '"done"', "'done'"):
        return "done"

    lines = response.strip().split("\n")

    # Check for markdown code block
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
        cmd = "\n".join(code_lines).strip()
        return cmd

    # Find the first command-like line, then check if it's a heredoc
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

    # Handle heredoc: if the line contains << 'EOF' or << EOF, capture until EOF
    import re
    heredoc_match = re.search(r"<<\s*'?(\w+)'?", first_line)
    if heredoc_match:
        delimiter = heredoc_match.group(1)
        heredoc_lines = [first_line]
        for line in lines[cmd_start + 1:]:
            heredoc_lines.append(line)
            if line.strip() == delimiter:
                break
        return "\n".join(heredoc_lines)

    # Handle multi-line quoted commands (echo '...' > file, printf "..." > file)
    # If the first command line has an unclosed quote, capture until closing quote + redirect
    remaining = "\n".join(lines[cmd_start:])
    for quote_char in ["'", '"']:
        # Count quotes in first line (excluding escaped ones)
        count = first_line.count(quote_char) - first_line.count("\\" + quote_char)
        if count % 2 == 1:  # Unclosed quote
            # Find the closing quote in subsequent lines
            multi_lines = [first_line]
            for line in lines[cmd_start + 1:]:
                multi_lines.append(line)
                line_count = line.count(quote_char) - line.count("\\" + quote_char)
                if line_count % 2 == 1:  # Found closing quote
                    # Also grab any redirect after the closing quote line
                    break
            return "\n".join(multi_lines)

    return first_line.strip()


def main():
    parser = argparse.ArgumentParser(description="Run agent through phased KatNip environment")
    parser.add_argument("--model", default="qwen/qwen3-coder-30b-a3b-instruct")
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--sandbox", action="store_true")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("ERROR: Set OPENROUTER_APIKEY")
        sys.exit(1)

    print(f"Model: {args.model}")
    print(f"Max turns: {args.max_turns}")
    print("=" * 70)

    env = BuildingBlockEnvironment()
    obs = env.reset()

    print(f"\n{'='*70}")
    print("ENVIRONMENT → AGENT")
    print(f"{'='*70}")
    print(obs["stdout"][:1000])

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": obs["stdout"]},
    ]

    for turn in range(args.max_turns):
        print(f"\n{'─'*70}")
        print(f"TURN {turn + 1}/{args.max_turns}")
        print(f"{'─'*70}")

        # Get agent response
        try:
            response = call_model(messages, args.model, api_key)
        except Exception as e:
            print(f"API error: {e}")
            break

        command = extract_command(response)
        print(f"\nAGENT says: {response[:200]}")
        print(f"COMMAND: {command}")

        if command.strip().lower() == "done":
            obs = env.step("done")
            print(f"\n{'='*70}")
            print("FINAL RESULT")
            print(f"{'='*70}")
            print(obs["stdout"])
            print(f"\nReward: {obs['reward']}")
            break

        # Execute in environment
        obs = env.step(command)

        print(f"\nENVIRONMENT → AGENT:")
        # Show truncated output
        stdout = obs["stdout"]
        if len(stdout) > 1500:
            print(stdout[:1500] + "\n... (truncated)")
        else:
            print(stdout)

        print(f"Progress: {obs['criteria_met']}/{obs['criteria_total']} criteria met")

        # Feed back to agent
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": obs["stdout"][:3000]})
    else:
        # Hit max turns
        obs = env.step("done")
        print(f"\n{'='*70}")
        print("MAX TURNS REACHED — FINAL RESULT")
        print(f"{'='*70}")
        print(obs["stdout"])
        print(f"\nReward: {obs['reward']}")

    env.close()

    # Save results
    output = {
        "model": args.model,
        "max_turns": args.max_turns,
        "final_reward": obs.get("reward"),
        "criteria_met": obs.get("criteria_met"),
        "criteria_total": obs.get("criteria_total"),
        "steps_used": obs.get("step"),
    }
    output_path = Path("data/demo_result.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
