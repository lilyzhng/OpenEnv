#!/usr/bin/env python3
"""Inline elements/*.js into hand-draw HTML files so they work standalone."""
import re
from pathlib import Path

ELEMENTS_JS = """
// === Inlined building block functions ===
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
function drawCircle(rc, svg, cx, cy, diameter, opts) {
  svg.appendChild(rc.circle(cx, cy, diameter, opts));
}
function drawDot(rc, svg, cx, cy, size, ink) {
  svg.appendChild(rc.circle(cx, cy, size, {
    stroke: ink, strokeWidth: 2, fill: ink, fillStyle: 'solid', roughness: 0.5
  }));
}
function drawRectangle(rc, svg, x, y, w, h, opts) {
  svg.appendChild(rc.rectangle(x, y, w, h, opts));
}
function drawLine(rc, svg, x1, y1, x2, y2, opts) {
  svg.appendChild(rc.line(x1, y1, x2, y2, opts));
}
function drawSpark(rc, svg, x, y, len, angle, ink) {
  const rad = angle * Math.PI / 180;
  svg.appendChild(rc.line(x, y, x + len*Math.cos(rad), y + len*Math.sin(rad), {
    stroke: ink, strokeWidth: 2.5, roughness: 0.8
  }));
}
function drawArc(rc, svg, x1, y1, x2, y2, rx, ry, opts) {
  svg.appendChild(rc.path('M '+x1+' '+y1+' A '+rx+' '+ry+' 0 0 1 '+x2+' '+y2, opts));
}
function drawCurve(rc, svg, points, opts) {
  svg.appendChild(rc.curve(points, opts));
}
function drawPath(rc, svg, pathData, opts) {
  svg.appendChild(rc.path(pathData, opts));
}
function drawEllipse(rc, svg, cx, cy, width, height, opts) {
  svg.appendChild(rc.ellipse(cx, cy, width, height, opts));
}
"""

html_dir = Path(__file__).parent.parent / "data" / "handdraw_v6" / "html"

for html_file in sorted(html_dir.glob("*.html")):
    content = html_file.read_text()

    # Remove all <script src="elements/..."> tags (including commented ones)
    content = re.sub(r'<!--\s*<script src="elements/[^"]*"></script>\s*-->\n?', '', content)
    content = re.sub(r'<script src="elements/[^"]*"></script>\n?', '', content)

    # Insert inlined functions right after the rough.js script tag
    rough_pattern = r'(<script src="https://[^"]*rough[^"]*"></script>)'
    content = re.sub(rough_pattern, r'\1\n<script>' + ELEMENTS_JS + '</script>', content)

    html_file.write_text(content)
    print(f"Inlined: {html_file.name} ({len(content)} bytes)")
