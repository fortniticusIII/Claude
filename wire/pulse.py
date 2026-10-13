"""The Pulse: which countries are getting unusual attention in the Wire's outlets this week.

    python3 -m wire.pulse                 # 7 days ending yesterday (Eastern) vs the 12 weeks before
    python3 -m wire.pulse 2026-10-12      # 7 days ending on that date
Writes wire/pulse/<end>.json and prints a summary.

Method. Each outlet has its own habits (Ukrinform is about Ukraine, NK News about North Korea), so
raw counts would mostly measure the feed mix. Instead, for every outlet f and country c the baseline
share p_fc is the fraction of f's stories that mentioned c over the 12 weeks before, shrunk a little
toward the all-outlet share so a country an outlet never covered still has a small expectation.
This week's expected count is E_c = sum over outlets of (stories f ran this week) x p_fc, and the
observed count O_c is how many of those stories mentioned c. The ratio O/E is attention against the
outlets' own habits, already adjusted for how much each outlet published.

Stories cluster (one event brings many stories), so plain Poisson noise understates the swings. For
each country the 12 baseline weeks are scored the same way (each against the other 11), and the
excess variance there sets the noise for this week's z-score. 'Highest in 13 weeks' means this week's
ratio beats every one of the 12 baseline weeks.

Flags (see flag()): 'heating' at z >= 3 with O >= 8 and O/E >= 1.5; 'watch' for a sudden jump on few
stories (z >= 3, O >= 4, O/E >= 3); 'cooling' at z <= -3 with E >= 10 and O/E <= 0.67, or a country
expected 20+ stories at its lowest ratio of every week compared. Back-tested over the 9 weeks to Oct 12,
2026, heating fired about once a week, on events like Brazil's election, fighting in Tigray, the
Houthis, Germany's state election and a Nepal disaster. These are attention measures: they show what
the outlets wrote about, not how much happened on the ground.

Streams: outlets with a census (wire/census.py) use it for every week, so this week and the baseline
are counted the same way. Outlets without one use the Wire archive (wire/archive.py) and join once
their archive covers this week and at least 4 baseline weeks.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wire import archive, census  # noqa: E402
from wire.places import NAMES, slug_text, tag  # noqa: E402

EASTERN = ZoneInfo("America/New_York")
OUT = Path(__file__).with_name("pulse")
FEEDS = json.load(open(Path(__file__).with_name("feeds.json")))
WEEKS = 12
MIN_BASE_WEEKS = 4
ALPHA = 10.0          # shrinkage weight, in stories, toward the all-outlet share
HOME = "US"


def feed_names():
    rows = FEEDS if isinstance(FEEDS, list) else FEEDS.get("feeds", FEEDS)
    if isinstance(rows, dict):
        return {k: v.get("name", k) for k, v in rows.items()}
    return {r.get("id") or r.get("feed"): r.get("name") for r in rows}


def stories(feed: str):
    """(day, codes, headline-or-slug, link) for every story we have for an outlet, and which stream."""
    rows, stream = census.load(feed), "census"
    if not rows:
        rows, stream = archive.load(feed), "wire archive"
    out = []
    for r in rows:
        text = r.get("title") or slug_text(r["link"])
        out.append((r["d"], tag(text, slug=not r.get("title")), text, r["link"]))
    return out, stream


def flag(o: float, e: float, r: float, z: float, ratios: list[float]) -> str:
    """heating: a clear rise with enough stories to mean something. watch: a sudden jump on few stories.
    cooling: a clear drop, or a big country at its lowest of every week compared."""
    if z >= 3 and o >= 8 and r >= 1.5:
        return "heating"
    if z >= 3 and o >= 4 and r >= 3:
        return "watch"
    if z <= -3 and e >= 10 and r <= 0.67:
        return "cooling"
    if e >= 20 and r <= 0.7 and len(ratios) >= 8 and r < min(ratios):
        return "cooling"
    return ""


def windows(end: dt.date):
    """[(start, end)] for this week (index 0) and the WEEKS before it, as ISO dates."""
    return [((end - dt.timedelta(days=7 * k + 6)).isoformat(), (end - dt.timedelta(days=7 * k)).isoformat())
            for k in range(WEEKS + 1)]


def run(end: dt.date, all_feeds: list[str]) -> dict:
    wins = windows(end)
    counts = {}           # feed -> list over windows of (n, Counter of codes)
    used, skipped, streams, examples = [], {}, {}, defaultdict(list)
    for f in all_feeds:
        rows, stream = stories(f)
        if not rows:
            skipped[f] = "no stories stored"; continue
        first = min(d for d, *_ in rows)
        per = []
        for k, (s, e) in enumerate(wins):
            if s < first:            # window starts before this outlet's data does
                per.append(None); continue
            n, c = 0, Counter()
            for d, codes, text, link in rows:
                if s <= d <= e:
                    n += 1; c.update(codes)
                    if k == 0:
                        for code in codes:
                            examples[code].append((f, d, text, link))
            per.append((n, c))
        base_weeks = sum(1 for x in per[1:] if x is not None and x[0] > 0)
        if per[0] is None:
            skipped[f] = f"{stream} starts {first}, after this week began"; continue
        if per[0][0] == 0:
            skipped[f] = "no stories this week"; continue
        if base_weeks < MIN_BASE_WEEKS:
            skipped[f] = f"only {base_weeks} baseline weeks ({stream} starts {first})"; continue
        counts[f] = per; used.append(f); streams[f] = stream

    # all-outlet baseline share per country, for shrinkage
    tot_n, tot_c = 0, Counter()
    for f in used:
        for x in counts[f][1:]:
            if x: tot_n += x[0]; tot_c.update(x[1])
    pool = {c: tot_c[c] / tot_n for c in tot_c} if tot_n else {}
    codes = set(pool) | {c for f in used for c in counts[f][0][1]}

    def share(f, c, skip=None):
        n = k = 0
        for j, x in enumerate(counts[f][1:], start=1):
            if x and j != skip:
                n += x[0]; k += x[1][c]
        return (k + ALPHA * pool.get(c, 0.0)) / (n + ALPHA)

    def score(c, week, skip=None):
        o = e = 0.0
        for f in used:
            x = counts[f][week]
            if not x:
                continue
            o += x[1][c]; e += x[0] * share(f, c, skip)
        return o, e

    rows = []
    for c in codes:
        o, e = score(c, 0)
        hist = []
        for j in range(1, WEEKS + 1):
            oj, ej = score(c, j, skip=j)
            if ej > 0:
                hist.append((oj, ej))
        if e <= 0:
            continue
        phi = max(1.0, sum((oj - ej) ** 2 / ej for oj, ej in hist) / len(hist)) if hist else 1.0
        z = (o - e) / math.sqrt(phi * e)
        ratios = [oj / ej for oj, ej in hist]
        r = o / e
        rows.append({
            "code": c, "name": NAMES.get(c, c), "observed": int(o), "expected": round(e, 1), "ratio": round(r, 2),
            "z": round(z, 1), "dispersion": round(phi, 2),
            "baseline_ratios": [round(x, 2) for x in ratios],
            "rank": 1 + sum(x >= r for x in ratios), "weeks_compared": len(ratios) + 1,
            "flag": flag(o, e, r, z, ratios),
            "by_outlet": {f: counts[f][0][1][c] for f in used if counts[f][0][1][c]},
            "examples": [{"outlet": f, "day": d, "text": t, "link": l} for f, d, t, l in sorted(examples[c], key=lambda x: x[1], reverse=True)[:6]],
        })
    rows.sort(key=lambda r: r["z"], reverse=True)
    week_n = {f: counts[f][0][0] for f in used}
    return {
        "end": end.isoformat(), "week": list(wins[0]), "baseline": [wins[-1][0], wins[1][1]],
        "outlets_used": {f: {"stream": streams[f], "stories_this_week": week_n[f],
                             "baseline_weeks": sum(1 for x in counts[f][1:] if x)} for f in used},
        "outlets_skipped": skipped, "stories_this_week": sum(week_n.values()),
        "method": "see wire/pulse.py docstring", "countries": rows,
    }


def summary(res: dict, top: int = 8) -> str:
    rows = res["countries"]
    lines = [f"Pulse for {res['week'][0]} to {res['week'][1]}: {res['stories_this_week']} stories from "
             f"{len(res['outlets_used'])} outlets, against {res['baseline'][0]} to {res['baseline'][1]}."]
    hot = [r for r in rows if r["flag"] == "heating"]
    watch = [r for r in rows if r["flag"] == "watch"]
    cold = [r for r in rows if r["flag"] == "cooling"]
    fmt = lambda r: (f"{r['name']}: {r['observed']} stories vs {r['expected']} expected ({r['ratio']}x, z {r['z']}"
                     + (", highest in %d weeks" % r["weeks_compared"] if r["rank"] == 1 else f", rank {r['rank']} of {r['weeks_compared']}") + ")")
    lines.append("Heating: " + ("; ".join(fmt(r) for r in hot[:top]) if hot else "none"))
    lines.append("Watch: " + ("; ".join(fmt(r) for r in watch[:top]) if watch else "none"))
    lines.append("Cooling: " + ("; ".join(fmt(r) for r in sorted(cold, key=lambda r: r['z'])[:top]) if cold else "none"))
    if res["outlets_skipped"]:
        lines.append("Not yet counted: " + ", ".join(f"{k} ({v})" for k, v in res["outlets_skipped"].items()))
    return "\n".join(lines)


if __name__ == "__main__":
    end = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.datetime.now(EASTERN).date() - dt.timedelta(days=1)
    names = feed_names()
    res = run(end, sorted(names))
    OUT.mkdir(exist_ok=True)
    json.dump(res, open(OUT / f"{end.isoformat()}.json", "w"), indent=1, ensure_ascii=False)
    print(summary(res))
