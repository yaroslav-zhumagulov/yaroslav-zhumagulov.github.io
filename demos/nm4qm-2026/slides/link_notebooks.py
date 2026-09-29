"""Put links to the slides under the step headings of the notebooks, in place.

Each step of graphene.ipynb and mnte.ipynb (and of their executed copies in
reference/) gets a line such as  *Slides [12–13](...#s8)*  under its heading.
Slide numbers follow the order of the slides in index.html, so run this again
after adding or moving slides:
    python slides/link_notebooks.py
Only markdown cells change; code cells and outputs are left as they are.
The slides link back to the notebook steps through the pills in their headers.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLIDES_URL = "https://yaroslav-zhumagulov.github.io/demos/nm4qm-2026/slides/"   # the copy on the personal website
# heading of a notebook section -> ids of the slides that go with it
LINKS = {
    "graphene.ipynb": {
        "# Act 1": ["a1", "s6", "s7", "s8", "s9", "s10"],
        "## Step 1": ["s6"],
        "## Step 2": ["s5", "w1", "s6"],
        "## Step 3": ["s7"],
        "## Step 4": ["s8", "s9"],
        "## Step 5": ["s10"],
        "## Bonus 6": ["b1"],
        "## Bonus 7": ["s10", "b3"],
    },
    "mnte.ipynb": {
        "# Act 2": ["a2", "s11", "s12", "s13", "s14", "s15", "s16", "s17"],
        "## Step 1": ["s11", "s12"],
        "## Step 2": ["s12"],
        "## Step 3": ["s13"],
        "## Step 4": ["s14"],
        "## Step 5": ["s15"],
        "## Step 6": ["s16", "s17"],
        "## Bonus 7": ["s11", "b2"],
    },
}
NOTEBOOKS = ["01_graphene/graphene.ipynb", "02_mnte/mnte.ipynb", "reference/graphene.ipynb", "reference/mnte.ipynb"]
OLD_LINE = re.compile(r"^\*Slides? .*\*$")


def slide_numbers():
    ids = re.findall(r'<article class="slide-wrap[^"]*" id="([^"]+)"', (ROOT / "slides/index.html").read_text())
    return {sid: i + 1 for i, sid in enumerate(ids)}


def slides_line(ids, number):
    """'*Slides [12–13](url#s8), [27](url#b1)*': consecutive slides are joined into one link."""
    runs = []
    for sid in sorted(ids, key=number.get):
        if runs and number[sid] == number[runs[-1][-1]] + 1:
            runs[-1].append(sid)
        else:
            runs.append([sid])
    links = [f"[{number[r[0]]}{'–' + str(number[r[-1]]) if len(r) > 1 else ''}]({SLIDES_URL}#{r[0]})" for r in runs]
    word = "Slide" if len(ids) == 1 else "Slides"
    return f"*{word} {', '.join(links)}*"


def link(notebook, sections, number):
    """Add or refresh the slides line under each heading of `notebook` (a dict); returns how many."""
    n = 0
    for cell in notebook["cells"]:
        if cell["cell_type"] != "markdown":
            continue
        lines = "".join(cell["source"]).split("\n")
        for prefix, ids in sections.items():
            if lines and (lines[0] == prefix or lines[0].startswith(prefix + " ")):
                rest = lines[1:]
                while rest and (not rest[0].strip() or OLD_LINE.match(rest[0])):
                    rest = rest[1:]
                lines = [lines[0], slides_line(ids, number), ""] + rest
                n += 1
        text = "\n".join(lines)
        cell["source"] = text.splitlines(keepends=True)
    return n


def main():
    number = slide_numbers()
    for path in NOTEBOOKS:
        path = ROOT / path
        notebook = json.loads(path.read_text())
        n = link(notebook, LINKS[path.name], number)
        path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
        print(f"{path.relative_to(ROOT)}: {n} sections linked")


if __name__ == "__main__":
    sys.exit(main())
