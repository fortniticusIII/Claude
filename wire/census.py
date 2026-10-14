"""Headline census: every story an outlet published in a date range, from the outlet's own sitemaps or
paged feeds. Unlike the Wire (which keeps whatever sits in each feed at 6:16am), this is complete and
reproducible, so the Pulse can compare this week with past weeks on equal terms.

    python3 -m wire.census 2026-07-01 2026-10-12            # all census sources, writes wire/census/<feed>.jsonl.gz
    python3 -m wire.census 2026-10-01 2026-10-12 aljazeera   # one source

Each line: {"d": "YYYY-MM-DD" (Eastern publication day), "link": ..., "title": ... (only where the source gives one)}.
Without a title, wire.places tags the URL slug, which for these outlets is the headline in lower case.
Runs merge into the existing file (deduplicated by link), so overlapping ranges are safe.

Sources (Oct 13, 2026). Outlets not listed have no usable history route and rely on the Wire archive:
the Africanews and Taipei Times sitemaps answered 403 (refusals, recorded in kit/refused.json); JPost's
sitemap URLs carry no headline words; NPR's sitemap covers all of NPR, not its World feed; Meduza has none.
Dates: path dates (Al Jazeera, Defense News) and pubDate (paged feeds) are publication days. Ukrinform,
The War Zone and The Record give only lastmod, which moves when a story is edited; Ukrinform's is clamped
into the publication week its sitemap file covers.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter
import gzip
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kit import http  # noqa: E402

EASTERN = ZoneInfo("America/New_York")
OUT = Path(__file__).with_name("census")


def _get(url: str, ttl: float = 3600) -> str:
    c = http.get(url, ttl=ttl).content
    if c[:2] == b"\x1f\x8b":
        c = gzip.decompress(c)
    return c.decode("utf-8", "replace")


def _urls(xml: str):
    """(loc, lastmod or '') for each <url> in a sitemap."""
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block)
        mod = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block)
        if loc:
            yield loc.group(1).replace("&amp;", "&"), (mod.group(1) if mod else "")


def _eastern_day(stamp: str) -> str | None:
    try:
        t = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if not t.tzinfo:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(EASTERN).date().isoformat()


def _path_day(url: str) -> str | None:
    m = re.search(r"/(20\d\d)/(\d{1,2})/(\d{1,2})/", url)
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat() if m else None


def aljazeera(start: dt.date, end: dt.date):
    months = sorted({(d.year, d.month) for d in (start + dt.timedelta(n) for n in range((end - start).days + 1))})
    for y, m in months:
        for loc, _ in _urls(_get(f"https://www.aljazeera.com/sitemaps/article-archive/{y}/{m:02d}.xml")):
            if "/sports/" in loc:          # the Wire's own rule for this feed
                continue
            yield {"d": _path_day(loc), "link": loc}


def _kyiv_week(stamp: str):
    try:
        t = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(ZoneInfo("Europe/Kyiv")).isocalendar()[:2]


def ukrinform(start: dt.date, end: dt.date):
    """Weekly files /sitemap/YYYY/WW.xml exist only once a week is over; the week in progress is
    /sitemap/currentweek.xml (found Oct 14, 2026: until then the census silently missed it)."""
    weeks, d = set(), start
    while d <= end:
        weeks.add(d.isocalendar()[:2]); d += dt.timedelta(days=1)
    current = None
    for y, w in sorted(weeks):
        mon = dt.date.fromisocalendar(y, w, 1)
        rows = list(_urls(_get(f"https://www.ukrinform.net/sitemap/{y}/{w:02d}.xml")))
        if not rows:                       # 404 page: this week isn't filed yet
            if current is None:
                current = list(_urls(_get("https://www.ukrinform.net/sitemap/currentweek.xml", ttl=600)))
            held = Counter(_kyiv_week(m) for _, m in current if m).most_common(1)
            if held and held[0][0] == (y, w):
                rows = current
        for loc, mod in rows:
            day = _eastern_day(mod) or mon.isoformat()
            day = min(max(day, mon.isoformat()), (mon + dt.timedelta(days=6)).isoformat())
            yield {"d": day, "link": loc}


def defensenews(start: dt.date, end: dt.date):
    idx = _get("https://www.defensenews.com/arc/outboundfeeds/sitemap-index/?outputType=xml")
    for page in re.findall(r"<loc>\s*(.*?)\s*</loc>", idx):
        page = page.replace("&amp;", "&")
        sep = "&" if "?" in page else "?"
        for loc, _ in _urls(_get(page if "outputType" in page else page + sep + "outputType=xml")):
            yield {"d": _path_day(loc), "link": loc}


def twz(start: dt.date, end: dt.date):
    idx = _get("https://www.twz.com/sitemap_index.xml")
    posts = sorted((int(m or 1), u) for u, m in re.findall(r"<loc>\s*(https://www\.twz\.com/post-sitemap(\d*)\.xml)\s*</loc>", idx))
    for _, u in reversed(posts[-2:]):    # the two newest files hold well over three months
        for loc, mod in _urls(_get(u)):
            yield {"d": _eastern_day(mod), "link": loc}


def therecord(start: dt.date, end: dt.date):
    idx = _get("https://therecord.media/sitemap.xml")
    for u in re.findall(r"<loc>\s*(.*?)\s*</loc>", idx):
        rows = list(_urls(_get(u)))
        for loc, mod in rows:
            yield {"d": _eastern_day(mod), "link": loc}
        if rows and max((_eastern_day(m) or "") for _, m in rows) < start.isoformat():
            break


def _paged(feed_url: str, link_filter=None):
    def source(start: dt.date, end: dt.date):
        import feedparser
        for page in range(1, 200):
            f = feedparser.parse(http.get(feed_url, {"paged": page}, ttl=3600).content)
            if not f.entries:
                return
            oldest = None
            for e in f.entries:
                when = e.get("published") or e.get("updated") or ""
                try:
                    t = dt.datetime(*e.published_parsed[:6], tzinfo=dt.timezone.utc) if e.get("published_parsed") else None
                except Exception:
                    t = None
                day = t.astimezone(EASTERN).date().isoformat() if t else None
                link = e.get("link", "")
                if link_filter and not link_filter(link):
                    continue
                oldest = day if oldest is None or (day and day < oldest) else oldest
                yield {"d": day, "link": link, "title": e.get("title", "").strip()}
            if oldest and oldest < start.isoformat():
                return
    return source


SOURCES = {
    "aljazeera": aljazeera,
    "ukrinform": ukrinform,
    "defensenews": defensenews,
    "twz": twz,
    "therecord": therecord,
    "breakingdefense": _paged("https://breakingdefense.com/feed/"),
    "usni": _paged("https://news.usni.org/feed"),
    "nknews": _paged("https://www.nknews.org/feed/"),
    "insightcrime": _paged("https://insightcrime.org/feed/"),
    "whitehouse": _paged("https://www.whitehouse.gov/news/feed/"),
}


def load(feed: str) -> list[dict]:
    p = OUT / f"{feed}.jsonl.gz"
    if not p.exists():
        return []
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save(feed: str, rows: list[dict]):
    OUT.mkdir(exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["d"], r["link"]))
    with gzip.open(OUT / f"{feed}.jsonl.gz", "wt", encoding="utf-8", compresslevel=9) as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")


def collect(feed: str, start: dt.date, end: dt.date) -> tuple[int, int]:
    have = {r["link"]: r for r in load(feed)}
    before = len(have)
    for r in SOURCES[feed](start, end):
        if not r.get("d") or not r.get("link") or not (start.isoformat() <= r["d"] <= end.isoformat()):
            continue
        r["link"] = r["link"].split("?traffic_source")[0]
        have[r["link"]] = {**have.get(r["link"], {}), **{k: v for k, v in r.items() if v}}
    save(feed, list(have.values()))
    return before, len(have)


if __name__ == "__main__":
    start, end = dt.date.fromisoformat(sys.argv[1]), dt.date.fromisoformat(sys.argv[2])
    for feed in sys.argv[3:] or SOURCES:
        try:
            a, b = collect(feed, start, end)
            print(f"{feed:16} {b - a:5d} new, {b:6d} stored")
        except Exception as e:  # report and carry on; a refusal is policy, never retried another way
            print(f"{feed:16} FAILED {type(e).__name__}: {str(e)[:160]}")
