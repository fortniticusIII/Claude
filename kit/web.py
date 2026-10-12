"""kit.web: read the actual text of pages and PDFs, not a summary of them.

WebFetch hands pages to a small model and returns its summary. When an exact figure,
a quote under 15 words, a table or a date matters, read the source itself:

    from kit import web
    doc = web.page("https://www.federalreserve.gov/newsevents/pressreleases/monetary20250917a.htm")
    doc.title, doc.date, doc.author, doc.text            # main text, boilerplate stripped
    doc.find("percent")                                  # sentences that mention a term
    tables = web.tables(url)                             # every HTML <table> as a DataFrame
    pdf = web.pdf("https://.../report.pdf", pages="1-5") # text per page
    web.links(url, contains="press")                     # links on a page, filtered

Rules: robots.txt is honoured for pages; hosts on kit/refused.json raise Refused. If WebFetch
declined a site, add it there instead of reading it here. Quoting limits still apply to anything
read this way: paraphrase, one short quote per source.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from . import http


@dataclass
class Doc:
    url: str
    title: str = ""
    author: str = ""
    date: str = ""
    sitename: str = ""
    text: str = ""
    meta: dict = field(default_factory=dict)

    def find(self, term: str, width: int = 0) -> list[str]:
        """Sentences (or +-width chars) containing term, case-insensitive."""
        out = []
        if width:
            for m in re.finditer(re.escape(term), self.text, re.I):
                out.append(self.text[max(0, m.start() - width): m.end() + width].replace("\n", " "))
            return out
        for s in re.split(r"(?<=[.!?])\s+|\n+", self.text):
            if term.lower() in s.lower():
                out.append(s.strip())
        return out

    def __repr__(self) -> str:
        return f"Doc({self.title!r}, {self.date or 'undated'}, {len(self.text):,} chars, {self.url})"


def page(url: str, ttl: float = 24 * 3600, robots: bool = True) -> Doc:
    """Main text and metadata of a web page (trafilatura, with a BeautifulSoup fallback)."""
    r = http.get(url, ttl=ttl, robots=robots, headers={"Accept": "text/html,application/xhtml+xml"})
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status} from {url}")
    if "pdf" in r.headers.get("content-type", "") or r.content[:5] == b"%PDF-":
        d = _pdf_doc(r)
        http.note_title(r.url, d.title or url)
        return d
    html = r.text
    doc = Doc(url=r.url)
    try:
        import trafilatura
        j = trafilatura.bare_extraction(html, url=r.url, include_tables=True, include_comments=False,
                                        with_metadata=True)
        if j is not None:
            j = j if isinstance(j, dict) else j.as_dict()
            doc.title, doc.author = j.get("title") or "", j.get("author") or ""
            doc.date, doc.sitename = j.get("date") or "", j.get("sitename") or ""
            doc.text = j.get("text") or ""
    except ImportError:
        pass
    if len(doc.text) < 200:  # fallback: visible text of the whole page
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for t in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
            t.decompose()
        doc.title = doc.title or (soup.title.get_text(strip=True) if soup.title else "")
        doc.text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
    http.note_title(r.url, doc.title or r.url)
    return doc


def text(url: str, **kw) -> str:
    return page(url, **kw).text


def _pages_sel(spec, n: int) -> list[int]:
    if spec is None:
        return list(range(n))
    out = []
    for part in str(spec).split(","):
        a, _, b = part.partition("-")
        lo, hi = int(a), int(b or a)
        out.extend(range(lo - 1, min(hi, n)))
    return out


def _pdf_doc(r: http.Response, pages=None) -> Doc:
    import pdfplumber
    doc = Doc(url=r.url)
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        info = pdf.metadata or {}
        doc.title = str(info.get("Title") or "")
        doc.author = str(info.get("Author") or "")
        doc.date = str(info.get("CreationDate") or "")[2:10]
        sel = _pages_sel(pages, len(pdf.pages))
        texts = [f"[page {i + 1}]\n{pdf.pages[i].extract_text() or ''}" for i in sel]
        doc.meta = {"pages": len(pdf.pages)}
    doc.text = "\n\n".join(texts)
    return doc


def pdf(url: str, pages: str | None = None, ttl: float = 7 * 24 * 3600) -> Doc:
    """Text of a PDF by page ('1-5,9'). Scanned PDFs come back empty: say so rather than guess."""
    r = http.get(url, ttl=ttl, robots=True)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status} from {url}")
    d = _pdf_doc(r, pages)
    http.note_title(r.url, d.title or url.rsplit("/", 1)[-1])
    return d


def tables(url: str, match: str = ".+", ttl: float = 24 * 3600):
    """Every HTML table on a page as pandas DataFrames (filter with a regex `match`)."""
    import pandas as pd
    r = http.get(url, ttl=ttl, robots=True)
    return pd.read_html(io.StringIO(r.text), match=match)


def links(url: str, contains: str = "", ttl: float = 24 * 3600) -> list[tuple[str, str]]:
    """(text, absolute href) for links on a page, optionally filtered by a substring of either."""
    from urllib.parse import urljoin
    from bs4 import BeautifulSoup
    r = http.get(url, ttl=ttl, robots=True)
    soup = BeautifulSoup(r.text, "lxml")
    out = []
    for a in soup.find_all("a", href=True):
        t, h = a.get_text(" ", strip=True), urljoin(r.url, a["href"])
        if not contains or contains.lower() in (t + " " + h).lower():
            out.append((t, h))
    return out


def feed(url: str, ttl: float = 3600) -> list[dict]:
    """Entries of an RSS/Atom feed: title, link, published, summary."""
    import feedparser
    r = http.get(url, ttl=ttl)
    f = feedparser.parse(r.content)
    return [{"title": e.get("title", ""), "link": e.get("link", ""),
             "published": e.get("published", e.get("updated", "")),
             "summary": re.sub(r"<[^>]+>", "", e.get("summary", ""))[:500]} for e in f.entries]


def wayback(url: str, when: str = "") -> str | None:
    """Closest Internet Archive snapshot URL (when='YYYYMMDD'), for dead or changed pages."""
    params = {"url": url, **({"timestamp": when} if when else {})}
    j = http.get_json("https://archive.org/wayback/available", params, ttl=86400)
    snap = j.get("archived_snapshots", {}).get("closest")
    return snap["url"] if snap and snap.get("available") else None
