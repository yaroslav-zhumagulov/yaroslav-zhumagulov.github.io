"""Print the slides to slides/wannier-berri-demo.pdf, one 16:9 page per slide.

Needs Playwright:  pip install playwright && playwright install chromium
Run:               python slides/make_pdf.py

The page size and layout come from the @media print rules in index.html, so
"Print → Save as PDF" in Chrome or Firefox gives the same result.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PDF = HERE / "wannier-berri-demo.pdf"

# index.html has no doctype (it is also published as a page fragment), so wrap
# it for standards-mode rendering; the copy sits next to it so figures resolve
page_html = HERE / ".print.html"
page_html.write_text("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"></head><body>\n"
                     + (HERE / "index.html").read_text() + "\n</body></html>\n")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(color_scheme="light")
        page.goto(page_html.as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.pdf(path=str(PDF), prefer_css_page_size=True, print_background=True)
        browser.close()
finally:
    page_html.unlink()
print(f"wrote {PDF}")
