# How the Wire collects

**Since Oct 13, 2026 the preferred method is `wire/collect.py`**, which parses each feed's XML directly from the shell (see its docstring for the steps). An audit of the Oct 13 scheduled run found the WebFetch method below missed 80 of 213 in-window stories (38%): The War Zone 5 of 6, Breaking Defense 7 of 13, Defense News 8 of 22, Meduza 21 of 30, and the whole day's Taipei Times. WebFetch seems to serve stale copies of some feeds. The method below stays as the fallback for any feed the shell can't reach.

The Wire is a database-backed page. A scheduled task reads every feed in `feeds.json` each morning at 6:16 Eastern, half an hour before a daily geopolitical brief reads the result.

## Storage

- `feeds`: one doc per feed: name, url, region, kind, optional `skip` rule, plus health fields (status, last_ok, last_count, last_error).
- `items`: one doc per feed per day, id `<YYYYMMDD>-<feed id>`, body `{feed, source, region, day, run, items: [{t, title, link, summary}]}`. Kept 14 days.
- `meta/status`: last_run, window_from, added, feeds_ok, feeds_failed, note.

## Each run (WebFetch method, now the fallback)

1. Window start = now minus 30 hours (UTC).
2. WebFetch every feed with this prompt:

   > This is an RSS or Atom feed. List every item published on or after `<WINDOW START>`, newest first, one per line in exactly this form:
   > ISO-8601 date-time with offset | title | link | one plain sentence of at most 25 words, in your own words, saying what the item reports (or - if the feed gives no description)
   > No other text. If no item is that recent, reply NONE.

3. Parse on ` | `. Drop items older than the window (some feeds ignore it), apply the feed's skip rule, and drop links already stored for today or yesterday.
4. Store only title, link, time and the one-sentence summary. Never more of a story than that.
5. Mark feeds that fail as failing. A refusal (blocked site, robots.txt) is final: never route around it.
6. Delete items docs older than 14 days.

## Lessons from the first run (Oct 12, 2026)

- Weekends are quiet: half the feeds had nothing new.
- Defense News returned items older than the window; the date filter in code catches it.
- Al Jazeera mixes in sport and the Taipei Times mixes in lifestyle, hence their skip rules.
- Long feeds stop at about 100,000 characters in WebFetch, which still covers the newest items.

## Lessons from the first direct runs (Oct 14, 2026)

- Direct parsing worked first time from a scheduled session (the open web is reachable there): 219 stories, 17 of 17 feeds, no fallback, 2.5 minutes.
- Feeds only hold their newest N stories. Busy outlets publish more than that between morning runs: Al Jazeera ~50 a day with 25 in its feed, Ukrinform ~64 a day (p90 93) with 30, Meduza 30. Fixes: Al Jazeera's Google News sitemap is read alongside its feed (feed doc field `sitemap`), and the collector runs twice a day (6:16am and 6:16pm Eastern). Ukrinform can still overflow on its busiest days.
- Defense News looked capped too, but the census showed every missed Oct 13 URL was a video, which its RSS never carries.
