#!/usr/bin/env python3
"""Build data/publications.bib from OpenAlex + arXiv.

Run once (or whenever a new paper appears):

    .venv/bin/python tools/fetch_pubs.py

The script merges the OpenAlex record (DOI, venue, volume/pages, citations)
with the arXiv record (arXiv id, author list as printed) by normalised title,
drops errata / abstracts / repository duplicates, and tags every paper with a
research subgroup from the GROUPS table below.  Unmapped papers are reported
so the table can be extended.  The bib file is the single source of truth for
the site; hand edits survive re-runs only if you also update GROUPS.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "publications.bib"

OPENALEX_AUTHOR = "A5006511863"
ARXIV_QUERY = "au:Zhumagulov"
SELF = re.compile(r"zhumagulov", re.I)

# --- subgroup assignment -----------------------------------------------------
# key: arXiv id (without version) or DOI suffix (lower-case); value: (group, selected)
GROUPS: dict[str, tuple[str, bool]] = {
    # 1 correlated phases in multilayer graphene
    "2305.14277": ("graphene", True),
    "2307.16025": ("graphene", False),
    "2403.17140": ("graphene", False),
    "2508.14630": ("graphene", True),
    "2509.24672": ("graphene", False),
    "2111.06369": ("graphene", False),
    # 2 excitons, trions and polaritons
    "2002.08938": ("excitons", True),
    "2005.09306": ("excitons", False),
    "2104.11800": ("excitons", False),
    "10.3390/nano12213728": ("excitons", False),
    "2107.06927": ("excitons", True),
    "2109.11633": ("excitons", False),
    "10.1039/d2nr00315e": ("excitons", False),
    "2306.01483": ("excitons", False),
    "2303.15325": ("excitons", False),
    "2208.12228": ("excitons", False),
    "2304.00331": ("excitons", False),
    "2205.15221": ("excitons", False),
    # 3 first-principles methods
    "2607.25690": ("methods", True),
    "2604.06441": ("methods", False),
    "2608.05788": ("methods", False),
    "1908.10941": ("methods", False),
    "10.1103/physrevb.100.241109": ("methods", False),
    "2209.10257": ("methods", False),
    # 4 spintronics, superconductivity and topology
    "2303.11975": ("spintronics", False),
    "2606.04587": ("spintronics", False),
    "2607.13294": ("spintronics", False),
    # 5 layered materials with experimental collaborators
    "2608.23003": ("materials", False),
    "10.1021/acsnano.5c20066": ("materials", False),
    "2602.02256": ("materials", False),
    "2602.08525": ("materials", False),
    "10.1126/sciadv.aeb0659": ("materials", False),  # induced magnetism, Science Advances
    # 6 correlated superconductors and QMC
    "2006.11791": ("correlated", False),
    "2110.00084": ("correlated", False),
    "10.1103/physrevresearch.6.023307": ("correlated", False),
    "1610.05582": ("correlated", False),
    "10.1103/physrevb.94.235145": ("correlated", False),
    "10.1103/physrevmaterials.5.054008": ("correlated", False),
    "10.1134/s0021364019130149": ("correlated", False),
    "10.1134/s0021364019010144": ("correlated", False),
    "10.1134/s0021364016050052": ("correlated", False),
}
# Papers OpenAlex does not attribute to the author profile yet.
EXTRA_DOIS = ["10.1126/sciadv.aeb0659"]

PROCEEDINGS_VENUES = ("Journal of Physics Conference Series", "Journal of Siberian Federal University")
DROP_TITLE = re.compile(r"^(erratum|corrigendum)", re.I)
DROP_VENUES = ("Bulletin of the American Physical Society",)
# papers the author does not want listed (removed 2026-09-12)
DROP_DOIS = {"10.1016/j.physb.2017.11.015", "10.1063/1.5009280", "10.1134/s1063774519020159", "10.1134/s1063774519020160", "10.48550/arxiv.1612.03288"}
DROP_TITLES = ("signatures of trions in the optical spectra",)  # v1 title of the JCP trion paper
TITLE_FIX = {"Direct evidence of real-space pairing in Ba BiO 3": "Direct evidence of real-space pairing in BaBiO$_3$"}
DOI_JOURNAL = {
    "physrevlett": "Physical Review Letters", "physrevb": "Physical Review B",
    "physrevresearch": "Physical Review Research", "physrevmaterials": "Physical Review Materials",
}
JREF_ABBR = {
    "Phys. Rev. B": "Physical Review B", "Phys. Rev. Lett.": "Physical Review Letters",
    "Phys. Rev. Research": "Physical Review Research", "J. Chem. Phys.": "The Journal of Chemical Physics",
}


def parse_journal_ref(jr: str) -> tuple[str, str, str]:
    """'Phys. Rev. B 113, 035132 (2026)' -> (journal, volume, pages)."""
    m = re.match(r"(.+?)\s+(\d+),\s*([A-Za-z]?\d+)", jr)
    if not m:
        return jr, "", ""
    return JREF_ABBR.get(m.group(1).strip(), m.group(1).strip()), m.group(2), m.group(3)


def norm_title(t: str) -> str:
    t = re.sub(r"\$[^$]*\$", lambda m: m.group(0).replace("$", ""), t)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("\\text", "").replace("{", "").replace("}", "").replace("_", "").replace("^", "")
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    return " ".join(t.split())[:80]


def get_json(url: str):
    r = requests.get(url, timeout=60, headers={"User-Agent": "yz-site-builder (mailto:yaroslav.zhumagulov@gmail.com)"})
    r.raise_for_status()
    return r.json()


def fetch_openalex() -> list[dict]:
    works = []
    url = f"https://api.openalex.org/works?filter=author.id:{OPENALEX_AUTHOR}&per-page=100&cursor=*"
    while True:
        j = get_json(url)
        works += j["results"]
        nxt = j["meta"].get("next_cursor")
        if not nxt or not j["results"]:
            break
        url = re.sub(r"cursor=[^&]*", f"cursor={nxt}", url)
    for doi in EXTRA_DOIS:
        try:
            works.append(get_json(f"https://api.openalex.org/works/https://doi.org/{doi}"))
        except Exception:  # noqa: BLE001
            cr = crossref_meta(doi)  # not in OpenAlex yet: synthesise a minimal record from Crossref
            if not cr.get("title"):
                print(f"warning: could not fetch {doi} from OpenAlex or Crossref", file=sys.stderr)
                continue
            works.append({
                "title": cr["title"], "publication_year": cr["year"], "doi": f"https://doi.org/{doi}",
                "primary_location": {"source": {"display_name": cr["venue"]}},
                "biblio": {"volume": cr["volume"], "first_page": cr["pages"]},
                "authorships": [{"author": {"display_name": a}} for a in cr["authors"]],
                "cited_by_count": 0,
            })
    return works


def fetch_arxiv() -> list[dict]:
    r = requests.get(
        "https://export.arxiv.org/api/query",
        params={"search_query": ARXIV_QUERY, "max_results": 300, "sortBy": "submittedDate", "sortOrder": "descending"},
        timeout=60,
    )
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom", "ar": "http://arxiv.org/schemas/atom"}
    out = []
    for e in ET.fromstring(r.text).findall("a:entry", ns):
        arxiv_id = e.find("a:id", ns).text.split("/abs/")[-1]
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
        if arxiv_id == "1612.03288":  # dropped paper (Rev. Sci. Instrum. 2018)
            continue
        jr = e.find("ar:journal_ref", ns)
        doi = e.find("ar:doi", ns)
        out.append(
            {
                "arxiv": arxiv_id,
                "title": " ".join(e.find("a:title", ns).text.split()),
                "authors": [x.find("a:name", ns).text for x in e.findall("a:author", ns)],
                "year": int(e.find("a:published", ns).text[:4]),
                "journal_ref": jr.text if jr is not None else "",
                "doi": doi.text if doi is not None else "",
                "abstract": " ".join(e.find("a:summary", ns).text.split()),
            }
        )
    return out


def crossref_meta(doi: str) -> dict:
    """Printed author names, volume, article number and journal year from Crossref
    (OpenAlex lacks APS article numbers and sometimes returns transliterated names)."""
    try:
        m = get_json(f"https://api.crossref.org/works/{doi}")["message"]
    except Exception:  # noqa: BLE001
        return {}
    authors = []
    for a in m.get("author", []):
        if "family" in a:
            authors.append(f"{a.get('given', '')} {a['family']}".strip())
        elif "name" in a:
            authors.append(a["name"])
    issued = (m.get("issued") or {}).get("date-parts") or [[None]]
    return {
        "authors": authors,
        "volume": m.get("volume", ""),
        "pages": m.get("article-number") or (m.get("page") or "").split("-")[0],
        "year": issued[0][0],
        "venue": (m.get("container-title") or [""])[0],
        "title": (m.get("title") or [""])[0],
    }


def oa_record(w: dict) -> dict | None:
    title = w.get("title") or ""
    if not title or DROP_TITLE.search(title) or norm_title(title).startswith(DROP_TITLES):
        return None
    title = TITLE_FIX.get(title, title)
    loc = w.get("primary_location") or {}
    src = (loc.get("source") or {}).get("display_name") or ""
    if any(v in src for v in DROP_VENUES) or any(v in src for v in PROCEEDINGS_VENUES):
        return None  # conference proceedings are not listed (author's choice, 2026-09-12)
    doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
    if doi in DROP_DOIS:
        return None
    is_repo = "arxiv" in src.lower() or "publication server" in src.lower() or doi.startswith("10.48550") or doi.startswith("10.5283")
    biblio = w.get("biblio") or {}
    authors = [a["author"]["display_name"] for a in w.get("authorships", [])]
    return {
        "title": title,
        "year": w.get("publication_year"),
        "doi": "" if is_repo else doi,
        "venue": "" if is_repo else src,
        "volume": biblio.get("volume") or "",
        "pages": biblio.get("first_page") or "",
        "authors": authors,
        "citations": w.get("cited_by_count", 0),
        "is_repo": is_repo,
    }


VENUE_ABBR = {
    "Physical review. B./Physical review. B": "Physical Review B",
    "Physical Review B": "Physical Review B",
    "Journal of Experimental and Theoretical Physics Letters": "JETP Letters",
    "Journal of Physics Conference Series": "Journal of Physics: Conference Series",
    "Journal of Siberian Federal University Mathematics & Physics": "Journal of Siberian Federal University. Mathematics & Physics",
    "Physica B Condensed Matter": "Physica B: Condensed Matter",
    "The Journal of Chemical Physics": "The Journal of Chemical Physics",
}


def clean_title(t: str) -> str:
    t = re.sub(r"<sub>(.*?)</sub>", r"$_{\1}$", t)
    t = re.sub(r"<sup>(.*?)</sup>", r"$^{\1}$", t)
    t = t.replace("ß", "$_3$")
    t = re.sub(r"\\text\{([^}]*)\}", r"\1", t)
    return t


def bib_escape(s: str) -> str:
    """Escape a metadata value so it stays inside its {...} field.

    Braces are kept only when balanced (legitimate LaTeX); otherwise all braces are dropped,
    so a value can never terminate the field or inject a new record. Newlines and '@' at a line
    start are neutralised for the same reason.
    """
    s = " ".join(s.split())
    depth = 0
    for ch in s:
        depth += (ch == "{") - (ch == "}")
        if depth < 0:
            break
    if depth != 0:
        s = s.replace("{", "").replace("}", "")
    return s.replace("&", r"\&").replace("%", r"\%").replace("@", "\\@")


def fix_author(a: str) -> str:
    a = a.strip()
    a = a.replace("Iaroslav Zhumagulov", "Yaroslav Zhumagulov").replace("Ya. V. Zhumagulov", "Yaroslav V. Zhumagulov")
    return a


def main() -> None:
    oa = [r for r in (oa_record(w) for w in fetch_openalex()) if r]
    ax = fetch_arxiv()

    merged: dict[str, dict] = {}
    for r in oa:
        k = norm_title(r["title"])
        cur = merged.get(k)
        if cur is None or (cur["is_repo"] and not r["is_repo"]):
            if cur:
                r["citations"] += cur["citations"]
            merged[k] = r
        elif cur and not cur["is_repo"] and r["is_repo"]:
            cur["citations"] += r["citations"]
    for a in ax:
        k = norm_title(a["title"])
        rec = merged.get(k)
        if rec is None:
            rec = merged[k] = {
                "title": a["title"], "year": a["year"], "doi": a["doi"].lower(), "venue": "", "volume": "", "pages": "",
                "authors": a["authors"], "citations": 0, "is_repo": True,
            }
        rec["arxiv"] = a["arxiv"]
        rec["authors"] = a["authors"]  # as printed on the paper
        rec["abstract"] = a["abstract"]
        rec["title"] = a["title"]
        if not rec["venue"] and a["journal_ref"]:
            rec["journal_ref"] = a["journal_ref"]
        if not rec["doi"] and a["doi"]:
            rec["doi"] = a["doi"].lower()

    # second pass: merge records that share a DOI but differ in title spelling
    by_doi: dict[str, str] = {}
    for k, rec in list(merged.items()):
        d = rec.get("doi")
        if not d:
            continue
        if d in by_doi:
            keep = merged[by_doi[d]]
            if keep["is_repo"] and not rec["is_repo"]:
                keep, rec = rec, keep
                merged[by_doi[d]] = keep
            for f in ("arxiv", "abstract", "journal_ref"):
                if f in rec and not keep.get(f):
                    keep[f] = rec[f]
            if "arxiv" in rec:
                keep["authors"] = rec["authors"]
            keep["citations"] += rec["citations"]
            merged = {kk: vv for kk, vv in merged.items() if vv is not rec}
        else:
            by_doi[d] = k

    for rec in merged.values():
        if not rec["doi"]:
            continue
        cr = crossref_meta(rec["doi"])
        if not cr:
            continue
        if "arxiv" not in rec and cr["authors"] and any(SELF.search(a) for a in cr["authors"]):
            rec["authors"] = cr["authors"]
        rec["volume"] = rec["volume"] or cr["volume"]
        rec["pages"] = rec["pages"] or cr["pages"]
        rec["venue"] = rec["venue"] or cr["venue"]
        if cr["year"]:
            rec["year"] = cr["year"]  # journal year, not preprint year

    entries = []
    unmapped = []
    for rec in merged.values():
        key_candidates = [rec.get("arxiv", ""), rec.get("doi", "")]
        tag = next((GROUPS[k] for k in key_candidates if k and k in GROUPS), None)
        proceedings = any(v in rec["venue"] for v in PROCEEDINGS_VENUES)
        if tag is None:
            if proceedings:
                tag = ("correlated", False)
            else:
                unmapped.append(rec)
                continue
        group, selected = tag
        authors = [fix_author(a) for a in rec["authors"]]
        first = bool(authors) and bool(SELF.search(authors[0]))
        year = rec["year"]
        surname_first = re.sub(r"[^a-z]", "", authors[0].split()[-1].lower()) if authors else "anon"
        word = next((w for w in re.findall(r"[a-z]{4,}", rec["title"].lower()) if w not in ("with", "from", "into", "their", "monolayer", "monolayers")), "paper")
        key = f"{surname_first}{year}{word}"
        venue = VENUE_ABBR.get(rec["venue"], rec["venue"])
        if not venue and rec.get("journal_ref"):
            venue, v, pg = parse_journal_ref(rec["journal_ref"])
            rec["volume"], rec["pages"] = rec["volume"] or v, rec["pages"] or pg
        if not venue and rec["doi"]:
            m = re.match(r"10\.1103/([a-z]+)\.", rec["doi"])
            if m:
                venue = DOI_JOURNAL.get(m.group(1), "")
        fields = {
            "title": bib_escape(clean_title(rec["title"])),
            "author": " and ".join(authors),
            "year": str(year),
            "journal": venue if venue else ("arXiv preprint" if rec.get("arxiv") else ""),
            "volume": rec["volume"],
            "pages": rec["pages"],
            "doi": rec["doi"],
            "eprint": rec.get("arxiv", ""),
            "journalref": rec.get("journal_ref", ""),
            "group": group,
            "selected": "true" if selected else "",
            "proceedings": "true" if proceedings else "",
            "firstauthor": "true" if first else "",
            "citations": str(rec["citations"]) if rec["citations"] else "",
            "abstract": bib_escape(rec.get("abstract", "")),
        }
        entries.append((key, fields))

    # unique keys
    seen: dict[str, int] = {}
    lines = ["% Generated by tools/fetch_pubs.py — edit GROUPS there, not here, unless adding a paper by hand.\n"]
    for key, fields in sorted(entries, key=lambda e: (-int(e[1]["year"]), e[0])):
        n = seen.get(key, 0)
        seen[key] = n + 1
        k = key if n == 0 else f"{key}{chr(ord('a') + n)}"
        lines.append(f"@article{{{k},")
        for f, v in fields.items():
            if v:
                if f not in ("title", "abstract"):
                    v = bib_escape(v)
                lines.append(f"  {f} = {{{v}}},")
        lines.append("}\n")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines))
    print(f"wrote {len(entries)} entries to {OUT.relative_to(ROOT)}")
    for rec in unmapped:
        print(f"UNMAPPED: {rec['year']} | {rec['title'][:80]} | {rec.get('arxiv','')} {rec.get('doi','')} | {rec['venue']}")


if __name__ == "__main__":
    main()
