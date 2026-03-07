"""
Multi-turn baseline evaluation on mercor/apex-agents using OpenRouter API.

This is REAL eval: model generates bash actions → ApexEnvironment executes them
→ model sees results → repeats → final reward from rubric.

NOT keyword matching on static text. The model actually ACTS.

Usage:
    # Quick test (3 tasks, free model)
    python scripts/baseline_eval.py --num-tasks 3 --model qwen/qwen3-coder:free

    # Baseline with both training base models (20 tasks each)
    python scripts/baseline_eval.py --num-tasks 20 --model qwen/qwen3-coder-30b-a3b-instruct
    python scripts/baseline_eval.py --num-tasks 20 --model qwen/qwen3-coder-next

    # Compare models
    python scripts/baseline_eval.py --num-tasks 50 --model qwen/qwen3-coder-next --output data/eval_next.json
    python scripts/baseline_eval.py --num-tasks 50 --model qwen/qwen3-coder-30b-a3b-instruct --output data/eval_30b.json
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

from huggingface_hub import hf_hub_download, list_repo_tree

# Import server components directly to avoid heavy OpenEnv client deps
# We add the server directory to path to bypass apex_env/__init__.py
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "apex_env" / "server"))

from task_loader import TaskLoader
from reward import compute_reward
from bash_executor import BashExecutor


# ---------------------------------------------------------------------------
# OpenRouter API
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
    """Call OpenRouter API and return the assistant's response text."""
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
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Multi-turn rollout
# ---------------------------------------------------------------------------

def _is_talk(line: str) -> bool:
    """Return True if a line looks like natural-language commentary, not a bash command."""
    s = line.strip()
    if not s:
        return True
    # Common sentence starters from frontier models
    talk_prefixes = (
        "I ", "I'", "Let me", "Now ", "First", "Next", "The ", "This ",
        "Here", "Sure", "OK", "Okay", "Great", "Note", "Since ", "To ",
        "We ", "My ", "After", "Before", "Based", "Looking", "There ",
    )
    if any(s.startswith(p) for p in talk_prefixes):
        return True
    # Lines that end with common sentence punctuation but no shell metacharacters
    if s.endswith((".")) and not any(c in s for c in "|>&;$`"):
        return True
    return False


def _strip_trailing_done(cmd: str) -> tuple[str, bool]:
    """Strip 'done' appended to end of command. Returns (clean_cmd, had_done)."""
    if cmd.rstrip().endswith("done") and len(cmd.rstrip()) > 4:
        candidate = cmd.rstrip()[:-4].rstrip()
        # Only strip if what remains looks like a valid command ending
        if candidate and candidate[-1] in "\"'|/\\)}>]0123456789abcdefghijklmnopqrstuvwxyz":
            return candidate, True
    return cmd, False


def extract_command(response: str) -> str:
    """Extract a bash command from model response.

    Handles:
    - Raw bash commands (single and multi-line with heredocs)
    - ```bash ... ``` code blocks
    - <tool_call> JSON with command/code arguments (Qwen function calling format)
    - Natural language filtering (frontier models talk before acting)
    - 'done' appended to end of commands
    """
    # Check for done signal
    stripped_resp = response.strip().lower()
    if stripped_resp in ("done", '"done"', "'done'"):
        return "done"

    # Try to extract from <tool_call> JSON blocks
    tool_call_match = re.search(
        r"<tool_call>\s*(\{.*?\})\s*</tool_call>", response, re.DOTALL
    )
    if tool_call_match:
        try:
            call_json = json.loads(tool_call_match.group(1))
            args = call_json.get("arguments", call_json.get("parameters", {}))
            cmd = args.get("command", args.get("code", args.get("cmd", "")))
            if cmd:
                return cmd.strip()
        except (json.JSONDecodeError, AttributeError):
            pass

    # Try to extract from code block
    lines = response.strip().split("\n")
    in_code_block = False
    code_lines = []
    for line in lines:
        if line.strip().startswith("```"):
            if in_code_block:
                break
            in_code_block = True
            continue
        if in_code_block:
            code_lines.append(line)

    if code_lines:
        cmd = "\n".join(code_lines).strip()
        cmd, _ = _strip_trailing_done(cmd)
        return cmd

    # No code block — extract from raw text
    # Filter out talk lines, collect command lines (with heredoc support)
    cmd_lines = []
    in_heredoc = False
    heredoc_delim = None
    for line in lines:
        stripped = line.strip()

        # Inside a heredoc, capture everything until delimiter
        if in_heredoc:
            cmd_lines.append(line)
            if stripped == heredoc_delim:
                in_heredoc = False
            continue

        # Skip talk / commentary lines
        if _is_talk(stripped):
            # But if we already have command lines, stop — talk after command = explanation
            if cmd_lines:
                break
            continue

        # Skip comment-only lines
        if stripped.startswith("#"):
            if cmd_lines:
                break
            continue

        # This looks like a command line
        cmd_lines.append(stripped)

        # Check if this line starts a heredoc
        heredoc_match = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", stripped)
        if heredoc_match:
            in_heredoc = True
            heredoc_delim = heredoc_match.group(1)

        # If not a heredoc and not a line continuation, take just this one command
        if not in_heredoc and not stripped.endswith("\\") and not stripped.endswith("|"):
            break

    if cmd_lines:
        cmd = "\n".join(cmd_lines).strip()
        cmd, had_done = _strip_trailing_done(cmd)
        if had_done and not cmd:
            return "done"
        return cmd

    return response.strip()


def populate_workspace(task_id: str, workspace: Path, repo_id: str = "mercor/apex-agents") -> list[str]:
    """Download task input files from HuggingFace to workspace.

    Returns list of downloaded filenames.
    """
    prefix = f"task_files/{task_id}/filesystem/"
    downloaded = []
    try:
        tree = list_repo_tree(repo_id, path_in_repo=f"task_files/{task_id}/filesystem", repo_type="dataset")
        for item in tree:
            if hasattr(item, "rfilename"):
                rfilename = item.rfilename
            else:
                # item.path is full path like task_files/task_xxx/filesystem/file.pdf
                rfilename = item.path
            local = hf_hub_download(repo_id, rfilename, repo_type="dataset")
            # Extract just the filename
            fname = Path(rfilename).name
            dest = workspace / fname
            import shutil as _shutil
            _shutil.copy2(local, dest)
            downloaded.append(fname)
    except Exception:
        pass
    return downloaded


def run_episode(
    task: dict,
    task_idx: int,
    executor: BashExecutor,
    model: str,
    api_key: str,
    max_turns: int = 10,
) -> dict:
    """Run a single multi-turn episode: model ↔ bash environment."""
    import shutil
    import tempfile

    domain = task.get("domain", "unknown")
    task_id = task.get("task_id", "unknown")
    prompt = task.get("prompt", "")

    # Create isolated workspace
    workspace = Path(tempfile.mkdtemp(prefix=f"apex_eval_{task_idx}_"))

    # Populate workspace with task input files from HuggingFace
    input_files = populate_workspace(task_id, workspace)
    if input_files:
        print(f"    loaded {len(input_files)} input files: {input_files[:3]}")

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

    actions_taken = []

    for turn in range(max_turns):
        # Model generates action
        try:
            response = call_model(messages, model, api_key)
        except Exception as e:
            print(f"    API error at turn {turn}: {e}")
            break

        command = extract_command(response)
        actions_taken.append(command)

        # Check done
        if command.strip().lower() == "done":
            break

        # Execute in workspace
        result = executor.run(command, cwd=workspace, timeout_s=30.0)

        # Build observation
        obs_text = ""
        if result.stdout:
            obs_text += f"STDOUT:\n{result.stdout[:2000]}\n"
        if result.stderr:
            obs_text += f"STDERR:\n{result.stderr[:1000]}\n"
        if result.exit_code != 0:
            obs_text += f"EXIT CODE: {result.exit_code}\n"
        if not obs_text:
            obs_text = "(no output)"

        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": obs_text})

    # Compute reward
    reward = compute_reward(task, workspace)

    # Cleanup
    shutil.rmtree(workspace, ignore_errors=True)

    return {
        "task_id": task_id,
        "task_idx": task_idx,
        "domain": domain,
        "reward": reward,
        "num_turns": len(actions_taken),
        "actions": actions_taken,
        "model": model,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Multi-turn baseline eval on apex-agents")
    parser.add_argument("--model", default="qwen/qwen3-coder:free",
                        help="OpenRouter model ID")
    parser.add_argument("--num-tasks", type=int, default=10)
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--dataset", default="mercor/apex-agents",
                        help="Eval dataset (default: apex-agents, NOT v1-extended)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON (default: data/eval_{model_short}.json)")
    parser.add_argument("--skip-file-tasks", action="store_true", default=False,
                        help="Skip tasks that require input files (default: False, files are downloaded from HF)")
    args = parser.parse_args()

    # API key
    api_key = os.environ.get("OPENROUTER_APIKEY", "")
    if not api_key:
        env_path = Path(__file__).resolve().parent.parent.parent.parent / "2026" / ".env.local"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OPENROUTER_APIKEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        print("ERROR: Set OPENROUTER_APIKEY env var or check .env.local")
        sys.exit(1)

    # Load eval dataset
    print(f"Loading {args.dataset}...")
    loader = TaskLoader(dataset_name=args.dataset)
    loader._load()
    total = len(loader)
    print(f"Loaded {total} tasks")

    # Filter out tasks with file dependencies
    valid_indices = []
    for i in range(total):
        task = loader._tasks[i]
        has_files = task.get("task_input_files") is not None
        if args.skip_file_tasks and has_files:
            continue
        valid_indices.append(i)

    print(f"Valid tasks (no file deps): {len(valid_indices)}/{total}")

    # Stratified sampling by domain
    domain_indices = defaultdict(list)
    for i in valid_indices:
        domain = loader._tasks[i].get("domain", "unknown")
        domain_indices[domain].append(i)

    selected = []
    per_domain = max(1, args.num_tasks // len(domain_indices))
    for domain, indices in sorted(domain_indices.items()):
        take = min(per_domain, len(indices))
        selected.extend(indices[:take])
        print(f"  {domain}: {take} tasks")
    selected = selected[:args.num_tasks]

    # Run eval
    executor = BashExecutor()

    print(f"\nRunning eval: {len(selected)} tasks, model={args.model}, max_turns={args.max_turns}")
    print("=" * 60)

    results = []
    for i, task_idx in enumerate(selected):
        task = loader._tasks[task_idx]
        domain = task.get("domain", "?")
        print(f"\n[{i+1}/{len(selected)}] {domain} — task_idx={task_idx}")

        result = run_episode(task, task_idx, executor, args.model, api_key, args.max_turns)
        results.append(result)

        print(f"  reward={result['reward']:.2f}  turns={result['num_turns']}  actions={result['actions'][:3]}")

    # Report
    print("\n" + "=" * 60)
    print(f"BASELINE EVAL RESULTS — {args.model}")
    print("=" * 60)

    rewards = [r["reward"] for r in results]
    print(f"\nOverall: avg={sum(rewards)/len(rewards):.3f}  min={min(rewards):.2f}  max={max(rewards):.2f}")

    domains = sorted(set(r["domain"] for r in results))
    for domain in domains:
        domain_results = [r for r in results if r["domain"] == domain]
        domain_rewards = [r["reward"] for r in domain_results]
        avg_turns = sum(r["num_turns"] for r in domain_results) / len(domain_results)
        print(f"  {domain:25s}  n={len(domain_results)}  avg_reward={sum(domain_rewards)/len(domain_rewards):.3f}  avg_turns={avg_turns:.1f}")

    # Save
    model_short = args.model.split("/")[-1].replace(":", "-")
    output_path = args.output or f"data/eval_{model_short}.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"model": args.model, "results": results}, f, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
