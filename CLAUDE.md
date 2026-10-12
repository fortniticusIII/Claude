# Working in this repo

This is my (Claude's) workspace. My memory lives in the work log artifact
(https://claude.ai/artifact/Hsi1HpXecLi5iRa3WpyqQp); this repo holds code and safe-to-publish notes.

## Research kit (`kit/`)

Set up in any session: `bash /home/claude/claude/bootstrap.sh` (installs extras, checks every
source live), then `import sys; sys.path.insert(0, "/home/claude/claude"); import kit; kit.help()`.

- `kit.scholar` papers: `landmarks(topic)` for the most-cited work, `find(q)` across Crossref,
  Europe PMC and arXiv, `doi(d)`, `pubmed(q)`, `cited_by(doi)`.
- `kit.data` official statistics as DataFrames: FRED, World Bank, IMF, OWID, Eurostat, ECB, OECD,
  Treasury, Comtrade, Wikidata. `df.attrs["source"]` holds the citable page.
- `kit.web` exact text of pages, PDFs, tables and feeds (use it when a figure or date must be exact).
- `kit.lookup` packages, Federal Register, courts, NWS, books, music, Steam, Hacker News.
- `kit.qa` check any page before publishing: `python3 -m kit.qa page.html [--mock data.json]`.
- `kit.sources()` prints a Sources list of everything fetched this session.

Rules the kit enforces and I keep: honest User-Agent, robots.txt for pages, pacing per host, one
short retry on 429. A refusal (403, proxy block, a site WebFetch declined) is policy: add it to
`kit/refused.json` and report it, never route around it. Quoting limits apply to text read this way.

## Commits

Commit as `Claude` / `noreply@anthropic.com` (`git config user.name Claude && git config user.email
noreply@anthropic.com`): sessions sign commits for that identity, and the stop hook flags anything else
as Unverified. Keep the session's Co-Authored-By and Claude-Session trailers. Never commit anything about the user (that stays in the log).
