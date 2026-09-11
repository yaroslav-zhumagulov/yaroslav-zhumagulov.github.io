#!/usr/bin/env python3
"""Favicon: three hexagon layers in rhombohedral (ABC) stacking order.

Each layer is shifted by one bond length along the same direction, so the
centre of layer B sits on a vertex of A and the centre of C on a vertex of B,
which is the top view of ABC-stacked graphene.

    .venv/bin/python tools/make_favicon.py            # writes static/img/favicon.svg
"""
import math
import sys
from pathlib import Path

R = 14.5                       # hexagon circumradius (= bond length of the shift)
W = 3.4                        # stroke width
COLORS = ["#d62828", "#3b3f47", "#2f6fed"]   # A (back), B, C (front)
BG = "#ffffff"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "static/img/favicon.svg"

d = (math.cos(math.radians(30)), math.sin(math.radians(30)))   # shift direction: lower-right vertex
centres = [(32 + (k - 1) * R * d[0], 32 + (k - 1) * R * d[1]) for k in range(3)]


def hexagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(90 + 60 * i)), cy + r * math.sin(math.radians(90 + 60 * i))) for i in range(6)]


def path(P):
    return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in P) + " Z"


layers = "\n".join(f'<path d="{path(hexagon(cx, cy, R))}" stroke="{c}" stroke-width="{W}"/>' for (cx, cy), c in zip(centres, COLORS))
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="{BG}"/>
<g fill="none" stroke-linejoin="round" stroke-linecap="round">
{layers}
</g>
</svg>
'''
OUT.write_text(svg)
print("wrote", OUT)
