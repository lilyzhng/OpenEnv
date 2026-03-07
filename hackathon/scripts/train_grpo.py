"""
GRPO training on APEX professional tasks using TRL + OpenEnv.

The agent learns to solve real-world tasks (law, IB, consulting) by executing
bash commands in a sandbox. Reward comes from rubric-based evaluation of the
agent's workspace output — not keyword matching.

This follows the official TRL OpenEnv integration pattern:
  https://huggingface.co/docs/trl/main/en/openenv

Usage:
    # Local with colocate vLLM (1 GPU, e.g. A100-80GB)
    python scripts/train_grpo.py

    # With remote environment on HF Space
    python scripts/train_grpo.py --env-url https://lilyzhng-apex-env-server.hf.space

    # Modal (recommended for real training)
    modal run scripts/train_grpo.py
"""

import argparse
import sys
from pathlib import Path

from datasets import load_dataset
from transformers import AutoTokenizer

from trl import GRPOConfig, GRPOTrainer
from trl.experimental.openenv import generate_rollout_completions

# Add server modules to path for local environment
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "apex_env" / "server"))


# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------

def make_local_env():
    """Create a local ApexEnvironment instance (no Docker/server needed)."""
    from task_loader import TaskLoader
    from bash_executor import BashExecutor
    from reward import compute_reward

    import shutil
    import tempfile

    class LocalApexEnv:
        """Lightweight local env that doesn't need openenv installed."""

        def __init__(self, dataset_name="mercor/APEX-v1-extended"):
            self._loader = TaskLoader(dataset_name=dataset_name)
            self._executor = BashExecutor()
            self._task = None
            self._workspace = None
            self._step_count = 0
            self._max_steps = 10
            self._actions = []

        def reset(self, task_idx=None):
            """Reset environment with a new task."""
            if self._workspace and Path(self._workspace).exists():
                shutil.rmtree(self._workspace, ignore_errors=True)

            self._loader._load()
            if task_idx is not None:
                self._task = self._loader._tasks[task_idx % len(self._loader)]
            else:
                import random
                self._task = random.choice(self._loader._tasks)

            self._workspace = Path(tempfile.mkdtemp(prefix="apex_train_"))
            self._step_count = 0
            self._actions = []

            # Download input files if available
            self._download_files()

            prompt = self._task.get("Prompt", self._task.get("prompt", ""))
            domain = self._task.get("Domain", self._task.get("domain", ""))
            task_id = self._task.get("Task ID", self._task.get("task_id", ""))

            instruction = (
                f"# Task: {task_id}\n"
                f"# Domain: {domain}\n\n"
                f"{prompt}\n\n"
                f"Your workspace is: {self._workspace}\n"
                f"Create your output files in the workspace directory.\n"
                f"When finished, send the command: done"
            )
            return {"observation": instruction, "done": False, "reward": None}

        def step(self, action_text: str):
            """Execute a bash action, return observation + reward."""
            self._step_count += 1
            self._actions.append(action_text)

            # Check done signal
            if action_text.strip().lower() == "done":
                reward = self._compute_reward()
                return {"observation": "Episode finished.", "done": True, "reward": reward}

            # Execute bash
            result = self._executor.run(action_text, cwd=self._workspace, timeout_s=30.0)

            obs = ""
            if result.stdout:
                obs += result.stdout[:2000]
            if result.stderr:
                obs += f"\nSTDERR: {result.stderr[:500]}"
            if result.exit_code != 0:
                obs += f"\nEXIT CODE: {result.exit_code}"
            if not obs.strip():
                obs = "(no output)"

            # Check step limit
            at_limit = self._step_count >= self._max_steps
            reward = None
            if at_limit:
                reward = self._compute_reward()

            return {"observation": obs, "done": at_limit, "reward": reward}

        def _compute_reward(self):
            return compute_reward(self._task, self._workspace)

        def _download_files(self):
            """Download input files from HF to workspace."""
            file_attachments = self._task.get("File Attachments", "")
            if not file_attachments:
                return
            try:
                from huggingface_hub import hf_hub_download
                for fpath in file_attachments.strip().split("\n"):
                    fpath = fpath.strip()
                    if not fpath:
                        continue
                    local = hf_hub_download(
                        "mercor/APEX-v1-extended",
                        fpath,
                        repo_type="dataset",
                    )
                    fname = Path(fpath).name
                    import shutil as _sh
                    _sh.copy2(local, self._workspace / fname)
            except Exception:
                pass

        def close(self):
            if self._workspace and Path(self._workspace).exists():
                shutil.rmtree(self._workspace, ignore_errors=True)

    return LocalApexEnv()


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a professional analyst. You solve tasks by executing bash commands one at a time.\n"
    "You have access to: python3, grep, awk, sed, jq, and standard unix tools.\n"
    "Each response should contain EXACTLY ONE bash command to execute.\n"
    "Do NOT wrap commands in markdown code blocks. Just output the raw command.\n"
    "After seeing the result, decide your next command.\n"
    "When you have completed the task and written your output files, respond with exactly: done"
)


# ---------------------------------------------------------------------------
# Rollout function — multi-turn agent ↔ environment interaction
# ---------------------------------------------------------------------------

def make_rollout_func(env, tokenizer, max_turns=6):
    """Create a rollout function compatible with TRL GRPOTrainer."""

    def rollout_func(prompts: list[str], trainer: GRPOTrainer) -> dict[str, list]:
        all_prompt_ids = []
        all_completion_ids = []
        all_logprobs = []
        all_env_rewards = []

        for prompt_text in prompts:
            # Reset environment with a random task
            result = env.reset()
            observation = result["observation"]

            episode_prompt_ids = []
            episode_completion_ids = []
            episode_logprobs = []

            for turn in range(max_turns):
                if result.get("done"):
                    break

                # Build messages for this turn
                user_content = observation if turn == 0 else f"Command output:\n{observation}"
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ]
                turn_prompt = tokenizer.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    tokenize=False,
                )

                # Generate completion
                outputs = generate_rollout_completions(trainer, [turn_prompt])[0]
                episode_prompt_ids.extend(outputs["prompt_ids"])
                episode_completion_ids.extend(outputs["completion_ids"])
                episode_logprobs.extend(outputs["logprobs"])

                completion_text = outputs.get("text") or tokenizer.decode(
                    outputs["completion_ids"], skip_special_tokens=True
                )

                # Extract bash command (strip code blocks if present)
                command = completion_text.strip()
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

                # Step environment
                result = env.step(command)
                observation = result["observation"]

            # Get final reward
            reward = result.get("reward") or 0.0
            all_env_rewards.append(reward)
            all_prompt_ids.append(episode_prompt_ids)
            all_completion_ids.append(episode_completion_ids)
            all_logprobs.append(episode_logprobs)

        return {
            "prompt_ids": all_prompt_ids,
            "completion_ids": all_completion_ids,
            "logprobs": all_logprobs,
            "env_reward": all_env_rewards,
        }

    return rollout_func


# ---------------------------------------------------------------------------
# Reward function — extracts env_reward from rollout kwargs
# ---------------------------------------------------------------------------

def reward_from_env(completions, **kwargs):
    """Extract environment rewards passed via rollout_func."""
    rewards = kwargs.get("env_reward", [])
    return [float(r) for r in rewards] if rewards else [0.0] * len(completions)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def load_apex_dataset(dataset_name="mercor/APEX-v1-extended", max_tasks=None):
    """Load APEX-v1-extended as a simple prompt dataset for GRPO."""
    ds = load_dataset(dataset_name, split="train")
    if max_tasks:
        ds = ds.select(range(min(max_tasks, len(ds))))

    # Convert to simple prompt format expected by GRPOTrainer
    def to_prompt(row):
        prompt = row.get("Prompt", row.get("prompt", ""))
        domain = row.get("Domain", row.get("domain", ""))
        task_id = row.get("Task ID", row.get("task_id", ""))
        row["prompt"] = (
            f"[{domain}] Task {task_id}: {prompt[:500]}"
        )
        return row

    ds = ds.map(to_prompt)
    return ds


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GRPO training on APEX tasks")
    parser.add_argument("--model", default="Qwen/Qwen3-Coder-30B-A3B-Instruct",
                        help="Base model for training")
    parser.add_argument("--dataset", default="mercor/APEX-v1-extended")
    parser.add_argument("--max-tasks", type=int, default=None,
                        help="Limit number of training tasks (None = all 100)")
    parser.add_argument("--max-turns", type=int, default=6,
                        help="Max turns per episode")
    parser.add_argument("--num-generations", type=int, default=4,
                        help="GRPO generations per prompt")
    parser.add_argument("--max-steps", type=int, default=50,
                        help="Training steps")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=5e-6)
    parser.add_argument("--output-dir", default="checkpoints/apex-grpo")
    parser.add_argument("--env-url", default=None,
                        help="Remote environment URL (if None, run locally)")
    args = parser.parse_args()

    print(f"Loading dataset: {args.dataset}")
    dataset = load_apex_dataset(args.dataset, args.max_tasks)
    print(f"Loaded {len(dataset)} tasks")

    print(f"Loading tokenizer: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model)

    print("Creating environment...")
    env = make_local_env()

    print("Setting up GRPO trainer...")
    rollout_fn = make_rollout_func(env, tokenizer, max_turns=args.max_turns)

    grpo_config = GRPOConfig(
        output_dir=args.output_dir,
        num_train_epochs=1,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        num_generations=args.num_generations,
        max_completion_length=512,
        learning_rate=args.lr,
        use_vllm=True,
        vllm_mode="colocate",
        logging_steps=1,
        save_steps=25,
        report_to="wandb",
        run_name="apex-grpo",
    )

    trainer = GRPOTrainer(
        model=args.model,
        processing_class=tokenizer,
        reward_funcs=reward_from_env,
        train_dataset=dataset,
        rollout_func=rollout_fn,
        args=grpo_config,
    )

    print("Starting training...")
    trainer.train()

    print(f"Training complete. Checkpoints saved to {args.output_dir}")
    env.close()


if __name__ == "__main__":
    main()
