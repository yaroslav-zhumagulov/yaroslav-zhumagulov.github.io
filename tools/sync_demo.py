#!/usr/bin/env python3
"""Copy a demo repository into demos/<name>/; build.py publishes only its slides, at /demos/<name>/slides/.

    .venv/bin/python tools/sync_demo.py ~/GitLab/wannier-berri-demo nm4qm-2026
    .venv/bin/python tools/sync_demo.py <repository>          # name = the repository's folder name

Takes the last commit of the repository (git archive HEAD: tracked files only, so no local edits
and no DFT output). If the demo has slides/index.html, a page fragment as published on claude.ai,
it becomes a complete page: site icon, canonical URL, description from the talk in data/talks.yml
whose `demo` is <name>, and the IBM Plex fonts from static/fonts/plex/ instead of Google Fonts, so
the slides make no third-party requests, like the rest of the site.
"""
from __future__ import annotations

import html
import io
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GOOGLE_FONTS = re.compile(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts\.(?:googleapis|gstatic)\.com[^"]*"[^>]*>\n?')
CHARSET = '<meta charset="utf-8">\n'


def slides_page(fragment: str, name: str, commit: str) -> str:
    profile = yaml.safe_load((ROOT / "data/profile.yml").read_text())
    talks = yaml.safe_load((ROOT / "data/talks.yml").read_text())["talks"]
    talk = next((t for t in talks if t.get("demo") == name), {})
    summary = " ".join(talk.get("summary", f"Slides of {name}").split())
    if not fragment.startswith(CHARSET):
        sys.exit("slides/index.html: expected a page fragment that starts with <meta charset=\"utf-8\">")
    fragment = GOOGLE_FONTS.sub("", fragment)
    head = (
        CHARSET
        + '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + f'<meta name="description" content="{html.escape(summary)}">\n'
        + f'<meta name="author" content="{html.escape(profile["name"])}">\n'
        + f'<link rel="canonical" href="{profile["url"].rstrip("/")}/demos/{name}/slides/">\n'
        + '<link rel="icon" href="/static/img/favicon.svg" type="image/svg+xml">\n'
        + '<link rel="stylesheet" href="../../../static/fonts/plex/fonts.css">\n'
        + f"<!-- {name} {commit}, copied by tools/sync_demo.py -->\n"
    )
    return '<!DOCTYPE html>\n<html lang="en">\n' + head + fragment[len(CHARSET):]


def main(repo: Path, name: str) -> None:
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], check=True,
                            capture_output=True, text=True).stdout.strip()
    archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", "HEAD"], check=True,
                             capture_output=True).stdout
    dest = ROOT / "demos" / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter="data")
    slides = dest / "slides/index.html"
    if slides.exists():
        slides.write_text(slides_page(slides.read_text(), name, commit))
    n = sum(1 for f in dest.rglob("*") if f.is_file())
    print(f"{repo} @ {commit} -> {dest.relative_to(ROOT)}/  ({n} files; slides published at /demos/{name}/slides/)")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    repo = Path(sys.argv[1]).expanduser().resolve()
    main(repo, sys.argv[2] if len(sys.argv) == 3 else repo.name)
