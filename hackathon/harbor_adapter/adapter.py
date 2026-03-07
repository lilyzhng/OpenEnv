"""
APEX-Agents Adapter - Convert mercor/apex-agents tasks to Harbor format.

mercor/apex-agents: 480 professional tasks (Law, IB, Consulting).
This dataset is EVAL ONLY — training is forbidden.

Each task becomes a Harbor task directory with:
- instruction.md: task prompt + available files
- environment/Dockerfile: Python + standard tools
- tests/test.sh: rubric-based keyword grading
- tests/config.json: rubric + expected output (hidden from agent)
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "template"

# Noise words to filter from keywords
KEYWORD_NOISE = {
    "The", "This", "That", "These", "Those", "Each", "For", "And",
    "But", "Not", "All", "Any", "Has", "Are", "Was", "Were", "Can",
    "May", "Should", "Would", "Could", "Will", "Must", "Also",
    "Based", "Using", "FROM", "INTO", "WITH", "THEN", "WHEN",
    "NULL", "TRUE", "ELSE", "CASE", "JSON",
}


def extract_keywords(rubric_raw) -> list[str]:
    """Extract meaningful keywords from apex-agents rubric."""
    if isinstance(rubric_raw, str):
        try:
            rubric = json.loads(rubric_raw)
        except json.JSONDecodeError:
            return []
    else:
        rubric = rubric_raw

    criteria = []
    if isinstance(rubric, dict):
        criteria = list(rubric.values())
    elif isinstance(rubric, list):
        criteria = rubric
    else:
        return []

    keywords = set()
    for criterion in criteria:
        if isinstance(criterion, str):
            text = criterion
        elif isinstance(criterion, dict):
            text = " ".join([
                criterion.get("criteria", ""),
                criterion.get("criterion", ""),
                criterion.get("description", ""),
                criterion.get("justification", ""),
            ])
        else:
            continue

        # Capitalized terms
        keywords.update(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text))
        # Quoted terms
        keywords.update(re.findall(r'"([^"]+)"', text))
        # Acronyms
        keywords.update(re.findall(r"\b[A-Z]{2,6}\b", text))
        # Numbers with units
        keywords.update(re.findall(r"\$?[\d,.]+[%BMK]?\b", text))

    keywords -= KEYWORD_NOISE
    keywords = {kw for kw in keywords if len(kw) > 1}
    return sorted(keywords)


class ApexAgentsAdapter:
    """Adapter for mercor/apex-agents benchmark."""

    NAME = "apex-agents"

    @staticmethod
    def make_local_task_id(domain: str, index: int) -> str:
        normalized = domain.lower().replace(" ", "-")
        return f"apex-{normalized}-{index:03d}"

    def __init__(self, task_dir: Path, dataset):
        self.task_dir = Path(task_dir)
        self.dataset = dataset

    def get_all_ids(self) -> list[int]:
        return list(range(len(self.dataset)))

    def generate_task(self, source_idx: int, local_task_id: str) -> None:
        row = self.dataset[source_idx]
        output_dir = self.task_dir / local_task_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Copy template
        self._copy_template(output_dir)

        domain = row.get("domain", "unknown")
        prompt = row.get("prompt", row.get("Prompt", ""))
        rubric_raw = row.get("rubric", row.get("Rubric JSON", []))
        expected_output = row.get("expected_output", "text")
        gold_response = row.get("gold_response", "")

        keywords = extract_keywords(rubric_raw)

        # Write instruction.md
        instruction = f"""You are a professional analyst specializing in {domain}.

Solve the following task using bash commands. You have access to:
- Python 3 with pandas, openpyxl, pdfplumber
- Standard unix tools (grep, awk, sed, jq, etc.)
- Any files in /app/data/

## Task

{prompt}

## Instructions

1. Read and analyze any provided files in /app/data/
2. Perform calculations or analysis as needed
3. Write your final answer to /app/answer.txt

Your answer should be thorough and address all aspects of the task.
When finished, write your complete analysis to /app/answer.txt.
"""
        (output_dir / "instruction.md").write_text(instruction)

        # Write test config (hidden from agent)
        test_config = {
            "task_id": local_task_id,
            "source_index": source_idx,
            "domain": domain,
            "keywords": keywords,
            "num_keywords": len(keywords),
            "expected_output": expected_output,
            "gold_response": gold_response[:500] if gold_response else "",
        }

        # Serialize rubric
        if isinstance(rubric_raw, (dict, list)):
            test_config["rubric"] = rubric_raw
        elif isinstance(rubric_raw, str):
            try:
                test_config["rubric"] = json.loads(rubric_raw)
            except json.JSONDecodeError:
                test_config["rubric"] = rubric_raw

        (output_dir / "tests" / "config.json").write_text(
            json.dumps(test_config, indent=2, ensure_ascii=False)
        )

        # Write keywords file for test.sh
        (output_dir / "tests" / "keywords.json").write_text(
            json.dumps(keywords, ensure_ascii=False)
        )

        # Customize task.toml metadata
        task_toml = output_dir / "task.toml"
        if task_toml.exists():
            content = task_toml.read_text()
            content = content.replace("{domain}", domain)
            content = content.replace("{difficulty}", self._difficulty(rubric_raw))
            task_toml.write_text(content)

        # Write oracle solution
        solve_path = output_dir / "solution" / "solve.sh"
        if solve_path.exists() and gold_response:
            escaped = gold_response.replace("'", "'\\''")
            content = solve_path.read_text()
            content = content.replace("{GOLD_RESPONSE}", escaped)
            solve_path.write_text(content)

    def _copy_template(self, output_dir: Path) -> None:
        if TEMPLATE_DIR.exists():
            for item in TEMPLATE_DIR.iterdir():
                dst = output_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dst)

    @staticmethod
    def _difficulty(rubric_raw) -> str:
        if isinstance(rubric_raw, str):
            try:
                rubric = json.loads(rubric_raw)
            except json.JSONDecodeError:
                return "medium"
        else:
            rubric = rubric_raw

        n = len(rubric) if isinstance(rubric, (dict, list)) else 0
        if n <= 3:
            return "easy"
        elif n <= 6:
            return "medium"
        return "hard"
