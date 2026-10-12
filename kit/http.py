"""kit.http: the one door every kit module uses to reach the web from the shell.

What it adds over plain requests:
- an honest User-Agent naming the kit and its repo
- a disk cache (default 6 h for APIs; pass ttl=0 to bypass)
- per-host pacing, and at most one retry on 429 when the wait is short
- a refusal list: hosts that WebFetch declined or that refuse bots. Those are policy,
  so kit raises Refused instead of trying another way. Report them; never route around.
- a ledger of every source actually used, so answers can end with a real Sources list

    from kit import http
    r = http.get("https://api.crossref.org/works", params={"query": "x", "rows": 1})
    r.json(); r.text; r.content; r.url; r.status; r.from_cache
    http.sources_md()          # markdown Sources list for this session's fetches
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path

import requests

UA = "ClaudeResearchKit/1.0 (+https://github.com/fortniticusIII/claude)"
CACHE = Path(os.environ.get("KIT_CACHE", Path.home() / ".cache" / "kit"))
LEDGER = CACHE / "ledger.jsonl"
SESSION_START = time.time()

# Seconds between requests to one host. Set from each service's published guidance.
PACE = {
    "export.arxiv.org": 3.0,
    "api.gdeltproject.org": 5.5,
    "musicbrainz.org": 1.1,
    "eutils.ncbi.nlm.nih.gov": 0.4,
    "query.wikidata.org": 1.0,
    "api.coingecko.com": 2.0,
    "www.courtlistener.com": 1.0,
}
DEFAULT_PACE = 0.5
FRESH = False  # True makes every get skip the cache (selftest sets it)

# Hosts that refused this kit or WebFetch. Policy, not bugs. Add with a reason and date.
REFUSED_FILE = Path(__file__).with_name("refused.json")


class Refused(Exception):
    """The site or the proxy refused (policy). Report it; don't try another route."""


class RateLimited(Exception):
    """429 that didn't clear after one short wait. Shared egress IP; try later or another source."""


@dataclass
class Response:
    url: str
    status: int
    headers: dict
    content: bytes
    from_cache: bool = False
    fetched_at: float = field(default_factory=time.time)

    @property
    def text(self) -> str:
        ct = self.headers.get("content-type", "")
        enc = "utf-8"
        if "charset=" in ct:
            enc = ct.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        return self.content.decode(enc, errors="replace")

    def json(self):
        return json.loads(self.content)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def refused_hosts() -> dict:
    try:
        return json.loads(REFUSED_FILE.read_text())
    except FileNotFoundError:
        return {}


def _host(url: str) -> str:
    return urllib.parse.urlsplit(url).hostname or ""


def _check_refused(url: str) -> None:
    host = _host(url)
    for h, why in refused_hosts().items():
        if host == h or host.endswith("." + h):
            raise Refused(f"{host} is on the refusal list ({why}). Report it; use another source.")


_last: dict[str, float] = {}


def _pace(host: str) -> None:
    gap = PACE.get(host, DEFAULT_PACE)
    wait = _last.get(host, 0) + gap - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()


_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def robots_ok(url: str) -> bool:
    """True if robots.txt lets this kit fetch the URL (unreachable robots counts as allowed)."""
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=15)
            if r.status_code >= 400:
                rp = None
            else:
                rp.parse(r.text.splitlines())
        except requests.RequestException:
            rp = None
        _robots[base] = rp
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(UA, url)


def _key(url: str, params, data) -> str:
    raw = json.dumps([url, params or {}, data or {}], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _log(resp: Response, title: str | None = None) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(json.dumps({"url": resp.url, "status": resp.status, "t": resp.fetched_at,
                            "cached": resp.from_cache, "title": title}) + "\n")


def note_title(url: str, title: str) -> None:
    """Attach a human title to a ledger URL (web.text does this for pages)."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(json.dumps({"url": url, "title": title, "t": time.time(), "meta": True}) + "\n")


def get(url: str, params: dict | None = None, *, ttl: float = 6 * 3600, headers: dict | None = None,
        timeout: float = 30, robots: bool = False, method: str = "GET", data=None,
        log: bool = True) -> Response:
    """Fetch a URL politely. Raises Refused on policy refusals and RateLimited on stubborn 429s.

    robots=True checks robots.txt first (use it for ordinary web pages; documented APIs skip it).
    ttl=0 skips the cache. Non-2xx responses other than 403/429 are returned, not raised.
    """
    _check_refused(url)
    if robots and not robots_ok(url):
        raise Refused(f"robots.txt disallows {url} for automated clients.")
    key = _key(url, params, data)
    meta_p, body_p = CACHE / "http" / f"{key}.json", CACHE / "http" / f"{key}.bin"
    if ttl and not FRESH and meta_p.exists() and time.time() - meta_p.stat().st_mtime < ttl and method == "GET":
        m = json.loads(meta_p.read_text())
        resp = Response(m["url"], m["status"], m["headers"], body_p.read_bytes(), True, m["t"])
        if log:
            _log(resp)
        return resp
    host = _host(url)
    hdrs = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
    hdrs.update(headers or {})
    for attempt in (1, 2):
        _pace(host)
        try:
            r = requests.request(method, url, params=params, data=data, headers=hdrs, timeout=timeout)
        except requests.exceptions.ProxyError as e:
            raise Refused(f"the egress proxy refused {host}: {str(e)[:160]}. Check "
                          "curl -sS \"$HTTPS_PROXY/__agentproxy/status\"; don't route around it.")
        if r.status_code == 429 and attempt == 1:
            ra = r.headers.get("Retry-After", "")
            wait = float(ra) if ra.replace(".", "", 1).isdigit() else 20.0
            if wait <= 30:
                time.sleep(wait)
                continue
        break
    if r.status_code == 429:
        raise RateLimited(f"{host} answered 429 (shared egress IP). {r.text[:160]}")
    if r.status_code == 403:
        raise Refused(f"{host} answered 403 for {r.url}. Treat as a refusal: {r.text[:160]!r}")
    resp = Response(r.url, r.status_code, {k.lower(): v for k, v in r.headers.items()}, r.content)
    if resp.ok and ttl and method == "GET":
        meta_p.parent.mkdir(parents=True, exist_ok=True)
        body_p.write_bytes(resp.content)
        meta_p.write_text(json.dumps({"url": resp.url, "status": resp.status,
                                      "headers": resp.headers, "t": resp.fetched_at}))
    if log:
        _log(resp)
    return resp


def get_json(url: str, params: dict | None = None, **kw):
    r = get(url, params, **kw)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status} from {r.url}: {r.text[:200]}")
    return r.json()


def ledger(since: float | None = None) -> list[dict]:
    """Ledger rows since a time (default: this Python session), newest title per URL merged in."""
    since = SESSION_START if since is None else since
    if not LEDGER.exists():
        return []
    rows, titles = [], {}
    for line in LEDGER.read_text().splitlines():
        try:
            j = json.loads(line)
        except json.JSONDecodeError:
            continue
        if j.get("t", 0) < since:
            continue
        if j.get("meta"):
            titles[j["url"]] = j["title"]
        else:
            rows.append(j)
    seen, out = set(), []
    for j in rows:
        if j["url"] in seen or not (200 <= j.get("status", 0) < 300):
            continue
        seen.add(j["url"])
        j["title"] = titles.get(j["url"]) or j.get("title")
        out.append(j)
    return out


def sources_md(since: float | None = None, only: list[str] | None = None) -> str:
    """Markdown 'Sources:' list of what this session fetched. Pass `only` (substrings) to filter."""
    rows = ledger(since)
    if only:
        rows = [r for r in rows if any(s in r["url"] for s in only)]
    lines = []
    for r in rows:
        u = r["url"]
        title = r.get("title") or (_host(u) + urllib.parse.urlsplit(u).path)[:90]
        lines.append(f"- [{title}]({u})")
    return "Sources:\n" + "\n".join(lines) if lines else "Sources: (none fetched)"
