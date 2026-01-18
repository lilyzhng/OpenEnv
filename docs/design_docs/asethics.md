# Plan: Frontend Style Consistency Environment 
建立一个"前端风格一致性环境"，专门惩罚那种"默认炫酷蓝紫渐变、色彩斑斓、统一模板化"的输出，逼模型遵守你定义的产品风格。

## 0. 核心目标（What）

做一个可运行的前端 repo + 自动评测环境，用来：

1. 测试不同模型（Qwen3-Coder / Claude / GPT / Codex）在"风格一致性"上的 failure modes
2. 作为后续 SFT 的回归评测（训练前后分数对比）
3. 未来升级为 RL reward（把 score 当 reward）

重点解决的痛点：

* 模型经常默认输出"炫酷蓝紫渐变/霓虹风/色彩斑斓"的模板 UI
* 不会根据产品属性（例如金融/医疗/企业工具/消费品）调整设计系统与视觉语言
* 多轮编辑后风格漂移（新组件引入新颜色、新圆角、新阴影）

## 1. OpenEnv 集成架构

本环境遵循 OpenEnv 的 client-server 分离架构，确保与现有训练基础设施无缝集成。

### 1.1 目录结构（OpenEnv 标准）

```
envs/style_env/
├── __init__.py
├── client.py                 # StyleEnv(EnvClient) - 客户端
├── models.py                 # StyleAction, StyleObservation, StyleState
├── openenv.yaml              # 环境元数据（自动发现用）
├── pyproject.toml            # 包依赖（standalone 安装用）
├── README.md
├── server/
│   ├── __init__.py
│   ├── app.py                # FastAPI 入口（使用 openenv 标准模板）
│   ├── Dockerfile
│   ├── style_environment.py  # 核心环境逻辑
│   └── scorers/
│       ├── __init__.py
│       ├── lint_scorer.py
│       ├── token_scorer.py
│       ├── component_reuse_scorer.py
│       └── diff_discipline_scorer.py
├── frontend_template/        # 前端模板（每个 episode 复制一份）
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── .eslintrc.cjs
│   ├── .prettierrc
│   └── src/
│       ├── theme/
│       │   ├── tokens.ts
│       │   └── product_profiles.ts
│       ├── components/ui/
│       │   ├── Button.tsx
│       │   ├── Card.tsx
│       │   ├── Input.tsx
│       │   ├── Badge.tsx
│       │   └── Table.tsx
│       └── pages/
│           └── .gitkeep      # 评测目标目录
└── prompts/
    └── prompts.jsonl         # 评测任务集
```

### 1.2 关键设计决策

**Docker 构建优化**：`node_modules` 在 Docker 镜像构建时预装，每个 episode 只复制 `src/` 目录，避免重复安装依赖。

**Action 类型**：
- `READ_FILE`: 读取文件内容
- `CREATE_FILE`: 创建新文件（用于生成新组件/页面）
- `APPLY_PATCH`: 应用 unified diff
- `RUN`: 执行预定义命令 (BUILD, LINT, SCORE)
- `GET_PROFILE`: 获取当前 product profile 详细规则

**Observation 包含**：
- `output`: 命令输出/文件内容
- `current_profile`: 当前激活的 profile 名称
- `score_breakdown`: 各规则得分明细
- `build_passed`, `lint_passed`: 硬门槛状态
- `steps_remaining`: 剩余步数

## 2. 关键概念：Product Profile（产品属性驱动的设计系统）

你要做的关键不是"固定一个好看的风格"，而是：

* 给定产品属性（product profile），定义对应的 UI 设计系统
* 让模型生成时必须遵守该 profile
* **Profile 信息通过 observation 和 GET_PROFILE action 暴露给 agent**

### 2.1 MVP 先做 2 个 profile（降低 Day 1 复杂度）

1. **Enterprise B2B 工具**：低饱和、灰白为主、少渐变、强信息层级
2. **Consumer App**：可以更活泼，但仍受 token 限制，不允许随便炫

### 2.2 Iter 1 扩展到 3 个 profile

3. **FinTech**：稳重、克制、强调信任（蓝系可用但禁止霓虹/渐变）

### 2.3 每个 profile 明确规定（machine-readable）

```typescript
// product_profiles.ts 示例结构
interface ProductProfile {
  name: string;
  description: string;
  
  // 允许的 Tailwind 颜色 token（白名单）
  allowedColors: string[];  // e.g., ["gray-50", "gray-100", ..., "blue-600"]
  
  // 明确禁止的 pattern（黑名单）
  forbiddenPatterns: {
    gradients: boolean;           // 禁止 bg-gradient-to-*, from-*, to-*, via-*
    neonColors: string[];         // 禁止 ["purple-500", "fuchsia-*", "pink-400", ...]
    inlineStyles: boolean;        // 禁止 style={{...}}
    rawColorValues: boolean;      // 禁止 #xxx, rgb(), hsl()
  };
  
  // 允许的 spacing scale（白名单）
  allowedSpacing: string[];       // e.g., ["p-2", "p-4", "p-6", "p-8", "m-2", ...]
  
  // 允许的 radius
  allowedRadius: string[];        // e.g., ["rounded", "rounded-md", "rounded-lg"]
  
  // 允许的 shadow
  allowedShadow: string[];        // e.g., ["shadow-sm", "shadow"]
}
```

## 3. 评测任务集（Eval Prompts）

每条任务包含：

```jsonc
{
  "id": "enterprise-settings-001",
  "profile": "enterprise",
  "task": "生成一个 Settings 页面，包含侧边栏导航、表单区（用户信息编辑）、保存按钮。",
  "constraints": [
    "必须使用 src/components/ui/ 中的 Button, Card, Input 组件",
    "禁止自定义颜色",
    "禁止渐变背景"
  ],
  "target_files": ["src/pages/Settings.tsx"],
  "allowed_modifications": ["src/pages/**"],  // diff discipline 用
  "max_new_files": 1,                         // 限制创建文件数
  "difficulty": "easy"                        // easy / medium / hard
}
```

**任务类型覆盖**：
- 从零生成页面（CREATE_FILE）
- 修改现有页面（APPLY_PATCH）
- 添加新组件到现有页面（混合）
- 多轮迭代任务（测试风格漂移）

## 4. Scoring（评分体系：先做规则，再做截图）

你要的"拒绝统一炫酷蓝紫风"可以用规则强行打掉。

### 4.1 硬门槛（Fail fast）—— 不通过则 reward = -1.0

* `pnpm build` 必须通过（TypeScript 编译 + Vite 构建）
* `pnpm lint` 必须通过（ESLint）
* `pnpm format:check` 必须通过（Prettier）

不通过直接给 reward = -1.0，并在 observation 输出失败原因。

### 4.2 风格一致性规则分（MVP 重点）—— 0~100 分

Token/风格规则（可自动化）：

| 规则 ID | 描述 | 扣分权重 | 检测方式 |
|---------|------|----------|----------|
| R1 | 禁止新增任意颜色：`#...`、`rgb(...)`、`hsl(...)` | -10/次 | Regex |
| R2 | 禁止渐变 class：`bg-gradient-to-*`、`from-*`、`to-*`、`via-*` | -8/次 | Regex |
| R3 | 禁止 profile 黑名单颜色（如 `purple-500`、`fuchsia-*`） | -5/次 | Token 白名单检查 |
| R4 | 禁止 inline style：`style={{...}}` 或 `style={...}` | -10/次 | AST 或 Regex |
| R5 | 必须复用 UI 组件库（Button/Card/Input），禁止手写 `<button>` | -15/次 | Import 检查 + JSX tag 检查 |
| R6 | Tailwind class 必须排序（prettier-plugin-tailwindcss） | -2/次 | Prettier check |
| R7 | Spacing 必须在允许列表内 | -3/次 | Token 白名单检查 |
| R8 | Diff discipline：只允许修改 `allowed_modifications` 内的文件 | -20/次 | Git diff 分析 |

**重要：使用正则表达式的局限性**

对于 MVP，使用 Regex 是可接受的，但需注意以下 edge cases（记录为已知限制）：
- 模板字面量：`` className={`bg-gradient-to-${dir}`} ``
- `clsx`/`cn` 包装：`cn("bg-gradient-to-r", conditional && "...")`
- 动态 class 组合

**Iter 1 可升级为 AST-based 扫描**（使用 `@typescript-eslint/parser` + `@babel/parser`）。

### 4.3 评分输出格式

```json
{
  "total_score": 72,
  "max_score": 100,
  "hard_gates": {
    "build": true,
    "lint": true,
    "format": true
  },
  "rule_violations": [
    {"rule": "R1", "file": "src/pages/Settings.tsx", "line": 42, "snippet": "color: '#ff6b6b'", "penalty": -10},
    {"rule": "R5", "file": "src/pages/Settings.tsx", "line": 15, "snippet": "<button className=...", "penalty": -15}
  ],
  "penalties_total": -28
}
```

### 4.4 Reward 转换（用于 RL）

```python
def score_to_reward(score_result: dict) -> float:
    """Convert scoring result to RL reward."""
    # Hard gate failure
    if not all(score_result["hard_gates"].values()):
        return -1.0
    
    # Normalize score to [-0.5, 1.0] range
    # 100 → 1.0, 50 → 0.25, 0 → -0.5
    normalized = (score_result["total_score"] / 100) * 1.5 - 0.5
    
    # Add small step cost to encourage efficiency
    step_cost = 0.01
    
    return normalized - step_cost
```

### 4.5 截图评分（第二阶段，可选）

用 Playwright 渲染固定 viewport (1280x720) 截图：

* 检查 overflow、错位、对齐（DOM bbox 简单规则）
* 或做"与参考页面的视觉距离"对比（后续再做）

## 5. "模型对比实验"（你要的 failure modes）

跑同一套 eval prompts：

* Qwen3-Coder（baseline）
* Claude（Cursor）
* GPT/Codex
* Gemini（上限参考）

正确流程：
Step A：先有一个“已定义风格”的 repo（基线代码 + tokens + 组件库 + 参考页面）
Step B：给 coding agent（Claude/GPT/Qwen 等）一个任务：新增功能/新增页面/改一个组件
Step C：它输出一个 diff（或直接改文件）
Step D：环境应用 diff，然后 evaluate：
能不能跑：build/tsc/lint/format
风格是否一致：是否使用 tokens、是否复用组件库、是否引入渐变/紫色、是否 spacing 不在 scale、是否乱改无关文件
（可选）渲染截图检查：是否溢出、是否明显错位

你要的就是“新增代码是否跟原先风格 consistent”，这是环境的核心。


输出一份报告：

```markdown
## Model Comparison Report

### Summary
| Model | Avg Score | Hard Gate Pass Rate | Top 3 Violated Rules |
|-------|-----------|---------------------|----------------------|
| Qwen3-Coder | 45.2 | 78% | R2 (gradient), R3 (neon), R5 (raw button) |
| Claude | 72.1 | 95% | R5 (raw button), R7 (spacing) |
| GPT-4 | 68.5 | 92% | R2 (gradient), R5 (raw button) |
| Gemini | 81.3 | 98% | R7 (spacing) |

### Failure Mode Analysis
- **Qwen3-Coder**: 过度使用紫色渐变背景，几乎每个页面都有 `bg-gradient-to-br from-purple-500`
- **Claude**: 较好遵守颜色约束，但倾向于手写 `<button>` 而非使用组件库
- ...
```

这就是你要的 failure-mode driven development 起点。

## 6. 迭代路线（先环境后训练）

### Iter 0（1天）：环境 MVP

**产物**：
* [x] OpenEnv 目录结构搭建完成
* [x] `frontend_template/` 可独立运行（pnpm dev/build/lint）
* [x] Docker 镜像可构建，server 可启动
* [x] 2 个 profile 定义完成（Enterprise, Consumer）
* [x] 4 个核心 scorer 实现：lint_scorer, token_scorer, component_reuse_scorer, diff_discipline_scorer
* [x] 10 条 prompts 能对比出不同模型差异（降低初始工作量）

**验收标准**：
```bash
# 能跑通
docker build -t style-env:latest -f envs/style_env/server/Dockerfile .
python examples/style_simple.py  # 完成一个 episode
```

### Iter 1（第2天）：完善评测 + SFT 数据

* 扩展到 20 条 prompts，覆盖 3 个 profile
* 用 Gemini 生成 200 条 "符合 enterprise/fintech/consumer profile" 的页面代码作为 SFT 数据
* SFT 微调 Qwen3-Coder（LoRA/QLoRA）
* 用 evaluator 对比微调前后的分数提升（这就是正反馈）

### Iter 2（之后）：偏好优化 / RL

* 用 evaluator score 做 reward
* 或用 "同 prompt 多采样 → 选最高分" 做 rejection sampling
* 再做 DPO/ORPO（成本低、效果往往够用）

### Iter 3（可选）：截图评分

* Playwright 截图集成
* 视觉回归测试
* Layout 规则检查（overflow, alignment）

## 7. Pydantic Models（models.py 参考）

```python
from typing import Literal, Optional, List, Dict
from pydantic import Field
from openenv.core.env_server.types import Action, Observation, State


class StyleAction(Action):
    """Action for the Style Consistency environment."""
    
    action_type: Literal["READ_FILE", "CREATE_FILE", "APPLY_PATCH", "RUN", "GET_PROFILE"] = Field(
        ..., description="Type of action to perform"
    )
    path: Optional[str] = Field(
        default=None, description="File path for READ_FILE/CREATE_FILE"
    )
    content: Optional[str] = Field(
        default=None, description="File content for CREATE_FILE"
    )
    diff: Optional[str] = Field(
        default=None, description="Unified diff for APPLY_PATCH"
    )
    cmd_id: Optional[Literal["BUILD", "LINT", "SCORE"]] = Field(
        default=None, description="Command ID for RUN action"
    )


class RuleViolation(BaseModel):
    """A single rule violation."""
    rule: str
    file: str
    line: int
    snippet: str
    penalty: int


class ScoreBreakdown(BaseModel):
    """Detailed scoring breakdown."""
    total_score: int = Field(ge=0, le=100)
    max_score: int = 100
    hard_gates: Dict[str, bool]
    rule_violations: List[RuleViolation]
    penalties_total: int


class StyleObservation(Observation):
    """Observation from the Style Consistency environment."""
    
    output: str = Field(default="", description="Command output or file content")
    current_profile: str = Field(default="", description="Active product profile name")
    build_passed: Optional[bool] = Field(default=None)
    lint_passed: Optional[bool] = Field(default=None)
    score_breakdown: Optional[ScoreBreakdown] = Field(default=None)
    steps_remaining: int = Field(default=0, ge=0)


class StyleState(State):
    """State for the Style Consistency environment."""
    
    current_profile: str = ""
    task_id: str = ""
    build_passed: Optional[bool] = None
    lint_passed: Optional[bool] = None
    last_score: Optional[int] = None
```

## 8. 你需要 Cursor 生成的具体代码清单（Tasks for Cursor）

### Phase 1: 基础设施（Iter 0 必须）

1. 初始化 `envs/style_env/` 目录结构（按 1.1 节）
2. 创建 `frontend_template/`：Vite+React+TS+Tailwind repo（含 eslint/prettier/tailwind 插件）
3. 实现 `frontend_template/src/theme/tokens.ts`：定义所有允许的 design tokens
4. 实现 `frontend_template/src/theme/product_profiles.ts`：2 个 profile 的 machine-readable 定义
5. 写 `frontend_template/src/components/ui/` 的 Button/Card/Input/Badge/Table（强约束风格，使用 tokens）
6. 写 `models.py`：StyleAction, StyleObservation, StyleState, ScoreBreakdown
7. 写 `client.py`：StyleEnv 继承 EnvClient
8. 写 `openenv.yaml`：环境元数据
9. 写 `server/Dockerfile`：预装 node_modules，运行 FastAPI server

### Phase 2: 评分器（Iter 0 必须）

10. 写 `server/scorers/lint_scorer.py`：调用 pnpm build/lint/format:check
11. 写 `server/scorers/token_scorer.py`：扫描 forbidden patterns（hex/gradient/neon colors）
12. 写 `server/scorers/component_reuse_scorer.py`：检查是否使用 UI 组件库，禁止原生 `<button>`
13. 写 `server/scorers/diff_discipline_scorer.py`：限制改动范围

### Phase 3: 环境核心逻辑（Iter 0 必须）

14. 写 `server/style_environment.py`：实现 reset(), step(), 整合所有 scorer
15. 写 `server/app.py`：FastAPI 入口（使用 openenv 标准模板）

### Phase 4: 评测与示例（Iter 0 必须）

16. 写 `prompts/prompts.jsonl`：10 条初始评测任务
17. 写 `examples/style_simple.py`：完整 episode 示例
18. 写 `README.md`：环境说明文档

### Phase 5: 扩展（Iter 1）

19. 扩展 prompts 到 20 条，覆盖 3 个 profile
20. 添加 FinTech profile
21. 实现 AST-based 扫描（替换 Regex）
22. 添加多轮迭代任务（测试风格漂移）

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| pnpm build 太慢（>30s/episode） | RL 训练效率低 | Docker 预装依赖 + 增量构建 |
| Regex 扫描漏检动态 class | 评分不准 | 记录为已知限制，Iter 1 升级 AST |
| Profile 规则定义太严格 | 模型无法通过任何任务 | 从宽松规则开始，逐步收紧 |
| 不同 OS 的 pnpm/node 版本差异 | 评分不一致 | 强制 Docker 运行，固定版本 |

## 10. 责任分工（Who Does What）

本项目涉及两类完全不同的任务，需要不同工具的优势：

### 10.1 Claude Opus 负责：环境基础设施

**适用场景**：工程搭建、系统集成、代码脚手架

| 任务类型 | 具体内容 | 原因 |
|----------|----------|------|
| OpenEnv 集成 | 目录结构、client.py、models.py、server/*.py | 工程模板化，遵循现有 pattern |
| Docker 配置 | Dockerfile、构建优化、pnpm 预装 | 系统配置，无审美成分 |
| Scorer 实现 | lint_scorer.py、token_scorer.py 等 | 纯逻辑代码，规则检测 |
| FastAPI 入口 | app.py、WebSocket 处理 | 标准模板，参考 refactor_env |
| 工具链配置 | vite.config.ts、tailwind.config.js、eslint、prettier | 配置文件，无创意成分 |

**Claude Opus 的优势**：
- 能把执行计划里的目录结构、Docker、FastAPI、scorer、pnpm 命令一次性搭起来
- 严格遵循 OpenEnv 现有 pattern（如 refactor_env）
- 减少手工拼装时间
- 本计划本质是**工程实现清单**，而不是审美生成任务

### 10.2 Gemini 负责：参考页面代码（训练数据）

**适用场景**：生成"好看的页面样例"作为 SFT 训练数据 / reference style

| 任务类型 | 具体内容 | 原因 |
|----------|----------|------|
| UI 组件实现 | Button.tsx、Card.tsx、Input.tsx 等 | 需要审美判断，遵守 design token |
| 示例页面生成 | Dashboard.tsx、Settings.tsx、Pricing.tsx | 需要"有品味"的布局和配色 |
| SFT 训练数据 | 200 条符合 profile 的页面代码 | 作为"老师"产出高质量样本 |
| Profile 视觉定义 | 具体的配色方案、spacing 选择 | 审美决策，非工程决策 |

**Gemini 的优势**：
- 观察到 Gemini 更容易保持"有品味 + 一致性"
- 不会默认输出炫酷蓝紫渐变
- 适合作为"老师模型"产出训练数据
- 生成的页面代码可以直接用 scorer 验证

### 10.3 分工流程图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          项目分工流程                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────┐      ┌─────────────────────────────────┐  │
│  │   Claude Opus       │      │         Gemini                  │  │
│  │   (工程实现)         │      │       (审美生成)                 │  │
│  ├─────────────────────┤      ├─────────────────────────────────┤  │
│  │ • envs/style_env/   │      │ • frontend_template/src/        │  │
│  │   ├── client.py     │      │   ├── components/ui/*.tsx       │  │
│  │   ├── models.py     │      │   └── pages/*.tsx (示例)        │  │
│  │   ├── server/       │      │                                 │  │
│  │   │   ├── app.py    │      │ • SFT 训练数据                   │  │
│  │   │   ├── Dockerfile│      │   └── 200 条符合 profile 的页面  │  │
│  │   │   └── scorers/  │      │                                 │  │
│  │   └── openenv.yaml  │      │ • Profile 视觉定义               │  │
│  │                     │      │   └── 具体配色/spacing 选择      │  │
│  │ • 工具链配置         │      │                                 │  │
│  │   ├── vite.config   │      │                                 │  │
│  │   ├── tailwind.config│     │                                 │  │
│  │   └── eslint/prettier│     │                                 │  │
│  └─────────────────────┘      └─────────────────────────────────┘  │
│            │                              │                        │
│            ▼                              ▼                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    整合 & 验证                                │  │
│  │  • Gemini 生成的页面代码 → Claude Opus 搭建的 scorer 验证      │  │
│  │  • 确保"好看"的代码也能通过"规则"检查                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.4 具体执行顺序

**Day 1 (Iter 0)**：
1. **Claude Opus**：搭建 envs/style_env/ 完整目录结构、server、scorer、Dockerfile
2. **Claude Opus**：配置 vite/tailwind/eslint/prettier 工具链
3. **Gemini**：生成 tokens.ts、product_profiles.ts 的具体值（配色/spacing）
4. **Gemini**：生成 5 个 UI 组件（Button/Card/Input/Badge/Table）
5. **Claude Opus**：整合，确保 pnpm build/lint 通过
6. **验证**：用 scorer 验证 Gemini 生成的组件代码

**Day 2 (Iter 1)**：
1. **Gemini**：生成 200 条 SFT 训练数据（页面代码）
2. **Claude Opus**：批量运行 scorer，过滤不合格样本
3. **Gemini**：对低分样本进行修正
4. **训练**：用过滤后的数据微调 Qwen3-Coder

### 10.5 交接标准

| 从 Gemini 到 Claude Opus | 验收标准 |
|--------------------------|----------|
| UI 组件代码 | pnpm build 通过 + scorer 得分 > 90 |
| 页面代码 | pnpm lint 通过 + 无 R1-R5 违规 |
| Profile 定义 | machine-readable TypeScript 格式 |

| 从 Claude Opus 到 Gemini | 验收标准 |
|--------------------------|----------|
| tokens.ts 结构 | 接口定义清晰，Gemini 可直接填值 |
| scorer 规则 | 文档化每条规则，Gemini 生成时可参考 |

## 11. 成功指标

- **Iter 0 完成**：能在本地 Docker 中完成一个完整 episode，输出 score breakdown
- **模型差异可见**：不同模型在相同 prompt 上的分数差异 > 20 分
- **Failure modes 可解释**：能从 rule_violations 直接定位"为什么丑"
- **RL 可训练**：reward 分布合理（不是全 -1 或全 +1）
- **分工验证**：Gemini 生成的 UI 组件能通过 Claude Opus 搭建的 scorer 验证（得分 > 90）
