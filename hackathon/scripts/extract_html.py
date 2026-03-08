"""
Extract final hourglass.html content from agent run logs.

Handles multiple patterns:
1. `cat > hourglass.html << 'EOF' ... EOF` (heredoc write)
2. `cat hourglass.html` followed by output (reading back the file)
3. `echo '...' > .../hourglass.html` (echo redirect)

For each log, finds the LAST occurrence of a write or read-back,
and extracts the HTML content.
"""

import re
from pathlib import Path

BASE = Path("/Users/lilyzhang/Documents/lilyzhng/OpenEnv_Hackathon/OpenEnv/hackathon/data/handdraw_v6")

LOG_MAP = {
    "run_gpt54_hourglass.log": "html/gpt54_hourglass.html",
    "run_sonnet_hourglass.log": "html/sonnet_hourglass.html",
    "run_qwen30b_hourglass.log": "html/qwen30b_hourglass.html",
    "run_gpt4omini_hourglass.log": "html/gpt4omini_hourglass.html",
}


def extract_heredoc(lines: list[str], start_idx: int) -> str | None:
    """Extract content from a heredoc block starting after the COMMAND line.

    Looks for content between the COMMAND line and EOF.
    """
    # Find the actual HTML start (<!DOCTYPE or <html)
    html_lines = []
    collecting = False
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if line.strip() == "EOF":
            break
        if line.strip().startswith("<!DOCTYPE") or line.strip().startswith("<html"):
            collecting = True
        if collecting:
            html_lines.append(line)

    if html_lines:
        return "\n".join(html_lines)
    return None


def extract_cat_output(lines: list[str], cmd_idx: int) -> str | None:
    """Extract the output of `cat hourglass.html` from the log.

    Output starts after 'ENVIRONMENT → AGENT:' and ends before a line
    matching progress/criteria patterns or turn separators.
    """
    # Find "ENVIRONMENT → AGENT:" after the command
    env_idx = None
    for i in range(cmd_idx + 1, min(cmd_idx + 5, len(lines))):
        if "ENVIRONMENT" in lines[i] and "AGENT" in lines[i]:
            env_idx = i
            break

    if env_idx is None:
        return None

    html_lines = []
    for i in range(env_idx + 1, len(lines)):
        line = lines[i]
        # Stop at progress markers, turn separators, or empty lines followed by progress
        if line.strip().startswith("[Progress:"):
            break
        if line.strip().startswith("... (truncated)"):
            break
        if line.strip().startswith("──────"):
            break
        html_lines.append(line)

    # Remove trailing empty lines
    while html_lines and html_lines[-1].strip() == "":
        html_lines.pop()

    content = "\n".join(html_lines)
    if "<!DOCTYPE" in content or "<html" in content:
        return content
    return None


def extract_echo_redirect(lines: list[str], cmd_idx: int) -> str | None:
    """Extract HTML from an echo '...' > hourglass.html command.

    The echo content spans from COMMAND line to the redirect line.
    """
    echo_lines = []
    for i in range(cmd_idx, len(lines)):
        echo_lines.append(lines[i])
        if lines[i].rstrip().endswith("hourglass.html"):
            break

    full_cmd = "\n".join(echo_lines)

    # Extract content between echo ' and ' > .../hourglass.html
    match = re.search(
        r"COMMAND: echo '(.*?)'\s*>\s*\S*hourglass\.html",
        full_cmd,
        re.DOTALL,
    )
    if match:
        return match.group(1)
    return None


def extract_from_log(log_path: Path) -> str:
    """Extract the final hourglass.html content from a log file."""
    text = log_path.read_text()
    lines = text.split("\n")

    # Strategy: find ALL write/read events, take the last one that gives valid HTML
    events = []  # (index, type)

    for i, line in enumerate(lines):
        # Heredoc write: COMMAND: cat > hourglass.html << 'EOF'
        if re.match(r"COMMAND: cat > hourglass\.html\s*<<\s*'?EOF'?", line):
            events.append((i, "heredoc"))
        # Cat read: COMMAND: cat hourglass.html (not cat > or cat /path)
        elif re.match(r"COMMAND: cat hourglass\.html\s*$", line):
            events.append((i, "cat_read"))
        # Echo redirect: COMMAND: echo '... > .../hourglass.html
        elif re.match(r"COMMAND: echo '<!DOCTYPE", line):
            events.append((i, "echo"))

    # Try events in reverse order (last = final version)
    for idx, event_type in reversed(events):
        if event_type == "heredoc":
            result = extract_heredoc(lines, idx)
            if result:
                print(f"  Extracted from heredoc at line {idx + 1}")
                return result
        elif event_type == "cat_read":
            result = extract_cat_output(lines, idx)
            if result and "... (truncated)" not in result and "</html>" in result:
                print(f"  Extracted from cat output at line {idx + 1}")
                return result
            elif result:
                print(f"  Skipping truncated/incomplete cat output at line {idx + 1}")
        elif event_type == "echo":
            result = extract_echo_redirect(lines, idx)
            if result:
                print(f"  Extracted from echo redirect at line {idx + 1}")
                return result

    raise ValueError(f"Could not extract HTML from {log_path}")


def main():
    for log_name, out_name in LOG_MAP.items():
        log_path = BASE / log_name
        out_path = BASE / out_name

        print(f"\nProcessing {log_name}...")
        html_content = extract_from_log(log_path)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_content)
        print(f"  Saved to {out_path}")
        print(f"  Size: {len(html_content)} bytes")

        # Sanity checks
        checks = [
            ("<!DOCTYPE" in html_content or "<html" in html_content, "has HTML tag"),
            ("roughjs" in html_content or "rough.js" in html_content or "rough.min.js" in html_content, "has Rough.js"),
            ("</html>" in html_content, "has closing </html>"),
        ]
        for passed, label in checks:
            status = "OK" if passed else "WARN"
            print(f"  [{status}] {label}")


if __name__ == "__main__":
    main()
