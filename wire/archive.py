"""Long-term archive of what the Wire collected. The Wire deletes stories after 14 days; this keeps
headline, link, time and feed (never summaries) in wire/archive/YYYY-MM.jsonl.gz, one line per story.

    1. ArtifactData list 'items' on the Wire with out_dir=DUMP (limit 1000; page with the cursor if more).
    2. python3 -m wire.archive DUMP/items
    3. Commit wire/archive/.

Re-running over overlapping dumps is safe: lines are keyed by link. Run at least every 14 days (the
Sunday upkeep does it weekly) or stories are lost. For six outlets with no history route (Africanews,
BleepingComputer, JPost, Meduza, NPR World, Taipei Times) this archive is the only record, and the
Pulse starts using them once four weeks have built up.
"""
from __future__ import annotations

import datetime as dt
import glob
import gzip
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
OUT = Path(__file__).with_name("archive")


def day_of(t: str) -> str:
    when = dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
    if not when.tzinfo:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.astimezone(EASTERN).date().isoformat()


def load_month(month: str) -> dict:
    p = OUT / f"{month}.jsonl.gz"
    if not p.exists():
        return {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return {r["link"]: r for r in map(json.loads, f) if r.get("link")}


def load(feed: str | None = None) -> list[dict]:
    rows = []
    for p in sorted(OUT.glob("*.jsonl.gz")):
        rows += [r for r in load_month(p.name[:7]).values() if feed is None or r["feed"] == feed]
    return rows


def main(folder: str) -> None:
    new = {}
    for p in glob.glob(os.path.join(folder, "*.json")):
        doc = json.load(open(p))
        for i in doc.get("items", []):
            if not i.get("link") or not i.get("t"):
                continue
            link = i["link"].split("?traffic_source")[0]
            row = {"d": day_of(i["t"]), "t": i["t"], "feed": doc.get("feed"), "title": i.get("title", ""), "link": link}
            new.setdefault(row["d"][:7], {})[link] = row
    OUT.mkdir(exist_ok=True)
    for month, rows in sorted(new.items()):
        have = load_month(month)
        before = len(have)
        have.update(rows)
        with gzip.open(OUT / f"{month}.jsonl.gz", "wt", encoding="utf-8", compresslevel=9) as f:
            for r in sorted(have.values(), key=lambda r: (r["t"], r["link"])):
                f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"{month}: {len(have) - before} new, {len(have)} stored")


if __name__ == "__main__":
    main(sys.argv[1])
