"""
GRPO training on APEX professional tasks using ms-swift on Modal.

Adapts the proven ms-swift SFT pattern (modal_coder_instruct.py) for GRPO
reinforcement learning. Uses vLLM in server mode for generation and a custom
reward plugin for APEX rubric-based scoring.

Base model: Qwen/Qwen3-Coder-Next (80B MoE, 3B active, 512 experts)
Dataset: mercor/APEX-v1-extended (100 trainable professional tasks with rubrics)

IMPORTANT: Always use --detach. The 80B MoE model takes several minutes to load.
Without --detach, Modal's local heartbeat will time out and kill the job.

Usage:
    # Sanity check (1 step, 5 samples, 2 generations)
    modal run --detach envs/apex_env/modal_apex_grpo_msswift.py \\
        --max-steps 1 --train-size 5 --num-generations 2

    # Experiment (50 steps, 20 samples)
    modal run --detach envs/apex_env/modal_apex_grpo_msswift.py \\
        --max-steps 50 --train-size 20

    # Full training (1 epoch, 2x B200 for vLLM + training)
    modal run --detach envs/apex_env/modal_apex_grpo_msswift.py \\
        --num-epochs 1 --max-steps -1 --gpu-type B200 --num-gpus 2
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import modal

# ---------------------------------------------------------------------------
# Modal App & Infrastructure
# ---------------------------------------------------------------------------
app = modal.App('apex-grpo-msswift')

train_image = (
    modal.Image.from_registry('nvidia/cuda:12.8.0-devel-ubuntu22.04', add_python='3.11')
    .apt_install('git', 'build-essential')
    .pip_install(
        'ms-swift @ git+https://github.com/modelscope/ms-swift.git',
        'transformers>=4.57,<4.58',
        'trl<0.25',
        'bitsandbytes',
        'datasets',
        'wandb',
        'hf-transfer',
        'huggingface_hub',
        'flash-linear-attention',
        'vllm',
    )
    .run_commands('CC=gcc CXX=g++ pip install causal-conv1d --no-build-isolation')
    .env({
        'HF_HOME': '/model_cache',
        'HF_HUB_ENABLE_HF_TRANSFER': '1',
        'PYTORCH_CUDA_ALLOC_CONF': 'expandable_segments:True',
        'USE_HF': '1',
    })
)

checkpoint_vol = modal.Volume.from_name('apex-grpo-checkpoints', create_if_missing=True)
model_vol = modal.Volume.from_name('qwen-model-cache', create_if_missing=True)
MODEL_MOUNT = '/model_cache'
TIMEOUT_HOURS = 8


# ---------------------------------------------------------------------------
# GRPO Plugin (written to disk at runtime inside Modal)
# ---------------------------------------------------------------------------
APEX_GRPO_PLUGIN = r'''"""
APEX GRPO reward plugin for ms-swift.

Registers a custom reward function 'apex_task' that scores completions
on 4 signals: bash format, rubric keywords, completeness, structured output.

Also registers a dataset preprocessor to convert APEX-v1-extended format
into the prompt-only format required by GRPO.
"""

import json
import re


# ---------------------------------------------------------------------------
# Reward function
# ---------------------------------------------------------------------------
class ApexTaskReward:
    """
    Rubric-based reward for APEX professional tasks.

    Scores completions on 4 signals (each 0.0-1.0, then averaged):
      1. Bash format  (0.25) - completion contains bash code blocks
      2. Rubric keywords (0.25) - keyword coverage from task rubric
      3. Completeness (0.25) - response length and structure
      4. Structured output (0.25) - uses markdown headers, lists, code blocks
    """

    def __call__(self, completions: list[str], **kwargs) -> list[float]:
        rewards = []
        for completion in completions:
            score = 0.0

            # Signal 1: Bash format — contains bash/shell code blocks
            bash_blocks = re.findall(r'```(?:bash|sh|shell)(.*?)```', completion, re.DOTALL)
            if bash_blocks:
                score += 0.25
            elif '```' in completion:
                # Has some code block, partial credit
                score += 0.10

            # Signal 2: Rubric keywords — check against task rubric if available
            rubric_score = 0.0
            # Extract rubric from kwargs if provided by the dataset
            rubric_text = kwargs.get('rubric', [''])[0] if kwargs.get('rubric') else ''
            if rubric_text:
                keywords = _extract_keywords(rubric_text)
                if keywords:
                    matched = sum(1 for k in keywords if k.lower() in completion.lower())
                    rubric_score = matched / len(keywords)
            else:
                # No rubric available — give partial credit if completion is substantive
                rubric_score = 0.5 if len(completion) > 200 else 0.0
            score += 0.25 * rubric_score

            # Signal 3: Completeness — response length and substance
            word_count = len(completion.split())
            if word_count > 500:
                score += 0.25
            elif word_count > 200:
                score += 0.20
            elif word_count > 50:
                score += 0.10

            # Signal 4: Structured output — markdown headers, lists, code blocks
            structure_signals = 0
            if re.search(r'^#{1,3}\s', completion, re.MULTILINE):
                structure_signals += 1  # Has headers
            if re.search(r'^[-*]\s', completion, re.MULTILINE):
                structure_signals += 1  # Has bullet lists
            if re.search(r'^\d+\.\s', completion, re.MULTILINE):
                structure_signals += 1  # Has numbered lists
            if '```' in completion:
                structure_signals += 1  # Has code blocks
            score += 0.25 * min(structure_signals / 3, 1.0)

            rewards.append(round(score, 4))

        return rewards


def _extract_keywords(rubric_text: str) -> list[str]:
    """Extract meaningful keywords from rubric text."""
    if isinstance(rubric_text, str):
        try:
            rubric = json.loads(rubric_text)
        except (json.JSONDecodeError, TypeError):
            rubric = [{'criterion': rubric_text}]
    elif isinstance(rubric_text, list):
        rubric = rubric_text
    else:
        return []

    keywords = []
    for criterion in rubric:
        if isinstance(criterion, dict):
            text = criterion.get('criterion', '') + ' ' + criterion.get('description', '')
        else:
            text = str(criterion)
        # Extract capitalized terms
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        keywords.extend(words)
        # Extract quoted terms
        quoted = re.findall(r'"([^"]+)"', text)
        keywords.extend(quoted)

    return list(set(keywords)) if keywords else []


# ---------------------------------------------------------------------------
# Dataset preprocessor: APEX-v1-extended -> GRPO prompt format
# ---------------------------------------------------------------------------
def preprocess_apex_for_grpo(dataset):
    """
    Convert APEX-v1-extended dataset to GRPO format.

    APEX format has: task_description, rubric, domain, difficulty, etc.
    GRPO needs: prompt (str or messages list)

    We build a system prompt + user prompt from the task fields.
    """
    processed = []
    for example in dataset:
        task_desc = example.get('task_description', example.get('prompt', ''))
        domain = example.get('domain', 'general')
        rubric = example.get('rubric', '')

        if isinstance(rubric, list):
            rubric_str = json.dumps(rubric, indent=2)
        elif isinstance(rubric, str):
            rubric_str = rubric
        else:
            rubric_str = str(rubric)

        system_msg = (
            f"You are an expert professional assistant specializing in {domain}. "
            "You have access to a bash terminal to complete tasks. "
            "Write clear, well-structured responses with bash commands when needed. "
            "Use markdown formatting for readability."
        )

        user_msg = f"## Task\n\n{task_desc}"
        if rubric_str and rubric_str != '[]':
            user_msg += f"\n\n## Evaluation Criteria\n\n{rubric_str}"

        processed.append({
            'messages': [
                {'role': 'system', 'content': system_msg},
                {'role': 'user', 'content': user_msg},
            ],
            # Pass rubric through for reward function
            'rubric': rubric_str,
        })

    return processed


# ---------------------------------------------------------------------------
# Register with ms-swift plugin system
# ---------------------------------------------------------------------------
from swift.plugin import orms

orms['apex_task'] = ApexTaskReward()
'''


# ---------------------------------------------------------------------------
# GRPO Config
# ---------------------------------------------------------------------------
@dataclass
class GRPOConfig:
    # Model -- 80B MoE, 3B active
    model_name: str = 'Qwen/Qwen3-Coder-Next'
    max_seq_length: int = 4096

    # LoRA
    lora_rank: int = 8
    lora_alpha: int = 16
    target_modules: List[str] = field(
        default_factory=lambda: ['q_proj', 'k_proj', 'v_proj', 'o_proj']
    )

    # GRPO-specific
    learning_rate: float = 1e-6
    reward_funcs: List[str] = field(default_factory=lambda: ['apex_task'])
    num_generations: int = 4
    max_completion_length: int = 1024
    temperature: float = 1.0
    use_vllm: bool = True
    vllm_mode: str = 'server'
    external_plugins: str = None  # Set at runtime to /tmp/apex_grpo_plugin.py
    stop_words: List[str] = field(default_factory=lambda: ['<|endoftext|>', '<|im_end|>'])
    loss_scale: str = 'last_round'

    # Dataset
    dataset_name: str = 'mercor/APEX-v1-extended'
    train_size: int = None

    # Training
    num_epochs: int = 1
    max_steps: int = -1
    batch_size: int = 1
    gradient_accumulation_steps: int = 1
    warmup_steps: int = 5
    weight_decay: float = 0.01
    lr_scheduler_type: str = 'cosine'

    # MoE-specific
    router_aux_loss_coef: float = 1e-3

    # Logging
    logging_steps: int = 1
    save_steps: int = 25

    # Hardware
    gpu_type: str = 'B200'
    num_gpus: int = 2

    # HuggingFace Upload
    push_to_hub: bool = True
    hf_repo_name: Optional[str] = None
    hf_private: bool = False
    hf_username: str = 'lilyzhng'

    # Experiment
    seed: int = 3407
    experiment_name: Optional[str] = None
    wandb_project: str = 'apex-grpo-msswift'

    def __post_init__(self):
        if self.experiment_name is None:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            model_short = self.model_name.split('/')[-1]
            attn_only = set(self.target_modules) == {'q_proj', 'k_proj', 'v_proj', 'o_proj'}
            suffix = '-attn' if attn_only else ''
            self.experiment_name = (
                f'{model_short}-grpo-apex-r{self.lora_rank}{suffix}-{timestamp}'
            )
        if self.hf_repo_name is None:
            self.hf_repo_name = self.experiment_name


# ---------------------------------------------------------------------------
# GPU-specific Modal functions
# ---------------------------------------------------------------------------
@app.function(
    image=train_image,
    gpu='B200',
    cpu=8,
    volumes={'/checkpoints': checkpoint_vol, MODEL_MOUNT: model_vol},
    secrets=[modal.Secret.from_name('wandb-secret'), modal.Secret.from_name('hf-secret')],
    timeout=TIMEOUT_HOURS * 60 * 60,
)
def grpo_b200(config: GRPOConfig):
    return _grpo_impl(config)


@app.function(
    image=train_image,
    gpu='B200:2',
    cpu=16,
    volumes={'/checkpoints': checkpoint_vol, MODEL_MOUNT: model_vol},
    secrets=[modal.Secret.from_name('wandb-secret'), modal.Secret.from_name('hf-secret')],
    timeout=TIMEOUT_HOURS * 60 * 60,
)
def grpo_b200_2gpu(config: GRPOConfig):
    return _grpo_impl(config)


@app.function(
    image=train_image,
    gpu='H100',
    cpu=8,
    volumes={'/checkpoints': checkpoint_vol, MODEL_MOUNT: model_vol},
    secrets=[modal.Secret.from_name('wandb-secret'), modal.Secret.from_name('hf-secret')],
    timeout=TIMEOUT_HOURS * 60 * 60,
)
def grpo_h100(config: GRPOConfig):
    return _grpo_impl(config)


@app.function(
    image=train_image,
    gpu='H200',
    cpu=8,
    volumes={'/checkpoints': checkpoint_vol, MODEL_MOUNT: model_vol},
    secrets=[modal.Secret.from_name('wandb-secret'), modal.Secret.from_name('hf-secret')],
    timeout=TIMEOUT_HOURS * 60 * 60,
)
def grpo_h200(config: GRPOConfig):
    return _grpo_impl(config)


_gpu_functions = {
    'H100': grpo_h100,
    'H200': grpo_h200,
    'B200': grpo_b200,
    'B200:2': grpo_b200_2gpu,
}


# ---------------------------------------------------------------------------
# Training Implementation (swift rlhf --rlhf_type grpo)
# ---------------------------------------------------------------------------
def _write_plugin_file() -> str:
    """Write the APEX GRPO plugin to disk and return the path.

    Modal cannot import local files, so we write the plugin at runtime
    inside the container.
    """
    plugin_path = '/tmp/apex_grpo_plugin.py'
    with open(plugin_path, 'w') as f:
        f.write(APEX_GRPO_PLUGIN)
    print(f'Wrote APEX GRPO plugin to {plugin_path}')
    return plugin_path


def _grpo_impl(config: GRPOConfig):
    """Run GRPO training with ms-swift on Modal."""
    import os

    import torch

    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_properties(0)
        total_gb = round(gpu.total_memory / 1024**3, 1)
        print(f'GPU: {gpu.name}, {total_gb} GB VRAM')

    os.environ['WANDB_PROJECT'] = config.wandb_project

    # Write plugin file to disk (Modal can't import local files)
    plugin_path = _write_plugin_file()

    dataset_str = config.dataset_name
    if config.train_size:
        dataset_str = f'{config.dataset_name}#{config.train_size}'

    max_steps = config.max_steps if config.max_steps > 0 else -1
    num_epochs = config.num_epochs if max_steps == -1 else 1
    output_dir = f'/checkpoints/{config.experiment_name}'

    reward_funcs_str = ' '.join(config.reward_funcs)

    print('\n' + '=' * 80)
    print('ms-swift GRPO — APEX Professional Tasks — Qwen3-Coder-Next (MoE)')
    print('=' * 80)
    print(f'Model: {config.model_name} (80B total, 3B active, 512 experts)')
    print('Quantization: BNB 4-bit NF4 (QLoRA)')
    print(f'LoRA: rank={config.lora_rank}, alpha={config.lora_alpha}')
    print(f'LoRA targets: {" ".join(config.target_modules)}')
    print(f'Dataset: {dataset_str}')
    print(f'Training: {num_epochs} epoch(s), max {max_steps} steps')
    print(f'Batch: {config.batch_size} x {config.gradient_accumulation_steps} '
          f'= {config.batch_size * config.gradient_accumulation_steps} effective')
    print(f'Learning rate: {config.learning_rate} ({config.lr_scheduler_type})')
    print(f'MoE router aux loss coef: {config.router_aux_loss_coef}')
    print(f'Sequence length: {config.max_seq_length}')
    print(f'GRPO generations: {config.num_generations}')
    print(f'Max completion length: {config.max_completion_length}')
    print(f'Temperature: {config.temperature}')
    print(f'Reward functions: {reward_funcs_str}')
    print(f'vLLM: {config.use_vllm} (mode: {config.vllm_mode})')
    print(f'Loss scale: {config.loss_scale}')
    print(f'Plugin: {plugin_path}')
    print(f'Output: {output_dir}')
    print(f'Experiment: {config.experiment_name}')
    print('=' * 80 + '\n')

    if config.num_gpus > 1:
        import subprocess

        os.environ['NPROC_PER_NODE'] = str(config.num_gpus)

        cmd = [
            'swift', 'rlhf',
            '--rlhf_type', 'grpo',
            '--model', config.model_name,
            '--dataset', dataset_str,
            '--use_hf', 'true',

            # LoRA
            '--tuner_type', 'lora',
            '--lora_rank', str(config.lora_rank),
            '--lora_alpha', str(config.lora_alpha),
            '--target_modules', *config.target_modules,

            # QLoRA quantization
            '--quant_method', 'bnb',
            '--quant_bits', '4',
            '--bnb_4bit_compute_dtype', 'bfloat16',
            '--bnb_4bit_quant_type', 'nf4',
            '--bnb_4bit_use_double_quant', 'true',
            '--torch_dtype', 'bfloat16',

            # Sequence
            '--max_length', str(config.max_seq_length),
            '--max_completion_length', str(config.max_completion_length),

            # GRPO-specific
            '--reward_funcs', *config.reward_funcs,
            '--external_plugins', plugin_path,
            '--num_generations', str(config.num_generations),
            '--temperature', str(config.temperature),
            '--loss_scale', config.loss_scale,

            # vLLM generation
            '--use_vllm', str(config.use_vllm).lower(),
            '--vllm_mode', config.vllm_mode,

            # Training hyperparameters
            '--per_device_train_batch_size', str(config.batch_size),
            '--gradient_accumulation_steps', str(config.gradient_accumulation_steps),
            '--learning_rate', str(config.learning_rate),
            '--num_train_epochs', str(num_epochs),
            '--max_steps', str(max_steps),
            '--warmup_steps', str(config.warmup_steps),
            '--weight_decay', str(config.weight_decay),
            '--lr_scheduler_type', config.lr_scheduler_type,
            '--optim', 'adamw_8bit',

            # MoE
            '--router_aux_loss_coef', str(config.router_aux_loss_coef),

            # Logging & saving
            '--logging_steps', str(config.logging_steps),
            '--save_steps', str(config.save_steps),
            '--save_total_limit', '2',
            '--output_dir', output_dir,
            '--report_to', 'wandb',
            '--run_name', config.experiment_name,

            # Other
            '--gradient_checkpointing', 'false',
            '--seed', str(config.seed),
            '--dataloader_num_workers', '8',
            '--load_from_cache_file', 'false',
        ]

        # Add stop words
        if config.stop_words:
            cmd.extend(['--stop_words', *config.stop_words])

        print(f'Running GRPO with {config.num_gpus} GPUs via torchrun...')
        print('Command: ' + ' '.join(cmd) + '\n')
        subprocess.run(cmd, check=True)
    else:
        from swift import RLHFArguments, rlhf_main

        rlhf_main(RLHFArguments(
            rlhf_type='grpo',
            model=config.model_name,
            dataset=[dataset_str],
            use_hf=True,
            load_from_cache_file=False,

            # LoRA
            tuner_type='lora',
            lora_rank=config.lora_rank,
            lora_alpha=config.lora_alpha,
            target_modules=config.target_modules,

            # QLoRA quantization
            quant_method='bnb',
            quant_bits=4,
            bnb_4bit_compute_dtype='bfloat16',
            bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True,
            torch_dtype='bfloat16',

            # Sequence
            max_length=config.max_seq_length,
            max_completion_length=config.max_completion_length,

            # GRPO-specific
            reward_funcs=config.reward_funcs,
            external_plugins=[plugin_path],
            num_generations=config.num_generations,
            temperature=config.temperature,
            loss_scale=config.loss_scale,

            # vLLM generation
            use_vllm=config.use_vllm,
            vllm_mode=config.vllm_mode,

            # Training hyperparameters
            per_device_train_batch_size=config.batch_size,
            gradient_accumulation_steps=config.gradient_accumulation_steps,
            learning_rate=config.learning_rate,
            num_train_epochs=num_epochs,
            max_steps=max_steps,
            warmup_steps=config.warmup_steps,
            weight_decay=config.weight_decay,
            lr_scheduler_type=config.lr_scheduler_type,
            optim='adamw_8bit',

            # MoE
            router_aux_loss_coef=config.router_aux_loss_coef,

            # Logging & saving
            logging_steps=config.logging_steps,
            save_steps=config.save_steps,
            save_total_limit=2,
            output_dir=output_dir,
            report_to=['wandb'],
            run_name=config.experiment_name,

            # Other
            gradient_checkpointing=False,
            seed=config.seed,
            dataloader_num_workers=8,

            # Stop words
            stop_words=config.stop_words,
        ))

    checkpoint_vol.commit()
    print(f'\nCheckpoints saved to Modal volume: {output_dir}')

    if config.push_to_hub:
        hf_token = os.environ.get('HF_TOKEN')
        repo_id = f'{config.hf_username}/{config.hf_repo_name}'

        if not hf_token:
            print('Warning: HF_TOKEN not found. Skipping push to hub.')
        else:
            print(f'\nPushing LoRA adapter to HuggingFace: {repo_id}')
            try:
                from huggingface_hub import HfApi

                api = HfApi(token=hf_token)
                api.create_repo(repo_id, private=config.hf_private, exist_ok=True)
                api.upload_folder(
                    folder_path=output_dir,
                    repo_id=repo_id,
                    ignore_patterns=[
                        'checkpoint-*', 'runs/*', '*.bin',
                        'optimizer*', 'scheduler*', 'trainer_state*',
                    ],
                )
                print(f'Pushed to: https://huggingface.co/{repo_id}')
            except Exception as e:
                print(f'Warning: Failed to push to HuggingFace: {e}')
                print('LoRA adapter is still saved on the Modal volume.')

    print('\n' + '=' * 80)
    print('GRPO Training Complete!')
    print('=' * 80)
    print(f'Experiment: {config.experiment_name}')
    if config.push_to_hub:
        print(f'Model: https://huggingface.co/{config.hf_username}/{config.hf_repo_name}')
    print(f'To download from Modal: modal volume get apex-grpo-checkpoints /{config.experiment_name}/ ./output/')
    print('=' * 80)

    return config.experiment_name


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------
@app.local_entrypoint()
def main(
    model_name: str = None,
    max_steps: int = None,
    num_epochs: int = None,
    train_size: int = None,
    lora_rank: int = None,
    lora_alpha: int = None,
    learning_rate: float = None,
    batch_size: int = None,
    gradient_accumulation_steps: int = None,
    max_seq_length: int = None,
    gpu_type: str = None,
    num_gpus: int = None,
    dataset_name: str = None,
    experiment_name: str = None,
    push_to_hub: bool = None,
    hf_repo_name: str = None,
    hf_username: str = None,
    hf_private: bool = None,
    router_aux_loss_coef: float = None,
    target_modules: str = None,
    num_generations: int = None,
    max_completion_length: int = None,
    temperature: float = None,
    loss_scale: str = None,
    wandb_project: str = None,
):
    """
    Launch GRPO training on APEX professional tasks using ms-swift on Modal.

    Uses Qwen3-Coder-Next (80B MoE) with QLoRA + vLLM generation.
    Reward function scores completions on bash format, rubric keywords,
    completeness, and structured output.

    Always use --detach (80B MoE takes minutes to load).

    Examples:
        # Sanity check
        modal run --detach envs/apex_env/modal_apex_grpo_msswift.py \\
            --max-steps 1 --train-size 5 --num-generations 2

        # Experiment
        modal run --detach envs/apex_env/modal_apex_grpo_msswift.py \\
            --max-steps 50 --train-size 20

        # Full training
        modal run --detach envs/apex_env/modal_apex_grpo_msswift.py \\
            --num-epochs 1 --max-steps -1 --gpu-type B200 --num-gpus 2
    """
    config_dict = {}
    for key, val in {
        'model_name': model_name,
        'max_steps': max_steps,
        'num_epochs': num_epochs,
        'train_size': train_size,
        'lora_rank': lora_rank,
        'lora_alpha': lora_alpha,
        'learning_rate': learning_rate,
        'batch_size': batch_size,
        'gradient_accumulation_steps': gradient_accumulation_steps,
        'max_seq_length': max_seq_length,
        'gpu_type': gpu_type,
        'num_gpus': num_gpus,
        'dataset_name': dataset_name,
        'experiment_name': experiment_name,
        'push_to_hub': push_to_hub,
        'hf_repo_name': hf_repo_name,
        'hf_username': hf_username,
        'hf_private': hf_private,
        'router_aux_loss_coef': router_aux_loss_coef,
        'num_generations': num_generations,
        'max_completion_length': max_completion_length,
        'temperature': temperature,
        'loss_scale': loss_scale,
        'wandb_project': wandb_project,
    }.items():
        if val is not None:
            config_dict[key] = val

    if target_modules is not None:
        config_dict['target_modules'] = target_modules.split()

    config = GRPOConfig(**config_dict)

    print('=' * 80)
    print('APEX GRPO Training (ms-swift + QLoRA + vLLM)')
    print('=' * 80)
    print(f'Model: {config.model_name}')
    print(f'GPU: {config.gpu_type} x {config.num_gpus}')
    print(f'Dataset: {config.dataset_name}')
    if config.train_size:
        print(f'  Training samples: {config.train_size}')
    else:
        print('  Training samples: full dataset')
    print(f'LoRA: rank={config.lora_rank}, alpha={config.lora_alpha}')
    print(f'LoRA targets: {" ".join(config.target_modules)}')
    print(f'Batch: {config.batch_size} x {config.gradient_accumulation_steps} '
          f'= {config.batch_size * config.gradient_accumulation_steps}')
    print(f'Training: {config.num_epochs} epoch(s), max {config.max_steps} steps')
    print(f'Learning rate: {config.learning_rate} ({config.lr_scheduler_type})')
    print(f'MoE router aux loss: {config.router_aux_loss_coef}')
    print(f'Sequence length: {config.max_seq_length}')
    print(f'GRPO generations: {config.num_generations}')
    print(f'Max completion length: {config.max_completion_length}')
    print(f'Temperature: {config.temperature}')
    print(f'Reward functions: {" ".join(config.reward_funcs)}')
    print(f'vLLM: {config.use_vllm} (mode: {config.vllm_mode})')
    print(f'Loss scale: {config.loss_scale}')
    print(f'Experiment: {config.experiment_name}')
    print(f'Push to HuggingFace: {"Yes" if config.push_to_hub else "No"}')
    if config.push_to_hub:
        print(f'  Repository: {config.hf_username}/{config.hf_repo_name}')
    print('=' * 80 + '\n')

    gpu_key = config.gpu_type
    if config.num_gpus > 1:
        gpu_key = f'{config.gpu_type}:{config.num_gpus}'

    if gpu_key not in _gpu_functions:
        raise ValueError(
            f'Unknown GPU config: {gpu_key}. Available: {list(_gpu_functions.keys())}'
        )

    print(f'Launching GRPO on Modal with {gpu_key} ({config.num_gpus} GPU(s))...\n')
    experiment = _gpu_functions[gpu_key].remote(config)

    print(f'\nDone! Experiment: {experiment}')
    print(f'To download: modal volume get apex-grpo-checkpoints /{experiment}/ ./output/')
