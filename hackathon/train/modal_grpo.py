"""
GRPO training on SuperGeneral environments using Unsloth + TRL on Modal.

Trains an agent to use tools in recursive environments across 4 domains:
  - Hand-Draw (hourglass SVG illustration)
  - Investment Banking (KatNip Co. financial analysis)
  - Law (royalty dispute)
  - Consulting (market entry)

The agent interacts with real environments via bash commands.
Reward = process signals (tool use/composition/creation) + correctness.

Usage:
    # Sanity check (1 step, 1 domain)
    modal run train/modal_grpo.py --max-steps 1 --domains handdraw

    # Quick experiment (50 steps, all domains)
    modal run --detach train/modal_grpo.py --max-steps 50

    # Full training
    modal run --detach train/modal_grpo.py --num-epochs 1 --max-steps -1
"""

import modal
import random
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Modal setup
# ---------------------------------------------------------------------------

app = modal.App("supergeneral-grpo")

train_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("nodejs", "npm")  # hand-draw env needs node for Rough.js
    .pip_install(
        "unsloth[cu128-torch270]",
        "datasets",
        "hf-transfer",
        "wandb",
        "trl>=0.22.0",
    )
    .env(
        {
            "HF_HOME": "/model_cache",
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        }
    )
    # Copy environment code into the container
    .copy_local_dir(
        str(Path(__file__).resolve().parent.parent / "server_space" / "apex_env" / "server"),
        "/app/envs",
    )
)

model_cache_vol = modal.Volume.from_name("supergeneral-model-cache", create_if_missing=True)
checkpoint_vol = modal.Volume.from_name("supergeneral-checkpoints", create_if_missing=True)


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

def make_rollout_func(envs, tokenizer, max_turns=10):
    """Create a rollout function that runs agents through real environments.

    Args:
        envs: dict of domain_name → environment instance
        tokenizer: model tokenizer for chat template
        max_turns: max bash commands per episode
    """
    from trl.experimental.openenv import generate_rollout_completions

    domain_names = list(envs.keys())

    def rollout_func(prompts: list[str], trainer) -> dict[str, list]:
        all_prompt_ids = []
        all_completion_ids = []
        all_logprobs = []
        all_env_rewards = []

        for prompt_text in prompts:
            # Pick a random domain for this episode
            domain = random.choice(domain_names)
            env = envs[domain]

            # Reset environment
            result = env.reset()
            observation = result["stdout"]

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
                command = _extract_command(completion_text)

                # Step environment
                result = env.step(command)
                observation = result["stdout"]

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


def _extract_command(text: str) -> str:
    """Extract bash command from model output, stripping markdown code blocks."""
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


# ---------------------------------------------------------------------------
# Reward function — extracts env_reward from rollout kwargs
# ---------------------------------------------------------------------------

def reward_from_env(completions, **kwargs):
    """Extract environment rewards passed via rollout_func."""
    rewards = kwargs.get("env_reward", [])
    return [float(r) for r in rewards] if rewards else [0.0] * len(completions)


# ---------------------------------------------------------------------------
# Dataset — simple prompt dataset for GRPO
# ---------------------------------------------------------------------------

def _make_prompt_dataset(num_prompts: int = 100):
    """Create a simple dataset of task prompts for GRPO.

    Each prompt is a generic instruction. The actual task comes from
    the environment's reset() — the prompt just kicks off the episode.
    """
    from datasets import Dataset

    prompts = []
    for i in range(num_prompts):
        # The actual task content comes from env.reset(), not from the dataset.
        # This prompt is just the initial trigger for the rollout.
        prompts.append([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "You have a new task. Begin by exploring your workspace."},
        ])

    return Dataset.from_dict({"prompt": prompts})


# ---------------------------------------------------------------------------
# Environment factory
# ---------------------------------------------------------------------------

def _create_envs(domains: list[str]) -> dict:
    """Create environment instances for requested domains."""
    sys.path.insert(0, "/app/envs")

    envs = {}

    if "handdraw" in domains:
        from handdraw_env import HandDrawEnvironment
        envs["handdraw"] = HandDrawEnvironment(task_id="hourglass")

    if "ib" in domains:
        from building_block_env import BuildingBlockEnvironment
        envs["ib"] = BuildingBlockEnvironment()

    if "law" in domains:
        from law_env import LawEnvironment
        envs["law"] = LawEnvironment()

    if "consulting" in domains:
        from consulting_env import ConsultingEnvironment
        envs["consulting"] = ConsultingEnvironment()

    return envs


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------

@app.function(
    image=train_image,
    gpu=modal.gpu.A100(size="80GB"),
    volumes={
        "/model_cache": model_cache_vol,
        "/checkpoints": checkpoint_vol,
    },
    secrets=[
        modal.Secret.from_name("huggingface-secret"),
        modal.Secret.from_name("wandb-secret"),
    ],
    timeout=7200,
)
def run_grpo(
    model_name: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    domains: str = "handdraw,ib,law,consulting",
    max_steps: int = -1,
    num_epochs: int = 1,
    num_prompts: int = 100,
    max_turns: int = 10,
    lora_r: int = 16,
    num_generations: int = 4,
    max_completion_length: int = 1024,
    push_to_hub: bool = True,
    experiment_name: str = "",
    wandb_project: str = "supergeneral-grpo",
):
    import os
    import time

    import wandb
    from trl import GRPOConfig, GRPOTrainer
    from unsloth import FastLanguageModel

    # Auto-generate experiment name
    if not experiment_name:
        model_short = model_name.split("/")[-1].lower().replace("-", "_")
        experiment_name = f"sg_grpo_{model_short}_{int(time.time())}"

    domain_list = [d.strip() for d in domains.split(",")]

    print(f"=== SuperGeneral GRPO Training ===")
    print(f"  Model:           {model_name}")
    print(f"  Domains:         {domain_list}")
    print(f"  Experiment:      {experiment_name}")
    print(f"  Max turns/ep:    {max_turns}")
    print(f"  LoRA r:          {lora_r}")
    print(f"  Num generations: {num_generations}")
    print(f"  Max steps:       {max_steps}")

    # ---- Load model ----
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=4096,
        dtype=None,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_r,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=lora_r,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # ---- Create environments ----
    print("Creating environments...")
    envs = _create_envs(domain_list)
    print(f"  Active envs: {list(envs.keys())}")

    # ---- Prepare dataset ----
    dataset = _make_prompt_dataset(num_prompts)
    print(f"  Dataset size: {len(dataset)}")

    # ---- Rollout function ----
    rollout_fn = make_rollout_func(envs, tokenizer, max_turns=max_turns)

    # ---- Checkpoint path ----
    checkpoint_path = f"/checkpoints/{experiment_name}"
    os.makedirs(checkpoint_path, exist_ok=True)

    # ---- W&B init ----
    wandb.init(
        project=wandb_project,
        name=experiment_name,
        config={
            "model_name": model_name,
            "domains": domain_list,
            "lora_r": lora_r,
            "num_generations": num_generations,
            "max_steps": max_steps,
            "max_turns": max_turns,
            "num_prompts": num_prompts,
            "max_completion_length": max_completion_length,
        },
    )

    # ---- Training config ----
    training_args = GRPOConfig(
        output_dir=checkpoint_path,
        learning_rate=5e-6,
        per_device_train_batch_size=num_generations,
        gradient_accumulation_steps=1,
        num_generations=num_generations,
        temperature=1.0,
        max_prompt_length=1024,
        max_completion_length=max_completion_length,
        num_train_epochs=num_epochs,
        max_steps=max_steps,
        optim="adamw_8bit",
        lr_scheduler_type="linear",
        warmup_ratio=0.1,
        logging_steps=1,
        report_to="wandb",
        save_steps=50,
        save_strategy="steps",
        seed=3407,
    )

    # ---- Trainer ----
    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=reward_from_env,
        train_dataset=dataset,
        rollout_func=rollout_fn,
        args=training_args,
    )

    print("Starting training...")
    trainer.train()
    print("Training complete.")

    # ---- Save model ----
    trainer.save_model(checkpoint_path)
    print(f"Model saved to {checkpoint_path}")

    if push_to_hub:
        hub_repo = f"lilyzhng/{experiment_name}"
        print(f"Pushing LoRA adapter to HuggingFace: {hub_repo}")
        model.push_to_hub(hub_repo, tokenizer=tokenizer)
        print(f"Pushed to https://huggingface.co/{hub_repo}")

    # ---- Cleanup ----
    for env in envs.values():
        env.close()

    checkpoint_vol.commit()
    model_cache_vol.commit()

    wandb.finish()
    print(f"\n=== Done: {experiment_name} ===")
    return experiment_name


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main(
    model_name: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    domains: str = "handdraw,ib,law,consulting",
    max_steps: int = -1,
    num_epochs: int = 1,
    num_prompts: int = 100,
    max_turns: int = 10,
    lora_r: int = 16,
    num_generations: int = 4,
    max_completion_length: int = 1024,
    push_to_hub: bool = True,
    experiment_name: str = "",
    wandb_project: str = "supergeneral-grpo",
):
    print(f"Launching SuperGeneral GRPO training on Modal...")
    result = run_grpo.remote(
        model_name=model_name,
        domains=domains,
        max_steps=max_steps,
        num_epochs=num_epochs,
        num_prompts=num_prompts,
        max_turns=max_turns,
        lora_r=lora_r,
        num_generations=num_generations,
        max_completion_length=max_completion_length,
        push_to_hub=push_to_hub,
        experiment_name=experiment_name,
        wandb_project=wandb_project,
    )
    print(f"Training complete. Experiment: {result}")
