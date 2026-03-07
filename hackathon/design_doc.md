---
date: 2026-03-06
time: 23:06
updated: 2026-03-07 07:45
status: v1 environment done, GRPO training scripts created (2 paths), ready to launch
repo: github.com/lilyzhng/apex-env (private)
---
# Design Doc: ApexEnvironment for OpenEnv Hackathon

## Context

We're building an OpenEnv environment for the hackathon (Mar 7-9) that lets agents tackle APEX professional tasks (law, IB, consulting) using bash commands. The goal is a complete RL loop: environment + training + benchmark improvement.

**Key prior work informing this design:**
- `coding_env/PythonCodeActEnv` — direct template (base `Environment`, not MCP)
- Harbor task format — `instruction.md` + `test.sh → reward.txt`
- SkyRL `HarborGenerator` — how RL training consumes environment outputs
- APEX-Agents (480 tasks) + APEX-v1-extended (100 trainable tasks with rubrics)
- User's GRPO experience: reward = format (0.2) + tool selection (0.4) + argument accuracy (0.4)
- User's base model experiments: Qwen3-Coder-Next (80B MoE) >> Qwen2.5-Coder-14B (dense) on pairwise eval
- User's SFT finding: SFT degrades base model — skip SFT, go directly to GRPO

**Core decisions:**
- Bash + File System action space, NOT MCP. All LLMs already know bash.
- Base model: Qwen3-Coder-Next (instruct) — "teach to ACT not THINK", Coder model = best at bash actions
- Training: ms-swift GRPO + QLoRA on Modal (2-4 × B200), skip SFT

---

## Mercor Public Repos — Overlap & Reuse Analysis

Mercor 有 8 个 public repo。我们逐一分析了跟 apex_env 的关系。

### 重合度总结

| Mercor Repo | 重合度 | 它做什么 | 跟我们的区别 |
|---|---|---|---|
| **[apex-evals](https://github.com/Mercor-Intelligence/apex-evals)** | **高** | Mercor 自己的 APEX 评估框架：text-in → LLM 生成 → LLM-as-judge 打分 | 它评的是 LLM 的文本输出质量；我们训的是 agent 在沙盒里的行动能力 |
| **[harbor](https://github.com/Mercor-Intelligence/harbor)** | **中** | 完整 agent eval + RL 框架，支持 10+ agents、Docker/Modal/GKE、40+ benchmarks | 比我们重得多；我们只需要轻量 OpenEnv 环境 |
| **[archipelago](https://github.com/Mercor-Intelligence/archipelago)** | **低** | MCP-based 考场，9 个工具。我们之前分析过（见 s2_findings_archipelago_api.md） | 我们选了 bash 路线，不用 MCP |
| [apex-evals/ACE](https://github.com/Mercor-Intelligence/apex-evals) | 无 | Consumer tasks（购物、游戏、DIY） | 不同 domain |
| [xpi-task-gen](https://github.com/Mercor-Intelligence/xpi-task-gen) | 无 | Cross-Prompt Injection 安全基准 | 无关 |
| [benchmark-planning-communication](https://github.com/Mercor-Intelligence/benchmark-planning-communication) | 无 | 内部工具 | 无关 |
| [benchmark-synthetic-kb](https://github.com/Mercor-Intelligence/benchmark-synthetic-kb) | 无 | 内部工具 | 无关 |
| [planning-review-prompts](https://github.com/Mercor-Intelligence/planning-review-prompts) | 无 | 内部工具 | 无关 |
| [aira-dojo](https://github.com/Mercor-Intelligence/aira-dojo) | 无 | AI research agent 框架 | 不同方向 |

### 核心结论：我们没有重复造轮子

- **apex-evals** = 评估 LLM 文本输出（"你写的分析报告好不好"）
- **apex_env** = 训练 agent 行动能力（"你能不能用 bash 读 PDF、算 IRR、写报告"）

这正是我们 thesis 的体现：**teach agents to ACT, not just THINK**。Mercor 自己都只在评 thinking output，没人在做 action training。这是我们的差异化。

### 可以偷的东西

#### 1. apex-evals 的 LLM-as-judge Grading（→ 升级 reward v2）

**文件：** `apex-evals-v1-extended/src/grading/executor.py`

apex-evals 的 grading 是 battle-tested 的：
- 逐 criterion 评分，每个 criterion 独立调用 LLM judge
- 支持多个 grading model（Gemini、GPT、Claude）
- 有 rubric validation、error classification、retry 逻辑

**怎么偷：** 直接用他们的 grading 逻辑替换我们 `reward.py` 里的 keyword matching：

```python
# reward_v2.py — 用 apex-evals 的 grading 模式
async def compute_reward_llm(task: dict, workspace_dir: Path) -> float:
    agent_output = collect_workspace_text(workspace_dir)
    rubric = task["rubric"]
    total_weight = sum(c["weight"] for c in rubric)
    earned = 0.0

    for criterion in rubric:
        # 每个 criterion 独立评分（跟 apex-evals 一样）
        score = await llm_judge(
            criterion=criterion["criterion"],
            description=criterion["description"],
            agent_output=agent_output,
            model="gemini-2.5-flash",  # 便宜快速
        )
        earned += score * criterion["weight"]

    return earned / total_weight if total_weight > 0 else 0.0
```

**时机：** Reward v1（keyword）先跑通 pipeline → v2（LLM judge）用于 final demo。

#### 2. Harbor 的 ATIF Trajectory 格式（→ RL 训练数据）

**文件：** `harbor/docs/rfcs/0001-trajectory-format.md`

ATIF (Agent Trajectory Interchange Format) 是标准化的 JSON，记录完整的 agent 交互历史：
```json
{
  "steps": [
    {"role": "assistant", "tool_calls": [...], "observation": "..."},
    ...
  ],
  "metrics": {"reward": 0.8, "steps": 5},
  "tool_definitions": [...]
}
```

**怎么偷：** 在 `apex_environment.py` 的 `step()` 里收集 trajectory，episode 结束时导出 ATIF 格式。这样 GRPO/SFT trainer 可以直接消费。

**时机：** 接 training pipeline 时再加，不影响 v1 环境。

#### 3. Harbor 的 Verifier 模式（→ 更好的 reward 结构）

**文件：** `harbor/src/harbor/verifier/verifier.py`

Harbor 的做法是把 test 脚本上传到容器里执行：`test.sh → reward.txt`。这比 keyword matching 更通用。

**怎么偷：** 对 APEX 任务，可以为每个 rubric criterion 生成一个 test script（检查文件是否存在、内容是否包含关键信息等），然后用 Harbor 的 verifier 模式执行。

**时机：** 这是 reward v1.5（介于 keyword 和 LLM judge 之间），如果 keyword matching 信号太弱可以考虑。

#### 4. apex-evals 的 litellm 集成（→ 多 LLM provider 支持）

apex-evals 用 `litellm` 统一调用多个 LLM provider（OpenAI、Anthropic、Google、xAI）。一行代码切换 model。

**怎么偷：** 如果做 LLM-as-judge reward，直接用 litellm 而不是手动写每个 provider 的 client。

### 不需要偷的东西

| 东西 | 为什么不需要 |
|------|-------------|
| Archipelago 的 MCP 工具集 | 我们选了 bash 路线 |
| Harbor 的 orchestrator | 我们是单环境，不需要分布式调度 |
| Harbor 的 agent registry | 我们通过 OpenEnv client 接 agent |
| apex-evals 的 Reducto 文档解析 | Agent 自己用 bash 工具读文件 |
| ACE 的 web scraping pipeline | 不同 domain |

---

## Architecture Overview

```
apex_env/
├── __init__.py              # Package init
├── models.py                # BashAction, ApexObservation, ApexState
├── client.py                # ApexEnv(EnvClient) — client-side wrapper
├── openenv.yaml             # Environment metadata
├── pyproject.toml            # Dependencies
├── server/
│   ├── __init__.py
│   ├── app.py               # FastAPI app via create_app()
│   ├── apex_environment.py  # ApexEnvironment(Environment) — core logic
│   ├── bash_executor.py     # Subprocess-based bash executor
│   ├── task_loader.py       # Load APEX tasks from HF dataset
│   └── reward.py            # Rubric-based reward computation
├── tasks/                   # Cached task data (downloaded from HF)
└── Dockerfile               # For HF Spaces deployment
```

---

## 1. Models (`models.py`)

Modeled directly after `coding_env/models.py`:

```python
from openenv.core.env_server.interfaces import Action, Observation, State

class BashAction(Action):
    """A bash command to execute in the sandbox."""
    command: str

class ApexObservation(Observation):
    """Result of executing a bash command."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    # done, reward, metadata inherited from Observation

class ApexState(State):
    """Environment state tracking task progress."""
    # episode_id, step_count inherited from State
    task_id: str | None = None
    domain: str | None = None          # "Legal" | "IB" | "Consulting"
    max_steps: int = 20                # Step budget
    files_in_workspace: list[str] = [] # Files agent has created
```

---

## 2. Core Environment (`server/apex_environment.py`)

Modeled after `PythonCodeActEnv`. Key differences:
- Uses subprocess for bash (not Python executor)
- Loads APEX tasks on reset
- Computes reward from rubric at episode end

```python
class ApexEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True  # Each session gets its own workspace

    def __init__(self):
        self._executor = BashExecutor()
        self._task_loader = TaskLoader()
        self._state = ApexState()
        self._current_task = None
        self._workspace_dir = None

    def reset(self, seed=None, episode_id=None, **kwargs) -> ApexObservation:
        """Load a task, create workspace, return instruction."""
        # 1. Pick task (by seed, or kwargs["task_id"], or random)
        task = self._task_loader.get_task(seed=seed, task_id=kwargs.get("task_id"))
        self._current_task = task

        # 2. Create isolated workspace directory
        self._workspace_dir = Path(tempfile.mkdtemp(prefix=f"apex_{task['task_id']}_"))

        # 3. Copy any input files to workspace
        if task.get("input_files"):
            for f in task["input_files"]:
                shutil.copy(f, self._workspace_dir)

        # 4. Reset state
        self._state = ApexState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=str(task["task_id"]),
            domain=task["domain"],
        )

        # 5. Return instruction as initial observation
        return ApexObservation(
            stdout=task["prompt"],  # The task instruction
            stderr="",
            exit_code=0,
            done=False,
            reward=None,
            metadata={
                "task_id": task["task_id"],
                "domain": task["domain"],
                "workspace": str(self._workspace_dir),
                "instruction": task["prompt"],
            },
        )

    def step(self, action: Action, timeout_s=None, **kwargs) -> ApexObservation:
        """Execute bash command, return output, check termination."""
        if not isinstance(action, BashAction):
            raise ValueError(f"Expected BashAction, got {type(action)}")

        self._state.step_count += 1

        # Execute in workspace
        result = self._executor.run(
            action.command,
            cwd=self._workspace_dir,
            timeout_s=timeout_s or 30.0,
        )

        # Check termination conditions
        at_step_limit = self._state.step_count >= self._state.max_steps
        agent_said_done = action.command.strip().lower() == "done"

        is_done = at_step_limit or agent_said_done

        # Compute reward only at episode end
        reward = None
        if is_done:
            reward = self._compute_reward()

        # Update workspace file list
        self._state.files_in_workspace = [
            f.name for f in self._workspace_dir.iterdir() if f.is_file()
        ]

        return ApexObservation(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            done=is_done,
            reward=reward,
            metadata={"step": self._state.step_count},
        )

    def _compute_reward(self) -> float:
        """Evaluate agent's work against rubric."""
        # See Section 4: Reward Pipeline
        ...

    @property
    def state(self) -> ApexState:
        return self._state

    def close(self):
        """Clean up workspace."""
        if self._workspace_dir and self._workspace_dir.exists():
            shutil.rmtree(self._workspace_dir, ignore_errors=True)
```

---

## 3. Bash Executor (`server/bash_executor.py`)

Simple subprocess wrapper (much simpler than `PyExecutor` which wraps smolagents):

```python
class BashExecutor:
    def run(self, command: str, cwd: Path, timeout_s: float = 30.0) -> CodeExecResult:
        """Execute a bash command in the given working directory."""
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            return CodeExecResult(
                stdout=result.stdout[:10000],   # Truncate to prevent huge outputs
                stderr=result.stderr[:5000],
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return CodeExecResult(stdout="", stderr="Command timed out", exit_code=124)
        except Exception as e:
            return CodeExecResult(stdout="", stderr=str(e), exit_code=1)
```

**Key design choice:** Reuse `CodeExecResult` from OpenEnv types — it already has stdout/stderr/exit_code.

---

## 4. Reward Pipeline (`server/reward.py`)

This is the most important part for training quality. Based on APEX rubric structure and our prior GRPO reward design.

**APEX rubric structure (from v1-extended):**
```json
{
  "rubric": [
    {
      "criterion": "Correctly identifies the applicable statute",
      "weight": 0.3,
      "description": "Agent should cite...",
      "sources": ["statute_42_usc_1983.pdf"],
      "justification": "This is the primary legal basis..."
    }
  ]
}
```

**Reward function — multi-signal, similar to Harbor's `test.sh → reward.txt`:**

```python
def compute_reward(task: dict, workspace_dir: Path) -> float:
    """
    Compute reward from rubric criteria.

    Returns float in [0, 1].
    """
    rubric = task["rubric"]
    total_weight = sum(c["weight"] for c in rubric)
    earned = 0.0

    # Collect all agent outputs
    agent_output = collect_workspace_output(workspace_dir)

    for criterion in rubric:
        # Use LLM-as-judge to score each criterion
        score = llm_judge(
            criterion=criterion["criterion"],
            description=criterion["description"],
            agent_output=agent_output,
            gold_response=task.get("gold_response", ""),
        )
        earned += score * criterion["weight"]

    return earned / total_weight if total_weight > 0 else 0.0
```

**For hackathon simplicity, we can start with a simpler reward:**

```python
def compute_reward_simple(task: dict, workspace_dir: Path) -> float:
    """Simplified reward: did agent produce output + keyword matching."""
    score = 0.0

    # 1. Did agent create any output files? (0.3)
    output_files = list(workspace_dir.glob("output*")) + list(workspace_dir.glob("*.txt"))
    if output_files:
        score += 0.3

    # 2. Keyword coverage from rubric (0.7)
    agent_text = " ".join(f.read_text() for f in workspace_dir.iterdir() if f.is_file() and f.suffix in ('.txt', '.md', '.csv'))
    keywords = extract_keywords_from_rubric(task["rubric"])
    if keywords:
        matched = sum(1 for k in keywords if k.lower() in agent_text.lower())
        score += 0.7 * (matched / len(keywords))

    return score
```

**Progression (3 levels):**

| Level | Method | Speed | Quality | When |
|-------|--------|-------|---------|------|
| **v1 (current)** | Keyword matching + file existence | Fast (0 API calls) | Low — 但够跑通 pipeline | ✅ 已实现 |
| **v1.5** | Harbor-style test scripts per criterion | Medium | Medium — 可编程验证 | 如果 v1 信号太弱 |
| **v2** | LLM-as-judge per criterion (偷 apex-evals 的 grading) | Slow (~1s/criterion) | High — battle-tested | Final demo |

v2 的具体实现见上面「可以偷的东西 → 1. apex-evals 的 LLM-as-judge Grading」。

---

## 5. Task Loader (`server/task_loader.py`)

Loads from HuggingFace dataset `mercor/APEX-v1-extended` (100 trainable tasks).

```python
class TaskLoader:
    def __init__(self, dataset_name="mercor/APEX-v1-extended"):
        self._tasks = None
        self._dataset_name = dataset_name

    def _load(self):
        if self._tasks is None:
            from datasets import load_dataset
            ds = load_dataset(self._dataset_name, split="train")
            self._tasks = list(ds)

    def get_task(self, seed=None, task_id=None) -> dict:
        self._load()
        if task_id:
            return next(t for t in self._tasks if str(t["task_id"]) == str(task_id))
        if seed is not None:
            return self._tasks[seed % len(self._tasks)]
        return random.choice(self._tasks)
```

---

## 6. Server App (`server/app.py`)

Identical pattern to `coding_env/server/app.py`:

```python
from apex_env.models import BashAction, ApexObservation
from apex_env.server.apex_environment import ApexEnvironment
from openenv.core.env_server import create_app

app = create_app(ApexEnvironment, BashAction, ApexObservation, env_name="apex_env")
```

---

## 7. Client (`client.py`)

Identical pattern to `coding_env/client.py`:

```python
class ApexEnv(EnvClient[BashAction, ApexObservation, ApexState]):
    def _step_payload(self, action: BashAction) -> dict:
        return {"command": action.command}

    def _parse_result(self, payload: dict) -> StepResult[ApexObservation]:
        obs = ApexObservation(**payload["observation"])
        return StepResult(observation=obs, reward=payload.get("reward"), done=bool(payload.get("done", False)))

    def _parse_state(self, payload: dict) -> ApexState:
        return ApexState(**payload)
```

---

## 8. Training Strategy

### 8.1 Base Model: Qwen3-Coder-Next (instruct) — 80B MoE, 3B active

**Why Coder model, not Instruct or Thinking model?**

Our thesis: **"Teach agents to ACT, not THINK."** APEX 任务的 action space 是 Bash + File System。计算 IRR → 写 Python。读法律 PDF → `pdftotext` + `grep`。所有 domain task 最终都通过写代码执行。Coder model 天然最强。

**Empirical validation (Lily's experiments, Feb 2026):**

| Model | Type | Score (pairwise, 5 samples) |
|-------|------|----|
| **Qwen3-Coder-Next (instruct)** | 80B MoE, 3B active, r=8 attn-only | **5.8** |
| Qwen2.5-Coder-14B (r=32, all 7 linear) | 14B dense | 3.0 |
| Qwen2.5-Coder-14B (r=8, attn-only) | 14B dense | 1.2 |
| Qwen2.5-Coder-14B (r=32, Unsloth) | 14B dense | 1.0 |

**Key insight: base model capability > LoRA rank > framework > dataset.** MoE 用更少的 LoRA 参数吊打 14B 所有变体。

**Other frameworks' base model choices (research, Mar 7 2026):**

| Framework | Base Model | Type |
|-----------|-----------|------|
| OpenClaw-RL (latest) | Qwen3-4B-Thinking-2507 | Thinking |
| Agent-R1 | Qwen2.5-3B-Instruct | Instruct |
| WebAgent-R1 | Qwen2.5-3B-Instruct | Instruct |
| Search-R1 | Qwen2.5-7B-Base | Base |
| SkyRL (coding tasks) | Qwen2.5-Coder-7B-Instruct | Coder-Instruct |

No one has done Coder model → domain agent RL before. But our reasoning: Bash action space = coding. Coder model = best at coding. The transfer is direct.

### 8.2 Skip SFT, Go Directly to GRPO

**SFT degrades base model.** Lily's data scaling experiment:

| Samples | Score | vs Instruct baseline (6.6) |
|---------|-------|---------------------------|
| 0 (instruct baseline) | **6.6** | — |
| 100 | 5.4 | -1.2 |
| 500 | 4.2 | -2.4 (worse with more data!) |
| ~645 (full) | 5.0 | -1.6 |

SFT tries to memorize domain-specific patterns → model gets confused → loses base capability. This is consistent across UI code gen and likely applies to APEX professional tasks.

**Pipeline: instruct model → GRPO directly.** The instruct model already knows tool calling format. GRPO teaches it to use tools **more efficiently** (fewer steps, more unique tools, less doom-looping — exactly what the APEX paper found separates success from failure).

### 8.3 Training Framework: ms-swift GRPO + QLoRA on Modal

**Framework comparison:**

| Framework | Qwen3-Coder-Next (80B) | Precision | GPU | Cost/hr | Lily's experience |
|-----------|----------------------|-----------|-----|---------|-------------------|
| **ms-swift** (primary) | ✅ validated | QLoRA 4-bit | 2-4 × B200 | ~$14-28 | ✅ SFT pipeline exists, just change to GRPO |
| Unsloth (backup) | ❌ not in mapper | — | — | — | ❌ for 80B; ✅ for 30B-A3B |
| SLIME | ✅ config exists | Full precision | 32 × H100 | ~$112 | ❌ never tried, too expensive |

**Primary path: ms-swift GRPO**
- Existing `modal_coder_instruct.py` → adapt to `modal_coder_grpo.py`
- ms-swift has built-in: `ToolCallScheduler`, `ToolUseFormatReward`, `ToolUseCorrectnessReward`
- `--loss_scale last_round` masks tool output tokens (agent tokens = train, env tokens = skip)
- Key args: `swift rlhf --rlhf_type grpo --external_plugins plugin.py --reward_funcs <custom> --use_vllm true --vllm_mode server`

**Backup path: Unsloth + TRL GRPOTrainer + Qwen3-Coder-30B-A3B**
- Smaller model (30B MoE, 3B active) — same active params, less total knowledge
- Single A100-80GB — proven working pattern from SofaGenius project
- Uses TRL `GRPOTrainer` directly (no ms-swift dependency)
- Reward functions inline (no external plugin needed)
- Good for quick demo if ms-swift 80B has issues

### 8.4 RL Loop

```
┌──────────────────────────────────────────────────────┐
│                RL Loop (Hackathon)                    │
│                                                      │
│   ┌─────────────────┐  BashAction  ┌──────────────┐ │
│   │  Agent           │ ──────────→ │ ApexEnviron  │ │
│   │  Qwen3-Coder-Next│ ←────────── │  ment        │ │
│   │  (80B MoE)       │ Observation  └──────────────┘ │
│   └─────────────────┘  + reward                      │
│       ↑                                              │
│       │ GRPO weight update                           │
│   ┌─────────────────┐                                │
│   │ ms-swift GRPO   │  QLoRA 4-bit, 2-4 × B200     │
│   │ + vLLM rollout  │  on Modal                     │
│   └─────────────────┘                                │
└──────────────────────────────────────────────────────┘
```

**Rollout loop per episode:**
1. `reset()` → get task instruction
2. Agent generates BashAction (via vLLM server)
3. `step(action)` → execute bash, return observation
4. Repeat until done (agent says "done" or step limit)
5. Compute reward from rubric
6. GRPO updates policy using group-relative advantages

**Trajectory format (偷 Harbor 的 ATIF):**
- 每个 episode 导出标准化 JSON：steps[] + tool_calls + observations + reward
- ms-swift GRPO 通过 `ToolCallScheduler` 自动管理 multi-turn trajectory
- `loss_mask`: agent tokens = 1, tool/env output = 0（只训练 agent 的决策）

---

## 9. Implementation Order

| Step | What | Files | Depends on |
|------|------|-------|------------|
| 1 | Models | `models.py` | Nothing |
| 2 | Bash executor | `server/bash_executor.py` | Nothing |
| 3 | Task loader | `server/task_loader.py` | Nothing |
| 4 | Core environment | `server/apex_environment.py` | Steps 1-3 |
| 5 | Simple reward | `server/reward.py` | Step 3 (task data) |
| 6 | Server app | `server/app.py` | Steps 1, 4 |
| 7 | Client | `client.py` | Step 1 |
| 8 | Package files | `pyproject.toml`, `openenv.yaml`, `__init__.py` | All |
| 9 | Dockerfile | `Dockerfile` | Step 8 |
| 10 | Tests | `tests/` | Steps 1-7 |

**Steps 1-3 are independent → implement in parallel.**

---

## 10. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Action space | Bash commands | All LLMs know bash. No MCP overhead. Harbor validates this. |
| Base class | `Environment`, not `MCPEnvironment` | Simpler. `coding_env` proves this works. |
| Executor | `subprocess.run` | Simpler than smolagents. We just need bash, not Python sandbox. |
| Task source | HF dataset (`APEX-v1-extended`) | 100 trainable tasks with rubrics. Already analyzed. |
| Reward v1 | Keyword matching + file existence | Fast, no LLM call needed. Good enough for first training run. |
| Reward v2 | LLM-as-judge per rubric criterion | Higher quality, slower. Reuse apex-evals' grading pattern. For final demo. |
| Termination | Step limit (20) or agent says "done" | Prevents infinite loops. Agent can finish early. |
| Workspace | `tempfile.mkdtemp()` per episode | Isolated. Clean. Auto-cleanup on close(). |
| Concurrency | `SUPPORTS_CONCURRENT_SESSIONS = True` | Each session gets own workspace dir. No shared state. |

---

## 11. Verification Plan

1. **Unit test models:** `BashAction(command="ls")` serializes correctly
2. **Unit test executor:** `BashExecutor.run("echo hello")` returns stdout="hello\n"
3. **Unit test task loader:** Loads at least 1 task from HF (or mock)
4. **Integration test:** `reset()` → `step(BashAction(command="ls"))` → get ApexObservation with file listing
5. **End-to-end:** Start server with `uvicorn`, connect via `ApexEnv` client, run a full episode
6. **Reward test:** Agent creates expected output file → reward > 0

```bash
# Run tests
PYTHONPATH=src:envs uv run pytest tests/envs/test_apex_environment.py -v

# Manual test
cd envs/apex_env && uvicorn server.app:app --port 8000
# In another terminal, use the client or curl
```

---

## 12. Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Done | `models.py` — BashAction, ApexObservation, ApexState |
| Bash executor | ✅ Done | `server/bash_executor.py` — subprocess + timeout + truncation |
| Task loader | ✅ Done | `server/task_loader.py` — lazy-load from HF |
| Core environment | ✅ Done | `server/apex_environment.py` — reset/step/close lifecycle |
| Reward v1 | ✅ Done | `server/reward.py` — keyword matching + file existence |
| Server app | ✅ Done | `server/app.py` — FastAPI via create_app() |
| Client | ✅ Done | `client.py` — EnvClient wrapper |
| Package files | ✅ Done | pyproject.toml, openenv.yaml, __init__.py |
| Dockerfile | ✅ Done | Python 3.11-slim + curl/wget/jq/git |
| Tests | ✅ Done | 29/29 passing |
| Private repo | ✅ Done | github.com/lilyzhng/apex-env |
| GRPO script (Unsloth) | ✅ Done | `modal_apex_grpo_unsloth.py` — Qwen3-Coder-30B-A3B, TRL GRPOTrainer, 472 lines |
| GRPO script (ms-swift) | ✅ Done | `modal_apex_grpo_msswift.py` — Qwen3-Coder-Next 80B, swift rlhf, 759 lines |
| GRPO reward functions | ✅ Done | 4 signals: bash_format, rubric_keyword, completeness, structured_output |

### GRPO Training Scripts — Detail

两个 GRPO 脚本已创建，来自不同的 proven codebase：

| Script | Base model | Framework | Source | GPU |
|--------|-----------|-----------|--------|-----|
| `modal_apex_grpo_unsloth.py` | Qwen3-Coder-30B-A3B-Instruct | Unsloth + TRL | SofaGenius `app.py::run_grpo` | A100-80GB × 1 |
| `modal_apex_grpo_msswift.py` | Qwen3-Coder-Next (80B MoE) | ms-swift | `modal_coder_instruct.py` | B200 × 2 |

**Key insight from SofaGenius:** SofaGenius GRPO 用的是 **Qwen2.5-Coder-14B**（dense），不是 MoE。
所以 Unsloth 路线只能用 30B-A3B（在 mapper 里），不能用 80B。
80B MoE 必须走 ms-swift 路线（已验证 QLoRA SFT）。

**4 个 APEX reward functions（两个脚本共享）：**
1. `bash_format_reward` — 检查 completion 是否包含 bash 命令模式（echo, python, grep, pipe, etc.）
2. `rubric_keyword_reward` — rubric 关键词覆盖率（0.0-1.0 graduated）
3. `completeness_reward` — 长度检查 + 是否截断
4. `structured_output_reward` — 是否创建输出文件（`> file`, `tee`, `cat > file` etc.）

---

## 13. What's Next

| Task | Priority | Status | Notes |
|------|----------|--------|-------|
| **Launch Unsloth GRPO sanity check** | **P0 — now** | 待做 | `modal run --detach ... --max-steps 1 --train-size 5` |
| **Launch ms-swift GRPO sanity check** | **P0 — now** | 待做 | `modal run --detach ... --max-steps 1 --train-size 5 --num-generations 2` |
| **Scale up training** — 50 steps, 20 samples | **P0 — Friday AM** | 待做 | Whichever path works first |
| **Full training run** — all 100 tasks, 1 epoch | **P0 — Friday PM** | 待做 | Generate reward curves for demo |
| HF Spaces deployment | P1 — Saturday | 待做 | For demo |
| Reward v2 (LLM-as-judge) | P1 — for demo | 待做 | 偷 apex-evals 的 grading/executor.py |
| Colab minimal training script | P1 — Sunday | 待做 | Hackathon packaging requirement |
| APEX-Agents eval harness (480 eval tasks) | P2 | 待做 | apex-evals 有 batch runner 可参考 |
| ATIF trajectory export | P2 | 待做 | Harbor 的 trajectory format |
