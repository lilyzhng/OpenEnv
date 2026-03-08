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
    "curve.js": """\
// Building Block: Smooth Curve (multi-point)
// Import via <script src="elements/curve.js"></script>
// Then call: drawCurve(rc, svg, points, opts)
// points is an array of [x, y] pairs — Rough.js draws a smooth curve through them
function drawCurve(rc, svg, points, opts) {
  svg.appendChild(rc.curve(points, opts));
}
""",
    "path.js": """\
// Building Block: Custom SVG Path
// Import via <script src="elements/path.js"></script>
// Then call: drawPath(rc, svg, pathData, opts)
// pathData is an SVG path string like 'M 50 50 Q 100 20 150 50'
function drawPath(rc, svg, pathData, opts) {
  svg.appendChild(rc.path(pathData, opts));
}
""",
    "ellipse.js": """\
// Building Block: Ellipse
// Import via <script src="elements/ellipse.js"></script>
// Then call: drawEllipse(rc, svg, cx, cy, width, height, opts)
function drawEllipse(rc, svg, cx, cy, width, height, opts) {
  svg.appendChild(rc.ellipse(cx, cy, width, height, opts));
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
<!-- <script src="elements/curve.js"></script> -->
<!-- <script src="elements/path.js"></script> -->
<!-- <script src="elements/ellipse.js"></script> -->
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
             "check_keywords": ["polygon", "drawTriangle", "drawRectangle"]},
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
             "check_keywords": ["polygon", "circle", "line", "drawTriangle", "drawCircle", "drawLine", "drawRectangle"]},
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
             "check_keywords": ["rc.", "drawTriangle", "drawCircle", "drawLine", "drawRectangle", "drawArc"]},
            {"id": 6, "description": "Rendered illustration visually depicts a temple",
             "check_type": "visual_check", "file_name": "temple.html",
             "concept": "temple"},
        ],
    },

    # ========== COMPLEX COMPOSITIONS (harder) ==========

    "flower": {
        "task_id": "handdraw_flower",
        "concept": "flower",
        "output_file": "flower.html",
        "transfer_distance": "far",
        "spec": (
            "# Task: Compose a FLOWER illustration\n\n"
            "Create a flower illustration using Rough.js.\n"
            "The flower should have petals, a center, a stem, and a leaf.\n\n"
            "## Requirements\n"
            "- Output file: `flower.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `flower.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file flower.html exists",
             "check_type": "file_exists", "file_name": "flower.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Uses SVG paths or curves for organic shapes",
             "check_keywords": ["rc.path", "rc.curve", "drawPath", "drawCurve"]},
            {"id": 4, "description": "Uses circle element for flower center",
             "check_keywords": ["rc.circle", "drawCircle", "drawDot"]},
            {"id": 5, "description": "Has multiple petal shapes (at least 3)",
             "check_keywords": ["path", "petal", "Q "]},
            {"id": 6, "description": "Rendered illustration visually depicts a flower",
             "check_type": "visual_check", "file_name": "flower.html",
             "concept": "flower with petals and stem"},
        ],
    },

    "balanced_scale": {
        "task_id": "handdraw_balanced_scale",
        "concept": "balanced scale",
        "output_file": "balanced_scale.html",
        "transfer_distance": "far",
        "spec": (
            "# Task: Compose a BALANCED SCALE illustration\n\n"
            "Create a balanced scale (scales of justice) illustration using Rough.js.\n"
            "It should have a vertical post, a horizontal beam, and two hanging pans.\n\n"
            "## Requirements\n"
            "- Output file: `balanced_scale.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `balanced_scale.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file balanced_scale.html exists",
             "check_type": "file_exists", "file_name": "balanced_scale.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Uses line elements for post and beam",
             "check_keywords": ["rc.line", "drawLine"]},
            {"id": 4, "description": "Uses arc or path for pan curves",
             "check_keywords": ["rc.path", "rc.curve", "drawArc", "drawPath", "A "]},
            {"id": 5, "description": "Has symmetric structure (two pans)",
             "check_keywords": ["line", "circle", "polygon", "path"]},
            {"id": 6, "description": "Rendered illustration visually depicts a balanced scale",
             "check_type": "visual_check", "file_name": "balanced_scale.html",
             "concept": "balanced scale or scales of justice"},
        ],
    },

    "cherry_blossom": {
        "task_id": "handdraw_cherry_blossom",
        "concept": "cherry blossom tree",
        "output_file": "cherry_blossom.html",
        "transfer_distance": "very_far",
        "spec": (
            "# Task: Compose a CHERRY BLOSSOM TREE illustration\n\n"
            "Create a cherry blossom tree illustration using Rough.js.\n"
            "It should have a trunk, branching limbs, and blossom nodes at the tips.\n\n"
            "## Requirements\n"
            "- Output file: `cherry_blossom.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `cherry_blossom.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file cherry_blossom.html exists",
             "check_type": "file_exists", "file_name": "cherry_blossom.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Uses paths or curves for branches",
             "check_keywords": ["rc.path", "rc.curve", "drawPath", "drawCurve"]},
            {"id": 4, "description": "Uses circles for blossom nodes",
             "check_keywords": ["rc.circle", "drawCircle", "drawDot"]},
            {"id": 5, "description": "Has multiple branches (at least 4 path/curve calls)",
             "check_keywords": ["path", "curve", "branch"]},
            {"id": 6, "description": "Rendered illustration visually depicts a cherry blossom tree",
             "check_type": "visual_check", "file_name": "cherry_blossom.html",
             "concept": "cherry blossom tree with trunk and branches"},
        ],
    },

    "fish": {
        "task_id": "handdraw_fish",
        "concept": "fish",
        "output_file": "fish.html",
        "transfer_distance": "very_far",
        "spec": (
            "# Task: Compose a FISH illustration\n\n"
            "Create a fish illustration using Rough.js.\n"
            "It should have a body, eye, tail fin, and dorsal fin.\n\n"
            "## Requirements\n"
            "- Output file: `fish.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `fish.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file fish.html exists",
             "check_type": "file_exists", "file_name": "fish.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Uses path for body outline",
             "check_keywords": ["rc.path", "drawPath", "Q ", "C "]},
            {"id": 4, "description": "Has eye element",
             "check_keywords": ["rc.circle", "drawCircle", "drawDot", "eye"]},
            {"id": 5, "description": "Has tail and fin shapes",
             "check_keywords": ["path", "tail", "fin", "polygon"]},
            {"id": 6, "description": "Rendered illustration visually depicts a fish",
             "check_type": "visual_check", "file_name": "fish.html",
             "concept": "fish with body, tail, and fins"},
        ],
    },

    "stacking_stones": {
        "task_id": "handdraw_stacking_stones",
        "concept": "stacking stones",
        "output_file": "stacking_stones.html",
        "transfer_distance": "far",
        "spec": (
            "# Task: Compose a STACKING STONES illustration\n\n"
            "Create a stacking stones (zen balance) illustration using Rough.js.\n"
            "It should show organic, rounded stones balanced on top of each other.\n\n"
            "## Requirements\n"
            "- Output file: `stacking_stones.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `stacking_stones.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file stacking_stones.html exists",
             "check_type": "file_exists", "file_name": "stacking_stones.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Uses curves or ellipses for organic stone shapes",
             "check_keywords": ["rc.curve", "rc.ellipse", "rc.path", "drawCurve", "drawEllipse", "drawPath"]},
            {"id": 4, "description": "Has multiple stacked shapes (at least 3)",
             "check_keywords": ["curve", "ellipse", "path"]},
            {"id": 5, "description": "Uses SVG element with viewBox",
             "check_keywords": ["viewBox"]},
            {"id": 6, "description": "Rendered illustration visually depicts stacking stones",
             "check_type": "visual_check", "file_name": "stacking_stones.html",
             "concept": "stacking stones or balanced zen rocks"},
        ],
    },

    "neural_net": {
        "task_id": "handdraw_neural_net",
        "concept": "neural network",
        "output_file": "neural_net.html",
        "transfer_distance": "very_far",
        "spec": (
            "# Task: Compose a NEURAL NETWORK illustration\n\n"
            "Create a neural network diagram illustration using Rough.js.\n"
            "It should show nodes (circles) connected by lines/edges in a network topology.\n\n"
            "## Requirements\n"
            "- Output file: `neural_net.html`\n"
            "- Must use the HTML template from `template.html`\n"
            "- Must use Rough.js (loaded via script tag)\n\n"
            "Write the complete HTML file to `neural_net.html` in your workspace.\n"
        ),
        "criteria": [
            {"id": 1, "description": "Output file neural_net.html exists",
             "check_type": "file_exists", "file_name": "neural_net.html"},
            {"id": 2, "description": "Uses Rough.js script tag",
             "check_keywords": ["rough.js", "roughjs"]},
            {"id": 3, "description": "Uses circles for nodes",
             "check_keywords": ["rc.circle", "drawCircle", "drawDot"]},
            {"id": 4, "description": "Uses lines for connections",
             "check_keywords": ["rc.line", "drawLine"]},
            {"id": 5, "description": "Has multiple nodes and connections (network structure)",
             "check_keywords": ["circle", "line"]},
            {"id": 6, "description": "Rendered illustration visually depicts a neural network",
             "check_type": "visual_check", "file_name": "neural_net.html",
             "concept": "neural network diagram with connected nodes"},
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
