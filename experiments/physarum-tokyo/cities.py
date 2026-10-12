"""Fetch coordinates for my reconstruction of the Tero et al. (2010) city set from Wikipedia."""
import json, urllib.request, urllib.parse
TITLES = {
 # Tokyo: seven food sources at major hubs (the paper aggregated Tokyo as 7 FSs)
 "Tokyo Station":"Tokyo Station","Shinjuku":"Shinjuku Station","Ikebukuro":"Ikebukuro Station",
 "Shibuya":"Shibuya Station","Shinagawa":"Shinagawa Station","Ueno":"Ueno Station","Kinshicho":"Kinshichō Station",
 # Kanagawa
 "Yokohama":"Yokohama","Kawasaki":"Kawasaki, Kanagawa","Yokosuka":"Yokosuka, Kanagawa","Fujisawa":"Fujisawa, Kanagawa",
 "Hiratsuka":"Hiratsuka, Kanagawa","Odawara":"Odawara","Atsugi":"Atsugi","Sagamihara":"Sagamihara",
 # Tama
 "Hachioji":"Hachiōji","Tachikawa":"Tachikawa","Ome":"Ōme",
 # Saitama
 "Saitama":"Saitama (city)","Kawagoe":"Kawagoe","Tokorozawa":"Tokorozawa","Kumagaya":"Kumagaya","Kasukabe":"Kasukabe","Hanno":"Hannō",
 # Ibaraki
 "Tsukuba":"Tsukuba","Tsuchiura":"Tsuchiura","Toride":"Toride","Koga":"Koga, Ibaraki",
 # Chiba
 "Chiba":"Chiba (city)","Funabashi":"Funabashi","Kashiwa":"Kashiwa","Narita":"Narita, Chiba","Sakura":"Sakura, Chiba",
 "Ichihara":"Ichihara","Kisarazu":"Kisarazu","Mobara":"Mobara",
}
def fetch(titles):
    q = urllib.parse.urlencode({"action":"query","prop":"coordinates","titles":"|".join(titles),
                                "format":"json","redirects":1,"colimit":"max"})
    req = urllib.request.Request("https://en.wikipedia.org/w/api.php?"+q, headers={"User-Agent":"physarum-experiment/0.1 (research notebook)"})
    return json.load(urllib.request.urlopen(req, timeout=30))
if __name__ == "__main__":
    out = {}
    names = list(TITLES)
    for i in range(0, len(names), 40):
        chunk = names[i:i+40]
        d = fetch([TITLES[n] for n in chunk])
        q = d["query"]
        redirect = {r["from"]: r["to"] for r in q.get("redirects", [])}
        norm = {r["from"]: r["to"] for r in q.get("normalized", [])}
        bytitle = {p["title"]: p for p in q["pages"].values()}
        for n in chunk:
            t = TITLES[n]; t = norm.get(t, t); t = redirect.get(t, t)
            p = bytitle.get(t, {})
            c = p.get("coordinates")
            out[n] = (c[0]["lat"], c[0]["lon"]) if c else None
    missing = [n for n, v in out.items() if v is None]
    print("missing:", missing)
    json.dump({"source":"en.wikipedia.org API prop=coordinates, fetched 2026-10-12","cities":out}, open("cities.json","w"), indent=1)
    for n, v in out.items(): print(f"{n:12s} {v}")
