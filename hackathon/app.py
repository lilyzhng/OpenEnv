"""
APEX Environment — Spend Less, Do More
HF Spaces app for OpenEnv Hackathon
"""

import json
from pathlib import Path

import gradio as gr
import pandas as pd

# ---------------------------------------------------------------------------
# Load benchmark data
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

MODELS = [
    ("eval_v4_gpt4omini.json", "GPT-4o-mini", "Closed-source", "$"),
    ("eval_v4_30b.json", "Qwen3-Coder-30B", "Open-source", "Free"),
    ("eval_v4_deepseek.json", "DeepSeek-V3", "Open-source", "Free"),
    ("eval_v4_kimik2.json", "Kimi-K2", "Open-source", "Free"),
    ("eval_v4_glm45.json", "GLM-4.5", "Open-source", "Free"),
    ("eval_v4_sonnet.json", "Claude Sonnet 4", "Closed-source", "$$$"),
    ("eval_v4_codernext.json", "Coder-Next (80B)", "Open-source", "Free"),
    ("eval_v4_gpt54.json", "GPT-5.4", "Closed-source", "$$$$"),
    ("eval_v4_opus.json", "Claude Opus 4.6", "Closed-source", "$$$$$"),
]

TALK_PREFIXES = (
    "I ", "I'", "Let me", "Now ", "First", "Next", "The ", "This ",
    "Here", "Sure", "OK", "Okay", "Great", "Note", "Since ", "To ",
    "We ", "My ", "After", "Before", "Based", "Looking", "There ",
)


def is_talk(action: str) -> bool:
    s = action.strip()
    if not s:
        return True
    if any(s.startswith(p) for p in TALK_PREFIXES):
        return True
    if s.endswith(".") and not any(c in s for c in "|>&;$`"):
        return True
    return False


def load_all_results():
    rows = []

    for fname, label, mtype, cost in MODELS:
        fpath = DATA_DIR / fname
        if not fpath.exists():
            continue
        with open(fpath) as f:
            data = json.load(f)

        results = data["results"]
        rewards = [r["reward"] for r in results]
        avg_reward = sum(rewards) / len(rewards) if rewards else 0

        total_actions = 0
        talk_actions = 0
        for r in results:
            for a in r["actions"]:
                if a.strip().lower() != "done":
                    total_actions += 1
                    if is_talk(a):
                        talk_actions += 1

        talk_pct = talk_actions / total_actions * 100 if total_actions else 0
        avg_turns = sum(r["num_turns"] for r in results) / len(results)

        # Efficiency reward
        talk_penalty = -0.2 * (talk_pct / 100)
        eff_bonus = 0.1 * max(0, 1 - avg_turns / 10) if avg_reward > 0 else 0
        final = max(0, avg_reward + talk_penalty + eff_bonus)

        rows.append({
            "Rank": 0,
            "Model": label,
            "Type": mtype,
            "Cost": cost,
            "Task Score": round(avg_reward, 3),
            "Talk %": round(talk_pct, 1),
            "Final Score": round(final, 3),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("Final Score", ascending=False).reset_index(drop=True)
    df["Rank"] = range(1, len(df) + 1)

    return df


LEADERBOARD_DF = load_all_results()


# ---------------------------------------------------------------------------
# Load trajectory data from eval results
# ---------------------------------------------------------------------------

MODEL_LABELS = {m[0]: m[1] for m in MODELS}  # fname -> label

def load_trajectory_data():
    """Build task_id -> {model_label -> {actions, reward, domain}} from eval JSONs."""
    traj_data = {}  # task_id -> {model_label -> info}
    task_meta = {}  # task_id -> {domain, task_id_short}

    for fname, label, _, cost in MODELS:
        fpath = DATA_DIR / fname
        if not fpath.exists():
            continue
        with open(fpath) as f:
            data = json.load(f)

        for r in data["results"]:
            tid = r["task_id"]
            if tid not in traj_data:
                traj_data[tid] = {}
                task_meta[tid] = {
                    "domain": r["domain"],
                    "short": tid[:12] + "...",
                }
            traj_data[tid][f"{label} ({cost})"] = {
                "actions": r["actions"],
                "reward": r["reward"],
            }

    return traj_data, task_meta

TRAJ_DATA, TASK_META = load_trajectory_data()
TASK_IDS = sorted(TRAJ_DATA.keys(), key=lambda t: TASK_META[t]["domain"])
TASK_CHOICES = [f"{TASK_META[t]['domain']} — {TASK_META[t]['short']}" for t in TASK_IDS]
AGENT_CHOICES = sorted({agent for agents in TRAJ_DATA.values() for agent in agents})


# ---------------------------------------------------------------------------
# CSS — clean terminal aesthetic
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');

:root {
    --bg: #F5F0E8;
    --charcoal: #1E1E1E;
    --text: #1E1E1E;
    --text-dim: #6B6560;
    --green: #39FF14;
    --cyan: #00E5FF;
    --amber: #FFB800;
    --red: #FF3B3B;
    --font-mono: 'Space Mono', 'SF Mono', monospace;
    --font-sans: 'Space Grotesk', system-ui, sans-serif;
}

.gradio-container {
    background: var(--bg) !important;
    font-family: var(--font-sans) !important;
    max-width: 1100px !important;
}

/* Hero */
.hero-section {
    background: var(--charcoal);
    padding: 28px 36px;
    margin-bottom: 20px;
}
.hero-section .window-dots {
    display: flex;
    gap: 6px;
    margin-bottom: 16px;
}
.hero-section .dot { width: 12px; height: 12px; border-radius: 50%; }
.hero-section .dot-red { background: #FF5F57; }
.hero-section .dot-yellow { background: #FFBD2E; }
.hero-section .dot-green { background: #28C840; }
.hero-section h1 {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 4px !important;
    text-transform: uppercase !important;
    color: var(--green) !important;
    margin: 0 0 6px 0 !important;
}
.hero-section .tagline {
    font-family: var(--font-sans);
    font-size: 26px;
    font-weight: 600;
    color: #E0DCD4;
    margin-bottom: 8px;
}
.hero-section .subtitle {
    font-family: var(--font-mono);
    font-size: 12px;
    color: #888;
}
.hero-section .highlight { color: var(--cyan); }

/* Mascot animation */
.mascot {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 14px;
    letter-spacing: 0;
    text-transform: none;
    color: var(--amber);
    margin-left: 12px;
    min-width: 80px;
}

/* Cards */
.card {
    background: var(--charcoal);
    padding: 18px 22px;
    margin-bottom: 14px;
}
.card .label {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.card .label.green { color: var(--green); }
.card .label.amber { color: var(--amber); }
.card .label.red { color: var(--red); }
.card .label.cyan { color: var(--cyan); }
.card .body {
    font-family: var(--font-sans);
    font-size: 14px;
    color: #D0CCC4;
    line-height: 1.5;
}
.card .detail {
    font-family: var(--font-mono);
    font-size: 11px;
    color: #666;
    margin-top: 6px;
}

/* Section headers */
.section-header {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    color: var(--text) !important;
    border-bottom: 3px solid var(--charcoal);
    padding-bottom: 8px;
    margin-bottom: 14px;
}

/* Table */
.gradio-dataframe {
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
}

/* Tabs */
.tab-nav button {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
}
.tab-nav button.selected {
    border-bottom: 3px solid var(--charcoal) !important;
}

/* Align button with inputs in row */
.live-row {
    align-items: flex-end !important;
}
.live-row .gr-button {
    margin-bottom: 6px !important;
}

/* Footer */
.footer {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-dim);
    text-align: center;
    padding: 20px;
    letter-spacing: 1px;
}
"""

# ---------------------------------------------------------------------------
# Mascot JS — animates after Gradio renders
# ---------------------------------------------------------------------------

MASCOT_JS = """
function() {
    var frames = ['>(^_^)<', '>(^_>)<', '>(>_^)<', '>(<_<)<', '>(^_^)<'];
    var idx = 0;
    function tryStart() {
        var el = document.querySelector('.mascot');
        if (el) {
            el.textContent = frames[0];
            setInterval(function() { idx = (idx + 1) % frames.length; el.textContent = frames[idx]; }, 400);
        } else {
            setTimeout(tryStart, 300);
        }
    }
    setTimeout(tryStart, 500);
}
"""


# ---------------------------------------------------------------------------
# App — 3 tabs: Leaderboard, Try It, About
# ---------------------------------------------------------------------------

with gr.Blocks(
    css=CUSTOM_CSS,
    js=MASCOT_JS,
    theme=gr.themes.Base(
        primary_hue="green",
        neutral_hue="stone",
        font=("Space Grotesk", "system-ui", "sans-serif"),
        font_mono=("Space Mono", "SF Mono", "monospace"),
    ),
    title="APEX Environment — Spend Less, Do More",
) as demo:

    # Hero
    gr.HTML("""
    <div class="hero-section">
        <div class="window-dots">
            <div class="dot dot-red"></div>
            <div class="dot dot-yellow"></div>
            <div class="dot dot-green"></div>
        </div>
        <h1>APEX Environment <span class="mascot"></span></h1>
        <div class="tagline">Spend Less, Do More.</div>
        <div class="subtitle">
            9 models. 18 professional tasks. <span class="highlight">Can your agent ACT, or does it just TALK?</span>
        </div>
    </div>
    """)

    with gr.Tabs():

        # ── Tab 1: Leaderboard ──────────────────────────────────
        with gr.Tab("Leaderboard"):
            gr.HTML('<div class="section-header">Model Rankings</div>')

            gr.Dataframe(
                value=LEADERBOARD_DF[["Rank", "Model", "Type", "Cost", "Task Score", "Talk %", "Final Score"]],
                interactive=False,
                wrap=True,
            )

            # One-liner key finding
            if not LEADERBOARD_DF.empty:
                best = LEADERBOARD_DF.iloc[0]
                worst = LEADERBOARD_DF.iloc[-1]
                gr.HTML(f"""
                <div class="card">
                    <div class="label amber">Key Finding</div>
                    <div class="body">
                        {best['Model']} ({best['Cost']}) scores <b>{best['Final Score']}</b> —
                        {worst['Model']} ({worst['Cost']}) scores <b>{worst['Final Score']:.3f}</b>.
                        Cheaper models act more, talk less.
                    </div>
                    <div class="detail">
                        Final = Task Score - 0.2 x Talk Ratio + Efficiency Bonus (if task solved in fewer turns)
                    </div>
                </div>
                """)

        # ── Tab 2: Trajectory ───────────────────────────────────
        with gr.Tab("Trajectory"):
            gr.HTML('<div class="section-header">Same Task, Different Agents</div>')

            with gr.Row():
                traj_task = gr.Dropdown(choices=TASK_CHOICES, value=TASK_CHOICES[0], label="Task", scale=2)
            with gr.Row():
                left_agent = gr.Dropdown(choices=AGENT_CHOICES, value=AGENT_CHOICES[0], label="Agent A", scale=1)
                right_agent = gr.Dropdown(choices=AGENT_CHOICES, value=AGENT_CHOICES[-1], label="Agent B", scale=1)

            traj_output = gr.HTML()

            def render_agent_column(actions, agent_name, reward):
                """Render one agent's trajectory from raw action list."""
                reward_color = "var(--green)" if reward > 0.3 else "var(--amber)" if reward > 0 else "var(--red)"
                html = f'<div class="label amber" style="margin-bottom:10px;">{agent_name} &nbsp; <span style="color:{reward_color};">reward: {reward:.2f}</span></div>'

                for i, action in enumerate(actions):
                    idx = i + 1
                    a = action.strip()
                    if a.lower() == "done":
                        border = "var(--green)"
                        coin = "&#10004;"
                        label = "DONE"
                    elif is_talk(a):
                        border = "#555"
                        coin = "&#8226;"
                        label = f"TALK {idx}"
                    else:
                        border = "var(--amber)"
                        coin = "&#9733;"
                        label = f"ACT {idx}"

                    action_esc = a[:150].replace("<", "&lt;").replace(">", "&gt;")
                    html += f'''
                    <div style="border-left:3px solid {border}; padding:8px 12px; margin-bottom:6px; background:rgba(255,255,255,0.02);">
                        <div style="font-family:var(--font-mono); font-size:9px; letter-spacing:2px; text-transform:uppercase; margin-bottom:3px;">
                            <span style="font-size:14px; margin-right:3px;">{coin}</span>{label}
                        </div>
                        <div style="font-family:var(--font-mono); font-size:10px; color:var(--amber); background:#111; padding:4px 8px; border:1px solid #333; white-space:pre-wrap;">$ {action_esc}</div>
                    </div>'''

                act_count = sum(1 for a in actions if a.strip().lower() != "done" and not is_talk(a))
                talk_count = sum(1 for a in actions if a.strip().lower() != "done" and is_talk(a))

                html += f'''
                <div style="padding:8px 0; border-top:1px solid #333; margin-top:6px; font-family:var(--font-mono); font-size:10px; color:#888;">
                    ACTS: <b style="color:var(--amber);">{act_count}</b> &nbsp;
                    TALKS: <b style="color:var(--red);">{talk_count}</b> &nbsp;
                    TURNS: <b style="color:var(--cyan);">{len(actions)}</b>
                </div>'''
                return html

            def render_comparison(task_choice, left_name, right_name):
                idx = TASK_CHOICES.index(task_choice) if task_choice in TASK_CHOICES else 0
                tid = TASK_IDS[idx]
                agents = TRAJ_DATA.get(tid, {})

                left_data = agents.get(left_name, {"actions": [], "reward": 0})
                right_data = agents.get(right_name, {"actions": [], "reward": 0})

                left_html = render_agent_column(left_data["actions"], left_name, left_data["reward"])
                right_html = render_agent_column(right_data["actions"], right_name, right_data["reward"])

                return f'''
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
                    <div class="card">{left_html}</div>
                    <div class="card">{right_html}</div>
                </div>'''

            traj_task.change(fn=render_comparison, inputs=[traj_task, left_agent, right_agent], outputs=traj_output)
            left_agent.change(fn=render_comparison, inputs=[traj_task, left_agent, right_agent], outputs=traj_output)
            right_agent.change(fn=render_comparison, inputs=[traj_task, left_agent, right_agent], outputs=traj_output)
            demo.load(fn=render_comparison, inputs=[traj_task, left_agent, right_agent], outputs=traj_output)

        # ── Tab 3: Try It ───────────────────────────────────────
        with gr.Tab("Try It"):
            gr.HTML('<div class="section-header">Run a Live Agent</div>')

            with gr.Row(elem_classes="live-row"):
                tryit_task_idx = gr.Dropdown(
                    choices=list(range(18)),
                    value=0,
                    label="Task (0-17)",
                    scale=2,
                )
                tryit_model = gr.Dropdown(
                    choices=[
                        ("GPT-4o-mini ($)", "openai/gpt-4o-mini"),
                        ("Qwen3-Coder-30B (free)", "qwen/qwen3-coder-30b-a3b-instruct"),
                        ("DeepSeek-V3 (free)", "deepseek/deepseek-chat-v3-0324"),
                    ],
                    value="openai/gpt-4o-mini",
                    label="Model",
                    scale=3,
                )
                tryit_turns = gr.Slider(minimum=3, maximum=10, step=1, value=5, label="Max Turns", scale=2)
                tryit_btn = gr.Button("Run Agent", variant="primary", scale=1, min_width=100)
            tryit_output = gr.HTML(
                value='<div class="card"><div class="body" style="color:#888;">Click "Run Agent" to start.</div></div>'
            )

            def run_live_episode(task_choice, model_id, max_turns):
                """Run a real agent episode via OpenRouter API."""
                import os
                import sys
                import tempfile
                import shutil
                from pathlib import Path as P

                _root = P(__file__).resolve().parent
                sys.path.insert(0, str(_root / "apex_env" / "server"))
                from task_loader import TaskLoader
                from reward import compute_reward
                from bash_executor import BashExecutor

                # API key
                api_key = os.environ.get("OPENROUTER_APIKEY", "")
                if not api_key:
                    for env_path in [
                        _root.parent.parent / "2026" / ".env.local",
                        _root.parent.parent.parent / "2026" / ".env.local",
                        _root / ".env.local",
                    ]:
                        if env_path.exists():
                            for line in env_path.read_text().splitlines():
                                if line.startswith("OPENROUTER_APIKEY="):
                                    api_key = line.split("=", 1)[1].strip()
                                    break
                        if api_key:
                            break
                if not api_key:
                    return '<div class="card"><div class="label red">ERROR</div><div class="body">OPENROUTER_APIKEY not set.</div></div>'

                # Load task
                loader = TaskLoader(dataset_name="mercor/apex-agents")
                loader._load()

                from collections import defaultdict
                domain_indices = defaultdict(list)
                for i in range(len(loader)):
                    domain = loader._tasks[i].get("domain", "unknown")
                    domain_indices[domain].append(i)
                selected = []
                for domain, indices in sorted(domain_indices.items()):
                    selected.extend(indices[:6])
                selected = selected[:18]

                if task_choice >= len(selected):
                    task_choice = 0
                task_idx = selected[task_choice]
                task = loader._tasks[task_idx]

                domain = task.get("domain", "unknown")
                task_id = task.get("task_id", "unknown")
                prompt = task.get("prompt", "")

                workspace = P(tempfile.mkdtemp(prefix="apex_tryit_"))
                executor = BashExecutor()

                # Download input files
                try:
                    from huggingface_hub import hf_hub_download, list_repo_tree
                    tree = list_repo_tree("mercor/apex-agents", path_in_repo=f"task_files/{task_id}/filesystem", repo_type="dataset")
                    for item in tree:
                        rfilename = item.path if hasattr(item, "path") else item.rfilename
                        local = hf_hub_download("mercor/apex-agents", rfilename, repo_type="dataset")
                        fname = P(rfilename).name
                        shutil.copy2(local, workspace / fname)
                except Exception:
                    pass

                input_files = [f.name for f in workspace.iterdir() if f.is_file()]

                import requests as req

                SYSTEM_PROMPT = (
                    "You are a professional analyst. You solve tasks by executing bash commands one at a time.\n"
                    "You have access to: python3, grep, awk, sed, jq, and standard unix tools.\n"
                    "Each response should contain EXACTLY ONE bash command to execute.\n"
                    "Do NOT wrap commands in markdown code blocks. Just output the raw command.\n"
                    "After seeing the result, decide your next command.\n"
                    "When you have completed the task and written your output files, respond with exactly: done"
                )

                files_note = ""
                if input_files:
                    files_note = "\nAvailable input files:\n" + "\n".join(f"  - {f}" for f in input_files) + "\n"

                task_prompt = (
                    f"# Task: {task_id}\n# Domain: {domain}\n\n{prompt}\n\n"
                    f"Your workspace is: {workspace}\n{files_note}"
                    f"Create your output files in the workspace directory.\nWhen finished, send: done"
                )

                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": task_prompt},
                ]

                html = f'''
                <div class="card">
                    <div class="label cyan">TASK: {domain} -- {task_id[:12]}...</div>
                    <div class="body" style="font-size:13px; margin-bottom:12px;">{prompt[:200]}{"..." if len(prompt) > 200 else ""}</div>
                '''

                if input_files:
                    html += f'<div class="detail">Input files: {", ".join(input_files[:5])}</div><br>'

                actions = []
                for turn in range(int(max_turns)):
                    import time as _time
                    response_text = None
                    for attempt in range(3):
                        try:
                            resp = req.post(
                                "https://openrouter.ai/api/v1/chat/completions",
                                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                                json={"model": model_id, "messages": messages, "temperature": 0.3, "max_tokens": 1024},
                                timeout=60,
                            )
                            if resp.status_code == 429:
                                _time.sleep(3 * (attempt + 1))
                                continue
                            resp.raise_for_status()
                            response_text = resp.json()["choices"][0]["message"]["content"].strip()
                            break
                        except Exception as e:
                            if attempt == 2:
                                html += f'<div style="color:var(--red); font-family:monospace; font-size:11px;">API Error: {str(e)[:100]}</div>'
                            else:
                                _time.sleep(3 * (attempt + 1))
                    if response_text is None:
                        break

                    # Extract command
                    command = response_text.strip()
                    if command.lower() in ("done", '"done"'):
                        command = "done"

                    # Code block extraction
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

                    actions.append(command)
                    is_done = command.strip().lower() == "done"
                    is_talk_action = is_talk(command)

                    if is_done:
                        border = "var(--green)"
                        label = f"DONE (turn {turn+1})"
                        lclass = "green"
                        coin = "&#10004;"
                    elif is_talk_action:
                        border = "#555"
                        label = f"TALK {turn+1}"
                        lclass = "red"
                        coin = "&#8226;"
                    else:
                        border = "var(--amber)"
                        label = f"ACTION {turn+1}"
                        lclass = "amber"
                        coin = "&#9733;"

                    cmd_escaped = command[:200].replace("<", "&lt;").replace(">", "&gt;")
                    html += f'''
                    <div style="border-left:3px solid {border}; padding:10px 14px; margin-bottom:8px; background:rgba(255,255,255,0.02);">
                        <div style="font-family:var(--font-mono); font-size:10px; letter-spacing:2px; text-transform:uppercase; margin-bottom:4px;">
                            <span style="font-size:16px; margin-right:4px;">{coin}</span>
                            <span class="label {lclass}" style="margin:0; display:inline;">{label}</span>
                        </div>
                        <div style="font-family:var(--font-mono); font-size:11px; color:var(--amber); background:#111; padding:6px 10px; border:1px solid #333; white-space:pre-wrap;">$ {cmd_escaped}</div>
                    '''

                    if is_done:
                        html += '</div>'
                        break

                    result = executor.run(command, cwd=workspace, timeout_s=30.0)
                    obs = ""
                    if result.stdout:
                        obs += result.stdout[:500]
                    if result.stderr:
                        obs += "\nSTDERR: " + result.stderr[:300]
                    if result.exit_code != 0:
                        obs += f"\nEXIT CODE: {result.exit_code}"
                    if not obs.strip():
                        obs = "(no output)"

                    obs_escaped = obs.replace("<", "&lt;").replace(">", "&gt;")
                    html += f'''
                        <div style="background:#111; border:1px solid #333; padding:6px 10px; margin-top:6px; font-size:10px; color:#aaa; font-family:var(--font-mono); white-space:pre-wrap; max-height:100px; overflow-y:auto;">{obs_escaped}</div>
                    </div>'''

                    messages.append({"role": "assistant", "content": response_text})
                    messages.append({"role": "user", "content": obs})

                # Reward
                reward = compute_reward(task, workspace)
                act_count = sum(1 for a in actions if not is_talk(a) and a.lower() != "done")
                talk_count = sum(1 for a in actions if is_talk(a))

                reward_color = "var(--green)" if reward > 0.3 else "var(--amber)" if reward > 0 else "var(--red)"
                html += f'''
                <div style="display:flex; gap:20px; padding:12px 0; border-top:1px solid #333; margin-top:12px; font-family:var(--font-mono); font-size:12px;">
                    <span>REWARD: <b style="color:{reward_color}; font-size:16px;">{reward:.2f}</b></span>
                    <span>ACTS: <b style="color:var(--amber);">{act_count}</b></span>
                    <span>TALKS: <b style="color:var(--red);">{talk_count}</b></span>
                </div>
                </div>'''

                shutil.rmtree(workspace, ignore_errors=True)
                return html

            tryit_btn.click(fn=run_live_episode, inputs=[tryit_task_idx, tryit_model, tryit_turns], outputs=tryit_output)

        # ── Tab 4: About ───────────────────────────────────────
        with gr.Tab("About"):
            gr.HTML("""
            <div class="card">
                <div class="label cyan">What Is This?</div>
                <div class="body">
                    APEX Environment evaluates AI agents on real professional tasks (investment banking, law, consulting)
                    from the <a href="https://huggingface.co/datasets/mercor/apex-agents" style="color:var(--cyan);">mercor/apex-agents</a> dataset.
                    Agents execute bash commands in a workspace. We score them on task completion AND action efficiency.
                </div>
                <div class="detail">
                    "Spend Less, Do More" — penalize talk, reward action. The cheapest models win because they act instead of deliberate.
                </div>
            </div>
            """)

    # Footer
    gr.HTML("""
    <div class="footer">
        APEX Environment // OpenEnv Hackathon 2026
    </div>
    """)


if __name__ == "__main__":
    demo.launch()
