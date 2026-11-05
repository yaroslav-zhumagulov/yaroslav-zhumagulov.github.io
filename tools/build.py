#!/usr/bin/env python3
"""Render the site into ./site from data/*.yml, data/publications.bib and templates/.

    .venv/bin/python tools/build.py          # build
    .venv/bin/python tools/build.py --serve  # build and serve on http://localhost:8000
"""
from __future__ import annotations

import datetime as dt
import html
import json
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
SELF_NAME = "Yaroslav Zhumagulov"  # sources spell him Y., Yaroslav V., Iaroslav; the site, once

VENUE_SHORT = {
    "Physical Review Letters": "Phys. Rev. Lett.",
    "Physical Review B": "Phys. Rev. B",
    "Physical Review Research": "Phys. Rev. Research",
    "Physical Review Materials": "Phys. Rev. Materials",
    "npj Computational Materials": "npj Comput. Mater.",
    "The Journal of Chemical Physics": "J. Chem. Phys.",
    "2D Materials": "2D Mater.",
    "Applied Physics Letters": "Appl. Phys. Lett.",
    "Science Advances": "Sci. Adv.",
    "Nature Communications": "Nat. Commun.",
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
    s = html.escape(s.replace(r"\&", "&").replace(r"\%", "%"), quote=False)  # never trust upstream markup
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


def safe_url(u: str) -> str:
    """Only http(s) URLs are allowed to reach an href."""
    return u if re.match(r"^https?://", u or "") else ""


PARTICLES = {"de", "van", "von", "der", "da", "di", "al", "del", "la", "le"}


def split_name(full: str) -> tuple[str, str]:
    """'Yaroslav V. Zhumagulov' -> ('Yaroslav V.', 'Zhumagulov'); 'Surname, Given' is read too."""
    full = full.strip()
    if "," in full:
        sur, given = [x.strip() for x in full.split(",", 1)]
        toks = given.split() + [sur]
    else:
        toks = full.split()
    if not toks:
        return "", full
    n_sur = 1
    if toks[-1].rstrip(".").lower() in {"junior", "jr"} and len(toks) > 2:
        n_sur = 2
    if len(toks) - n_sur - 1 >= 1 and toks[-n_sur - 1].lower() in PARTICLES:
        n_sur += 1
    return " ".join(toks[:-n_sur]), " ".join(toks[-n_sur:])


def short_name(full: str) -> str:
    """'Yaroslav V. Zhumagulov' -> 'Y. V. Zhumagulov'."""
    given, sur = split_name(full)
    initials = " ".join(
        "-".join(p[0] + "." for p in g.split("-") if p)
        for g in given.split() if g and g[0].isalpha()
    )
    return f"{initials} {sur}".strip()


def format_authors(raw: str) -> tuple[str, list[str]]:
    """Co-authors as initials, the site's owner in full: one spelling for readers and for search."""
    names = [SELF_NAME if SELF.search(a) else short_name(a) for a in raw.split(" and ")]
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


def plain(s: str) -> str:
    """Rendered HTML back to the plain text an agent or a Markdown file wants."""
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


# --- machine-readable exports -------------------------------------------------
def csl_json(pubs: list[dict]) -> str:
    """The publication list as CSL-JSON, for reference managers and machine readers."""
    items = []
    for p in pubs:
        item = {
            "id": p["key"],
            "type": "article" if p["preprint"] else "article-journal",
            "title": p["title_plain"],
            "author": [{"given": g, "family": f} for g, f in map(split_name, p["authors_full"])],
            "issued": {"date-parts": [[int(x) for x in p["date"].split("-") if x.isdigit()]]},
            "URL": p["url"],
        }
        for key, value in (
            ("container-title", "" if p["preprint"] else p["journal"]),
            ("volume", p["volume"]),
            ("page", p["pages"]),
            ("DOI", p["doi"]),
            ("number", f"arXiv:{p['arxiv']}" if p["arxiv"] else ""),
        ):
            if value:
                item[key] = value
        items.append(item)
    return json.dumps(items, indent=1, ensure_ascii=False) + "\n"


def jsonld_nodes(page: str, profile: dict, pubs: list[dict], software: dict) -> str:
    """The page's own schema.org nodes, serialised for the @graph that base.html opens.

    Both lists carry the author's @id, so a paper and a package resolve to the same Person
    node as the profile does.
    """
    base, person = profile["url"].rstrip("/"), {"@id": profile["url"].rstrip("/") + "/#person"}
    nodes: list[dict] = []
    if page == "publications":
        for p in pubs:
            node = {
                "@type": "ScholarlyArticle",
                "@id": f"{base}/publications/#{p['key']}",
                "name": p["title_plain"],
                "author": [
                    dict({"@type": "Person", "name": a}, **(person if SELF.search(a) else {}))
                    for a in p["authors_full"]
                ],
                "datePublished": p["date"],
                "url": p["url"],
            }
            ids = [{"@type": "PropertyValue", "propertyID": k, "value": v}
                   for k, v in (("DOI", p["doi"]), ("arXiv", p["arxiv"])) if v]
            if ids:
                node["identifier"] = ids
            if not p["preprint"]:
                node["isPartOf"] = {"@type": "Periodical", "name": p["journal"]}
                if p["volume"]:
                    node["volumeNumber"] = p["volume"]
                if p["pages"]:
                    node["pagination"] = p["pages"]
            nodes.append(node)
        nodes.append({
            "@type": "ItemList",
            "@id": f"{base}/publications/#list",
            "name": f"Publications of {profile['name']}",
            "numberOfItems": len(pubs),
            "itemListElement": [{"@type": "ListItem", "position": i, "url": n["@id"]}
                                for i, n in enumerate(nodes, 1)],
        })
    elif page == "software":
        for s in software["projects"]:
            role = "contributor" if s["status"] == "contributor" else "author"
            node = {
                "@type": "SoftwareSourceCode",
                "@id": f"{base}/software/#{s['slug']}",
                "name": s["name"],
                "description": plain(s["tagline"] + " " + s["description"]),
                role: person,
                "programmingLanguage": s["stack"],
            }
            hrefs = [link["href"] for link in s.get("links", [])]
            repo = next((h for h in hrefs if "github.com" in h), "")
            cite = next((h for h in hrefs if "arxiv.org" in h), "")
            if repo:
                node["codeRepository"] = repo
            if cite:
                node["citation"] = cite
            nodes.append(node)
    return "".join(",\n    " + json.dumps(n, ensure_ascii=False) for n in nodes)


def llms_txt(profile: dict, research: dict, software: dict, pubs: list[dict], stamp: str) -> str:
    """The whole site as one Markdown file at /llms.txt, for agents that read rather than browse."""
    base = profile["url"].rstrip("/")
    out = [
        f"# {profile['name']}",
        "",
        f"> {profile['title']} at {profile['institution']}, {profile['group']}, "
        f"{profile['location']}. {' '.join(profile['tagline'].split())} "
        f"The same person is published as {', '.join(profile['alt_names'])}.",
        "",
    ]
    out += [f"- {link['label']}: {link['href'].replace('mailto:', '')}" for link in profile["links"]]
    out += [f"- Updated: {stamp[:10]}", "", "## Pages", ""]
    out += [
        f"- [Research]({base}/research/): {len(research['groups'])} subgroups, "
        f"{sum(len(g['projects']) for g in research['groups'])} projects, each with its papers",
        f"- [Publications]({base}/publications/): all {len(pubs)} papers with DOI and arXiv links",
        f"- [Software]({base}/software/): {', '.join(s['name'] for s in software['projects'])}",
        f"- [Talks]({base}/talks/): slides and hands-on material",
        f"- [CV]({base}/cv/): positions, education, awards",
        "",
        "## About",
        "",
    ]
    out += [" ".join(p.split()) + "\n" for p in profile["bio"]]
    out += ["## Research", ""]
    for g in research["groups"]:
        out += [f"### {g['number']:02d} {plain(g['title'])}", "", " ".join(g["lede"].split()), ""]
        for pr in g["projects"]:
            papers = ", ".join(
                f"arXiv:{p['arxiv']}" if p["preprint"]
                else f"{p['venue_short']} {p['year']}, doi:{p['doi']}"
                for p in pr["pubs"]
            )
            cite = f" ({papers})" if papers else ""
            out.append(f"- **{plain(pr['title'])}** — {plain(pr['summary'])}{cite}")
        out.append("")
    out += ["## Software", ""]
    for s in software["projects"]:
        links = ", ".join(f"{link['label']}: {link['href']}" for link in s.get("links", []))
        out.append(f"- **{s['name']}** ({s['status_text']}) — {plain(s['tagline'])} {links}")
    span = f"{min(p['year'] for p in pubs)}–{max(p['year'] for p in pubs)}"
    out += ["", f"## Publications ({len(pubs)}, {span})", ""]
    for p in pubs:
        ident = (f"arXiv:{p['arxiv']}" if p["preprint"]
                 else f"doi:{p['doi']}" if p["doi"] else p["ref"])
        out.append(f'- {p["date"]}. {p["authors_plain"]}. "{p["title_plain"]}". '
                   f'{p["ref"]}. {ident}. {p["url"]}')
    out += [
        "",
        "## Machine-readable",
        "",
        f"- BibTeX of every paper: {base}/publications.bib",
        f"- The same list as CSL-JSON: {base}/publications.json",
        f"- Sitemap: {base}/sitemap.xml",
        "",
    ]
    return "\n".join(out)


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
        journal = e.get("journal", "").replace(r"\&", "&")
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
                "authors_plain": ", ".join(names),
                "authors_full": [a.strip() for a in e.get("author", "").split(" and ") if a],
                "n_authors": len(names),
                "journal": journal,
                "venue_short": venue_short,
                "volume": volume,
                "pages": pages,
                "ref": ref,
                "ref_short": ref_short,
                "year": year,
                "date": e.get("date", "") or f"{year}-12-31",  # year-only entries sort last within their year
                "doi": e.get("doi", ""),
                "arxiv": e.get("eprint", ""),
                "url": f"https://doi.org/{e['doi']}" if e.get("doi") else (f"https://arxiv.org/abs/{e['eprint']}" if e.get("eprint") else safe_url(e.get("url", ""))),
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
    pubs.sort(key=lambda p: (p["date"], p["key"]), reverse=True)
    return pubs


def main(serve: bool = False) -> None:
    profile = load_yaml("profile.yml")
    research = load_yaml("research.yml")
    software = load_yaml("software.yml")
    cv = load_yaml("cv.yml")
    talks = load_yaml("talks.yml")

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
    links = profile["links"]
    profile["same_as"] = [link["href"] for link in links if not link["href"].startswith("mailto")]
    profile["orcid"] = next((link["href"] for link in links if link["label"] == "ORCID"), "")

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    ctx = dict(
        profile=profile, research=research, software=software, cv=cv, talks=talks, pubs=pubs, selected=selected,
        stats=stats, years=years, groups=research["groups"], now=dt.date.today(), build_time=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), build_year=dt.date.today().year,
    )

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    (OUT / ".nojekyll").write_text("")
    token = profile.get("google_site_verification")
    if token:  # Google Search Console checks that this file exists at the site root
        (OUT / f"{token}.html").write_text(f"google-site-verification: {token}.html")

    pages = [
        ("index.html", "index.html", "home"),
        ("research.html", "research/index.html", "research"),
        ("publications.html", "publications/index.html", "publications"),
        ("software.html", "software/index.html", "software"),
        ("talks.html", "talks/index.html", "talks"),
        ("cv.html", "cv/index.html", "cv"),
        ("404.html", "404.html", "404"),
    ]
    for tpl, out, page in pages:
        dest = OUT / out
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(env.get_template(tpl).render(
            page=page, jsonld_extra=jsonld_nodes(page, profile, pubs, software), **ctx
        ))

    for t in talks["talks"]:  # only the slides of a demo are published; the rest stays in the repository
        if t.get("demo"):
            src, dst = ROOT / "demos" / t["demo"] / "slides", OUT / "demos" / t["demo"] / "slides"
            if not (src / "index.html").exists():
                print(f"warning: no slides in {src.relative_to(ROOT)}/", file=sys.stderr)
                continue
            dst.mkdir(parents=True)
            shutil.copy(src / "index.html", dst)
            shutil.copytree(src / "figures", dst / "figures", ignore=shutil.ignore_patterns("*.json"))
            for pdf in src.glob("*.pdf"):
                shutil.copy(pdf, dst)

    base = profile["url"].rstrip("/")
    stamp = ctx["build_time"]
    urls = [base + "/"] + [base + "/" + out.rsplit("/", 1)[0] + "/" for _, out, _ in pages[1:-1]]
    urls += [base + t["slides"] for t in talks["talks"] if t.get("slides")]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{stamp}</lastmod><changefreq>monthly</changefreq><priority>{'1.0' if u.endswith('.io/') else '0.8'}</priority></url>\n" for u in urls)
        + "</urlset>\n"
    )
    # the wildcard already allows them; naming the answer engines records that this is deliberate
    agents = ["*", "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
              "anthropic-ai", "PerplexityBot", "Perplexity-User", "Google-Extended",
              "Applebot-Extended", "CCBot", "Amazonbot", "Bytespider", "Meta-ExternalAgent"]
    (OUT / "robots.txt").write_text(
        "".join(f"User-agent: {a}\nAllow: /\n\n" for a in agents) + f"Sitemap: {base}/sitemap.xml\n"
    )
    (OUT / "publications.bib").write_text("\n\n".join(p["bibtex"] for p in pubs) + "\n")
    (OUT / "publications.json").write_text(csl_json(pubs))
    (OUT / "llms.txt").write_text(llms_txt(profile, research, software, pubs, stamp))
    print(f"built {len(pages)} pages, {len(pubs)} publications -> {OUT.relative_to(ROOT)}/")

    if serve:
        import functools
        import http.server

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
        print("serving on http://localhost:8000  (Ctrl-C to stop)")
        http.server.ThreadingHTTPServer(("127.0.0.1", 8000), handler).serve_forever()


if __name__ == "__main__":
    main(serve="--serve" in sys.argv)
