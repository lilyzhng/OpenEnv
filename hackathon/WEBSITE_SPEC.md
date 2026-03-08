---
date: 2026-03-07
time: 20:44
---
# Website Spec — APEX Environment Dashboard

## Overview

单页 HTML 网站，展示 APEX 环境的 benchmark 结果。**不用 Gradio**，做一个独立的 HTML + JS 页面。部署到 HF Spaces (static) 或直接在 pitch 时本地打开。

## 设计风格

沿用现有 app.py 的 terminal aesthetic：
- 背景：`#F5F0E8`（warm beige）
- 深色面板：`#1E1E1E`（charcoal）
- 字体：Space Mono（代码/标签），Space Grotesk（正文）
- 颜色：green `#39FF14`（成功），amber `#FFB800`（gold coin/action），cyan `#00E5FF`（重点），red `#FF3B3B`（失败）
- macOS window chrome（红黄绿三个点）装饰面板顶部

## 页面结构（4 个 section，上下滚动）

---

### Section 1: Hero

```
┌──────────────────────────────────────────────┐
│ ● ● ●                                        │
│                                               │
│ APEX ENVIRONMENT                              │  ← green, Space Mono, uppercase
│                                               │
│ Building-Block Environments for               │  ← 大标题，Space Grotesk
│ Professional Agent Evaluation                 │
│                                               │
│ OpenEnv Hackathon 2026                        │  ← 小字
└──────────────────────────────────────────────┘
```

简洁，不需要太多文字。

---

### Section 2: Leaderboard（双栏：IB + Hand-Draw）

两个并排的排名表。每个表是一个 charcoal 面板。

**左表：IB Financial Analysis**

```
┌──────────────────────────────────────────┐
│ ● ● ●  IB Financial Analysis            │
│                                          │
│  #  Model          Criteria  Reward      │
│  1  GPT-5.4        11/11     1.000  ███  │  ← green bar
│  2  Sonnet 4       10/11     0.455  ██   │
│  3  GPT-4o-mini     6/11     0.273  █    │
│  3  Qwen3-30B       6/11     0.273  █    │
│  5  DeepSeek-V3     6/11     0.273  █    │
└──────────────────────────────────────────┘
```

**右表：Hand-Draw Hourglass**

```
┌──────────────────────────────────────────┐
│ ● ● ●  Hand-Draw: Hourglass             │
│                                          │
│  #  Model          Criteria  Correct?    │
│  1  GPT-5.4        5/6       ✓ HOURGLASS │  ← green
│  2  GPT-4o-mini    5/6       ✗ DIAMOND   │  ← red
│  2  Qwen3-30B      5/6       ✗ UNCLEAR   │  ← amber
│  4  DeepSeek-V3    4/6       ✗ DIAMOND   │  ← red
│  5  Sonnet 4       5/6       ✓ HOURGLASS │  ← green
└──────────────────────────────────────────┘
```

注意：Hand-Draw 的排序不要按 reward 排，按 "Correct Shape" 分组 — 正确的排前面，错误的排后面。在每组内按 reward 排。这样视觉上一眼能看出谁对谁错。

右表的 "Correct?" 列用颜色区分：✓ 绿色，✗ 红色。

---

### Section 3: Hand-Draw Gallery（SVG 渲染对比）

**这是整个页面最有视觉冲击力的部分。**

5 个 HTML 渲染并排显示（用 iframe 或直接 inline SVG）。每个下面标注模型名 + 正确/错误。

```
┌──────────────────────────────────────────────────────────────────────┐
│ ● ● ●  What Each Model Drew                                         │
│                                                                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │         │  │         │  │         │  │         │  │         │  │
│  │  GPT-5.4│  │ Sonnet  │  │ 4o-mini │  │ Qwen3  │  │DeepSeek │  │
│  │         │  │         │  │         │  │         │  │         │  │
│  │(render) │  │(render) │  │(render) │  │(render) │  │(render) │  │
│  │         │  │         │  │         │  │         │  │         │  │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │
│   ✓ Hourglass  ✓ Hourglass  ✗ Diamond   ✗ Unclear    ✗ Diamond    │
│   "Adapted"    "Best look"  "Ignored"    "From scratch""Copied"    │
│                                                                      │
│  Task: "Compose an hourglass illustration"                           │
│  Example given: diamond.html (two triangles base-to-base)            │
│  Challenge: adapt to point-to-point orientation                      │
└──────────────────────────────────────────────────────────────────────┘
```

**实现方式：** 每个模型的 HTML 文件已经在 `data/handdraw_v1/html/` 里。用 `<iframe>` 嵌入，设置固定宽高（200x200 或 250x250），sandbox 属性允许 scripts。

排列顺序：先放正确的（GPT-5.4, Sonnet），再放错误的（4o-mini, Qwen3, DeepSeek）。

每个渲染下面加一行简短描述（Method）：
- GPT-5.4: "Knowledge-based: trapezoids + frame + sand"
- Sonnet 4: "Analogical: adapted diamond → point-to-point"
- GPT-4o-mini: "Ignored example, drew raw lines"
- Qwen3-30B: "Built from scratch with arcs, no adaptation"
- DeepSeek-V3: "Copied diamond base-to-base pattern"

---

### Section 4: Trajectory Comparison（Side-by-Side）

选两个有对比性的模型展示 trajectory。**默认展示 Sonnet vs GPT-4o-mini 在 hourglass task 上的对比。**

每一步是一行，用图标区分行为类型：
- 🟡 Gold coin = 有意义的 bash action
- ⚫ Grey dot = talk / 废话
- 🟢 Green = done signal
- 📄 特殊图标 = 读了 example file

```
┌────────────────────────────────┬────────────────────────────────┐
│ ● ● ●  Sonnet 4               │ ● ● ●  GPT-4o-mini            │
│ Result: ✓ HOURGLASS            │ Result: ✗ DIAMOND              │
│                                │                                │
│ 🟡 ls                          │ 🟡 ls                          │
│ 🟡 cat specs.md                │ 🟡 cat specs.md                │
│ 🟡 cat template.html           │ 🟡 cat template.html           │
│ 🟡 ls elements                 │ 🟡 cat > hourglass.html <<EOF  │ ← 直接写了！
│ 🟡 cat elements/triangle.js    │ 🟡 (rewrites file)             │
│ 📄 cat examples/diamond.html   │ 🟡 (rewrites file)             │
│ 🟡 cat elements/circle.js      │ ...                            │
│ 🟡 cat elements/line.js        │ 🟢 done                        │
│ 🟡 cat > hourglass.html <<EOF  │                                │
│   (adapted diamond pattern!)   │                                │
│ 🟡 (rewrites... 5 times)       │                                │
│ 🟢 done                        │                                │
│                                │                                │
│ Explored: specs, template,     │ Explored: specs, template      │
│ ALL elements, diamond example  │ Skipped: elements, example     │
│ Key: adapted diamond →         │ Key: ignored example,          │
│ point-to-point orientation     │ drew from scratch (wrong)      │
└────────────────────────────────┴────────────────────────────────┘
```

**数据来源：** 解析 `data/handdraw_v1/run_sonnet_hourglass.log` 和 `run_gpt4omini_hourglass.log`。每个 log 的格式是：

```
TURN N/25
AGENT says: <可能有 talk text>
<bash command>
COMMAND: <actual executed command>
ENVIRONMENT → AGENT:
<output>
[Progress: X→Y/6 criteria met]
```

解析每个 turn 的 COMMAND 行，作为 trajectory 的一步。如果 AGENT says 里有 talk text（以 "I'll", "Let me", "Now" 等开头），标记为有 talk 前缀。

**可选：** 如果时间够，做成下拉选择（选 task + 选两个 model），跟之前 Gradio app 一样。如果时间不够，就硬编码 Sonnet vs GPT-4o-mini。

---

## 数据源

所有数据已经在 `data/` 目录里：

| 数据 | 路径 | 格式 |
|------|------|------|
| IB v5 logs | `data/ib_v5/run_*.log` | 文本 log，需要解析 |
| HD v1 logs | `data/handdraw_v1/run_*.log` | 文本 log，需要解析 |
| HD renders | `data/handdraw_v1/html/*.html` | 直接用 iframe 嵌入 |

**建议：** 写一个 `scripts/parse_logs.py` 把 log 解析成 JSON，然后 website 直接读 JSON。

Log 解析需要提取：
- model name
- task type (ib / handdraw)
- 每个 turn: command, output (truncated), progress change
- final: criteria_met, criteria_total, reward, total_steps

IB v5 结果汇总（从 Bruce 的报告）：

```json
{
  "ib_v5": [
    {"model": "GPT-5.4", "criteria": "11/11", "reward": 1.000, "steps": 5},
    {"model": "Claude Sonnet 4", "criteria": "10/11", "reward": 0.455, "steps": 31},
    {"model": "GPT-4o-mini", "criteria": "6/11", "reward": 0.273, "steps": 31},
    {"model": "Qwen3-30B", "criteria": "6/11", "reward": 0.273, "steps": 31},
    {"model": "DeepSeek-V3", "criteria": "6/11", "reward": 0.273, "steps": 20}
  ],
  "handdraw_v1": [
    {"model": "GPT-5.4", "criteria": "5/6", "reward": 0.833, "correct_shape": "HOURGLASS", "method": "Knowledge-based: trapezoids + frame + sand"},
    {"model": "Claude Sonnet 4", "criteria": "5/6", "reward": 0.417, "correct_shape": "HOURGLASS", "method": "Analogical: adapted diamond point-to-point"},
    {"model": "GPT-4o-mini", "criteria": "5/6", "reward": 0.667, "correct_shape": "DIAMOND", "method": "Ignored example, drew raw lines"},
    {"model": "Qwen3-30B", "criteria": "5/6", "reward": 0.667, "correct_shape": "UNCLEAR", "method": "Built from scratch with arcs"},
    {"model": "DeepSeek-V3", "criteria": "4/6", "reward": 0.500, "correct_shape": "DIAMOND", "method": "Copied diamond base-to-base"}
  ]
}
```

如果 log 解析太麻烦，可以直接把上面这个 JSON 硬编码到 HTML 里。Hackathon 不需要动态加载。

---

## 技术要求

1. **单文件 HTML** — 所有 CSS + JS inline，不依赖 build tool
2. **Hand-draw renders 用 iframe** — `<iframe src="handdraw_v1/html/sonnet_hourglass.html" sandbox="allow-scripts">`
3. **Responsive** — 在 1080p 投影和笔记本屏幕上都能看
4. **不需要后端** — 纯静态页面
5. **文件位置** — 保存为 `hackathon/dashboard.html`，HTML renders 相对路径引用 `data/handdraw_v1/html/`

---

## 优先级

1. **P0: Section 3 (Gallery)** — 最有视觉冲击力，pitch 必须有
2. **P0: Section 2 (Leaderboard)** — 数据展示核心
3. **P1: Section 1 (Hero)** — 简单，几分钟就好
4. **P2: Section 4 (Trajectory)** — 如果时间不够可以砍

Gallery 是关键 — 评审看到 5 个模型画的 "hourglass"，一眼就能理解 analogical reasoning 的差异。这比任何数字都直观。
