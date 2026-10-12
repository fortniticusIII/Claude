"""Catchment population of each food source from the 2015 census 1 km grid (MLIT mesh1000h30, PTN_2015).
Each populated cell joins its nearest food source by land distance on the mesh; cells more than CAP km
from every food source are left out."""
import zipfile, io, json, pickle, numpy as np, shapefile, scipy.sparse.csgraph as cg
from scipy.spatial import cKDTree
import mesh, metrics
CAP = 20.0
DL = "/tmp/claude-0/-home-claude/b68b65fe-d5a7-572d-b8c9-d9130b2838af/scratchpad/dl_pop"
def decode(code):
    s = f"{int(code):08d}"; p, u, q, v, r, w = int(s[:2]), int(s[2:4]), int(s[4]), int(s[5]), int(s[6]), int(s[7])
    lat = p / 1.5 + q * 5 / 60 + r * 30 / 3600 + 15 / 3600
    lon = 100 + u + v * 7.5 / 60 + w * 45 / 3600 + 22.5 / 3600
    return lat, lon
def cells():
    lat, lon, pop = [], [], []
    for pref in ("08", "09", "10", "11", "12", "13", "14"):
        z = zipfile.ZipFile(f"{DL}/m{pref}.zip")
        name = [n for n in z.namelist() if n.endswith(".dbf")][0]
        r = shapefile.Reader(dbf=io.BytesIO(z.read(name)))
        fields = [f[0] for f in r.fields][1:]; im, ip = fields.index("MESH_ID"), fields.index("PTN_2015")
        for rec in r.iterRecords():
            pv = rec[ip]
            if not pv: continue
            la, lo = decode(rec[im]); lat.append(la); lon.append(lo); pop.append(float(pv))
    return np.array(lat), np.array(lon), np.array(pop)
if __name__ == "__main__":
    m = pickle.load(open("runs/mesh_250.pkl", "rb"))
    lat, lon, pop = cells()
    lo0, lo1, la0, la1 = mesh.BOX; inb = (lon >= lo0) & (lon <= lo1) & (lat >= la0) & (lat <= la1)
    lat, lon, pop = lat[inb], lon[inb], pop[inb]
    x, y = mesh.proj(lat, lon); xy = np.column_stack([x, y])
    d0, node = cKDTree(m["xy"]).query(xy)
    D = cg.dijkstra(metrics.mesh_graph(m), directed=False, indices=m["fs"])   # FS x nodes
    dist = D[:, node] + d0[None, :]
    owner = dist.argmin(axis=0); dmin = dist.min(axis=0)
    keep = dmin <= CAP
    names = json.load(open("cities.json"))["cities"]
    P = np.bincount(owner[keep], weights=pop[keep], minlength=len(m["fs"]))
    out = dict(source="MLIT mesh1000h30 (2018), PTN_2015 = 2015 census population per 1 km cell", cap_km=CAP,
               total_in_box=float(pop.sum()), assigned=float(P.sum()), pop={n: round(float(p)) for n, p in zip(names, P)})
    json.dump(out, open("catchments.json", "w"), indent=1)
    print(f"cells in box {inb.sum()}, people in box {pop.sum()/1e6:.2f}M, assigned within {CAP} km: {P.sum()/1e6:.2f}M")
    for n, p in sorted(out["pop"].items(), key=lambda kv: -kv[1]): print(f"  {n:14s} {p/1e3:8.0f}k")
