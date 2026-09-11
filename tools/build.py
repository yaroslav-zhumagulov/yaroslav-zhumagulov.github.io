#!/usr/bin/env python3
"""Render the site into ./site from data/*.yml, data/publications.bib and templates/.

    .venv/bin/python tools/build.py          # build
    .venv/bin/python tools/build.py --serve  # build and serve on http://localhost:8000
"""
from __future__ import annotations

import datetime as dt
import html
import re
import shutil
import sys
from pathlib import Path

import bibtexparser
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site"
SELF = re.compile(r"zhumagulov", re.I)

VENUE_SHORT = {
    "Physical Review Letters": "Phys. Rev. Lett.",
    "Physical Review B": "Phys. Rev. B",
    "Physical Review Research": "Phys. Rev. Research",
    "Physical Review Materials": "Phys. Rev. Materials",
    "npj Computational Materials": "npj Comput. Mater.",
    "The Journal of Chemical Physics": "J. Chem. Phys.",
    "2D Materials": "2D Mater.",
    "Science Advances": "Sci. Adv.",
    "JETP Letters": "JETP Lett.",
    "Journal of Physics: Conference Series": "J. Phys.: Conf. Ser.",
    "Journal of Siberian Federal University. Mathematics & Physics": "J. Sib. Fed. Univ. Math. Phys.",
    "Physica B: Condensed Matter": "Physica B",
    "Review of Scientific Instruments": "Rev. Sci. Instrum.",
    "Crystallography Reports": "Crystallogr. Rep.",
    "arXiv preprint": "arXiv",
}


# --- text helpers -------------------------------------------------------------
def tex_to_html(s: str) -> str:
    """Minimal LaTeX-in-title -> HTML: sub/superscripts, \\text, --, \\&."""
    s = s.replace(r"\&", "&amp;").replace(r"\%", "%")
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)

    def math(m: re.Match) -> str:
        inner = m.group(1)
        inner = re.sub(r"_\{([^}]*)\}", r"<sub>\1</sub>", inner)
        inner = re.sub(r"\^\{([^}]*)\}", r"<sup>\1</sup>", inner)
        inner = re.sub(r"_(\S)", r"<sub>\1</sub>", inner)
        inner = re.sub(r"\^(\S)", r"<sup>\1</sup>", inner)
        return inner.replace("{", "").replace("}", "")

    s = re.sub(r"\$([^$]*)\$", math, s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("--", "\u2013")
    # bare chemical formulas that came through without $: MoS2, PtSe2, CrI3, WSe2, MoSe2, hBN-PbI2
    s = re.sub(r"\b(MoS|PtSe|CrI|WSe|MoSe|PbI|BaBiO|ZrZn|CaWO)\s?(\d)\b", r"\1<sub>\2</sub>", s)
    s = re.sub(r"\bFe3(Ge|Ga)Te2\b", r"Fe<sub>3</sub>\1Te<sub>2</sub>", s)
    return s


PARTICLES = {"de", "van", "von", "der", "da", "di", "al", "del", "la", "le"}


def short_name(full: str) -> str:
    """'Yaroslav V. Zhumagulov' -> 'Y. V. Zhumagulov'."""
    full = full.strip()
    if "," in full:  # 'Surname, Given'
        sur, given = [x.strip() for x in full.split(",", 1)]
        toks = given.split() + [sur]
    else:
        toks = full.split()
    if not toks:
        return full
    n_sur = 1
    if toks[-1].rstrip(".").lower() in {"junior", "jr"} and len(toks) > 2:
        n_sur = 2
    if len(toks) - n_sur - 1 >= 1 and toks[-n_sur - 1].lower() in PARTICLES:
        n_sur += 1
    given, sur = toks[:-n_sur], " ".join(toks[-n_sur:])
    initials = " ".join(
        "-".join(p[0] + "." for p in g.split("-") if p) for g in given if g and g[0].isalpha()
    )
    return f"{initials} {sur}".strip()


def format_authors(raw: str) -> tuple[str, list[str]]:
    names = [short_name(a) for a in raw.split(" and ")]
    parts = []
    for n in names:
        e = html.escape(n)
        parts.append(f"<b>{e}</b>" if SELF.search(n) else e)
    return ", ".join(parts), names


def bibtex_of(e: dict) -> str:
    fields = [
        ("title", e.get("title", "")),
        ("author", e.get("author", "")),
        ("journal", e.get("journal", "")),
        ("year", e.get("year", "")),
        ("volume", e.get("volume", "")),
        ("pages", e.get("pages", "")),
        ("doi", e.get("doi", "")),
    ]
    if e.get("eprint"):
        fields += [("eprint", e["eprint"]), ("archivePrefix", "arXiv")]
    body = "".join(f"  {k} = {{{v}}},\n" for k, v in fields if v)
    return f"@article{{{e['ID']},\n{body}}}"


# --- data loading -------------------------------------------------------------
def load_yaml(name: str):
    return yaml.safe_load((ROOT / "data" / name).read_text())


def load_pubs(groups: dict[str, dict]) -> list[dict]:
    parser = bibtexparser.bparser.BibTexParser(common_strings=True, ignore_nonstandard_types=False)
    entries = []
    for name in ("publications.bib", "publications_extra.bib"):
        f = ROOT / "data" / name
        if f.exists():
            parser = bibtexparser.bparser.BibTexParser(common_strings=True, ignore_nonstandard_types=False)
            entries += bibtexparser.loads(f.read_text(), parser=parser).entries
    pubs = []
    for e in entries:
        journal = e.get("journal", "")
        authors_html, names = format_authors(e.get("author", ""))
        g = groups.get(e.get("group", ""), {})
        year = int(e.get("year", 0))
        volume, pages = e.get("volume", ""), e.get("pages", "")
        venue_short = VENUE_SHORT.get(journal, journal)
        if journal == "arXiv preprint":
            ref = f"arXiv:{e.get('eprint', '')}"
            ref_short = f"arXiv {year}"
        else:
            ref = venue_short + (f" {volume}" if volume else "") + (f", {pages}" if pages else "") + f" ({year})"
            ref_short = f"{venue_short} {year}"
        pubs.append(
            {
                "key": e["ID"],
                "title": tex_to_html(e.get("title", "")),
                "title_plain": html.unescape(re.sub(r"<[^>]+>", "", tex_to_html(e.get("title", "")))),
                "authors_html": authors_html,
                "n_authors": len(names),
                "journal": journal,
                "venue_short": venue_short,
                "ref": ref,
                "ref_short": ref_short,
                "year": year,
                "doi": e.get("doi", ""),
                "arxiv": e.get("eprint", ""),
                "url": f"https://doi.org/{e['doi']}" if e.get("doi") else (f"https://arxiv.org/abs/{e['eprint']}" if e.get("eprint") else e.get("url", "")),
                "group": e.get("group", ""),
                "group_title": g.get("title", ""),
                "group_color": g.get("color", "#888"),
                "group_number": g.get("number", 0),
                "selected": e.get("selected") == "true",
                "first": e.get("firstauthor") == "true",
                "proceedings": e.get("proceedings") == "true",
                "citations": int(e.get("citations", 0) or 0),
                "abstract": html.escape(e.get("abstract", "")),
                "bibtex": bibtex_of(e),
                "preprint": journal == "arXiv preprint",
            }
        )
    pubs.sort(key=lambda p: (-p["year"], p["preprint"], p["proceedings"], p["key"]))
    return pubs


def main(serve: bool = False) -> None:
    profile = load_yaml("profile.yml")
    research = load_yaml("research.yml")
    software = load_yaml("software.yml")
    cv = load_yaml("cv.yml")

    groups = {g["slug"]: g for g in research["groups"]}
    pubs = load_pubs(groups)
    by_id = {}
    for p in pubs:
        by_id[p["key"].lower()] = p
        if p["arxiv"]:
            by_id[p["arxiv"]] = p
        if p["doi"]:
            by_id[p["doi"].lower()] = p

    unresolved = []
    for g in research["groups"]:
        g["n_papers"] = sum(1 for p in pubs if p["group"] == g["slug"])
        for pr in g["projects"]:
            pr["pubs"] = []
            for ref in pr.get("papers", []):
                p = by_id.get(str(ref).lower())
                if p and p not in pr["pubs"]:
                    pr["pubs"].append(p)
                elif p:
                    pass
                else:
                    unresolved.append(ref)
            pr["figure_exists"] = bool(pr.get("figure")) and (ROOT / pr["figure"]).exists()
            pr["anchor"] = re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", pr["title"]).lower()).strip("-")
    if unresolved:
        print("warning: unresolved paper references:", unresolved, file=sys.stderr)

    selected = [p for p in pubs if p["selected"]]
    stats = {
        "total": sum(1 for p in pubs if not p["proceedings"]),
        "first": sum(1 for p in pubs if p["first"] and not p["proceedings"]),
        "preprints": sum(1 for p in pubs if p["preprint"]),
        "proceedings": sum(1 for p in pubs if p["proceedings"]),
        "years": f"{min(p['year'] for p in pubs)}–{max(p['year'] for p in pubs)}",
        "citations": sum(p["citations"] for p in pubs),
    }
    years = sorted({p["year"] for p in pubs if not p["proceedings"]}, reverse=True)
    cv["pdf_exists"] = (ROOT / cv["pdf"]).exists()
    profile["photo_exists"] = (ROOT / profile["photo"]).exists()
    profile["same_as"] = [l["href"] for l in profile["links"] if not l["href"].startswith("mailto")]

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    ctx = dict(
        profile=profile, research=research, software=software, cv=cv, pubs=pubs, selected=selected,
        stats=stats, years=years, groups=research["groups"], now=dt.date.today(), build_year=dt.date.today().year,
    )

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    (OUT / ".nojekyll").write_text("")
    if (ROOT / "root").exists():  # files served from the site root, e.g. search-engine verification
        for f in (ROOT / "root").iterdir():
            if f.is_file():
                shutil.copy(f, OUT / f.name)

    pages = [
        ("index.html", "index.html", "home"),
        ("research.html", "research/index.html", "research"),
        ("publications.html", "publications/index.html", "publications"),
        ("software.html", "software/index.html", "software"),
        ("cv.html", "cv/index.html", "cv"),
        ("404.html", "404.html", "404"),
    ]
    for tpl, out, page in pages:
        dest = OUT / out
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(env.get_template(tpl).render(page=page, **ctx))

    base = profile["url"].rstrip("/")
    urls = [base + "/"] + [base + "/" + out.rsplit("/", 1)[0] + "/" for _, out, _ in pages[1:-1]]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{dt.date.today()}</lastmod><changefreq>monthly</changefreq><priority>{'1.0' if u.endswith('.io/') else '0.8'}</priority></url>\n" for u in urls)
        + "</urlset>\n"
    )
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    print(f"built {len(pages)} pages, {len(pubs)} publications -> {OUT.relative_to(ROOT)}/")

    if serve:
        import functools
        import http.server

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
        print("serving on http://localhost:8000  (Ctrl-C to stop)")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()


if __name__ == "__main__":
    main(serve="--serve" in sys.argv)
