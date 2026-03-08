"""Demo task: Hand-Draw SVG Composition — cross-domain building block proof.

Agent must discover basic Rough.js elements, study example compositions,
and compose a new illustration (hourglass) from basic elements.

Same four principles as IB environment:
1. Provide building blocks (elements/*.js code snippets)
2. Tell if right (criteria: does output contain correct elements?)
3. Don't tell how to build (agent decides composition)
4. Don't tell where blocks are (agent discovers via ls/cat)
"""
from __future__ import annotations

TASK_ID = "handdraw_hourglass"
DOMAIN = "Illustration"

# === Workspace files: Basic Elements (from hand-draw SKILL.md Part 1) ===

ELEMENTS = {
    "triangle.js": """\
// Basic Element: Triangle (outline-only)
// Usage: svg.appendChild(rc.polygon([[x1,y1], [x2,y2], [x3,y3]], outlineOpts))
//
// Example — upward-pointing triangle:
const outlineOpts = { stroke: INK, strokeWidth: 3.5, fill: 'none', roughness: 0.8 };
svg.appendChild(rc.polygon([[148, 52], [76, 182], [224, 178]], outlineOpts));

// Tips:
// - Offset vertices 2-6px from "perfect" positions for hand-drawn feel
// - Never use perfectly symmetric coordinates
""",
    "circle.js": """\
// Basic Element: Circle (outline or tiny filled dot)
// Usage: rc.circle(cx, cy, diameter, options)  — NOTE: diameter, not radius!
//
// Outline circle:
const outlineOpts = { stroke: INK, strokeWidth: 3.5, fill: 'none', roughness: 0.7 };
svg.appendChild(rc.circle(150, 150, 80, outlineOpts));

// Tiny filled dot (accent only, < 15px):
svg.appendChild(rc.circle(150, 150, 10, {
    stroke: INK, strokeWidth: 2, fill: INK, fillStyle: 'solid', roughness: 0.5
}));
""",
    "rectangle.js": """\
// Basic Element: Rectangle (outline-only)
// Usage: rc.rectangle(x, y, width, height, options)
//
const outlineOpts = { stroke: INK, strokeWidth: 3.5, fill: 'none', roughness: 0.7 };
svg.appendChild(rc.rectangle(72, 68, 158, 165, outlineOpts));
""",
    "line.js": """\
// Basic Element: Line
// Usage: rc.line(x1, y1, x2, y2, options)
//
const lineOpts = { stroke: INK, strokeWidth: 3.5, roughness: 0.8 };
svg.appendChild(rc.line(55, 210, 248, 85, lineOpts));

// Spark/detail line (thinner):
const sparkOpts = { stroke: INK, strokeWidth: 2.5, roughness: 0.8 };
svg.appendChild(rc.line(55, 58, 42, 42, sparkOpts));
""",
    "arc.js": """\
// Basic Element: Arc / Dome
// Usage: rc.path('M x1 y1 A rx ry rotation large-arc sweep x2 y2', options)
//
const arcOpts = { stroke: INK, strokeWidth: 4, fill: 'none', roughness: 0.8 };
svg.appendChild(rc.path('M 58 205 A 92 88 0 0 1 242 198', arcOpts));
""",
}

# === Example compositions (from SKILL.md Part 2) ===

EXAMPLES = {
    "diamond.html": """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Example: Diamond</title></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#e8dcc8;">
<svg id="art" viewBox="0 0 300 300" width="300" height="300" xmlns="http://www.w3.org/2000/svg"></svg>
<script src="https://unpkg.com/roughjs/bundled/rough.js"></script>
<script>
const INK = '#1a1a1a';
const svg = document.getElementById('art');
const rc = rough.svg(svg);

// Diamond = 2 x Triangle + spark Lines
// Composition: two triangles meeting at their bases
const outlineOpts = { stroke: INK, strokeWidth: 3.5, fill: 'none', roughness: 0.8 };
svg.appendChild(rc.polygon([[146, 42], [66, 148], [228, 155]], outlineOpts));   // top triangle
svg.appendChild(rc.polygon([[154, 262], [72, 152], [232, 148]], outlineOpts));  // bottom triangle

// Spark detail lines
const sparkOpts = { stroke: INK, strokeWidth: 2.5, roughness: 0.8 };
svg.appendChild(rc.line(55, 58, 42, 42, sparkOpts));
svg.appendChild(rc.line(48, 65, 34, 60, sparkOpts));
</script>
</body>
</html>
""",
    "seesaw.html": """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Example: Seesaw</title></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#e8dcc8;">
<svg id="art" viewBox="0 0 300 300" width="300" height="300" xmlns="http://www.w3.org/2000/svg"></svg>
<script src="https://unpkg.com/roughjs/bundled/rough.js"></script>
<script>
const INK = '#1a1a1a';
const svg = document.getElementById('art');
const rc = rough.svg(svg);

// Seesaw = Triangle (fulcrum) + Line (beam) + 2 x Circle (weights)
const outlineOpts = { stroke: INK, strokeWidth: 3.5, fill: 'none', roughness: 0.8 };
svg.appendChild(rc.polygon([[148, 218], [118, 258], [178, 260]], outlineOpts));  // fulcrum
svg.appendChild(rc.line(52, 195, 252, 162, { stroke: INK, strokeWidth: 3.5, roughness: 0.7 }));  // tilted beam
svg.appendChild(rc.circle(68, 172, 48, outlineOpts));   // heavy side — bigger
svg.appendChild(rc.circle(238, 140, 30, outlineOpts));   // light side — smaller
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
<script>
const INK = '#1a1a1a';
const WHITE = '#f0ebe0';

const svg = document.getElementById('art');
const rc = rough.svg(svg);

// === YOUR ILLUSTRATION CODE HERE ===
// Use basic elements from elements/ directory
// Study examples in examples/ directory for composition patterns

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

# === Task spec ===

SPEC_CONTENT = """\
# Task: Compose an HOURGLASS illustration

Using the basic elements in `elements/` and studying the example
compositions in `examples/`, create an hourglass illustration.

## Requirements
- Output file: `hourglass.html`
- Must use the HTML template from `template.html`
- Must use Rough.js (loaded via script tag)
- An hourglass is two triangles meeting at a point (one inverted)

## Hints
- Look at how diamond.html combines two triangles
- Offset vertices 2-6px from perfect positions for hand-drawn feel
- Keep it minimal: the best illustrations use 5-15 draw calls

Write the complete HTML file to `hourglass.html` in your workspace.
"""

# === Evaluation criteria ===

CRITERIA = [
    {
        "id": 1,
        "description": "Output file hourglass.html exists",
        "check_keywords": ["hourglass.html"],
        "check_type": "file_exists",
        "file_name": "hourglass.html",
    },
    {
        "id": 2,
        "description": "Uses Rough.js script tag",
        "check_keywords": ["rough.js", "roughjs"],
    },
    {
        "id": 3,
        "description": "Contains rc.polygon calls for triangles",
        "check_keywords": ["rc.polygon"],
    },
    {
        "id": 4,
        "description": "Contains at least 2 polygon/triangle shapes",
        "check_keywords": ["polygon"],
    },
    {
        "id": 5,
        "description": "Uses SVG element with viewBox",
        "check_keywords": ["viewBox"],
    },
    {
        "id": 6,
        "description": "Uses INK color constant (#1a1a1a)",
        "check_keywords": ["#1a1a1a", "INK"],
    },
    {
        "id": 7,
        "description": "Contains outline style (fill: 'none' or fill:'none')",
        "check_keywords": ["fill: 'none'", "fill:'none'", 'fill: "none"'],
    },
]
