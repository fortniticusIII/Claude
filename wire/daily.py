"""Daily Pulse: the weekly Pulse's method, run every morning on the 7 days ending yesterday, with episodes.

    python3 -m wire.daily              # 7 days ending yesterday (Eastern)
    python3 -m wire.daily 2026-10-13   # 7 days ending on that date
Writes wire/pulse/daily.json, the doc 'pulse/daily' on the Wire, and prints a summary.
Run `python3 -m wire.census <end - 27 days> <end>` first so the last weeks are complete.

Method. Exactly wire/pulse.py (same baseline, noise and flag rules), so the daily and weekly readings
agree on any day they share. A 7-day window ending on any weekday is compared with the twelve 7-day
windows before it.

Episodes. Flags on overlapping windows repeat for days and can switch between 'watch' and 'heating',
so each flagged country also gets:
  since     the first day of its current run of flags in the same direction (heating and watch are
            both up, cooling is down), allowing one missed day
  new       true on the first day of that run
  upgraded  true if it was 'watch' yesterday and is 'heating' today
  outlets   how many outlets ran stories mentioning it this window, and the leading outlet's share
A daily reader should report new and upgraded rows, and mention continuing ones only if they changed.

Back-test (Aug 17 - Oct 13, 2026, 58 daily readings, census outlets only). The flags were real news
events on inspection of their headlines (an earthquake, a ferry disaster, elections, the Greenland
basing deal, Houthi-Saudi fighting, Kenya's first Ebola case, drone strikes on ships off Bulgaria).
Daily readings caught several episodes days before the Sunday reading or that the Sunday reading
missed entirely (Venezuela Sep 3-5, Greenland heating Sep 22-26, Taiwan Oct 6-7). The cost is volume:
see the printout of `python3 -m wire.daily --backtest START END`. Relevance (does this matter to the
reader?) is left to the reader's own scope rules: a single foreign minister's visit to Kyiv produces
a real, but minor, 'watch' through Ukrinform.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wire import pulse  # noqa: E402

pulse.stories = functools.lru_cache(maxsize=None)(pulse.stories)   # tagging is the slow part; reuse it
OUT = pulse.OUT / "daily.json"
UP, DOWN = {"heating", "watch"}, {"cooling"}
LOOKBACK = 21


def _dir(flag: str) -> str:
    return "up" if flag in UP else "down" if flag in DOWN else ""


@functools.lru_cache(maxsize=None)
def flags_on(end: dt.date) -> dict[str, str]:
    """{country code: flag} for the 7 days ending on `end`."""
    res = pulse.run(end, sorted(pulse.feed_names()))
    return {r["code"]: r["flag"] for r in res["countries"] if r["flag"]}


def episode(code: str, flag: str, end: dt.date, lookback: int = LOOKBACK) -> dict:
    """When this country's current run of same-direction flags began, allowing one missed day."""
    want, since, gap = _dir(flag), end, 0
    for k in range(1, lookback + 1):
        d = end - dt.timedelta(days=k)
        if _dir(flags_on(d).get(code, "")) == want:
            since, gap = d, 0
        else:
            gap += 1
            if gap > 1:
                break
    prev = flags_on(end - dt.timedelta(days=1)).get(code, "")
    return {"since": since.isoformat(), "new": since == end,
            "upgraded": prev == "watch" and flag == "heating"}


def reading(end: dt.date) -> tuple[dict, dict]:
    """(full result, card) for the 7 days ending on `end`."""
    res = pulse.run(end, sorted(pulse.feed_names()))
    names = pulse.feed_names()
    full = {r["code"]: r for r in res["countries"]}
    card = pulse.card(res)
    for row in card["rows"]:
        if not row["flag"]:
            continue
        row.update(episode(row["code"], row["flag"], end))
        by = full[row["code"]]["by_outlet"]
        top = max(by, key=by.get) if by else ""
        row["outlets"] = len(by)
        row["lead"] = {"outlet": names.get(top, top), "share": round(by[top] / sum(by.values()), 2)} if by else None
    card.update({"kind": "daily", "end": end.isoformat(),
                 "new": [r["name"] for r in card["rows"] if r.get("new") or r.get("upgraded")]})
    return res, card


def summary(card: dict) -> str:
    lines = [f"Daily Pulse for {card['week'][0]} to {card['week'][1]}: {card['stories']} stories from {len(card['outlets'])} outlets."]
    for r in card["rows"]:
        if not r["flag"]:
            continue
        tag = "NEW " if r.get("new") else "UP " if r.get("upgraded") else ""
        lead = f", {r['lead']['outlet']} {round(100 * r['lead']['share'])}%" if r.get("lead") else ""
        lines.append(f"  {tag}{r['flag']:8} {r['name']}: {r['observed']} vs {r['expected']} ({r['ratio']}x) since {r['since']}, {r['outlets']} outlets{lead}")
    if len(lines) == 1:
        lines.append("  Nothing unusual.")
    return "\n".join(lines)


def backtest(start: dt.date, stop: dt.date) -> None:
    """Every daily reading from start to stop: how many flags, how many new each day, and lead over Sundays."""
    d, per_day, new_per_day, episodes = start, [], [], []
    while d <= stop:
        fl = flags_on(d)
        per_day.append(len(fl))
        news = [(c, f) for c, f in fl.items() if episode(c, f, d)["new"]]
        new_per_day.append(len(news))
        for c, f in news:
            # The weekly reading covers the 7 days ending Saturday (the Sunday-evening upkeep) and reaches the
            # Monday brief; a daily reading ending on day d reaches the brief on d + 1.
            sat = d + dt.timedelta(days=(5 - d.weekday()) % 7)
            if sat <= stop:
                episodes.append((d, c, f, _dir(flags_on(sat).get(c, "")) == _dir(f), (sat - d).days + 1))
        d += dt.timedelta(days=1)
    n = len(per_day)
    print(f"{n} daily readings {start} to {stop}")
    print(f"flagged countries per reading: mean {sum(per_day) / n:.1f}, max {max(per_day)}")
    print(f"new or restarted episodes per day: mean {sum(new_per_day) / n:.1f}, days with none {sum(1 for x in new_per_day if not x)}")
    caught = [e for e in episodes if e[3]]
    leads = sorted(e[4] for e in caught)
    print(f"episodes with a following weekly reading: {len(episodes)}; also flagged weekly: {len(caught)}"
          f" (reached the brief a median {leads[len(leads) // 2] if leads else '-'} days earlier daily); weekly never flagged: {len(episodes) - len(caught)}")
    for d0, c, f, hit, lead in episodes:
        print(f"  {d0} {f:8} {pulse.NAMES.get(c, c):24} {'weekly too, ' + str(lead) + 'd earlier' if hit else 'daily only'}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--backtest" in sys.argv:
        backtest(dt.date.fromisoformat(args[0]), dt.date.fromisoformat(args[1]))
        sys.exit()
    end = dt.date.fromisoformat(args[0]) if args else dt.datetime.now(pulse.EASTERN).date() - dt.timedelta(days=1)
    res, card = reading(end)
    print(summary(card))
    if not res["outlets_used"] or res["stories_this_week"] < 200:
        print("daily: NOT written: too few outlets or stories to compare (census refresh failed?). Keep the old reading.")
        OUT.unlink(missing_ok=True)
    else:
        OUT.parent.mkdir(exist_ok=True)
        json.dump(card, open(OUT, "w"), indent=1, ensure_ascii=False)
        print(f"daily: {len(card['rows'])} rows -> {OUT}")
