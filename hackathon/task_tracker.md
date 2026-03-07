---
date: 2026-03-06
type: roadmap
updated: 2026-03-07 14:30
---

# OpenEnv Hackathon Roadmap

## Priority Restack (based on judge feedback, 03-07 afternoon)

> **评审（Meta team）原话：专注于环境设计，不要急着训练。想象自己是 Agent，在什么环境下能得到什么反馈？**
> **评审标准：Environment 40% + Storytelling 30% = 70% >> Training 20% + Reward 10% = 30%**

### P0 — Environment Polish + Storytelling (70% of judging)

| # | Task | Status | Why |
|---|------|--------|-----|
| 1 | **Difficulty Tier 支持 (E10)** | **进行中** | 给 TaskLoader 加 difficulty tier（easy/medium/hard），用已有公式分级，跑分层 eval 验证 performance gap |
| 2 | Docker sandbox (E11) | 待做 | 环境跑 bash 没隔离 = 不 production-ready，评审会问 |
| 3 | 手动当 agent 测环境，找 edge case | 待做 | 评审原话："穿上 agent 的鞋子" |
| 4 | Make repo public | 待做 | Hackathon rule，评审要看代码 |
| 5 | 写 3 分钟 pitch 草稿 | 待做 | **RecomposeRL narrative** — Scale Down → Internalize → Scale Out |
| 6 | 录 1 分钟 demo video | 待做 | 没 video = 不能参赛 |

### P1 — Training (20% of judging)

| # | Task | Status | Why |
|---|------|--------|-----|
| 7 | 跑一个 minimal training run | 待做 | 不需要完美，有 reward curve 上升趋势就行 |
| 8 | Before/after 对比截图 | 待做 | 哪怕只训 10 steps，有 curve > 没有 |

### 砍掉

| Task | Why |
|------|-----|
| ~~E9 Knowledge vs Action 双维度~~ | 锦上添花，不影响 judging |
| ~~R3 LLM-as-judge reward~~ | 同上 |

### 时间分配

```
Saturday 下午:
  Docker sandbox (2h) — 或至少在 pitch 里说明隔离设计
  Progressive difficulty tiers (1h) — 分 3 tier
  手动测环境，找 2-3 个好的 failure case 用于 storytelling

Saturday 晚上:
  写 pitch + 录 demo video
  如果有空，挂 minimal training run 过夜

Sunday 上午:
  Polish pitch
  检查 training 结果（如果跑了的话）
  Make repo public
```

---

## Story (30%)

**核心 statement:**
> Agent 把金融分析、法律审核、咨询策略这些被锁在高薪专业人士手里的能力，还给每一个普通人。

| # | Task | Status | 结果/笔记 |
|---|------|--------|-----------|
| S1 | 问 Shubham 关于 Lionel 的 motivation — democratization resonates? | 待回复 | 已发消息 |
| S2 | 跟 Simon 碰 storytelling（他的强项） | 待做 | 周末 remote call |
| S3 | 听 kickoff presentations (Sat 10:00-11:30)，找灵感 | ✅ Done | Scale AI = verification 是核心瓶颈，Mercor = 递进难度，详见 Guidelines Section 12-13 |
| S4 | 写 3 分钟 pitch 草稿 | **P0 待做** | "Spend Less, Do More" + verification framing |
| S5 | 录 1 分钟 demo video | **P0 待做** | 没 video = 不能参赛 |

---

## Environment (40%) — Core done, polish needed

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
| ~~E9~~  | ~~Knowledge vs Action 双维度评分~~                   | 砍掉 | 锦上添花，不影响 judging |
| **E10** | **Progressive Difficulty Tiers**                | **进行中** | 2D curriculum: tool complexity × reasoning complexity。已有公式和 2x2 矩阵（s2_findings_apex_analysis.md），现在加到 TaskLoader + 跑分层 eval |
| **E11** | **Docker Sandbox**                              | **P0 待做** | Harbor / Daytona / 自建 Docker，隔离执行环境（评审关注点）|
| **E13** | **手动当 agent 测环境**                           | **P0 待做** | 评审原话："穿上 agent 的鞋子"，找 edge case 用于 storytelling |
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

## Training (20%) — P1, deprioritized per judge feedback

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
| ~~R3~~ | ~~Reward v2 — LLM-as-judge~~ | 砍掉 | 锦上添花，不影响 judging |

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

> **探索日志已提取到** `~/Documents/lilyzhng/2026/20260306_thinking_artifact.md`
> 包含：design decisions, benchmark results, post-mortems, 03-06/03-07 全部探索记录
