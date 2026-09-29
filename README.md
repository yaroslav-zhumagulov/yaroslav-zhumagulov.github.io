<img src="static/img/favicon.svg" width="48" align="left" alt="">

# yaroslav-zhumagulov.github.io

Personal academic site of Yaroslav Zhumagulov, built by a small Python script and
deployed to GitHub Pages by the workflow in `.github/workflows/pages.yml`.

```
data/            all content: profile.yml, research.yml, software.yml, cv.yml, publications.bib
templates/       Jinja2 templates (base, index, research, publications, software, talks, cv)
demos/           demo repositories (notebooks, scripts, slides); only the slides are published
static/          css, js, images, files (cv.pdf)
tools/build.py   renders ./site from data + templates
tools/fetch_pubs.py  regenerates data/publications.bib from OpenAlex + arXiv
```

## Local preview

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python tools/build.py --serve      # http://localhost:8000
```

## Editing

- **Text and links**: `data/profile.yml`.
- **Research projects**: `data/research.yml`. Projects reference papers by arXiv id or DOI.
  Figures go under `static/img/research/`; a placeholder is shown until the file exists.
- **Publications**: `data/publications.bib` is generated; to refresh it from the web, extend
  `GROUPS` in `tools/fetch_pubs.py` and run it. Papers the databases miss go in
  `data/publications_extra.bib` by hand, with `group = {...}` (a subgroup slug) and optionally
  `selected = {true}`, `firstauthor = {true}`, `url = {...}`.
- **Software**: `data/software.yml`.
- **CV**: `data/cv.yml`; put the PDF at `static/files/cv.pdf`.
- **Talks**: `data/talks.yml`. The material of a talk goes in `demos/<name>/`; its slides are published at
  `/demos/<name>/slides/`, the rest is browsable on GitHub.
  `tools/sync_demo.py <repository> <name>` copies the last commit of a demo repository there, and makes its
  `slides/index.html` use the fonts in `static/fonts/plex/` instead of Google Fonts.
- **Portrait**: `static/img/portrait.jpg`.
- **Root files** (e.g. Google Search Console verification): anything in `root/` is copied to the site root.

Pushing to `main` rebuilds and deploys the site.
