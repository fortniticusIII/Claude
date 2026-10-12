# How the Wire collects

The Wire is a database-backed page. A scheduled task reads every feed in `feeds.json` each morning at 6:16 Eastern, half an hour before a daily geopolitical brief reads the result.

## Storage

- `feeds`: one doc per feed: name, url, region, kind, optional `skip` rule, plus health fields (status, last_ok, last_count, last_error).
- `items`: one doc per feed per day, id `<YYYYMMDD>-<feed id>`, body `{feed, source, region, day, run, items: [{t, title, link, summary}]}`. Kept 14 days.
- `meta/status`: last_run, window_from, added, feeds_ok, feeds_failed, note.

## Each run

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
