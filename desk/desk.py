"""desk.py: my data helpers for this sandbox (Claude's Data Desk).

Get a fresh copy in any session:
    Artifact action=read, url=<Data Desk url>, path="desk.py"   (saves the file locally)
    import sys; sys.path.insert(0, "<folder it was saved to>"); import desk

What the shell can reach (tested 2026-10-12): git clone of public GitHub repos and
GitHub release downloads. raw.githubusercontent.com, the package registries and the
open web are not reachable. For those, use WebFetch, WebSearch or the sports and
weather tools, and never route around a block: report it instead.

    desk.sources()                     # what's catalogued
    df = desk.load("brent_daily")      # pandas DataFrame
    df = desk.load("nfl_pbp", season=2026)
    p  = desk.clone("owner/repo")      # any public repo, cached
    p  = desk.release("owner/repo", "tag", "file.csv.gz")
    rows = desk.from_dump(folder)      # docs saved by ArtifactData list ... out_dir
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("DESK_CACHE", Path.home() / ".cache" / "desk"))
TTL = 6 * 3600  # seconds before a cached repo or download is refreshed

# Catalogue of tested sources. Keep in step with the 'routes' collection on the Data Desk page.
SOURCES = {
    "brent_daily": dict(repo="datasets/oil-prices", path="data/brent-daily.csv",
                        what="Brent crude spot price, USD per barrel, daily (EIA)"),
    "wti_daily": dict(repo="datasets/oil-prices", path="data/wti-daily.csv",
                      what="WTI crude spot price, USD per barrel, daily (EIA)"),
    "fx_daily": dict(repo="datasets/exchange-rates", path="data/daily.csv",
                     what="Federal Reserve H.10 exchange rates against USD, daily, long format"),
    "sp500_monthly": dict(repo="datasets/s-and-p-500", path="data/data.csv",
                          what="S&P 500 level, dividends, earnings and CPI, monthly"),
    "gold_monthly": dict(repo="datasets/gold-prices", path="data/monthly.csv",
                         what="Gold price, USD per troy ounce, monthly"),
    "co2": dict(repo="owid/co2-data", path="owid-co2-data.csv",
                what="Our World in Data: CO2 and greenhouse gas emissions by country, annual"),
    "energy": dict(repo="owid/energy-data", path="owid-energy-data.csv",
                   what="Our World in Data: energy production and mix by country, annual"),
    "legislators": dict(repo="unitedstates/congress-legislators", path="legislators-current.yaml",
                        what="Current members of the US Congress with terms and ids"),
    "nfl_pbp": dict(release=("nflverse/nflverse-data", "pbp", "play_by_play_{season}.csv.gz"),
                    params=("season",),
                    what="NFL play-by-play for one season, refreshed nightly in season (nflverse)"),
}


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd)} failed: {r.stderr.strip()[-500:]}")
    return r.stdout


def _fresh(p: Path) -> bool:
    return p.exists() and time.time() - p.stat().st_mtime < TTL


def clone(repo: str, refresh: bool = False) -> Path:
    """Shallow-clone github.com/<owner/repo> into the cache, or update it, and return its folder."""
    dest = CACHE / "git" / repo.replace("/", "__")
    stamp = dest / ".desk_pulled"
    if not (dest / ".git").exists():
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{repo}", str(dest)])
    elif refresh or not _fresh(stamp):
        _run(["git", "fetch", "-q", "--depth", "1", "origin"], cwd=dest)
        _run(["git", "reset", "-q", "--hard", "FETCH_HEAD"], cwd=dest)
    stamp.touch()
    return dest


def last_commit(repo: str) -> str:
    """ISO date of the newest commit in a cached clone (clones it first if needed)."""
    return _run(["git", "log", "-1", "--format=%cI"], cwd=clone(repo)).strip()


def release(repo: str, tag: str, name: str, refresh: bool = False) -> Path:
    """Download one GitHub release asset into the cache and return its path."""
    dest = CACHE / "releases" / repo.replace("/", "__") / tag / name
    if _fresh(dest) and not refresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{repo}/releases/download/{tag}/{name}"
    req = urllib.request.Request(url, headers={"User-Agent": "desk.py"})
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(req, timeout=600) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f)
    part.replace(dest)
    return dest


def read(path: str | Path, **kw):
    """Read a csv, csv.gz, json or yaml file into a pandas DataFrame."""
    import pandas as pd
    p = str(path)
    if p.endswith((".csv", ".csv.gz")):
        return pd.read_csv(p, low_memory=False, **kw)
    if p.endswith(".json"):
        return pd.read_json(p, **kw)
    if p.endswith((".yaml", ".yml")):
        import yaml
        with open(p) as f:
            return pd.json_normalize(yaml.safe_load(f))
    if p.endswith(".parquet"):
        return pd.read_parquet(p, **kw)  # needs pyarrow, which this sandbox lacks
    raise ValueError(f"don't know how to read {p}")


def path(name: str, refresh: bool = False, **params) -> Path:
    """Local path of a catalogued source, fetching it if needed."""
    s = SOURCES[name]
    missing = [k for k in s.get("params", ()) if k not in params]
    if missing:
        raise TypeError(f"{name} needs {', '.join(missing)}")
    if "repo" in s:
        p = clone(s["repo"], refresh) / s["path"]
        if not p.exists():
            raise FileNotFoundError(f"{s['path']} is no longer in {s['repo']}")
        return p
    repo, tag, pattern = s["release"]
    return release(repo, tag, pattern.format(**params), refresh)


def load(name: str, refresh: bool = False, **params):
    """Catalogued source as a DataFrame, e.g. load('nfl_pbp', season=2026)."""
    return read(path(name, refresh, **params))


def sources() -> None:
    for k, s in SOURCES.items():
        extra = f"  (needs {', '.join(s['params'])})" if s.get("params") else ""
        print(f"{k:15} {s['what']}{extra}")


def from_dump(folder: str | Path) -> list[dict]:
    """Docs written by `ArtifactData list ... out_dir=<folder>`: one dict per doc, with 'id'."""
    rows = []
    for f in sorted(Path(folder).rglob("*.json")):
        with open(f) as fh:
            j = json.load(fh)
        body = j.get("data", j) if isinstance(j, dict) else {"value": j}
        rows.append({"id": f.stem, **body})
    return rows


def wire_items(folder: str | Path):
    """Flatten Wire 'items' docs (one per feed per run) into one DataFrame of stories."""
    import pandas as pd
    out = []
    for doc in from_dump(folder):
        for it in doc.get("items", []):
            out.append({"source": doc.get("source"), "region": doc.get("region"), "day": doc.get("day"), **it})
    df = pd.DataFrame(out)
    if not df.empty and "t" in df:
        df["t"] = pd.to_datetime(df["t"], utc=True, errors="coerce")
        df = df.sort_values("t", ascending=False).drop_duplicates("link")
    return df


def probe(url: str) -> str:
    """One-shot reachability check from the shell. A 403 means policy: report it, don't work around it."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "desk.py"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"reachable ({r.status})"
    except urllib.error.HTTPError as e:
        return f"reachable, HTTP {e.code}"
    except Exception as e:  # tunnel refused, DNS failure, timeout
        return f"blocked or unreachable: {str(e)[:120]}"


if __name__ == "__main__":
    sources()
