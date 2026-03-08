"""Task family: Hand-Draw SVG Compositions — transfer distance curriculum.

NOT a single task with scaffolding. A FAMILY of tasks where:
- Diamond is the completed reference composition (always in examples/)
- Tasks vary by REASONING GAP from the reference
- Agent must do analogical reasoning to adapt the example

Transfer distance = reasoning gap the agent must cross, NOT concept similarity.

| Distance | Task      | Agent must...                                    |
|----------|-----------|--------------------------------------------------|
| Zero     | diamond   | Find and copy example directly                   |
| Near     | hourglass | Find diamond, extract pattern, ADAPT arrangement |
| Medium   | seesaw    | Diamond doesn't help, compose different elements |
| Far      | temple    | Example not applicable, build from scratch        |

Key insight from Run 13: agent treated diamond and hourglass as "same pattern"
and drew a diamond. Same elements != same pattern. The ADAPTATION (recognizing
same elements but different arrangement) IS the analogical reasoning we test.

specs.md is MINIMAL — no decomposition hints, no references to examples.
The agent must discover examples/ on its own and decide how to use them.
"""
from __future__ import annotations

DOMAIN = "Illustration"

# === Workspace files: Basic Elements (Rough.js code snippets) ===

ELEMENTS = {
    "triangle.js": """\
// Building Block: Triangle
// Import via <script src="elements/triangle.js"></script>
// Then call: drawTriangle(rc, svg, cx, cy, size, 'up'|'down', opts)
function drawTriangle(rc, svg, cx, cy, size, direction, opts) {
  const h = size * 0.866;
  let pts;
  if (direction === 'down') {
    pts = [[cx, cy + h*0.6], [cx - size*0.5, cy - h*0.4], [cx + size*0.5, cy - h*0.4]];
  } else {
    pts = [[cx, cy - h*0.6], [cx - size*0.5, cy + h*0.4], [cx + size*0.5, cy + h*0.4]];
  }
  svg.appendChild(rc.polygon(pts, opts));
}
""",
    "circle.js": """\
// Building Block: Circle & Dot
// Import via <script src="elements/circle.js"></script>
// Then call: drawCircle(rc, svg, cx, cy, diameter, opts)
//        or: drawDot(rc, svg, cx, cy, size, ink)
function drawCircle(rc, svg, cx, cy, diameter, opts) {
  svg.appendChild(rc.circle(cx, cy, diameter, opts));
}
function drawDot(rc, svg, cx, cy, size, ink) {
  svg.appendChild(rc.circle(cx, cy, size, {
    stroke: ink, strokeWidth: 2, fill: ink, fillStyle: 'solid', roughness: 0.5
  }));
}
""",
    "rectangle.js": """\
// Building Block: Rectangle
// Import via <script src="elements/rectangle.js"></script>
// Then call: drawRectangle(rc, svg, x, y, width, height, opts)
function drawRectangle(rc, svg, x, y, w, h, opts) {
  svg.appendChild(rc.rectangle(x, y, w, h, opts));
}
""",
    "line.js": """\
// Building Block: Line & Spark
// Import via <script src="elements/line.js"></script>
// Then call: drawLine(rc, svg, x1, y1, x2, y2, opts)
//        or: drawSpark(rc, svg, x, y, length, angleDeg, ink)
function drawLine(rc, svg, x1, y1, x2, y2, opts) {
  svg.appendChild(rc.line(x1, y1, x2, y2, opts));
}
function drawSpark(rc, svg, x, y, len, angle, ink) {
  const rad = angle * Math.PI / 180;
  svg.appendChild(rc.line(x, y, x + len*Math.cos(rad), y + len*Math.sin(rad), {
    stroke: ink, strokeWidth: 2.5, roughness: 0.8
  }));
}
""",
    "arc.js": """\
// Building Block: Arc / Dome
// Import via <script src="elements/arc.js"></script>
// Then call: drawArc(rc, svg, x1, y1, x2, y2, rx, ry, opts)
function drawArc(rc, svg, x1, y1, x2, y2, rx, ry, opts) {
  svg.appendChild(rc.path('M '+x1+' '+y1+' A '+rx+' '+ry+' 0 0 1 '+x2+' '+y2, opts));
}
""",
}

# === Reference composition — always available in examples/ ===
# Diamond is the COMPLETED sibling task. Agent studies this to learn
# how basic elements compose into illustrations.
# NOTE: No other examples. Agent has ONE reference point.

EXAMPLES = {
    "diamond.html": """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Diamond</title></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#e8dcc8;">
<svg id="art" viewBox="0 0 300 300" width="300" height="300" xmlns="http://www.w3.org/2000/svg"></svg>
<script src="https://unpkg.com/roughjs/bundled/rough.js"></script>
<script src="../elements/triangle.js"></script>
<script src="../elements/line.js"></script>
<script>
const INK = '#1a1a1a';
const svg = document.getElementById('art');
const rc = rough.svg(svg);
const opts = { stroke: INK, strokeWidth: 3.5, fill: 'none', roughness: 0.8 };

// Diamond = two triangles meeting at the middle
drawTriangle(rc, svg, 150, 100, 130, 'up', opts);
drawTriangle(rc, svg, 150, 200, 130, 'down', opts);

// Sparkle accents
drawSpark(rc, svg, 55, 58, 15, -135, INK);
drawSpark(rc, svg, 48, 68, 12, -170, INK);
</script>
</body>
</html>
""",
}

# === HTML template (boilerplate) ===

TEMPLATE = """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Draw: CONCEPT</title></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#e8dcc8;">
<svg id="art" viewBox="0 0 300 300" width="300" height="300" xmlns="http://www.w3.org/2000/svg"></svg>
<script src="https://unpkg.com/roughjs/bundled/rough.js"></script>
<!-- Import building blocks from elements/ -->
<!-- <script src="elements/triangle.js"></script> -->
<!-- <script src="elements/circle.js"></script> -->
<!-- <script src="elements/rectangle.js"></script> -->
<!-- <script src="elements/line.js"></script> -->
<!-- <script src="elements/arc.js"></script> -->
<script>
const INK = '#1a1a1a';
const svg = document.getElementById('art');
const rc = rough.svg(svg);
const opts = { stroke: INK, strokeWidth: 3.5, fill: 'none', roughness: 0.8 };

// === YOUR ILLUSTRATION CODE HERE ===
// Uncomment the element imports you need above
// Then use: drawTriangle(), drawCircle(), drawRectangle(), drawLine(), drawArc()

</script>
</body>
</html>
"""

# === Distractor files ===

DISTRACTORS = {
    "color_theory.md": (
        "# Color Theory Notes\n\n"
        "Primary colors: Red, Blue, Yellow\n"
        "Secondary colors: Green, Orange, Purple\n"
        "Complementary pairs create visual tension.\n"
        "Note: This project uses only INK (#1a1a1a) and WHITE (#f0ebe0).\n"
    ),
    "animation_notes.md": (
        "# Animation Reference\n\n"
        "CSS keyframes can add subtle motion:\n"
        "- Sway: rotate ±1.5deg\n"
        "- Breathe: scale 1.0-1.03\n"
        "Not needed for static illustrations.\n"
    ),
}

# === Task Family ===
# Each task has MINIMAL specs — no decomposition hints, no references to examples.
# The agent must discover examples/ on its own and do its own analogical reasoning.

TASK_FAMILY = {
    "diamond": {
        "task_id": "handdraw_diamond",
        "concept": "diamond",
        "output_file": "diamond.html",
        "transfer_distance": "zero",
        "spec": (
            "# Task: Compose a DIAMOND illustration\n\n"
            "Create a diamond illustration using Rough.js.\n\n"
            "## Requirements\n"
            "- Output file: `diamond.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `diamond.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file diamond.html exists",
             "check_type": "file_exists", "file_name": "diamond.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Uses SVG element with viewBox",
             "check_keywords": ["viewBox"]},
            {"id": 4, "description": "Uses INK color constant",
             "check_keywords": ["#1a1a1a", "INK"]},
            {"id": 5, "description": "Rendered illustration visually depicts a diamond",
             "check_type": "visual_check", "file_name": "diamond.html",
             "concept": "diamond"},
        ],
    },

    "hourglass": {
        "task_id": "handdraw_hourglass",
        "concept": "hourglass",
        "output_file": "hourglass.html",
        "transfer_distance": "near",
        "spec": (
            "# Task: Compose an HOURGLASS illustration\n\n"
            "Create an hourglass illustration using Rough.js.\n\n"
            "## Requirements\n"
            "- Output file: `hourglass.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `hourglass.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file hourglass.html exists",
             "check_type": "file_exists", "file_name": "hourglass.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Contains polygon shapes",
             "check_keywords": ["polygon"]},
            {"id": 4, "description": "Uses SVG element with viewBox",
             "check_keywords": ["viewBox"]},
            {"id": 5, "description": "Uses INK color constant",
             "check_keywords": ["#1a1a1a", "INK"]},
            {"id": 6, "description": "Rendered illustration visually depicts an hourglass",
             "check_type": "visual_check", "file_name": "hourglass.html",
             "concept": "hourglass"},
        ],
    },

    "seesaw": {
        "task_id": "handdraw_seesaw",
        "concept": "seesaw",
        "output_file": "seesaw.html",
        "transfer_distance": "medium",
        "spec": (
            "# Task: Compose a SEESAW illustration\n\n"
            "Create a seesaw illustration using Rough.js.\n\n"
            "## Requirements\n"
            "- Output file: `seesaw.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `seesaw.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file seesaw.html exists",
             "check_type": "file_exists", "file_name": "seesaw.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Uses multiple element types",
             "check_keywords": ["polygon", "circle", "line"]},
            {"id": 4, "description": "Uses SVG element with viewBox",
             "check_keywords": ["viewBox"]},
            {"id": 5, "description": "Uses INK color constant",
             "check_keywords": ["#1a1a1a", "INK"]},
            {"id": 6, "description": "Rendered illustration visually depicts a seesaw",
             "check_type": "visual_check", "file_name": "seesaw.html",
             "concept": "seesaw"},
        ],
    },

    "temple": {
        "task_id": "handdraw_temple",
        "concept": "temple",
        "output_file": "temple.html",
        "transfer_distance": "far",
        "spec": (
            "# Task: Compose a TEMPLE illustration\n\n"
            "Create a temple illustration using Rough.js.\n\n"
            "## Requirements\n"
            "- Output file: `temple.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `temple.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file temple.html exists",
             "check_type": "file_exists", "file_name": "temple.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Uses SVG element with viewBox",
             "check_keywords": ["viewBox"]},
            {"id": 4, "description": "Uses INK color constant",
             "check_keywords": ["#1a1a1a", "INK"]},
            {"id": 5, "description": "Contains multiple draw calls",
             "check_keywords": ["rc."]},
            {"id": 6, "description": "Rendered illustration visually depicts a temple",
             "check_type": "visual_check", "file_name": "temple.html",
             "concept": "temple"},
        ],
    },
}

# Default task for backward compatibility
DEFAULT_TASK = "hourglass"

# Backward compat exports
_default = TASK_FAMILY[DEFAULT_TASK]
TASK_ID = _default["task_id"]
CRITERIA = _default["criteria"]
SPEC_CONTENT = _default["spec"]
