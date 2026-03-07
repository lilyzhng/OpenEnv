"""
Modal script for GRPO training on APEX professional tasks using Unsloth + TRL GRPOTrainer.

Base model: Qwen/Qwen3-Coder-30B-A3B-Instruct (30B MoE, 3B active)
Dataset: mercor/APEX-v1-extended (100 trainable professional tasks with rubrics)

Usage:
    # Sanity check (1 step)
    modal run --detach envs/apex_env/modal_apex_grpo_unsloth.py --max-steps 1 --train-size 5

    # Quick experiment (50 steps)
    modal run --detach envs/apex_env/modal_apex_grpo_unsloth.py --max-steps 50 --train-size 20

    # Full training (all 100 tasks)
    modal run --detach envs/apex_env/modal_apex_grpo_unsloth.py --num-epochs 1 --max-steps -1
"""

import json
import re
import modal

# ---------------------------------------------------------------------------
# Modal setup
# ---------------------------------------------------------------------------

app = modal.App("apex-grpo-unsloth")

train_image = (
    modal.Image.debian_slim(python_version="3.11")
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
)

model_cache_vol = modal.Volume.from_name("apex-model-cache", create_if_missing=True)
checkpoint_vol = modal.Volume.from_name("apex-checkpoints", create_if_missing=True)

SYSTEM_PROMPT = (
    "You are a professional analyst. Given a task, solve it by writing bash commands.\n"
    "Create output files in the workspace directory with your analysis.\n"
    "Use tools like python, grep, awk, and standard unix utilities.\n"
    'When finished, write "done".'
)

# ---------------------------------------------------------------------------
# Helper: extract text from TRL completion format
# ---------------------------------------------------------------------------


def _get_completion_text(completion) -> str:
    """Extract plain text from a TRL completion.

    Completions can be ``str`` or ``list[dict]`` (chat format).
    """
    if isinstance(completion, str):
        return completion
    if isinstance(completion, list):
        # list[dict] chat format – concatenate assistant content
        parts = []
        for msg in completion:
            if isinstance(msg, dict):
                parts.append(msg.get("content", ""))
            else:
                parts.append(str(msg))
        return " ".join(parts)
    return str(completion)


# ---------------------------------------------------------------------------
# Dataset preparation
# ---------------------------------------------------------------------------


def _prepare_apex_dataset(dataset_name: str, train_size: int | None = None):
    """Load mercor/APEX-v1-extended and prepare for GRPO.

    Returns a HuggingFace Dataset with columns: prompt, rubric_keywords, domain.
    """
    from datasets import Dataset, load_dataset

    ds = load_dataset(dataset_name, split="train")

    if train_size is not None:
        ds = ds.select(range(min(train_size, len(ds))))

    prompts = []
    rubric_keywords_list = []
    domains = []

    for row in ds:
        # The dataset may use "prompt" or "instruction" for the task text
        task_text = row.get("prompt") or row.get("instruction") or row.get("task", "")

        # Build the GRPO prompt (list of messages for chat template)
        prompt_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task_text},
        ]

        # Extract rubric keywords
        rubric = row.get("rubric", [])
        keywords = []
        if isinstance(rubric, list):
            for criterion in rubric:
                if isinstance(criterion, str):
                    # Pull out meaningful words (>3 chars) from each criterion
                    words = re.findall(r"\b[a-zA-Z]{4,}\b", criterion.lower())
                    keywords.extend(words)
                elif isinstance(criterion, dict):
                    text = criterion.get("criterion", "") or criterion.get("description", "")
                    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
                    keywords.extend(words)
        elif isinstance(rubric, str):
            keywords = re.findall(r"\b[a-zA-Z]{4,}\b", rubric.lower())

        # Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        prompts.append(prompt_messages)
        rubric_keywords_list.append(json.dumps(unique_keywords))
        domains.append(row.get("domain", "unknown"))

    return Dataset.from_dict(
        {
            "prompt": prompts,
            "rubric_keywords": rubric_keywords_list,
            "domain": domains,
        }
    )


# ---------------------------------------------------------------------------
# Reward functions
# ---------------------------------------------------------------------------

BASH_PATTERNS = re.compile(
    r"(\$\(|`[^`]+`|echo\s|cat\s|python\s|grep\s|mkdir\s|cd\s|ls\s|awk\s|sed\s"
    r"|curl\s|wget\s|pip\s|chmod\s|touch\s|rm\s|cp\s|mv\s|\|\s*\w+|>\s|>>)",
    re.IGNORECASE,
)

OUTPUT_FILE_PATTERNS = re.compile(
    r"(>\s*\S+|>>\s*\S+|\btee\s|cat\s*>|echo\s.*>\s|python\s+-c\s)",
    re.IGNORECASE,
)


def bash_format_reward(completions, **kwargs) -> list[float]:
    """Does the completion contain bash commands? Score 0.0 or 1.0."""
    scores = []
    for c in completions:
        text = _get_completion_text(c)
        scores.append(1.0 if BASH_PATTERNS.search(text) else 0.0)
    return scores


def rubric_keyword_reward(completions, rubric_keywords=None, **kwargs) -> list[float]:
    """Fraction of rubric keywords mentioned in the completion. Score 0.0-1.0."""
    scores = []
    for i, c in enumerate(completions):
        text = _get_completion_text(c).lower()
        if rubric_keywords is not None and i < len(rubric_keywords):
            kw_list = json.loads(rubric_keywords[i]) if isinstance(rubric_keywords[i], str) else rubric_keywords[i]
            if kw_list:
                matched = sum(1 for kw in kw_list if kw in text)
                scores.append(matched / len(kw_list))
            else:
                scores.append(0.0)
        else:
            scores.append(0.0)
    return scores


def completeness_reward(completions, **kwargs) -> list[float]:
    """Is the response complete and well-structured?

    - Too short (<50 chars): -2.0
    - Too long (>4000 chars): -1.0
    - Ends properly (with 'done' or period/newline): 1.0
    - Otherwise: 0.0
    """
    scores = []
    for c in completions:
        text = _get_completion_text(c)
        if len(text.strip()) < 50:
            scores.append(-2.0)
        elif len(text) > 4000:
            scores.append(-1.0)
        elif text.strip().lower().endswith("done") or text.strip().endswith((".", "\n")):
            scores.append(1.0)
        else:
            scores.append(0.0)
    return scores


def structured_output_reward(completions, **kwargs) -> list[float]:
    """Does the completion create output files? Score 0.0 or 1.0."""
    scores = []
    for c in completions:
        text = _get_completion_text(c)
        scores.append(1.0 if OUTPUT_FILE_PATTERNS.search(text) else 0.0)
    return scores


# ---------------------------------------------------------------------------
# Quick eval helper
# ---------------------------------------------------------------------------


def _quick_eval(model, tokenizer, dataset, num_samples: int = 5):
    """Generate on a few samples and score with all 4 reward functions."""
    import torch

    samples = dataset.select(range(min(num_samples, len(dataset))))
    results = []

    for row in samples:
        prompt_text = tokenizer.apply_chat_template(
            row["prompt"], tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                do_sample=True,
            )
        generated = tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )

        completions = [generated]
        rk = [row["rubric_keywords"]]

        scores = {
            "bash_format": bash_format_reward(completions)[0],
            "rubric_keyword": rubric_keyword_reward(completions, rubric_keywords=rk)[0],
            "completeness": completeness_reward(completions)[0],
            "structured_output": structured_output_reward(completions)[0],
        }
        results.append(scores)
        print(f"[eval] domain={row['domain']}  scores={scores}")
        print(f"[eval] generated (first 200 chars): {generated[:200]}")

    # Aggregate
    avg_scores = {}
    for key in results[0]:
        avg_scores[key] = sum(r[key] for r in results) / len(results)
    print(f"\n[eval] Average scores over {len(results)} samples: {avg_scores}")
    return avg_scores


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
    dataset_name: str = "mercor/APEX-v1-extended",
    max_steps: int = -1,
    num_epochs: int = 1,
    train_size: int | None = None,
    lora_r: int = 16,
    num_generations: int = 4,
    max_completion_length: int = 1024,
    push_to_hub: bool = True,
    experiment_name: str = "",
    wandb_project: str = "apex-grpo",
):
    import os
    import time

    import wandb
    from trl import GRPOConfig, GRPOTrainer
    from unsloth import FastLanguageModel

    # Auto-generate experiment name
    if not experiment_name:
        model_short = model_name.split("/")[-1].lower().replace("-", "_")
        experiment_name = f"apex_grpo_{model_short}_{int(time.time())}"

    print(f"=== APEX GRPO Training ===")
    print(f"  Model:           {model_name}")
    print(f"  Dataset:         {dataset_name}")
    print(f"  Experiment:      {experiment_name}")
    print(f"  LoRA r:          {lora_r}")
    print(f"  Num generations: {num_generations}")
    print(f"  Max steps:       {max_steps}")
    print(f"  Num epochs:      {num_epochs}")
    print(f"  Train size:      {train_size or 'all'}")

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

    # ---- Prepare dataset ----
    dataset = _prepare_apex_dataset(dataset_name, train_size=train_size)
    print(f"  Dataset size:    {len(dataset)}")

    # ---- Checkpoint path ----
    checkpoint_path = f"/checkpoints/{experiment_name}"
    os.makedirs(checkpoint_path, exist_ok=True)

    # ---- W&B init ----
    wandb.init(
        project=wandb_project,
        name=experiment_name,
        config={
            "model_name": model_name,
            "dataset_name": dataset_name,
            "lora_r": lora_r,
            "num_generations": num_generations,
            "max_steps": max_steps,
            "num_epochs": num_epochs,
            "train_size": train_size,
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
    reward_funcs = [
        bash_format_reward,
        rubric_keyword_reward,
        completeness_reward,
        structured_output_reward,
    ]

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        args=training_args,
        train_dataset=dataset,
        reward_funcs=reward_funcs,
    )

    print("Starting training...")
    trainer.train()
    print("Training complete.")

    # ---- Quick eval ----
    print("\n=== Quick Eval ===")
    eval_scores = _quick_eval(model, tokenizer, dataset, num_samples=5)
    wandb.log({"eval/" + k: v for k, v in eval_scores.items()})

    # ---- Save model ----
    trainer.save_model(checkpoint_path)
    print(f"Model saved to {checkpoint_path}")

    if push_to_hub:
        hub_repo = f"lilyzhng/{experiment_name}"
        print(f"Pushing LoRA adapter to HuggingFace: {hub_repo}")
        model.push_to_hub(hub_repo, tokenizer=tokenizer)
        print(f"Pushed to https://huggingface.co/{hub_repo}")

    # Persist volumes
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
    dataset_name: str = "mercor/APEX-v1-extended",
    max_steps: int = -1,
    num_epochs: int = 1,
    train_size: int = 0,
    lora_r: int = 16,
    num_generations: int = 4,
    max_completion_length: int = 1024,
    gpu_type: str = "A100-80GB",
    push_to_hub: bool = True,
    experiment_name: str = "",
    wandb_project: str = "apex-grpo",
):
    # Modal local_entrypoint doesn't support Optional[int], so 0 means "use all"
    _train_size = train_size if train_size > 0 else None

    print(f"Launching APEX GRPO training on Modal ({gpu_type})...")
    result = run_grpo.remote(
        model_name=model_name,
        dataset_name=dataset_name,
        max_steps=max_steps,
        num_epochs=num_epochs,
        train_size=_train_size,
        lora_r=lora_r,
        num_generations=num_generations,
        max_completion_length=max_completion_length,
        push_to_hub=push_to_hub,
        experiment_name=experiment_name,
        wandb_project=wandb_project,
    )
    print(f"Training complete. Experiment: {result}")
