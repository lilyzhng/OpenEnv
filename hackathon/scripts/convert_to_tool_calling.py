"""
Convert APEX-v1-extended into a multi-turn tool calling dataset.

Transforms static QA rubrics into conversation format where each criterion
becomes a tool call + response turn. The key insight: rubric criteria
contain `sources` (which file to read) + `description` (what to extract/calculate)
+ `justification` (reasoning), which maps directly to tool calling turns.

Output format (OpenAI-compatible messages):
[
  {"role": "system", "content": "You are a professional analyst..."},
  {"role": "user", "content": "<task prompt>"},
  {"role": "assistant", "content": null, "tool_calls": [{"name": "read_file", "arguments": {...}}]},
  {"role": "tool", "name": "read_file", "content": "<file contents summary>"},
  {"role": "assistant", "content": "<reasoning + partial answer>"},
  ...
  {"role": "assistant", "content": "<final composed answer>"}
]

Usage:
    python convert_to_tool_calling.py
    python convert_to_tool_calling.py --output ../data/multiturn_tool_calling.json
    python convert_to_tool_calling.py --format chatml  # ChatML format
"""

import argparse
import json
import re
from pathlib import Path
from datasets import load_dataset


# Tool definitions matching Archipelago's 9 MCP tools
TOOL_DEFINITIONS = [
    {
        "name": "read_spreadsheet",
        "description": "Read and analyze spreadsheet files (.xlsx, .xls, .csv)",
        "parameters": {"file_path": "string", "sheet_name": "string (optional)"},
    },
    {
        "name": "read_pdf",
        "description": "Read and extract text from PDF documents",
        "parameters": {"file_path": "string", "pages": "string (optional, e.g. '1-5')"},
    },
    {
        "name": "read_document",
        "description": "Read text documents (.docx, .doc, .txt, .md)",
        "parameters": {"file_path": "string"},
    },
    {
        "name": "execute_code",
        "description": "Execute Python code for calculations and data analysis",
        "parameters": {"code": "string"},
    },
    {
        "name": "search_files",
        "description": "Search filesystem for relevant files",
        "parameters": {"query": "string", "directory": "string (optional)"},
    },
]


def load_data():
    ds = load_dataset("mercor/APEX-v1-extended", split="train")
    return ds


def classify_file(filepath):
    """Determine which tool to use for a file."""
    fp = filepath.lower()
    if any(ext in fp for ext in [".xlsx", ".xls", ".csv"]):
        return "read_spreadsheet"
    elif ".pdf" in fp:
        return "read_pdf"
    elif any(ext in fp for ext in [".docx", ".doc", ".txt", ".md"]):
        return "read_document"
    return "read_document"  # default


def parse_rubric(rubric_raw):
    """Parse rubric JSON into ordered criteria list."""
    try:
        rubric = json.loads(rubric_raw)
    except json.JSONDecodeError:
        return []

    criteria = []
    if isinstance(rubric, dict):
        for key in sorted(
            rubric.keys(),
            key=lambda k: int(re.search(r"\d+", k).group()) if re.search(r"\d+", k) else 0,
        ):
            val = rubric[key]
            if isinstance(val, dict):
                criteria.append(val)
            elif isinstance(val, str):
                criteria.append({"description": val})
    elif isinstance(rubric, list):
        criteria = [item for item in rubric if isinstance(item, dict)]
    return criteria


def resolve_source_files(sources_str, file_attachments):
    """Match source references to actual file paths."""
    if not sources_str or sources_str.lower() in ["prompt", "", "n/a", "none"]:
        return []

    matched = []
    attachments = [f.strip() for f in file_attachments.split("\n") if f.strip()]

    for attachment in attachments:
        filename = attachment.split("/")[-1] if "/" in attachment else attachment
        # Check if source mentions this file (fuzzy match)
        if (
            filename.lower() in sources_str.lower()
            or sources_str.lower() in filename.lower()
            # Also match without extension
            or filename.rsplit(".", 1)[0].lower() in sources_str.lower()
        ):
            matched.append(attachment)

    return matched


def build_system_prompt(domain):
    """Create domain-specific system prompt."""
    domain_context = {
        "Finance": (
            "You are a senior financial analyst. You solve tasks by reading financial "
            "models, SEC filings, and spreadsheets, then performing precise calculations. "
            "Always use tools to read files and execute calculations — do not guess numbers."
        ),
        "Legal": (
            "You are a corporate lawyer. You solve tasks by reading contracts, statutes, "
            "and case law PDFs, then providing legal analysis with citations. "
            "Always use tools to read documents — do not fabricate legal references."
        ),
        "Medicine": (
            "You are a clinical physician. You solve tasks by reading medical guidelines, "
            "immunization schedules, and clinical data, then providing evidence-based recommendations. "
            "Always use tools to read reference documents before making recommendations."
        ),
        "Consulting": (
            "You are a management consultant. You solve tasks by reading data files, "
            "performing quantitative analysis, and synthesizing recommendations. "
            "Always use tools to read data and execute calculations — show your work."
        ),
    }
    return domain_context.get(domain, "You are a professional analyst who uses tools to solve tasks.")


def criteria_to_action(criterion, file_attachments, files_already_read):
    """Convert a single rubric criterion into tool calling turn(s)."""
    desc = criterion.get("description", "")
    sources = criterion.get("sources", "")
    justification = criterion.get("justification", "")

    turns = []

    # Step 1: Read any new files needed
    source_files = resolve_source_files(sources, file_attachments)
    new_files = [f for f in source_files if f not in files_already_read]

    for filepath in new_files:
        tool_name = classify_file(filepath)
        filename = filepath.split("/")[-1] if "/" in filepath else filepath

        # Tool call turn
        turns.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_{hash(filepath) % 10000:04d}",
                    "name": tool_name,
                    "arguments": {"file_path": filepath},
                }
            ],
        })

        # Tool response (simulated — in real env this comes from the environment)
        turns.append({
            "role": "tool",
            "tool_call_id": f"call_{hash(filepath) % 10000:04d}",
            "name": tool_name,
            "content": f"[Contents of {filename} loaded. Relevant data available for analysis.]",
        })

        files_already_read.add(filepath)

    # Step 2: Determine if calculation is needed
    desc_lower = desc.lower()
    needs_calculation = any(
        w in desc_lower
        for w in [
            "calculate", "compute", "sum", "average", "irr", "npv",
            "moic", "wacc", "multiply", "divide", "percentage", "ratio",
            "acceptable range", "billion", "million",
        ]
    )

    if needs_calculation and justification:
        # Add a code execution tool call for calculation
        calc_code = justification_to_code_hint(justification, desc)
        turns.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_calc_{hash(desc) % 10000:04d}",
                    "name": "execute_code",
                    "arguments": {"code": calc_code},
                }
            ],
        })
        turns.append({
            "role": "tool",
            "tool_call_id": f"call_calc_{hash(desc) % 10000:04d}",
            "name": "execute_code",
            "content": f"[Calculation complete. Result matches criterion: {desc[:100]}]",
        })

    # Step 3: Assistant reasoning + answer for this criterion
    reasoning = build_reasoning(desc, justification, source_files)
    turns.append({
        "role": "assistant",
        "content": reasoning,
    })

    return turns


def justification_to_code_hint(justification, description):
    """Convert justification text into a code calculation hint."""
    # Extract numbers and operations from justification
    # This is a simplified version — in production you'd want more sophisticated parsing
    return f"# Calculate: {description[:100]}\n# Based on: {justification[:200]}"


def build_reasoning(description, justification, source_files):
    """Build the assistant's reasoning response for a criterion."""
    parts = []

    if source_files:
        filenames = [f.split("/")[-1] for f in source_files]
        parts.append(f"Based on the data from {', '.join(filenames)}:")

    if justification:
        # Use justification as the reasoning
        parts.append(justification[:500])
    else:
        parts.append(description)

    return " ".join(parts)


def convert_task(task):
    """Convert a single task into multi-turn tool calling conversation."""
    criteria = parse_rubric(task["Rubric JSON"])
    if not criteria:
        return None

    messages = []
    files_read = set()

    # System prompt
    messages.append({
        "role": "system",
        "content": build_system_prompt(task["Domain"]),
    })

    # User prompt (the task)
    user_content = task["Prompt"]
    if task["File Attachments"]:
        attachments = [f.strip() for f in task["File Attachments"].split("\n") if f.strip()]
        user_content += "\n\nAvailable files:\n" + "\n".join(f"- {a}" for a in attachments)

    messages.append({
        "role": "user",
        "content": user_content,
    })

    # Convert each criterion into tool calling turns
    for criterion in criteria:
        turns = criteria_to_action(criterion, task["File Attachments"], files_read)
        messages.extend(turns)

    # Final composed answer
    all_findings = []
    for criterion in criteria:
        desc = criterion.get("description", "")
        all_findings.append(f"- {desc}")

    messages.append({
        "role": "assistant",
        "content": "Based on my analysis, here is the complete response:\n\n" + "\n".join(all_findings),
    })

    return {
        "task_id": task["Task ID"],
        "domain": task["Domain"],
        "num_criteria": len(criteria),
        "num_turns": len(messages),
        "num_tool_calls": sum(1 for m in messages if m.get("tool_calls")),
        "messages": messages,
    }


def print_summary(conversations):
    """Print summary of the converted dataset."""
    print(f"\nConverted {len(conversations)} tasks")

    total_turns = sum(c["num_turns"] for c in conversations)
    total_tool_calls = sum(c["num_tool_calls"] for c in conversations)
    print(f"Total conversation turns: {total_turns}")
    print(f"Total tool calls: {total_tool_calls}")
    print(f"Avg turns per conversation: {total_turns / len(conversations):.1f}")
    print(f"Avg tool calls per conversation: {total_tool_calls / len(conversations):.1f}")

    # By domain
    print("\n--- By Domain ---")
    from collections import Counter, defaultdict
    domain_stats = defaultdict(lambda: {"count": 0, "turns": 0, "tools": 0})
    for c in conversations:
        d = c["domain"]
        domain_stats[d]["count"] += 1
        domain_stats[d]["turns"] += c["num_turns"]
        domain_stats[d]["tools"] += c["num_tool_calls"]

    for domain in sorted(domain_stats.keys()):
        s = domain_stats[domain]
        print(
            f"  {domain}: {s['count']} tasks, "
            f"avg {s['turns']/s['count']:.0f} turns, "
            f"avg {s['tools']/s['count']:.0f} tool calls"
        )

    # Show one sample
    print("\n--- Sample Conversation (first Finance task) ---")
    for c in conversations:
        if c["domain"] == "Finance":
            for msg in c["messages"][:12]:
                role = msg["role"]
                if msg.get("tool_calls"):
                    tc = msg["tool_calls"][0]
                    print(f"  [{role}] → tool_call({tc['name']}, {json.dumps(tc['arguments'])[:80]})")
                elif role == "tool":
                    print(f"  [{role}] ← {msg['content'][:80]}")
                elif role == "system":
                    print(f"  [{role}] {msg['content'][:80]}...")
                else:
                    content = msg.get("content", "")
                    print(f"  [{role}] {content[:100]}...")
            if c["num_turns"] > 12:
                print(f"  ... ({c['num_turns'] - 12} more turns)")
            break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", default="../data/multiturn_tool_calling.json")
    parser.add_argument(
        "--format",
        choices=["openai", "chatml", "sharegpt"],
        default="openai",
        help="Output format",
    )
    args = parser.parse_args()

    ds = load_data()
    conversations = []

    for i in range(len(ds)):
        result = convert_task(ds[i])
        if result:
            conversations.append(result)

    print_summary(conversations)

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(conversations, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(conversations)} conversations to {args.output}")

    # Also save just the messages in a flat format for SFT frameworks
    flat_path = output_path.with_stem(output_path.stem + "_flat")
    flat_data = [{"messages": c["messages"]} for c in conversations]
    with open(flat_path, "w", encoding="utf-8") as f:
        json.dump(flat_data, f, indent=2, ensure_ascii=False)
    print(f"Saved flat messages format to {flat_path}")


if __name__ == "__main__":
    main()
