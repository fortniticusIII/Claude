"""kit.selftest: one live probe per source, so a session (or the Sunday upkeep) knows what works today.

    python3 -m kit.selftest                 # table of ok / limited / refused / fail
    python3 -m kit.selftest --routes DIR    # also write Data Desk 'routes' docs as JSON files to DIR,
                                            # then ArtifactData batch them (file_path per doc)
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from . import data, http, lookup, scholar, web

# (id, group, name, what, how, freshness, probe)
ROUTES = [
    ("kit-crossref", "Research literature", "Crossref", "Metadata and citation counts for anything with a DOI; landmark search ranks a topic by citations.",
     'scholar.crossref("query", n=10, since="2023")\nscholar.landmarks("topic", n=10, biomed=False)\nscholar.doi("10.xxxx/...")', "live",
     lambda: len(scholar.crossref("adaptive network design", n=2))),
    ("kit-arxiv", "Research literature", "arXiv", "Preprints in physics, CS, maths, stats; abstracts and PDF links.",
     'scholar.arxiv("mixture of experts routing", n=10, sort="submittedDate")', "live",
     lambda: len(scholar.arxiv("transformer attention", n=2))),
    ("kit-europepmc", "Research literature", "Europe PMC", "Biomedical literature with abstracts, citation counts and open-access full-text links.",
     'scholar.europepmc("TITLE_ABS:\\"x\\" AND TITLE_ABS:\\"y\\"", n=10, sort="CITED desc")', "live",
     lambda: len(scholar.europepmc("semaglutide", n=2))),
    ("kit-pubmed", "Research literature", "PubMed", "NCBI ranking with MeSH and publication-type filters (trials, meta-analyses).",
     'scholar.pubmed("x[ti] AND randomized controlled trial[pt]", n=10)', "live",
     lambda: len(scholar.pubmed("semaglutide[ti]", n=2))),
    ("kit-opencitations", "Research literature", "OpenCitations", "Which DOIs cite a given DOI (partial coverage).",
     'scholar.cited_by("10.1126/science.1177894")', "weekly",
     lambda: len(scholar.cited_by("10.1126/science.1177894"))),
    ("kit-fred", "Economics and statistics", "FRED", "Any St. Louis Fed series: rates, prices, jobs, output.",
     'data.fred("UNRATE", start="2020-01-01")', "daily",
     lambda: str(data.fred("DGS10").dropna()["date"].max().date())),
    ("kit-worldbank", "Economics and statistics", "World Bank", "World Development Indicators by country and year.",
     'data.worldbank("NY.GDP.MKTP.CD", "US;CN", start=2000)', "annual",
     lambda: int(data.worldbank("SP.POP.TOTL", "US", 2020)["year"].max())),
    ("kit-imf", "Economics and statistics", "IMF DataMapper", "WEO macro series with IMF projections (growth, inflation, debt).",
     'data.imf("NGDP_RPCH", ["USA", "CHN"])', "twice a year",
     lambda: int(data.imf("NGDP_RPCH", ["USA"])["year"].max())),
    ("kit-owid", "Economics and statistics", "Our World in Data", "Any OWID chart by slug, plus its sources and units for the citation.",
     'data.owid("life-expectancy", ["USA", "JPN"])\ndata.owid_meta("life-expectancy")', "varies by chart",
     lambda: int(data.owid("life-expectancy", ["USA"])["year"].max())),
    ("kit-eurostat", "Economics and statistics", "Eurostat", "EU statistics, decoded from JSON-stat.",
     'data.eurostat("nama_10_gdp", geo="DE", unit="CP_MEUR", na_item="B1GQ")', "varies",
     lambda: len(data.eurostat("nama_10_gdp", geo="DE", unit="CP_MEUR", na_item="B1GQ", sinceTimePeriod="2022"))),
    ("kit-ecb", "Economics and statistics", "ECB Data Portal", "Euro area rates and exchange rates by series key.",
     'data.ecb("EXR/D.USD.EUR.SP00.A", last=30)', "daily",
     lambda: str(data.ecb("EXR/D.USD.EUR.SP00.A", last=1)["TIME_PERIOD"].iloc[-1])),
    ("kit-oecd", "Economics and statistics", "OECD", "OECD SDMX data by dataflow and series key.",
     'data.oecd("OECD.SDD.STES,DSD_STES@DF_CLI,4.1", "USA.M.LI...AA...H", last=12)', "monthly",
     lambda: str(data.oecd("OECD.SDD.STES,DSD_STES@DF_CLI,4.1", "USA.M.LI...AA...H", last=1)["TIME_PERIOD"].iloc[-1])),
    ("kit-treasury", "Economics and statistics", "US Treasury Fiscal Data", "Debt to the penny, interest rates, monthly statements.",
     'data.treasury("v2/accounting/od/debt_to_penny", size=5)', "daily",
     lambda: data.treasury("v2/accounting/od/debt_to_penny", size=1)["record_date"].iloc[0]),
    ("kit-comtrade", "Economics and statistics", "UN Comtrade (preview)", "Trade flows by reporter, partner and HS code; 500 rows without a key.",
     'data.comtrade(reporter=842, period=2023, flow="M", cmd="AG2")', "annual",
     lambda: len(data.comtrade(842, 2023))),
    ("kit-wikidata", "Reference", "Wikidata SPARQL", "Structured facts: people, offices, dates, places. Check anything current against a live source.",
     'data.wikidata("SELECT ... WHERE { ... }")', "live, community-edited",
     lambda: len(data.wikidata("SELECT ?x WHERE { wd:Q42 wdt:P31 ?x }"))),
    ("kit-crypto", "Economics and statistics", "CoinGecko", "Crypto spot prices.",
     'data.crypto(["bitcoin", "ethereum"])', "live",
     lambda: float(data.crypto(["bitcoin"])["usd"].iloc[0])),
    ("kit-web", "Web pages", "Page and PDF text", "The actual text of a page, PDF or HTML table, with title and date; robots.txt honoured, refused hosts skipped.",
     'web.page(url).text / .find("term")\nweb.pdf(url, pages="1-5")\nweb.tables(url)\nweb.feed(rss_url)', "live",
     lambda: len(web.page("https://www.federalreserve.gov/monetarypolicy/openmarket.htm", ttl=0).text)),
    ("kit-packages", "Reference", "PyPI and npm", "Latest version and release date of a package, before claiming 'the latest'.",
     'lookup.package("pandas")\nlookup.package("react", npm=True)', "live",
     lambda: lookup.package("requests")["latest"]),
    ("kit-fedreg", "Government and law", "Federal Register", "US rules, proposed rules, notices and presidential documents.",
     'lookup.fedreg("artificial intelligence", n=10, kind="RULE")', "daily",
     lambda: lookup.fedreg("energy", 1)["date"].iloc[0]),
    ("kit-courts", "Government and law", "CourtListener", "US court opinions by search.",
     'lookup.courts("geofence warrant", n=10)', "daily",
     lambda: len(lookup.courts("fourth amendment", 2))),
    ("kit-nws", "Reference", "National Weather Service", "US forecasts by coordinates (the weather tool covers elsewhere).",
     'lookup.forecast(40.71, -74.0)', "hourly",
     lambda: lookup.forecast(38.9, -77.0)["period"].iloc[0]),
    ("kit-books", "Culture", "Open Library", "Books: editions, first publication, subjects.",
     'lookup.books("title or author")', "live",
     lambda: int(lookup.books("dune", 1)["first_year"].iloc[0])),
    ("kit-music", "Culture", "MusicBrainz", "Artists and discographies with dates.",
     'lookup.music_artist("Rush")\nlookup.music_releases(mbid, kind="album")', "live",
     lambda: lookup.music_artist("Rush", 1)["name"].iloc[0]),
    ("kit-steam", "Culture", "Steam store", "Games: price, release date, genres, PC requirements.",
     'lookup.game("Bodycam")', "live",
     lambda: lookup.game("Baldur's Gate 3")["name"]),
    ("kit-hn", "Culture", "Hacker News", "What engineers are discussing, by search.",
     'lookup.hn("local llm inference", n=10)', "live",
     lambda: len(lookup.hn("python", 2))),
]

KNOWN_LIMITS = [
    ("kit-limit-shared-ip", "Rate-limited from the shared egress IP (2026-10-12)",
     "OpenAlex (needs a free key), Semantic Scholar, Wikipedia REST API, BLS, GDELT. Use WebFetch for Wikipedia; Crossref and Europe PMC for papers."),
    ("kit-limit-keys", "Need an API key",
     "Census API, Congress.gov, EIA. I keep no keys; read the agency pages with WebFetch, or tell the user what a key would unblock."),
    ("kit-limit-refused", "Refuse automated clients",
     "Reddit, TechPowerUp, SEC EDGAR (needs a contact email in the User-Agent), plus anything WebFetch declines. Listed in kit/refused.json; never route around."),
]


def probe(route) -> dict:
    rid, group, name, what, how, fresh, fn = route
    t0 = time.time()
    try:
        sample = fn()
        status, note = "ok", str(sample)[:60]
    except http.RateLimited as e:
        status, note = "limited", str(e)[:120]
    except http.Refused as e:
        status, note = "blocked", str(e)[:120]
    except Exception as e:
        status, note = "fail", f"{type(e).__name__}: {str(e)[:120]}"
    return {"id": rid, "group": group, "name": name, "what": what, "how": how, "freshness": fresh,
            "status": status, "sample": note, "secs": round(time.time() - t0, 1)}


def run(routes=ROUTES) -> list[dict]:
    http.FRESH = True
    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(probe, routes))


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", help="write Data Desk route docs (JSON) to this folder")
    a = ap.parse_args(argv)
    res = run()
    w = max(len(r["name"]) for r in res)
    for r in res:
        print(f"{r['status']:8} {r['name']:<{w}}  {r['secs']:>5}s  {r['sample']}")
    ok = sum(r["status"] == "ok" for r in res)
    print(f"\n{ok}/{len(res)} sources answering, {date.today()}")
    if a.routes:
        out = Path(a.routes)
        out.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        for i, r in enumerate(res):
            doc = {"name": r["name"], "kind": "kit", "group": r["group"], "status": r["status"] if r["status"] != "fail" else "limited",
                   "what": r["what"], "how": r["how"], "freshness": r["freshness"], "tested": today, "order": i}
            if r["status"] != "ok":
                doc["note"] = r["sample"]
            (out / f"{r['id']}.json").write_text(json.dumps(doc))
        for rid, name, what in KNOWN_LIMITS:
            (out / f"{rid}.json").write_text(json.dumps({"name": name, "kind": "blocked", "status": "blocked",
                                                         "what": what, "tested": today}))
        print(f"route docs written to {out}")
    return 0 if ok >= len(res) * 0.7 else 1


if __name__ == "__main__":
    sys.exit(main())
