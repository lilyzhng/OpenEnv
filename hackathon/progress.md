---
date: 2026-03-06
type: roadmap
updated: 2026-03-07 07:45
---

# OpenEnv Hackathon Roadmap

## Story (30%)

**核心 statement:**
> Agent 把金融分析、法律审核、咨询策略这些被锁在高薪专业人士手里的能力，还给每一个普通人。

| # | Task | Status | 结果/笔记 |
|---|------|--------|-----------|
| S1 | 问 Shubham 关于 Lionel 的 motivation — democratization resonates? | 待回复 | 已发消息 |
| S2 | 跟 Simon 碰 storytelling（他的强项） | 待做 | 周末 remote call |
| S3 | 听 kickoff presentations (Sat 10:00-11:30)，找灵感 | 待做 | 特别注意 Mercor/Scale AI 怎么 frame problem |
| S4 | 写 3 分钟 pitch 草稿 | 待做 | |
| S5 | 录 1 分钟 demo video | 待做 | |

---

## Environment (40%) — ✅ COMPLETE

**目标：** 把 APEX tasks 包成 OpenEnv environment，agent 在 sandbox 里用工具完成 professional tasks。

| #       | Task                                            | Status    | 结果/笔记                                                           |
| ------- | ----------------------------------------------- | --------- | --------------------------------------------------------------- |
| E1      | 读 OpenEnv 0.2.1 源码                              | ✅ Done    | `Environment` base class, `reset()`, `step()`, `state()` API    |
| E2      | 跑 OpenEnv 自带 examples                           | ✅ Done    | Echo + Coding environment 本地跑通                                  |
| E3      | 读 Archipelago 源码                                | ✅ Done    | 决定不用 MCP，走 bash 路线                                              |
| E4      | 设计 ApexEnvironment                              | ✅ Done    | Bash action space, rubric-based reward, 详见 design_doc.md        |
| E5      | 实现 APEX environment                             | ✅ Done    | 29/29 tests passing, 全部组件完成                                     |
| E6      | Reward v1 (keyword matching)                    | ✅ Done    | `server/reward.py` — 0.3 file existence + 0.7 keyword coverage  |
| E7      | Deploy 到 HF Spaces                              | ✅ Done    | https://huggingface.co/spaces/lilyzhng/apex-env (private)       |
| **E8**  | **Reward v2: Talk Penalty + Action Efficiency** | ✅ Done | `reward.py` — talk_penalty (-0.2 × talk_ratio) + efficiency_bonus (+0.1 if fast) |
| **E9**  | **Knowledge vs Action 双维度评分**                   | **P1 待做** | Knowledge score (LLM-as-judge) + Action score (执行结果)，gap = 训练目标 |
| E10     | Progressive Difficulty Tiers                    | 待做        | Tier 1 写文件 → Tier 2 计算 → Tier 3 多步推理                            |
| **E11** | **Docker Sandbox**                              | **P0 待做** | Harbor / Daytona / 自建 Docker，隔离执行环境                             |
| E12     | 修 extract_command() parsing                     | ✅ Done     | heredoc 支持, talk 过滤, `done` 后缀剥离, 多行命令处理                     |

**Environment Innovation Roadmap（基于 "Talk is cheap, show me the act" insight）：**

```
已做:  keyword matching reward (v1) → 9-model benchmark → 发现 talk vs act gap
下一步:
  E12 → 修 parsing，确保 eval 公平
  E8  → Talk Penalty + Action Efficiency reward (v2)
  E11 → Docker Sandbox (安全 + 可复现)
  E9  → Knowledge vs Action 双维度（environment 核心创新）
  E10 → Progressive Difficulty（训练用 curriculum）
```

**Architecture（已实现）：**
```
apex_env/
├── models.py                # BashAction, ApexObservation, ApexState
├── client.py                # ApexEnv(EnvClient)
├── server/
│   ├── apex_environment.py  # Core: reset/step/close
│   ├── bash_executor.py     # subprocess + timeout
│   ├── task_loader.py       # mercor/APEX-v1-extended (100 tasks)
│   └── reward.py            # Rubric keyword matching
├── modal_apex_grpo_unsloth.py   # GRPO: Unsloth + TRL (30B-A3B)
└── modal_apex_grpo_msswift.py   # GRPO: ms-swift (80B MoE)
```

---

## Baseline Eval (NEW — should have been FIRST)

**目标：** 在训练之前，用 base model 跑 `mercor/apex-agents` (480 eval tasks)，建立 baseline。

| # | Task | Status | 结果/笔记 |
|---|------|--------|-----------|
| B1 | 写 baseline eval 脚本 | ✅ Done | `scripts/baseline_eval.py` — stratified sampling, keyword reward |
| B2 | 9-model benchmark (无文件) | ✅ Done | v3 results — 发现数据缺失问题 |
| B3 | 下载 task input files from HF | ✅ Done | `populate_workspace()` 从 `mercor/apex-agents` 下载 PDF/Excel/docx |
| **B4** | **9-model benchmark v4 (有文件)** | ✅ Done | 9 models × 18 tasks，结果见下方 |
| B5 | 分析 failure modes | 待做 | 哪里弱？format? tool use? 理解力？ |
| B6 | 根据 baseline 调 reward weights | 待做 | 如果 bash_format 已经满分 → 降低权重 |
| **B7** | **加 Docker sandbox** | **P0 下一步** | 见下方 sandbox design decision |

---

## Training (20%) — BLOCKED (waiting for baseline)

**目标：** 展示 reward curve 上升，before/after behavior 对比。

**Key decisions made (see design_doc.md Section 8):**
- Base model: ~~Qwen3-Coder-Next (80B MoE)~~ → **Qwen3-Coder-30B-A3B-Instruct** (直接输出 bash, avg reward 0.65 vs Next 0.14)
- Skip SFT — SFT degrades base model (data scaling experiment)
- Direct GRPO — teach to ACT not THINK
- ~~Two paths: ms-swift (80B, primary) + Unsloth (30B, backup)~~ → **Single path: Unsloth (30B-A3B)**
- Action format: **Raw bash** — 能力向上兼容，训练底层，部署加封装

| # | Task | Status | 结果/笔记 |
|---|------|--------|-----------|
| T1 | 选 base model | ✅ Done | Qwen3-Coder-Next 5.8 vs Qwen2.5-Coder-14B 1.0-3.0 (pairwise eval) |
| T2 | 决定 SFT vs 直接 RL | ✅ Done | Skip SFT — 100 samples: 5.4, 500: 4.2, all below instruct baseline 6.6 |
| T3 | 选训练框架 | ✅ Done | ms-swift (80B QLoRA) + Unsloth backup (30B-A3B) |
| T4 | GRPO reward functions | ✅ Done | 4 signals: bash_format, rubric_keyword, completeness, structured_output |
| T5 | GRPO training script (Unsloth) | ✅ Done | `modal_apex_grpo_unsloth.py` — A100-80GB |
| T6 | GRPO training script (ms-swift) | ✅ Done | `modal_apex_grpo_msswift.py` — B200x2 |
| T7 | Launch Unsloth sanity check | ❌ CRASHED | `torch._dynamo` + bitsandbytes MoE incompatible, see post-mortem |
| **T8** | **GRPO training script (TRL + OpenEnv pattern)** | ✅ Done | `scripts/train_grpo.py` — rollout_func + real env reward |
| T9 | Scale up — 50 steps, 20 samples | 待做 | Whichever path works first |
| T10 | Full training — all 100 tasks | 待做 | Generate reward curves for demo |
| ~~T11~~ | ~~Colab minimal training script~~ | 不做 | 用 `scripts/train_grpo.py` 代替 |

---

## Reward Pipeline (10%) — v1 COMPLETE

| # | Task | Status | 结果/笔记 |
|---|------|--------|-----------|
| R1 | Reward v1 — keyword matching + file existence | ✅ Done | `server/reward.py`, fast (0 API calls) |
| R2 | GRPO proxy rewards (4 signals) | ✅ Done | Inline in both GRPO scripts |
| R3 | Reward v2 — LLM-as-judge | 待做 | 偷 apex-evals 的 grading/executor.py, for final demo |

---

## Submission Checklist

- [x] ~~Public GitHub repo~~ Private repo (github.com/lilyzhng/apex-env)
- [x] OpenEnv 0.2.1 deployed on HF Spaces — https://huggingface.co/spaces/lilyzhng/apex-env
- [x] Environment server deployed — https://huggingface.co/spaces/lilyzhng/apex-env-server
- [x] GRPO training script written — `scripts/train_grpo.py`
- [x] Training script: `scripts/train_grpo.py` (TRL + OpenEnv rollout_func)
- [ ] 1 minute demo video on YouTube
- [ ] Select up to 2 partner tracks (Mercor + ?)

---

## 可用数据（quick reference）

详见 `data_landscape_all_partners.md`

| 数据 | Size | 用途 |
|------|------|------|
| **APEX-v1-extended** | **100 tasks** | **GRPO 训练数据（当前使用）** |
| apex-multiturn-toolcalling | 100 tasks | SFT 备选 (已决定 skip SFT) |
| APEX-Agents | 480 tasks | Final eval (禁止训练) |
| MCP-Atlas trajectories | 500 tasks | 备选补充 (tool-use) |
| TRACE contrastive | 517 trajectories | 备选 DPO |

---

## 探索日志

每一步探索的结果记录在这里，按时间倒序。

### 2026-03-07

#### Commits

| Commit | Description |
|--------|-------------|
| `09e0764` | feat: APEX environment for OpenEnv hackathon (29/29 tests) |
| `9e3e4e6` | docs: add design doc with Mercor repo overlap analysis |
| `ecaebd1` | feat: add GRPO training scripts + progress tracker |
| `d98c193` | feat: add GRPO dataset conversion + update training scripts |
| `d2cbe1a` | refactor: deprecate keyword GRPO, add multi-turn Harbor eval pipeline |
| `94c406a` | fix: reward keyword extraction for apex-agents criteria field + v2 eval results |
| `401ac3a` | feat: fix extract_command parsing + add "Spend Less Do More" efficiency reward |
| `93ba2c5` | feat: add Gradio app with leaderboard, trajectory comparison, and live agent |
| `e210d80` | feat: add GRPO training script with TRL + OpenEnv rollout_func pattern |
| `aea26a7` | feat: add OpenEnv server space for HF Docker deployment |

#### Links

| Resource | URL |
|----------|-----|
| GitHub repo | https://github.com/lilyzhng/apex-env |
| HF Space (Dashboard) | https://huggingface.co/spaces/lilyzhng/apex-env |
| HF Space (Env Server) | https://huggingface.co/spaces/lilyzhng/apex-env-server |
| GRPO dataset (HF) | https://huggingface.co/datasets/lilyzhng/apex-grpo-tool-calling |
| SFT dataset (HF) | https://huggingface.co/datasets/lilyzhng/apex-multiturn-toolcalling |
| Modal run (Unsloth sanity) | https://modal.com/apps/lilyzhng/main/ap-WTCTGZbMNEvnQJ9WndudrE |

#### Progress

- [x] Training strategy finalized: skip SFT, direct GRPO, Qwen3-Coder-Next 80B MoE
- [x] Framework comparison: ms-swift (primary, 80B) + Unsloth (backup, 30B-A3B)
- [x] SofaGenius GRPO code reviewed — confirmed uses Qwen2.5-Coder-14B (dense), not MoE
- [x] Created `modal_apex_grpo_unsloth.py` — adapted from SofaGenius `run_grpo`
- [x] Created `modal_apex_grpo_msswift.py` — adapted from `modal_coder_instruct.py`
- [x] 4 APEX reward functions: bash_format, rubric_keyword, completeness, structured_output
- [x] Created `scripts/convert_to_grpo.py` — converts APEX-v1-extended to GRPO format
- [x] Pushed GRPO dataset to HF: `lilyzhng/apex-grpo-tool-calling` (100 tasks, 4 domains)
- [x] Updated both training scripts to use pre-converted GRPO dataset
- [x] Fixed Modal secrets (`hf-secret` not `huggingface-secret`) + GPU syntax (`"A100-80GB"` not `modal.gpu.A100(...)`)
- [x] Launched Unsloth GRPO sanity check (1 step, 5 samples) on Modal A100-80GB
- [x] ❌ Unsloth GRPO crashed — `torch._dynamo` incompatible with bitsandbytes MoE routing
- [x] Created `scripts/baseline_eval.py` — correct eval on `mercor/apex-agents` (not training data)
- [x] Created `harbor_adapter/` — converts apex-agents to Harbor task format
- [x] Tested adapter: 6 tasks generated, keyword extraction fixed (`criteria` field)
- [x] Discovered: keyword GRPO dataset is wrong paradigm — need on-policy multi-turn training
- [x] Found: OpenEnv `rollout_func` + durmstrang `ToolEnv` already support this natively
- [x] Fixed `reward.py`: `criteria` field + direct number/acronym extraction (was extracting 0 keywords)
- [x] Baseline eval v2 (3 tasks, fixed reward):

**Baseline Results (3 tasks, max 5 turns):**

| Model | IB | Law | Consulting | **Avg** |
|---|---|---|---|---|
| **30B-A3B-Instruct** | 0.65 | 0.77 | 0.52 | **0.65** |
| **Coder-Next (80B MoE)** | 0.00 | 0.42 | 0.00 | **0.14** |

**Key finding: 30B-A3B-Instruct >> Coder-Next for bash action space.**

Coder-Next 输出 `<tool_call>` (OpenAI function calling format)，不是 raw bash。
30B-A3B-Instruct 直接写 `echo "..." > file.txt`，能 ACT。

**Harbor/SkyRL 的 action format (from Terminus 2 agent):**
不是 function calling，也不是纯 raw bash。是轻量 XML wrapper + terminal keystrokes：
```xml
<analysis>思考过程</analysis>
<plan>计划</plan>
<commands><keystrokes duration="5">python3 calc.py</keystrokes></commands>
<task_complete>false</task_complete>
```
比 function calling 轻，比 raw bash 多一层结构（区分思考和行动）。

- [x] 9-model benchmark v3 完成（无输入文件）
- [x] 发现数据缺失问题：305 个"无文件" tasks 中 ~149 个实际需要外部数据
- [x] 发现 `mercor/apex-agents` HF repo 里有 `task_files/` 和 `world_files_zipped/` — 文件就在那里！
- [x] 修改 `baseline_eval.py`：`populate_workspace()` 自动下载 task input files 到 workspace
- [x] 移除 `--skip-file-tasks` 默认值，现在评估全部 480 tasks
- [x] 9-model benchmark v4（有文件）全部完成
- [x] 修 `extract_command()` — heredoc 支持, talk 过滤, `done` 后缀剥离
- [x] 实现 `compute_efficiency_reward()` — Talk Penalty + Action Efficiency ("Spend Less, Do More")
- [ ] **P0 下一步：加 Docker sandbox**

#### v4 Benchmark Results (18 tasks each, with input files, "Spend Less Do More" reward)

| # | Model | Type | Task Reward | Talk Penalty | Eff Bonus | **Final** | Talk% |
|---|-------|------|------------|-------------|-----------|-----------|-------|
| 1 | **GPT-4o-mini** | 闭源 cheap | 0.377 | -0.003 | +0.044 | **0.418** | 1.2% |
| 2 | **Qwen3-30B-A3B** | 开源 small | 0.269 | -0.004 | +0.025 | **0.291** | 2.2% |
| 3 | DeepSeek-V3 | 开源 | 0.189 | -0.038 | +0.020 | **0.203** | 20.8% |
| 4 | Kimi-K2 | 开源 | 0.167 | -0.033 | +0.017 | **0.180** | 16.9% |
| 5 | GLM-4.5 | 开源 | 0.138 | 0.000 | +0.014 | **0.152** | 0.0% |
| 6 | Claude Sonnet 4 | 闭源 frontier | 0.084 | **-0.102** | +0.008 | **0.081** | 51.1% |
| 7 | Coder-Next | 开源 | 0.049 | -0.047 | +0.003 | **0.052** | 22.5% |
| 8 | GPT-5.4 | 闭源 frontier | 0.037 | 0.000 | +0.003 | **0.041** | 0.0% |
| 9 | Opus 4.6 | 闭源 frontier | 0.017 | -0.047 | +0.003 | **0.017** | 23.3% |

**核心发现 — "Spend Less, Do More"：**

1. **最便宜的模型 (GPT-4o-mini) 得分最高 (0.418)**，最贵的 (Opus 4.6) 最低 (0.017)
2. **Claude Sonnet 4 被 talk penalty 惩罚最重** — 51% 的 actions 是废话 ("I'll help you...", "Let me explore...")，penalty = -0.102
3. **GPT-4o-mini 和 30B-A3B 几乎不说废话** (1-2% talk)，直接 ACT，还获得 efficiency bonus
4. **Frontier 模型花钱多，做事少** — 这就是训练目标：teach cheap models to act like they already want to

**v3 → v4 对比（加了 input files 后）：**

| Model | v3 (无文件) | v4 (有文件) | 变化 |
|-------|-----------|-----------|------|
| GPT-4o-mini | 0.325 | 0.377 | ↑ 更有数据可用 |
| 30B-A3B | 0.346 | 0.269 | ↓ 有文件反而更难 |
| DeepSeek-V3 | 0.116 | 0.189 | ↑↑ |
| Kimi-K2 | 0.082 | 0.167 | ↑↑ |
| GPT-5.4 | 0.088 | 0.037 | ↓ 文件让它更 distracted |
| Opus 4.6 | 0.056 | 0.017 | ↓ 同上 |

#### Design Decision: "Gold Coins" Trajectory Visualization + HF Spaces App (03-07 night)

**灵感来源：Acta**

Lily 之前做的视频编辑 app "Acta"（拉丁语 = "行动"）有一个可爱的 ASCII 动画 mascot `>(^_^)$`，
和我们的 "Spend Less, Do More" narrative 完美呼应 — Acta 本身就是 "act" 的词根。

**设计决策：Gold Coin 可视化**

核心思路：像 Super Mario 一样，每个 agent action 就是一步。
当 agent 做了真正有价值的事（执行 bash 命令），它获得一个 gold coin。
当 agent 浪费 turn 说废话（"Let me explore..."），它只是空跑，没有 coin。

这让观众一眼就能看出：
- 哪些模型"满屏金币" = 高效执行者
- 哪些模型"一路空跑" = 话多做少

**视觉设计（同 Acta 风格）：**
- 暖色调 beige 背景 (#F5F0E8) + charcoal 深色面板 (#1E1E1E)
- Space Mono 等宽字体
- macOS window chrome (红黄绿点)
- Gold coin = amber (#FFB800) 发光动画，代表 ACT
- Grey dot = #555，代表 TALK（浪费的 turn）
- Green check = #39FF14，代表 done signal

**实现：** `app.py` — Gradio app deployed to HF Spaces
- Tab 1: Leaderboard（9 模型排名 + key finding card）
- Tab 2: Trajectory（side-by-side agent comparison — 选 task + 选 2 个 agent 对比）
- Tab 3: Try It（live agent runner via OpenRouter API）
- Tab 4: About（简介）
- Terminal aesthetic: Space Mono, beige/charcoal, neon accents
- Animated mascot `>(^_^)<`（致敬 Acta 的 `✂(^-^)✂`）

**为什么这个可视化很重要？**

Hackathon judging 中 **Storytelling = 30%**。
3 分钟 pitch 不能只讲 reward 数字 — judges 需要"看到"差异。
Gold coin 可视化让 "talk vs act" 的差距变得直观：
- GPT-4o-mini 的 trajectory = 满屏金星
- Claude Sonnet 的 trajectory = 一半灰点
一图胜千言。

#### Design Decision: Docker Sandbox for Eval (P0 下一步)

**问题：当前 eval 直接在宿主机上跑 bash，不安全也不严谨。**

1. **不安全** — 模型的 bash 命令直接在 Mac 上执行。`rm -rf /` 或 `find /` 都能跑
2. **不隔离** — 模型能访问整个文件系统（GPT-5.4 在 `find /` 就证明了）
3. **不一致** — 不同机器工具不同（有没有 `pdftotext`？`pandas`？），结果不可复现

**正确做法：Docker sandbox。**

```
现在（不安全）:
  Model → bash → 直接在 Mac 上执行

应该（sandbox）:
  Model → bash → Docker 容器里执行
  容器有：python3, pandas, pdftotext, jq, openpyxl 等
  容器隔离：不能访问宿主机文件系统
```

**候选方案：**

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Harbor** | Terminal-native, SkyRL 集成, 已有 agent format | 需要搭建 Harbor infra |
| **Daytona** | 轻量 SDK, 快速创建 sandbox, API 简单 | 没有 RL 集成 |
| **自建 Docker** | 最简单, 完全控制 | 需要自己写 Dockerfile + 执行逻辑 |
| **Archipelago** | Mercor 官方, 有 grading | MCP action space, 不是 bash |

**决定：待定。先跑完 v4 benchmark，再选 sandbox 方案。**
核心需求：能在隔离环境里跑 bash + 有 python/pdftotext/pandas 等工具 + 文件系统隔离。

#### 🔥 Core Narrative: "Talk is Cheap, Show Me the Act" (03-07 night)

**9-Model Benchmark Results (18 tasks each, max 5 turns):**

| # | Model | Type | Final | Task Reward | Talk% |
|---|-------|------|-------|------------|-------|
| 1 | **GPT-4o-mini** | 闭源 cheap | **0.418** | 0.377 | 1.2% |
| 2 | **Qwen3-30B-A3B** | 开源 small | **0.291** | 0.269 | 2.2% |
| 3 | DeepSeek-V3 | 开源 | **0.203** | 0.189 | 20.8% |
| 4 | Kimi-K2 | 开源 | **0.180** | 0.167 | 16.9% |
| 5 | GLM-4.5 | 开源 | **0.152** | 0.138 | 0.0% |
| 6 | Claude Sonnet 4 | 闭源 frontier | **0.081** | 0.084 | 51.1% |
| 7 | Coder-Next | 开源 | **0.052** | 0.049 | 22.5% |
| 8 | GPT-5.4 | 闭源 frontier | **0.041** | 0.037 | 0.0% |
| 9 | Opus 4.6 | 闭源 frontier | **0.017** | 0.017 | 23.3% |

**核心发现：贵不等于能做事。Talk is cheap, show me the act.**

- GPT-5.4 (贵, frontier) = 0.088 < GPT-4o-mini (cheap) = 0.325
- Claude Sonnet 4 (frontier) = 0.059 < Qwen3-30B (开源 small) = 0.346
- **Frontier 模型全部在底部，最便宜/最小的模型反而最能 ACT**

**为什么？深度分析 action patterns：**

| Model | Total Actions | Bash % | Talk % | 行为特征 |
|-------|-------------|--------|--------|---------|
| GPT-5.4 | 80 | 96% | 0% | 全是 bash，但全在 find/grep 搜索不存在的文件 |
| Claude Sonnet 4 | 86 | 60% | 40% | 40% 废话 "I'll help you..."，echo 语法错误 |
| GPT-4o-mini | 83 | 98% | 0% | 直接写命令，直接产出结果 |
| 30B-A3B | 86 | 92% | 7% | 直接写 echo "EBITDA: 12.5" > file.txt，能 ACT |

**关键验证：不是 parsing 问题，是行为模式差异。**

GPT-5.4 的 96% 都是合法 bash — 我们的 parser 没有漏掉它的命令。
问题是：它花所有 5 个 turns 在 `find` 和 `grep` 搜索输入文件。
但这些 tasks 没有输入文件！模型需要用自己的知识 + 计算来产出结果。
**GPT-5.4 太 cautious — 不愿意"编造"数据去计算，一直在等不存在的数据出现。**

对比：30B-A3B 直接用知识写 `echo "Deal value/EBITDA: 12.5" > file.txt`。
它知道自己没有数据，但它选择 ACT — 用合理假设产出结果。

**这揭示了 agent capability 的三个层次：**
1. **Knowledge** — 所有模型都知道什么是 EBITDA（✅ 都有）
2. **Action willingness** — 愿不愿意在没有完美数据时也 ACT（❌ frontier 模型太 cautious）
3. **Action quality** — ACT 的结果对不对（需要更好的 reward 来评估）

**Domain 差异分析：**
- **Investment Banking**: 几乎所有模型都是 0 — 需要数值计算，最难 ACT
- **Law**: 所有模型都能得分 — 知识问答，`echo "答案" > file` 就行
- **Management Consulting**: 中间 — 需要结构化分析 + 数据

**这就是我们的 environment innovation story：**
> 我们的 environment 不测 intelligence，测 knowledge-action gap。
> 贵的模型知道更多，但便宜的模型更能 ACT。
> 训练目标：close the gap — 把 knowledge 变成 action。

- [x] ~~NOW:~~ Opus 4.6 结果已更新，rollout_func 已写（`scripts/train_grpo.py`），env server 已部署

#### Design Decision: Multi-Model Benchmark for Environment Validation (03-07 night)

**问题：两个模型的 eval 够不够？**

不够。两个模型只是 anecdotal evidence，不是 benchmark。
一个好的 RL environment 需要证明两件事：

**目标 1: Environment 具备 evaluation benchmark 价值**
- 对应 judging criteria: **Environment Innovation (40%)**
- 需要多模型评估证明 environment 有区分度 — 不同模型分数不同，说明 reward signal 有意义
- 如果所有模型都得一样的分，说明 environment 没有区分能力

**目标 2: Post-training 能提升弱模型**
- 对应 judging criteria: **Training Script (20%) + Reward Pipeline (10%)**
- 找一个分数低但有潜力的 base model，训练后分数上升
- Before/after 对比 = 最直观的 training evidence

**Judging Criteria 权重对照：**

| Criteria | Weight | 我们怎么证明 |
|----------|--------|-------------|
| Environment Innovation | **40%** | 多模型 benchmark，证明环境有区分度 |
| Storytelling | **30%** | 3 分钟 pitch + 1 分钟 demo video |
| Training Script Showing Improvement | **20%** | Before/after reward curves |
| Reward and Training Pipeline Setup | **10%** | Coherent reward + pipeline |

**这意味着 eval benchmark 本身就值 40 分。** 不是"跑完 eval 才能 train"，而是"eval 本身就是 deliverable"。

**公平性问题：Coder-Next 的 `<tool_call>` 格式**

Coder-Next 输出 `<tool_call>` / `<function=bash>` 格式，我们的 BashExecutor 无法执行。
这不公平 — 我们测的是"谁能输出 raw bash"，不是"谁能解决 professional tasks"。

解决方案：给 `extract_command()` 加了 `<tool_call>` JSON parsing。
结果：即使 parse 后，Coder-Next 依然只有 avg 0.023 — 因为它的格式不一致
（有时 `<tool_call>{json}</tool_call>`，有时 `<function=bash>`，有时 `function=bash`）。

**结论：这不是 adapter 能修的，是模型 RLHF 训练目标的冲突。**

**7-Model Benchmark（进行中）：**

| Model | 类型 | 为什么选 | OpenRouter ID |
|-------|------|---------|---------------|
| Claude Sonnet 4 | 闭源 frontier | 天花板，最强 agent | `anthropic/claude-sonnet-4` |
| GPT-4o-mini | 闭源 cheap | 最流行 baseline | `openai/gpt-4o-mini` |
| DeepSeek-V3 | 开源 中国 | Coding 能力强 | `deepseek/deepseek-chat-v3-0324` |
| GLM-4.5 | 开源 中国 | 智谱旗舰 | `z-ai/glm-4.5` |
| Kimi-K2 | 开源 中国 | Moonshot 旗舰 | `moonshotai/kimi-k2` |
| Qwen3-Coder-30B | 开源 中国 | 当前最佳 bash native | `qwen/qwen3-coder-30b-a3b-instruct` |
| Qwen3-Coder-Next | 开源 中国 | 对比：function calling 格式 | `qwen/qwen3-coder-next` |

覆盖：美国闭源 (Claude, GPT) + 中国开源 (Qwen, DeepSeek, GLM, Kimi) + function calling vs bash 对比。

**Coder-Next 结果（18 tasks, fixed tool_call parsing）：**

| Domain | n | Avg Reward | Avg Turns |
|--------|---|-----------|-----------|
| Investment Banking | 6 | 0.000 | 5.0 |
| Law | 6 | 0.069 | 4.3 |
| Management Consulting | 6 | 0.000 | 5.0 |
| **Overall** | **18** | **0.023** | **4.8** |

典型 failure pattern：输出 `<function=bash>` 或 `function=bash`（无 JSON body），BashExecutor 无法执行。
即使输出 bash 的少数 case（Law task），也只是 `echo "答案"` 而不是真正计算。

#### Design Decision: Train Bash, Not Tool Calling (03-07 night)

**问题：Coder-Next 是不是用错了版本？为什么 30B >> Coder-Next？**

不是版本问题。Coder-Next 本身就是 instruct 版本，但它被 RLHF 训练成优先输出 `<tool_call>` 格式（OpenAI function calling）。
30B-A3B-Instruct 没有这个训练，直接输出 raw bash — 在 BashExecutor 里能直接跑。

**这不是 bug，是 action format 选择的冲突。**

**Action Format 三层光谱：**

| 层次 | 例子 | 优点 | 缺点 |
|------|------|------|------|
| **High-level** | Claude Code Skills / MCP `tool_call(read_pdf, {file: "x.pdf"})` | 结构化、类型安全、可复用 | 需要 schema、不 universal |
| **Mid-level** | Harbor Terminus 2 XML `<keystrokes>cmd</keystrokes>` | 区分思考和行动、轻量 | 自定义格式，需训练 |
| **Low-level** | Raw bash `pdftotext file.pdf` | 最 universal、所有 LLM 都会 | 没结构，parsing 困难 |

**Decision: 训练 Bash（低层），部署时可以加封装（高层）。**

核心逻辑：
1. **能力向上兼容，不能向下。** 从 bash 可以升到 tool calling（加 XML wrapper 就行），但从 `<tool_call>` 降不到 bash（Coder-Next 就是反例）。
2. **迁移性最强。** APEX 480 tasks 跨 finance/law/consulting，不可能给每个任务预定义 tool schema。Bash 在任何环境都能跑。
3. **最接近 ground truth。** Agent 真正 ACT 的就是执行命令，不是填 JSON schema。
4. **训练时 low-level，部署时 high-level。** 能力在底层学会，格式在上层封装 — 就像 Claude Code 底层是 bash，但用 Skills 给用户用。

**Base model 选择确认：Qwen3-Coder-30B-A3B-Instruct。**
- 直接输出 raw bash，能 ACT
- Baseline avg reward 0.65 vs Coder-Next 0.14
- Coder-Next 的 function calling 训练反而成了阻碍

#### Design Decision: Kill Keyword GRPO, Go On-Policy (03-07 evening)

**发现：我们的整个 GRPO dataset 方向是错的。**

`lilyzhng/apex-grpo-tool-calling` 和 `convert_to_grpo.py` 做的是：
把 rubric 压缩成关键词 → 模型生成单轮文本 → keyword matching 打分。

这有两个根本问题：

1. **假打分。** 模型写了 "IRR" 这个词就给分，但它从来没有真的算过 IRR。
   Keyword matching ≠ 真正完成任务。我们选 Harbor 就是为了真打分，training 也不能用假分。

2. **不是 tool calling。** 单轮文本生成训练的是"写出像 bash 的文字"，不是真正的 tool calling。
   Tool calling 是多轮的：action → observation → action → observation。
   模型写了 `python3 calc.py` 但从没看到执行结果，怎么学会根据结果调整下一步？

**关键发现：OpenEnv 自己的 tutorial 就展示了正确的做法。**

```python
# OpenEnv 04-training.md — on-policy GRPO with real environment
def rollout_func(prompts, trainer=None):
    for prompt_text in prompts:
        episode = rollout_once(
            trainer=trainer,
            env=env,           # ← 真实环境交互！
            max_turns=6,       # ← 多轮！
        )
```

Patronus 的 durmstrang 也有 `ToolEnv`（multi-turn tool use）和 `MultiTurnEnv`。
SkyRL + Harbor 是最成熟的 terminal-native on-policy RL。
**大家都知道要 on-policy training with real environment interaction。我们自己绕远了。**

**正确的 pipeline：**
```
旧（错）: v1-extended → extract keywords → 单轮 GRPO → keyword reward
新（对）: ApexEnvironment → rollout_func → 多轮 action/observation → real reward
```

我们已经有 ApexEnvironment（29/29 tests passing），有 bash executor，有 reward.py。
只需要写一个 `rollout_func` 把它接到 GRPO trainer 上。

**废弃：**
- ~~`scripts/convert_to_grpo.py`~~ — 不再需要
- ~~`lilyzhng/apex-grpo-tool-calling`~~ — 方向错误的数据集
- ~~`modal_apex_grpo_unsloth.py` 里的 4 个 keyword reward functions~~ — 假打分

**保留：**
- `harbor_adapter/` — eval 用，方向正确
- `ApexEnvironment` — 核心，接 rollout_func
- `server/reward.py` — 需要从 keyword 升级为真实验证

#### Design Decision: Harbor as Eval + RL Infrastructure (03-07)

**问题：我们到底在解决什么？**

> 让 agent 在 professional tasks 上从 "会想" 变成 "会做"。
> Teach agents to ACT, not just THINK.

Baseline model 可能会写出漂亮的分析框架，但不会真的读 PDF、算 IRR、把结果写成文件。
我们训练它学会 ACT — 在正确的时候调用正确的工具。

**为什么 Harbor？**

Keyword matching reward 是假打分 — "你提到了 IRR 就给分"。这不是真正的 eval。
Harbor 提供真实沙盒：agent 真的跑 `python3 calc.py`，verifier 真的检查答案对不对。
Harbor + SkyRL = 真实环境 eval + RL training，end-to-end。

**为什么不用 Archipelago（Mercor 自研）？**

Archipelago 用 MCP action space（JSON-RPC tool schema）。
我们选的是 terminal/bash action space — 更 universal，所有 LLM 都已经会 bash。
Harbor 是 terminal-native，跟我们的设计完全对齐。
Harbor 还有 SkyRL 集成（GRPO/PPO），Archipelago 没有 RL。

**Tool calling 形式不重要，核心是 agent 学会在正确时候调用正确工具：**
- Bash: `python3 calc.py`, `pdftotext file.pdf`
- MCP: `tool_call(read_pdf, {file: "contract.pdf"})`
- Function calling: OpenAI style tool_use

形式是 implementation detail，能力才是目标。我们选 bash 因为最 universal。

**数据分割：**
- `mercor/apex-agents` 480 tasks 中 305 个无文件依赖 → 可直接用 Harbor eval
- 175 个有文件依赖（`snap_xxx`）→ 文件在 Mercor 基础设施里拿不到，暂时跳过
- `mercor/APEX-v1-extended` 100 tasks → 训练用（全部有文件但 rubric 自带 justification）

**Pipeline:**
```
Training: APEX-v1-extended (100 tasks) → GRPO reward → SkyRL
Eval:     apex-agents (305 no-file tasks) → Harbor sandbox → real verification
```

#### Post-Mortem: Mistakes Made (03-07)

**Mistake 1: Wrong order — training before eval**
- 我们跳过了 baseline eval 直接写训练脚本，相当于不知道病在哪就开药了
- 正确顺序：baseline eval → failure analysis → adjust rewards → THEN train
- **Fix:** 补写 `scripts/baseline_eval.py`，BLOCKED training until baseline done

**Mistake 2: Eval on wrong dataset**
- 之前 eval session 用的是 `mercor/APEX-v1-extended`（训练数据！）
- 正确的 eval 数据集是 `mercor/apex-agents`（480 tasks，禁止训练，专用于评估）
- 在训练数据上测试 = 在考试卷上练习后再考同一张卷子，结果没有参考价值
- **Fix:** `baseline_eval.py` 硬编码使用 `mercor/apex-agents`

**Mistake 3: Unsloth GRPO crash — torch._dynamo + bitsandbytes MoE**
- Error: `torch._dynamo.exc.Unsupported: non-function or method super` in bitsandbytes
- Root cause: Unsloth patches + bitsandbytes 4-bit quantization + MoE sparse routing = PyTorch dynamo 编译失败
- W&B run: https://wandb.ai/alchemxz/apex-grpo/runs/lfaklybp
- **Possible fix:** `TORCHDYNAMO_DISABLE=1` env var, or switch to non-4bit mode

**Mistake 4: GRPO keyword noise**
- `extract_keywords()` 提取了 `.`, `0`, `1` 等单字符 → 匹配一切 → rubric_keyword reward 虚高
- **Fix needed:** Filter `len(kw) > 1` in keyword extraction (已在 baseline_eval.py 修复)

**Lesson: 永远先 eval，再 train。不知道 baseline 在哪，就不知道 improvement 在哪。**

#### 03-07 03:38 — Session Wrap: HF Space Deployed

**Done tonight (03-07 late night session):**
- [x] Fixed `extract_command()` — heredoc, talk filtering, `done` suffix
- [x] Added "Spend Less, Do More" efficiency reward (`compute_efficiency_reward()`)
- [x] Built Gradio app (`app.py`) — 4 tabs: Leaderboard, Trajectory, Try It, About
- [x] Trajectory tab: side-by-side comparison — select any task + any 2 of 9 models
- [x] Try It tab: live agent via OpenRouter API (retry logic for 429 rate limits)
- [x] Terminal aesthetic (Space Mono, beige/charcoal, Acta-inspired)
- [x] Deployed to HF Spaces: https://huggingface.co/spaces/lilyzhng/apex-env
- [x] OPENROUTER_APIKEY set as HF Space secret
- [x] Wrote GRPO training script: `scripts/train_grpo.py` (TRL + OpenEnv rollout_func)
- [x] Created `server_space/` — OpenEnv environment server (Docker + FastAPI)
- [x] Deployed env server to HF: https://huggingface.co/spaces/lilyzhng/apex-env-server (Running ✅)

#### 03-07 04:15 — End of Night. TODO for Saturday (hackathon day)

**状态总结：** Environment 完成，dashboard 完成，server 部署完成，training script 写好但没跑过。

**P0 — Must do Saturday (hackathon 1PM Sunday deadline):**
1. **Run training on GPU (Modal)** — `scripts/train_grpo.py`, 需要 reward curve 上升的证据。Judges 20% weight on "Training Script Showing Improvement"
2. **1-minute demo video on YouTube** — 必须提交，没有 video = 不能参赛
3. **3-minute pitch** — "Spend Less, Do More" narrative + live demo

**P1 — Should do if time allows:**
4. **Docker sandbox (E11)** — 当前 bash 直接在容器里跑，server_space Dockerfile 已经有基本隔离，但可以加强
5. **Make GitHub repo public** — hackathon rule: "Please ensure your repository is public"
6. **Select partner tracks** — Mercor (APEX-Agents improvement) + Scale AI or Fleet AI

**P2 — Nice to have:**
7. **Improve reward** — LLM-as-judge (R3) 替代 keyword matching，会让 training signal 更真实
8. **Polish Gradio app** — 根据 kickoff presentations 调整 storytelling
9. **Attend kickoff presentations (10:00-11:30)** — 听 Mercor/Scale AI 怎么 frame problem

**已完成的 deliverables:**
- [x] OpenEnv environment (`apex_env/`) — 29/29 tests
- [x] HF Space dashboard — https://huggingface.co/spaces/lilyzhng/apex-env
- [x] HF Space env server — https://huggingface.co/spaces/lilyzhng/apex-env-server
- [x] 9-model benchmark with "Spend Less, Do More" reward
- [x] GRPO training script — `scripts/train_grpo.py`
- [x] Trajectory comparison visualization (gold coins)
- [ ] Training run with reward curve ← **this is the gap**
- [ ] Demo video ← **this is required for submission**
- [ ] Pitch ← **this wins or loses**

#### 03-07 04:10 — Environment Server Deployed to HF Spaces

**What:** Deployed `server_space/` as a Docker Space on HF — the actual OpenEnv environment server that trainers connect to.

- HF Space: https://huggingface.co/spaces/lilyzhng/apex-env-server
- URL: `https://lilyzhng-apex-env-server.hf.space`
- Endpoints: `POST /reset`, `POST /step`, `GET /state`
- SDK: Docker (Python 3.11-slim + uvicorn)
- Uses `openenv-core` `create_app()` to generate FastAPI server

**Now we have two HF Spaces:**
1. **`lilyzhng/apex-env`** — Gradio dashboard (storytelling, trajectory viz, leaderboard)
2. **`lilyzhng/apex-env-server`** — OpenEnv environment server (trainer connects here for rollouts)

**Commit:** `aea26a7`

#### 03-07 03:50 — Training Script Written: `scripts/train_grpo.py`

**What:** GRPO training script following official TRL + OpenEnv `rollout_func` pattern.
Based on: https://huggingface.co/docs/trl/main/en/openenv (echo.py + wordle.py examples)

**Architecture:**
```
mercor/APEX-v1-extended (100 tasks)
    ↓ load as prompts
GRPOTrainer + rollout_func
    ↓ for each prompt:
    LocalApexEnv.reset() → load task + download file attachments
    for turn in range(max_turns):
        model.generate() → bash command
        env.step(command) → observation
    env reward = compute_reward(task, workspace)  ← real rubric scoring
    ↓
    GRPO policy update with env_reward
```

**Key design decisions:**
- `LocalApexEnv` — lightweight wrapper, no openenv/Docker dependency needed for training
- Multi-turn rollout: agent does up to 6 turns of bash ↔ observation per episode
- File attachments: auto-downloaded from HF to workspace (v1-extended has PDFs)
- Reward = real `compute_reward()` from `reward.py` (keyword coverage + file existence)
- Base model: `Qwen/Qwen3-Coder-30B-A3B-Instruct` (best baseline scorer for bash)
- Compatible with Modal (GPU) or local (if you have A100)

**Still needs:**
- [ ] Actually run it (needs GPU — Modal)
- [ ] Verify reward curve goes up
- [x] Deploy ApexEnvironment as proper OpenEnv server on HF Space — `lilyzhng/apex-env-server`

**Priority for tomorrow:**
1. Run training on GPU (Modal) — judges need to see reward curve go up
2. Demo video — 1 minute, show the HF Space + trajectory comparison
3. Pitch draft — "Spend Less, Do More" story

#### Key Discovery: HF Space 应该是 Environment Server，不是 Dashboard (03-07 03:45)

**发现：** 其他 OpenEnv environment 在 HF Spaces 上都是 interactive environment servers，
不是展示 eval 结果的 dashboard。

参考：https://huggingface.co/spaces?category=agent-environment

| Space | 做什么 |
|-------|--------|
| [openenv/coding_env](https://huggingface.co/spaces/openenv/coding_env) | 发 Python 代码 → 执行 → 返回结果 |
| [openenv/echo_env](https://huggingface.co/spaces/openenv/echo_env) | 发文本 → echo 回来 |
| [openenv/sudoku](https://huggingface.co/spaces/openenv/sudoku) | 发 actions → 更新棋盘状态 |
| [shankerram3/wildfire_env](https://huggingface.co/spaces/shankerram3/Wildfire_env) | 放水/设防火线 → 模拟火势 |

**模式：** Environment server running on HF Space → trainer 通过 OpenEnv client 远程连接做 rollout。

**我们需要两个东西：**
1. **Environment Server (HF Space)** — 跑 `ApexEnvironment`，用 `APEX-v1-extended` (100 tasks) 作为 training data，接收 bash actions，返回 observations + reward
2. **Training Script** — `scripts/train_grpo.py` on Modal，连接 HF Space 做 GRPO training，展示 reward 上升

**我们现有的 Gradio dashboard 是 storytelling 用的，不是 environment。**
需要另外部署一个真正的 environment server（`apex_env/server/app.py` 用 `create_app()` 跑 FastAPI）。

**数据分割（再次确认）：**
- `mercor/APEX-v1-extended` (100 tasks) = Training — environment server 用这个
- `mercor/apex-agents` (480 tasks) = Eval only — dashboard + baseline_eval.py 用这个

**参考资料：**
- [HF Spaces - Agent Environment Category](https://huggingface.co/spaces?category=agent-environment)
- [OpenEnv Hub](https://huggingface.co/openenv)
- [OpenEnv Blog Post](https://huggingface.co/blog/openenv)
- [OpenEnv TRL Integration](https://huggingface.co/docs/trl/main/en/openenv)
- [OpenEnv Scaling Guide](https://huggingface.co/blog/burtenshaw/openenv-scaling)
- [OpenEnv Coding Env (reference implementation)](https://huggingface.co/spaces/openenv/coding_env)
- [OpenEnv GitHub](https://github.com/meta-pytorch/OpenEnv)

---

### 2026-03-06

- [x] Statement 1-5 全部过完，所有 partner 研究完成
- [x] 数据全景整理 → `data_landscape_all_partners.md`
- [x] Storytelling 初步方向：democratize professional capabilities
- [x] ApexEnvironment v1 implemented — 29/29 tests passing
- [x] Design doc written with Mercor repo overlap analysis
