#!/usr/bin/env python3
"""Favicon: three hexagons in rhombohedral (ABC) stacking, top view, triangular layout.

Layer A is centred on a hollow site H, layer B on an A-sublattice vertex of that
hexagon (lower-left vertex, 150 deg in SVG coordinates) and layer C on a B-sublattice vertex (straight below, 90 deg).
The three centres form an equilateral triangle with side = bond length, and each
centre sits on a vertex of the other two hexagons, exactly as in ABC graphene.

    .venv/bin/python tools/make_favicon.py            # writes static/img/favicon.svg
"""
import math
import sys
from pathlib import Path

R = 15.0                       # hexagon circumradius = bond length
W = 3.4                        # stroke width
COLORS = ["#d62828", "#3b3f47", "#2f6fed"]   # A (red), B (grey), C (blue); drawn in this order
BG = "#ffffff"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "static/img/favicon.svg"

# SVG coordinates: y grows downwards, angles measured clockwise from +x
H = (32 + R * math.cos(math.radians(30)) / 2, 32 - R / 2)   # chosen so the bounding box is centred
ROT = 60                       # rotate the triangle of centres (degrees, clockwise on screen); hexagons keep orientation
ROT_ALL = 30                   # rotate the whole picture, hexagons included, about the canvas centre
shifts = [(0, 0), (R * math.cos(math.radians(150)), R * math.sin(math.radians(150))), (0, R)]
centres = [(H[0] + dx, H[1] + dy) for dx, dy in shifts]
# rotate about the triangle centroid, then re-centre the bounding box in the 64x64 canvas
gx, gy = sum(c[0] for c in centres) / 3, sum(c[1] for c in centres) / 3
ca, sa = math.cos(math.radians(ROT)), math.sin(math.radians(ROT))
centres = [(gx + (x - gx) * ca - (y - gy) * sa, gy + (x - gx) * sa + (y - gy) * ca) for x, y in centres]
hw = R * math.cos(math.radians(30))
xs = [x for x, _ in centres]; ys = [y for _, y in centres]
ox, oy = 32 - (min(xs) - hw + max(xs) + hw) / 2, 32 - (min(ys) - R + max(ys) + R) / 2
centres = [(x + ox, y + oy) for x, y in centres]


def hexagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(90 + 60 * i)), cy + r * math.sin(math.radians(90 + 60 * i))) for i in range(6)]


def path(P):
    return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in P) + " Z"


layers = "\n".join(f'<path d="{path(hexagon(cx, cy, R))}" stroke="{c}" stroke-width="{W}"/>' for (cx, cy), c in zip(centres, COLORS))
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="{BG}"/>
<g fill="none" stroke-linejoin="round" stroke-linecap="round" transform="rotate({ROT_ALL} 32 32)">
{layers}
</g>
</svg>
'''
OUT.write_text(svg)
print("wrote", OUT, [(round(x, 1), round(y, 1)) for x, y in centres])
