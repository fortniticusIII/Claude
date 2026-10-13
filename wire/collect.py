"""The Wire's collector, parsing feeds directly instead of through WebFetch.

Why (audit, Oct 13 2026): the WebFetch collector missed 80 of 213 stories that sat inside its window
(38%), mostly defense press (The War Zone 5 of 6, Breaking Defense 7 of 13, Defense News 8 of 22), Meduza
(21 of 30) and the whole day's Taipei Times. WebFetch appears to serve stale copies of some feeds and
summarises others unevenly. Parsing the XML gets every item with its exact time, title and link.

Usage (any session whose shell reaches the open web):
    1. ArtifactData list 'feeds' and query 'items' where day in [today, yesterday], both with
       out_dir=DUMP (files land in DUMP/feeds and DUMP/items). The dump files hold no versions, so
       write DUMP/versions.json from the versions those two listings print, plus meta/status's:
       {"feeds": {"npr": 2, ...}, "items": {"20261013-npr": 1, ...}, "meta": {"status": 2}}.
       Anything missing is handled safely: no feed health update for a feed without a version, and
       new stories for an existing items doc go to a new doc <day>-<feed>-r<HHMM> instead of a merge.
    2. python3 wire/collect.py DUMP OUT
    3. Send each chunk of OUT/writes.json to ArtifactData 'batch' (chunks of <= 50).
    4. For each feed in OUT/manifest.json 'needs_webfetch', fall back to the WebFetch method in
       wire/collector.md. Feeds the proxy refused (403) are 'failing' and are never retried another way.

Stored per story: t (ISO time with offset), title, link, and summary = the feed's own description cut to
its first sentence, at most 200 characters. Never more of a story than that.

Feed doc fields used: url, name, region, and optional keep_link / drop_link (lists of substrings matched
against the link). The older free-text 'skip' rules map onto these.
"""
import datetime as dt
import email.utils
import glob
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
UA = "TheWire/1.0 (personal news collector; +https://github.com/fortniticusIII/Claude)"
WINDOW_HOURS = 30
KEEP_DAYS = 14


def load(folder, coll, versions):
    """Docs from an ArtifactData out_dir dump: {doc_id: (data, version or None)}."""
    v = versions.get(coll, {})
    return {os.path.basename(p)[:-5]: (json.load(open(p)), v.get(os.path.basename(p)[:-5]))
            for p in glob.glob(os.path.join(folder, coll, "*.json"))}


def parse_time(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        t = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        try:
            t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def first_sentence(text, limit=200):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return s


def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def entries(raw):
    """(time, title, link, description) for each item of an RSS 2.0, RSS 1.0 or Atom feed."""
    try:
        import feedparser  # lenient with broken XML when available
        f = feedparser.parse(raw)
        if f.entries:
            for e in f.entries:
                yield (parse_time(e.get("published") or e.get("updated") or e.get("dc_date") or ""),
                       html.unescape(e.get("title", "")).strip(), e.get("link", "").strip(),
                       e.get("summary", "") or e.get("description", ""))
            return
    except ImportError:
        pass
    root = ET.fromstring(raw)
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        kids = {c.tag.split("}")[-1]: c for c in el}
        link = kids.get("link")
        href = (link.get("href") or link.text or "").strip() if link is not None else ""
        when = next((kids[k].text for k in ("pubDate", "published", "updated", "date") if k in kids and kids[k].text), "")
        desc = next((kids[k].text for k in ("description", "summary", "content") if k in kids and kids[k].text), "")
        yield parse_time(when), html.unescape((kids["title"].text or "") if "title" in kids else "").strip(), href, desc


def rules(feed):
    keep, drop = list(feed.get("keep_link", [])), list(feed.get("drop_link", []))
    skip = feed.get("skip", "")
    if not keep and skip.lower().startswith("keep only links under"):
        keep = re.findall(r"(/[\w\-/]+/)", skip)
    if not drop and skip.lower().startswith("skip links under"):
        drop = re.findall(r"(/[\w\-/]+/)", skip)
    return keep, drop


def main(dump, out, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(hours=WINDOW_HOURS)
    today = now.astimezone(EASTERN).date()
    vp = os.path.join(dump, "versions.json")
    versions = json.load(open(vp)) if os.path.exists(vp) else {}
    feeds = load(dump, "feeds", versions)
    items = load(dump, "items", versions)
    meta_ver = versions.get("meta", {}).get("status")
    seen = {}
    for doc_id, (d, _) in items.items():
        seen.setdefault(d.get("feed"), set()).update(i["link"] for i in d.get("items", []))
    os.makedirs(out, exist_ok=True)
    writes, needs_webfetch, report = [], [], []
    added = ok = failed = 0
    stamp = now.astimezone(EASTERN).isoformat(timespec="seconds")
    for fid, (feed, fver) in sorted(feeds.items(), key=lambda kv: kv[1][0].get("order", 99)):
        keep, drop = rules(feed)
        try:
            raw = fetch(feed["url"])
            got = list(entries(raw))
        except urllib.error.HTTPError as e:
            if e.code in (403, 407):     # proxy or site refusal: policy, never route around
                failed += 1; report.append(f"{fid}: refused ({e.code})")
                if fver is not None:
                    writes.append(("update", "feeds", fid, {"status": "failing", "last_error": f"refused {e.code}"}, fver))
            else:
                needs_webfetch.append(fid); report.append(f"{fid}: HTTP {e.code}, fall back to WebFetch")
            continue
        except Exception as e:  # no egress, DNS, timeout, unparseable
            needs_webfetch.append(fid); report.append(f"{fid}: {type(e).__name__}, fall back to WebFetch")
            continue
        new = []
        for t, title, link, desc in got:
            if not link or not title or t is None or t < since or t > now + dt.timedelta(hours=1):
                continue
            if keep and not any(k in link for k in keep):
                continue
            if any(k in link for k in drop):
                continue
            if link in seen.get(fid, set()):
                continue
            seen.setdefault(fid, set()).add(link)
            s = first_sentence(desc)
            if s.rstrip(".… ").lower() == title.rstrip(". ").lower():
                s = ""
            new.append({"t": t.isoformat(), "title": title, "link": link, **({"summary": s} if s else {})})
        new.sort(key=lambda i: i["t"], reverse=True)
        ok += 1; added += len(new)
        if fver is not None:
            writes.append(("update", "feeds", fid, {"status": "ok", "last_ok": stamp, "last_count": len(new), "last_error": {"__delete__": True}}, fver))
        if new:
            doc_id = f"{today:%Y%m%d}-{fid}"
            prev, pver = items.get(doc_id, ({}, None))
            if doc_id in items and pver is None:     # exists but version unknown: never overwrite blind
                doc_id, prev = f"{doc_id}-r{now.astimezone(EASTERN):%H%M}", {}
            body = {"feed": fid, "source": feed.get("name", fid), "region": feed.get("region", ""), "day": today.isoformat(),
                    "run": stamp, "items": sorted(new + prev.get("items", []), key=lambda i: i["t"], reverse=True)}
            writes.append(("set", "items", doc_id, body, pver))
        report.append(f"{fid}: {len(new)} new of {len(got)} in feed")
    status = {"last_run": stamp, "window_from": since.isoformat(timespec="minutes"), "added": added, "feeds_ok": ok,
              "feeds_failed": failed, "method": "direct",
              "note": "Parsed feeds directly." + (f" WebFetch fallback needed for: {', '.join(needs_webfetch)}." if needs_webfetch else "")}
    writes.append(("set", "meta", "status", status, meta_ver))
    # prune: items docs older than KEEP_DAYS (only those present in the dump)
    cutoff = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    for doc_id, (d, v) in items.items():
        if d.get("day", "9999") < cutoff and v is not None:
            writes.append(("delete", "items", doc_id, None, v))
    batch = []
    for k, (op, coll, doc_id, data, ver) in enumerate(writes):
        entry = {"op": op, "collection": coll, "doc_id": doc_id}
        if data is not None:
            p = os.path.join(out, f"{k:03d}-{coll}-{doc_id}.json")
            json.dump(data, open(p, "w"), ensure_ascii=False)
            entry["file_path"] = os.path.abspath(p)
        if ver is not None:
            entry["if_version"] = ver
        batch.append(entry)
    chunks = [batch[i:i + 50] for i in range(0, len(batch), 50)]
    json.dump(chunks, open(os.path.join(out, "writes.json"), "w"), indent=1)
    json.dump({"added": added, "feeds_ok": ok, "feeds_failed": failed, "needs_webfetch": needs_webfetch,
               "report": report, "batches": len(chunks)}, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    print("\n".join(report))
    print(f"added {added}; feeds ok {ok}, failing {failed}, WebFetch fallback {len(needs_webfetch)}; {len(chunks)} batch(es) in {out}/writes.json")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
