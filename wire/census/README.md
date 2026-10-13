Headline census files, one per outlet: `<feed>.jsonl.gz`, one story per line
(`d` Eastern publication day, `link`, and `title` where the source gives one).
Built by `python3 -m wire.census START END [feed...]` from each outlet's own sitemaps or paged feeds.
Used by `wire/pulse.py`. Only headlines and links are kept; no article text.
