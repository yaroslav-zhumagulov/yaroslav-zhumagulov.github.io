#!/usr/bin/env python3
"""Copy a demo repository into the site: the demo to demos/<name>/, its slides to talks/<name>/.

    .venv/bin/python tools/sync_demo.py ~/GitLab/wannier-berri-demo nm4qm-2026

Takes the last commit of the repository (git archive HEAD: tracked files only, so no local edits
and no DFT output).

demos/<name>/ is the public copy for people who want to run the demo, browsable on GitHub and not
published on the site. It leaves out slides/ and everything that points to the slides: the
"## Slides" section and the slides/ line of the README, and the "*Slides …*" lines under the
notebook headings.

talks/<name>/ is published at /talks/<name>/: the slides page, its figures and the PDF (as
<name>.pdf). The page, a fragment as published on claude.ai, becomes a complete page with the site
icon, a canonical URL, the description of talk <name> from data/talks.yml, and the IBM Plex fonts
from static/fonts/plex/ instead of Google Fonts, so it makes no third-party requests.
"""
from __future__ import annotations

import html
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GOOGLE_FONTS = re.compile(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts\.(?:googleapis|gstatic)\.com[^"]*"[^>]*>\n?')
CHARSET = '<meta charset="utf-8">\n'
SLIDES_LINE = re.compile(r"^\*Slides? .*\*$")


def slides_page(fragment: str, name: str, commit: str) -> str:
    profile = yaml.safe_load((ROOT / "data/profile.yml").read_text())
    talk = next((t for t in yaml.safe_load((ROOT / "data/talks.yml").read_text())["talks"] if t["slug"] == name), {})
    summary = " ".join(talk.get("summary", f"Slides of {name}").split())
    if not fragment.startswith(CHARSET):
        sys.exit("slides/index.html: expected a page fragment that starts with <meta charset=\"utf-8\">")
    head = (
        CHARSET
        + '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + f'<meta name="description" content="{html.escape(summary)}">\n'
        + f'<meta name="author" content="{html.escape(profile["name"])}">\n'
        + f'<link rel="canonical" href="{profile["url"].rstrip("/")}/talks/{name}/">\n'
        + '<link rel="icon" href="/static/img/favicon.svg" type="image/svg+xml">\n'
        + '<link rel="stylesheet" href="../../static/fonts/plex/fonts.css">\n'
        + f"<!-- {name}, from commit {commit} of the demo repository, copied by tools/sync_demo.py -->\n"
    )
    return '<!DOCTYPE html>\n<html lang="en">\n' + head + GOOGLE_FONTS.sub("", fragment)[len(CHARSET):]


def without_slides(demo: Path) -> None:
    """Drop what points to the slides from the public copy."""
    readme = demo / "README.md"
    if readme.exists():
        text = readme.read_text()
        text = re.sub(r"\n## Slides\n.*?(?=\n## )", "\n", text, flags=re.S)
        text = re.sub(r"^slides/ .*\n", "", text, flags=re.M)
        readme.write_text(text)
    for nb in demo.rglob("*.ipynb"):
        notebook = json.loads(nb.read_text())
        for cell in notebook["cells"]:
            if cell["cell_type"] == "markdown":
                lines = "".join(cell["source"]).split("\n")
                cell["source"] = "\n".join(l for l in lines if not SLIDES_LINE.match(l)).splitlines(keepends=True)
        nb.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
    left = [str(f.relative_to(demo)) for f in demo.rglob("*")
            if f.is_file() and f.suffix in {".md", ".ipynb", ".py", ".sh"} and re.search("slide", f.read_text(errors="ignore"), re.I)]
    if left:
        print("note: the public copy still mentions slides in", ", ".join(left), file=sys.stderr)


def main(repo: Path, name: str) -> None:
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], check=True,
                            capture_output=True, text=True).stdout.strip()
    archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", "HEAD"], check=True,
                             capture_output=True).stdout
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(src, filter="data")

        talk = ROOT / "talks" / name
        if talk.exists():
            shutil.rmtree(talk)
        slides = src / "slides"
        if (slides / "index.html").exists():
            talk.mkdir(parents=True)
            (talk / "index.html").write_text(slides_page((slides / "index.html").read_text(), name, commit))
            shutil.copytree(slides / "figures", talk / "figures", ignore=shutil.ignore_patterns("*.json"))
            pdfs = sorted(slides.glob("*.pdf"))
            if len(pdfs) == 1:
                shutil.copy(pdfs[0], talk / f"{name}.pdf")
        if slides.exists():
            shutil.rmtree(slides)

        demo = ROOT / "demos" / name
        if demo.exists():
            shutil.rmtree(demo)
        shutil.copytree(src, demo)
        without_slides(demo)
    n = sum(1 for f in demo.rglob("*") if f.is_file())
    print(f"{repo} @ {commit} -> demos/{name}/ ({n} files) and talks/{name}/ (published at /talks/{name}/)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).expanduser().resolve(), sys.argv[2])
