"""kit.lookup: quick structured answers from reference databases (tested 2026-10-12).

    from kit import lookup
    lookup.books("the left hand of darkness")        # Open Library: editions, first year, ids
    lookup.music_artist("Rush")                      # MusicBrainz: type, country, life span, mbid
    lookup.music_releases(mbid, kind="album")        # an artist's release groups by year
    lookup.game("Baldur's Gate 3")                   # Steam store: price, release, specs, metacritic
    lookup.hn("local llm inference", n=10)           # Hacker News stories (what engineers are discussing)
    lookup.package("pandas") / lookup.package("react", npm=True)   # latest version and release date
    lookup.fedreg("artificial intelligence", n=10)   # Federal Register documents (rules, notices, EOs)
    lookup.courts("fourth amendment geofence warrant")# CourtListener opinions
    lookup.forecast(40.71, -74.0)                    # US National Weather Service forecast periods
    lookup.archive(url)                              # closest Wayback snapshot of a page
"""
from __future__ import annotations

import pandas as pd

from . import http


def books(q: str, n: int = 5) -> pd.DataFrame:
    j = http.get_json("https://openlibrary.org/search.json", {"q": q, "limit": n,
                      "fields": "title,author_name,first_publish_year,edition_count,key,isbn,subject"})
    return pd.DataFrame([{"title": d.get("title"), "authors": ", ".join(d.get("author_name", [])[:3]),
                          "first_year": d.get("first_publish_year"), "editions": d.get("edition_count"),
                          "url": "https://openlibrary.org" + d.get("key", ""),
                          "subjects": ", ".join(d.get("subject", [])[:6])} for d in j.get("docs", [])])


def music_artist(name: str, n: int = 3) -> pd.DataFrame:
    j = http.get_json("https://musicbrainz.org/ws/2/artist/", {"query": name, "fmt": "json", "limit": n})
    return pd.DataFrame([{"name": a.get("name"), "type": a.get("type"), "country": a.get("country"),
                          "begin": (a.get("life-span") or {}).get("begin"), "end": (a.get("life-span") or {}).get("end"),
                          "disambiguation": a.get("disambiguation", ""), "mbid": a.get("id"), "score": a.get("score")}
                         for a in j.get("artists", [])])


def music_releases(mbid: str, kind: str = "album") -> pd.DataFrame:
    j = http.get_json("https://musicbrainz.org/ws/2/release-group", {"artist": mbid, "type": kind, "fmt": "json", "limit": 100})
    df = pd.DataFrame([{"title": g.get("title"), "first_release": g.get("first-release-date"),
                        "type": g.get("primary-type"), "secondary": ", ".join(g.get("secondary-types", []))}
                       for g in j.get("release-groups", [])])
    return df.sort_values("first_release").reset_index(drop=True) if not df.empty else df


def game(name_or_appid, cc: str = "us") -> dict:
    """Steam store details for the best name match (or an app id): price, release date, genres,
    metacritic, PC requirements (HTML stripped)."""
    import re
    appid = name_or_appid
    if not str(name_or_appid).isdigit():
        s = http.get_json("https://store.steampowered.com/api/storesearch/", {"term": name_or_appid, "cc": cc, "l": "en"})
        if not s.get("items"):
            raise LookupError(f"no Steam match for {name_or_appid!r}")
        appid = s["items"][0]["id"]
    j = http.get_json("https://store.steampowered.com/api/appdetails", {"appids": appid, "cc": cc})[str(appid)]
    if not j.get("success"):
        raise LookupError(f"Steam has no details for {appid}")
    d = j["data"]
    strip = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()
    return {"appid": appid, "name": d.get("name"), "release": (d.get("release_date") or {}).get("date"),
            "price": (d.get("price_overview") or {}).get("final_formatted", "free" if d.get("is_free") else None),
            "developers": d.get("developers"), "genres": [g["description"] for g in d.get("genres", [])],
            "metacritic": (d.get("metacritic") or {}).get("score"),
            "min_pc": strip((d.get("pc_requirements") or {}).get("minimum")),
            "rec_pc": strip((d.get("pc_requirements") or {}).get("recommended")),
            "url": f"https://store.steampowered.com/app/{appid}/"}


def hn(q: str, n: int = 10, by_date: bool = False) -> pd.DataFrame:
    ep = "search_by_date" if by_date else "search"
    j = http.get_json(f"https://hn.algolia.com/api/v1/{ep}", {"query": q, "tags": "story", "hitsPerPage": n}, ttl=1800)
    return pd.DataFrame([{"title": h.get("title"), "points": h.get("points"), "comments": h.get("num_comments"),
                          "date": (h.get("created_at") or "")[:10], "url": h.get("url"),
                          "hn": f"https://news.ycombinator.com/item?id={h.get('objectID')}"} for h in j.get("hits", [])])


def package(name: str, npm: bool = False) -> dict:
    """Latest version and its release date from PyPI (default) or npm. Use before stating 'the latest version'."""
    if npm:
        j = http.get_json(f"https://registry.npmjs.org/{name}", ttl=3600)
        v = j["dist-tags"]["latest"]
        return {"name": name, "latest": v, "released": j.get("time", {}).get(v, "")[:10],
                "url": f"https://www.npmjs.com/package/{name}"}
    j = http.get_json(f"https://pypi.org/pypi/{name}/json", ttl=3600)
    v = j["info"]["version"]
    rel = j.get("releases", {}).get(v) or [{}]
    return {"name": name, "latest": v, "released": (rel[0].get("upload_time") or "")[:10],
            "requires_python": j["info"].get("requires_python"), "url": f"https://pypi.org/project/{name}/"}


def fedreg(q: str, n: int = 10, kind: str | None = None) -> pd.DataFrame:
    """Federal Register search. kind: RULE, PRORULE, NOTICE, PRESDOCU."""
    params = {"conditions[term]": q, "per_page": n, "order": "newest"}
    if kind:
        params["conditions[type][]"] = kind
    j = http.get_json("https://www.federalregister.gov/api/v1/documents.json", params, ttl=3600)
    return pd.DataFrame([{"date": d.get("publication_date"), "type": d.get("type"), "title": d.get("title"),
                          "agencies": ", ".join(a.get("name", "") for a in d.get("agencies", [])),
                          "url": d.get("html_url")} for d in j.get("results", [])])


def courts(q: str, n: int = 10) -> pd.DataFrame:
    j = http.get_json("https://www.courtlistener.com/api/rest/v4/search/", {"q": q, "type": "o", "order_by": "score desc"})
    return pd.DataFrame([{"case": r.get("caseName"), "court": r.get("court"), "filed": r.get("dateFiled"),
                          "citation": ", ".join(r.get("citation") or []),
                          "url": "https://www.courtlistener.com" + (r.get("absolute_url") or "")}
                         for r in j.get("results", [])[:n]])


def forecast(lat: float, lon: float) -> pd.DataFrame:
    """US-only NWS forecast (12-hour periods). Outside the US use the weather tool."""
    p = http.get_json(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}", ttl=86400)
    f = http.get_json(p["properties"]["forecast"], ttl=1800)
    return pd.DataFrame([{"period": x["name"], "temp": f"{x['temperature']}{x['temperatureUnit']}",
                          "wind": f"{x['windSpeed']} {x['windDirection']}", "forecast": x["shortForecast"],
                          "rain_pct": (x.get("probabilityOfPrecipitation") or {}).get("value")}
                         for x in f["properties"]["periods"]])


def archive(url: str, when: str = "") -> str | None:
    from .web import wayback
    return wayback(url, when)
