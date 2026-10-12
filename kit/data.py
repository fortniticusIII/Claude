"""kit.data: official statistics straight from the publisher, as tidy pandas DataFrames.

Every function returns a DataFrame and records the source URL in the kit ledger, so the
numbers in an answer can be traced. Each was tested live from this sandbox on 2026-10-12.

    from kit import data
    data.fred("UNRATE")                                   # any FRED series id (US macro, rates, prices)
    data.worldbank("NY.GDP.MKTP.CD", "US;CN;IN", 2000)    # World Bank WDI, tidy: country, year, value
    data.owid("life-expectancy", ["USA", "JPN"])          # any Our World in Data chart slug
    data.owid_meta("life-expectancy")                      # its sources and units, for the citation
    data.imf("NGDP_RPCH", ["USA", "CHN"])                  # IMF WEO DataMapper (includes projections)
    data.eurostat("nama_10_gdp", geo="DE", unit="CP_MEUR", na_item="B1GQ")
    data.ecb("EXR/D.USD.EUR.SP00.A", last=30)             # ECB data portal series key
    data.oecd("OECD.SDD.STES,DSD_STES@DF_CLI,4.1", "USA.M.LI...AA...H", last=12)
    data.treasury("v2/accounting/od/debt_to_penny", sort="-record_date", size=5)
    data.comtrade(reporter=842, period=2023, flow="M")    # UN Comtrade preview (500 rows max)
    data.wikidata("SELECT ?x ?xLabel WHERE { wd:Q30 wdt:P6 ?x . SERVICE wikibase:label { bd:serviceParam wikibase:language 'en'. } }")
    data.crypto(["bitcoin", "ethereum"])                   # CoinGecko spot prices in USD
    data.desk("brent_daily")                               # the GitHub-hosted sets catalogued in desk/desk.py

Not reachable without a key from here (2026-10-12): BLS (shared daily quota), Census API,
Congress.gov, EIA. For those, use WebFetch on the agency page or ask whether a key is wanted.
"""
from __future__ import annotations

import io
import itertools
import sys
from pathlib import Path

import pandas as pd

from . import http


def _csv(url: str, params: dict | None = None, **kw) -> pd.DataFrame:
    r = http.get(url, params)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status} from {r.url}: {r.text[:200]}")
    return pd.read_csv(io.StringIO(r.text), **kw)


# ---------- United States ----------
def fred(series: str, start: str | None = None) -> pd.DataFrame:
    """FRED series by id (find ids with WebSearch 'FRED <topic>'). Columns: date, value. Missing values are NaN."""
    df = _csv("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": series}, na_values=["."])
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    df.attrs.update(series=series, source=f"https://fred.stlouisfed.org/series/{series}")
    http.cite(df.attrs["source"], f"FRED: {series}")
    return df[df["date"] >= start] if start else df


def treasury(endpoint: str, sort: str = "-record_date", size: int = 100, **filters) -> pd.DataFrame:
    """US Treasury Fiscal Data API, e.g. 'v2/accounting/od/debt_to_penny',
    'v1/accounting/od/avg_interest_rates', 'v1/accounting/mts/mts_table_5'. filters become filter=k:eq:v."""
    params = {"sort": sort, "page[size]": size}
    if filters:
        params["filter"] = ",".join(f"{k}:eq:{v}" for k, v in filters.items())
    j = http.get_json(f"https://api.fiscaldata.treasury.gov/services/api/fiscal_service/{endpoint.strip('/')}", params)
    df = pd.DataFrame(j["data"])
    http.cite(f"https://fiscaldata.treasury.gov/api-documentation/", f"US Treasury Fiscal Data: {endpoint}")
    for c in df.columns:
        if c.endswith(("_amt", "_rate", "_pct")):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ---------- international ----------
def worldbank(indicator: str, countries: str = "all", start: int | None = None, end: int | None = None) -> pd.DataFrame:
    """World Bank indicator (e.g. NY.GDP.MKTP.CD, SP.POP.TOTL, FP.CPI.TOTL.ZG). countries 'US;CN' (ISO2/ISO3) or 'all'."""
    params = {"format": "json", "per_page": 20000}
    if start or end:
        params["date"] = f"{start or 1960}:{end or 2100}"
    j = http.get_json(f"https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}", params)
    if len(j) < 2 or not j[1]:
        raise RuntimeError(f"no data: {j[0]}")
    df = pd.DataFrame([{"country": r["country"]["value"], "iso3": r["countryiso3code"], "year": int(r["date"]),
                        "value": r["value"]} for r in j[1]])
    df.attrs.update(indicator=j[1][0]["indicator"]["value"], updated=j[0].get("lastupdated"),
                    source=f"https://data.worldbank.org/indicator/{indicator}")
    http.cite(df.attrs["source"], f"World Bank: {df.attrs['indicator']}")
    return df.sort_values(["country", "year"]).reset_index(drop=True)


def owid(slug: str, countries: list[str] | None = None) -> pd.DataFrame:
    """Any Our World in Data grapher chart by its URL slug. countries: ISO3 codes or names."""
    params = {"v": 1, "csvType": "full", "useColumnShortNames": "true"}
    df = _csv(f"https://ourworldindata.org/grapher/{slug}.csv", params)
    if countries:
        df = df[df["code"].isin(countries) | df["entity"].isin(countries)]
    df.attrs["source"] = f"https://ourworldindata.org/grapher/{slug}"
    http.cite(df.attrs["source"], f"Our World in Data: {slug}")
    return df.reset_index(drop=True)


def owid_meta(slug: str) -> dict:
    """Title, units, original sources and citation for an OWID chart."""
    return http.get_json(f"https://ourworldindata.org/grapher/{slug}.metadata.json", {"v": 1})


def imf(indicator: str, countries: list[str] | None = None) -> pd.DataFrame:
    """IMF DataMapper (WEO and others), e.g. NGDP_RPCH (real GDP growth), PCPIPCH (inflation),
    LUR (unemployment), GGXWDG_NGDP (gross debt % GDP). Includes IMF projections: check the year."""
    j = http.get_json(f"https://www.imf.org/external/datamapper/api/v1/{indicator}")
    rows = [{"iso3": c, "year": int(y), "value": v}
            for c, ys in j["values"][indicator].items() for y, v in ys.items()]
    df = pd.DataFrame(rows)
    if countries:
        df = df[df["iso3"].isin(countries)]
    df.attrs["source"] = f"https://www.imf.org/external/datamapper/{indicator}"
    http.cite(df.attrs["source"], f"IMF DataMapper: {indicator}")
    return df.sort_values(["iso3", "year"]).reset_index(drop=True)


def imf_indicators() -> pd.DataFrame:
    j = http.get_json("https://www.imf.org/external/datamapper/api/v1/indicators")
    return pd.DataFrame([{"id": k, **v} for k, v in j["indicators"].items()])


def eurostat(dataset: str, **filters) -> pd.DataFrame:
    """Eurostat dissemination API (JSON-stat 2.0) decoded to a tidy frame. filters: dimension=code."""
    j = http.get_json(f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}",
                      {"lang": "EN", **filters})
    dims, sizes = j["id"], j["size"]
    cats = []
    for d in dims:
        idx = j["dimension"][d]["category"]["index"]
        order = sorted(idx, key=idx.get) if isinstance(idx, dict) else idx
        cats.append(order)
    vals = j.get("value", {})
    rows = []
    for flat, combo in enumerate(itertools.product(*cats)):
        v = vals.get(str(flat)) if isinstance(vals, dict) else (vals[flat] if flat < len(vals) else None)
        if v is not None:
            rows.append(dict(zip(dims, combo), value=v))
    df = pd.DataFrame(rows)
    df.attrs.update(label=j.get("label"), updated=j.get("updated"),
                    source=f"https://ec.europa.eu/eurostat/databrowser/view/{dataset}/default/table")
    http.cite(df.attrs["source"], f"Eurostat: {j.get('label') or dataset}")
    return df


def ecb(key: str, last: int | None = None, start: str | None = None) -> pd.DataFrame:
    """ECB Data Portal, key 'FLOWREF/SERIESKEY', e.g. 'EXR/D.USD.EUR.SP00.A' (USD per EUR daily),
    'FM/B.U2.EUR.4F.KR.MRR_FR.LEV' (main refinancing rate)."""
    params = {"format": "csvdata"}
    if last:
        params["lastNObservations"] = last
    if start:
        params["startPeriod"] = start
    df = _csv(f"https://data-api.ecb.europa.eu/service/data/{key}", params)
    http.cite(f"https://data.ecb.europa.eu/data/datasets/{key.split('/')[0]}/{key.replace('/', '.')}", f"ECB: {key}")
    return df[["KEY", "TIME_PERIOD", "OBS_VALUE"] + [c for c in ("TITLE", "UNIT") if c in df]]


def oecd(flow: str, key: str = "all", last: int | None = None, start: str | None = None) -> pd.DataFrame:
    """OECD SDMX: flow 'AGENCY,DSD@DF,VERSION' and a dotted series key (find both in the OECD Data Explorer URL)."""
    params = {"format": "csvfile"}
    if last:
        params["lastNObservations"] = last
    if start:
        params["startPeriod"] = start
    return _csv(f"https://sdmx.oecd.org/public/rest/data/{flow}/{key}", params)


def comtrade(reporter: int, period: int | str, flow: str = "M", partner: int = 0, cmd: str = "TOTAL",
             freq: str = "A") -> pd.DataFrame:
    """UN Comtrade public preview (no key; 500 rows). reporter/partner are M49 codes (842 USA, 156 China, 0 World).
    flow M imports / X exports; cmd an HS code or TOTAL or AG2 for all 2-digit chapters."""
    j = http.get_json(f"https://comtradeapi.un.org/public/v1/preview/C/{freq}/HS",
                      {"reporterCode": reporter, "period": period, "partnerCode": partner,
                       "cmdCode": cmd, "flowCode": flow})
    return pd.DataFrame(j.get("data", []))


def wikidata(sparql: str) -> pd.DataFrame:
    """Wikidata SPARQL; returns one column per variable with plain values. Good for structured
    facts (officeholders, dates, populations), but check anything current against a live source."""
    j = http.get_json("https://query.wikidata.org/sparql", {"query": sparql, "format": "json"},
                      headers={"Accept": "application/sparql-results+json"})
    vars_ = j["head"]["vars"]
    return pd.DataFrame([{v: b.get(v, {}).get("value") for v in vars_} for b in j["results"]["bindings"]])


def crypto(ids: list[str], vs: str = "usd") -> pd.DataFrame:
    j = http.get_json("https://api.coingecko.com/api/v3/simple/price",
                      {"ids": ",".join(ids), "vs_currencies": vs, "include_last_updated_at": "true"}, ttl=60)
    return pd.DataFrame([{"id": k, vs: v.get(vs), "updated": pd.to_datetime(v.get("last_updated_at"), unit="s", utc=True)}
                         for k, v in j.items()])


# ---------- the GitHub-hosted catalogue from desk.py ----------
def desk(name: str, **params) -> pd.DataFrame:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desk"))
    import desk as _desk
    return _desk.load(name, **params)
