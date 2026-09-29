"""Typeset the formulas of index.html with LaTeX, in place.

Every formula is written as an element with a data-tex attribute (other
attributes may stand between class and data-tex):
    <span class="tex" data-tex="\\sigma_{xy}"></span>      inline (text style)
    <div class="eq" data-tex="H(\\mathbf k) = ..."></div>  display
The script runs latex once for all formulas and turns each one into an inline SVG
with dvisvgm. Glyphs become paths, so the page needs no maths fonts, and they take
the text colour, so both themes work. Glyph shapes are stored once, in a hidden SVG
at the end of the page. Needs latex and dvisvgm (any TeX Live); run it again after
editing a formula:
    python slides/render_latex.py
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PAGE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("index.html")
PATTERN = re.compile(r'<(span|div) class="(tex|eq)([^"]*)"((?: (?!data-tex=)[a-z-]+="[^"]*")*) data-tex="([^"]*)">.*?</\1>',
                     re.S)
GLYPHS = re.compile(r"\n?<!-- tex glyphs -->.*?<!-- /tex glyphs -->\n?", re.S)
PREAMBLE = r"""\documentclass[10pt]{article}
\usepackage{amsmath,amssymb,bm}
\hoffset=-1in \voffset=-1in
\newcommand\formula[2]{%
  \setbox0\hbox{$#2$}%
  \typeout{MATHBOX #1 \the\wd0\space\the\ht0\space\the\dp0}%
  \shipout\hbox{\special{papersize=\the\wd0,\the\dimexpr\ht0+\dp0\relax}\box0}}
\begin{document}
"""
EM = 10.0   # LaTeX font size in pt: 1 em of the formula = 1 em of the surrounding text


def typeset(formulas):
    """LaTeX + dvisvgm for [(tex, display), ...] -> (list of (svg text, wd, ht, dp) in pt, glyph paths)."""
    style = {True: r"\displaystyle ", False: ""}
    body = "".join(f"\\formula{{{i}}}{{{style[display]}{tex}}}\n" for i, (tex, display) in enumerate(formulas))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "f.tex").write_text(PREAMBLE + body + "\\end{document}\n")
        run = subprocess.run(["latex", "-interaction=nonstopmode", "-halt-on-error", "f.tex"], cwd=tmp,
                             capture_output=True, text=True)
        if run.returncode:
            sys.exit("latex failed:\n" + "\n".join(line for line in run.stdout.splitlines() if line.startswith("!"))
                     + "\n" + run.stdout[-1500:])
        boxes = {}
        for line in (tmp / "f.log").read_text(errors="replace").splitlines():
            if line.startswith("MATHBOX "):
                i, dims = line.split()[1], line.split(None, 2)[2]
                boxes[int(i)] = [float(v) for v in re.findall(r"(-?[\d.]+)pt", dims)]
        subprocess.run(["dvisvgm", "--no-fonts", "--bbox=papersize", "--page=1-", "--precision=3", "--optimize",
                        "-o", "f-%p.svg", "f.dvi"], cwd=tmp, capture_output=True, check=True)
        pages = sorted(tmp.glob("f-*.svg"), key=lambda p: int(re.search(r"(\d+)\.svg$", p.name).group(1)))
        if len(pages) != len(formulas):
            sys.exit(f"dvisvgm wrote {len(pages)} pages for {len(formulas)} formulas")
        glyphs, out = {}, []
        for i, page in enumerate(pages):
            svg = page.read_text()
            for gid, d in re.findall(r"<path id='([^']+)' d='([^']+)'/>", svg):
                glyphs[gid] = d
            view = re.search(r"viewBox='([^']+)'", svg).group(1)
            content = re.search(r"</defs>\s*(.*)</svg>", svg, re.S) or re.search(r"<svg[^>]*>\s*(.*)</svg>", svg, re.S)
            content = re.sub(r" id='page\d+'", "", content.group(1)).strip()
            content = re.sub(r"xlink:href='#", "href='#tx-", content).replace("'", '"')
            content = re.sub(r">\s+<", "><", content)
            out.append((view, content, *boxes[i]))
        return out, glyphs


def main():
    page = PAGE.read_text()
    matches = list(PATTERN.finditer(page))
    formulas = [(html.unescape(m.group(5)), m.group(1) == "div") for m in matches]
    rendered, glyphs = typeset(formulas)

    def svg(k):
        view, content, wd, ht, dp = rendered[k]
        style = f"width:{wd / EM:.4f}em;height:{(ht + dp) / EM:.4f}em;vertical-align:{-dp / EM:.4f}em"
        label = html.escape(formulas[k][0], quote=True)
        return (f'<svg class="tx" viewBox="{view}" style="{style}" fill="currentColor" role="img" '
                f'aria-label="{label}">{content}</svg>')

    counter = iter(range(len(matches)))

    def replace(m):
        tag, cls, extra, attrs, tex = m.groups()
        return f'<{tag} class="{cls}{extra}"{attrs} data-tex="{tex}">{svg(next(counter))}</{tag}>'

    page = GLYPHS.sub("", PATTERN.sub(replace, page))
    defs = "".join(f'<path id="tx-{gid}" d="{d}"/>' for gid, d in sorted(glyphs.items()))
    page = page.rstrip("\n") + ('\n<!-- tex glyphs --><svg width="0" height="0" style="position:absolute" '
                                f'aria-hidden="true"><defs>{defs}</defs></svg><!-- /tex glyphs -->\n')
    PAGE.write_text(page)
    print(f"typeset {len(matches)} formulas with LaTeX ({len(glyphs)} glyphs) in {PAGE.name}")


if __name__ == "__main__":
    main()
