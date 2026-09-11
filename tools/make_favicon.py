#!/usr/bin/env python3
"""Favicon: three overlapping hexagons in a triangle (red top, grey lower-left, blue lower-right).

    .venv/bin/python tools/make_favicon.py            # writes static/img/favicon.svg
"""
import math
import sys
from pathlib import Path

R = 16.0                       # hexagon circumradius
W = 3.4                        # stroke width
CENTRES = [(32, 28), (26, 36), (38, 36)]
COLORS = ["#d62828", "#3b3f47", "#2f6fed"]   # draw order: red, grey, blue (blue on top)
BG = "#ffffff"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "static/img/favicon.svg"


def hexagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(90 + 60 * i)), cy + r * math.sin(math.radians(90 + 60 * i))) for i in range(6)]


def path(P):
    return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in P) + " Z"


layers = "\n".join(f'<path d="{path(hexagon(cx, cy, R))}" stroke="{c}" stroke-width="{W}"/>' for (cx, cy), c in zip(CENTRES, COLORS))
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="{BG}"/>
<g fill="none" stroke-linejoin="round" stroke-linecap="round">
{layers}
</g>
</svg>
'''
OUT.write_text(svg)
print("wrote", OUT)
