"""Build a land mesh for the Kanto region: grid nodes on land (Natural Earth 10m land minus lakes),
8-neighbour edges, optional exclusion of high ground (the paper's illumination mask)."""
import json, numpy as np
from matplotlib.path import Path

LAT0, LON0 = 35.70, 139.75                       # projection centre
KX = 111.32 * np.cos(np.radians(LAT0)); KY = 110.57  # km per degree

def proj(lat, lon):
    return (np.asarray(lon) - LON0) * KX, (np.asarray(lat) - LAT0) * KY

def unproj(x, y):
    return LAT0 + np.asarray(y) / KY, LON0 + np.asarray(x) / KX

BOX = (138.95, 140.60, 35.10, 36.35)            # lon0, lon1, lat0, lat1

def _rings(geojson_path, box):
    lo0, lo1, la0, la1 = box
    out = []
    for f in json.load(open(geojson_path))["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for k, ring in enumerate(poly):
                r = np.asarray(ring)
                if r[:, 0].max() < lo0 or r[:, 0].min() > lo1 or r[:, 1].max() < la0 or r[:, 1].min() > la1:
                    continue
                out.append((k == 0, r))       # (is_exterior, ring lon/lat)
    return out

def inside(rings, lon, lat):
    pts = np.column_stack([lon, lat]); res = np.zeros(len(pts), bool)
    for ext, r in rings:
        hit = Path(r).contains_points(pts)
        res = res | hit if ext else res & ~hit
    return res

def load_elev():
    z = np.load("data/elev.npz")
    return z["elev"], z["lons"], z["lats"]

def elev_at(lat, lon, elev, lons, lats, radius_px=4):
    """Mean elevation in a small window around each point (window ~ 0.5 km at z10)."""
    ix = np.searchsorted(lons, lon).clip(radius_px, len(lons) - radius_px - 1)
    iy = np.searchsorted(-lats, -lat).clip(radius_px, len(lats) - radius_px - 1)
    out = np.empty(len(ix))
    for k, (a, b) in enumerate(zip(iy, ix)):
        out[k] = elev[a - radius_px:a + radius_px + 1, b - radius_px:b + radius_px + 1].mean()
    return out

def build(h=1.5, max_elev=None, seed=0):
    """Return dict with node xy, edges (u,v), lengths, FS node indices and names."""
    cities = json.load(open("cities.json"))["cities"]
    names = list(cities)
    lo0, lo1, la0, la1 = BOX
    x0, y0 = proj(la0, lo0); x1, y1 = proj(la1, lo1)
    xs = np.arange(x0, x1 + 1e-9, h); ys = np.arange(y0, y1 + 1e-9, h)
    X, Y = np.meshgrid(xs, ys); lat, lon = unproj(X.ravel(), Y.ravel())
    land = _rings("data/ne_10m_land.geojson", BOX)
    lakes = _rings("data/ne_10m_lakes.geojson", BOX)
    ok = inside(land, lon, lat)
    if lakes:
        ok &= ~inside([(True, r) for ext, r in lakes if ext], lon, lat)
    # elevation: inland water (Kasumigaura etc.) shows as bathymetry below sea level in the Terrarium
    # tiles, while Tokyo's zero-metre wards read positive there, so mean elevation < -1.5 m marks lakes.
    elev, elons, elats = load_elev()
    e = np.full(len(lat), np.nan)
    e[ok] = elev_at(lat[ok], lon[ok], elev, elons, elats)
    ok &= ~(e < -1.5)
    if max_elev is not None:
        ok &= ~(e > max_elev)
    # force-include the grid cell nearest each food source
    fx, fy = proj([cities[n][0] for n in names], [cities[n][1] for n in names])
    gi = np.rint((np.asarray(fy) - y0) / h).astype(int); gj = np.rint((np.asarray(fx) - x0) / h).astype(int)
    ny, nx = X.shape
    ok2 = ok.reshape(ny, nx).copy(); ok2[gi, gj] = True
    idx = -np.ones((ny, nx), int); idx[ok2] = np.arange(ok2.sum())
    edges = []
    for di, dj in [(0, 1), (1, 0), (1, 1), (1, -1)]:
        jlo, jhi = max(0, -dj), nx - max(0, dj)
        a = idx[0:ny - di, jlo:jhi]
        b = idx[di:ny, jlo + dj:jhi + dj]
        m = (a >= 0) & (b >= 0)
        edges.append(np.column_stack([a[m], b[m]]))
    edges = np.vstack(edges)
    xy = np.column_stack([X.ravel()[ok2.ravel()], Y.ravel()[ok2.ravel()]])
    # drop edges whose midpoint is in water (crossing a narrow bay mouth or lake)
    mid = (xy[edges[:, 0]] + xy[edges[:, 1]]) / 2
    mlat, mlon = unproj(mid[:, 0], mid[:, 1])
    wet = ~inside(land, mlon, mlat)
    if lakes:
        wet |= inside([(True, r) for ext, r in lakes if ext], mlon, mlat)
    edges = edges[~wet]
    L = np.linalg.norm(xy[edges[:, 0]] - xy[edges[:, 1]], axis=1)
    fs = idx[gi, gj]
    # keep the component(s) containing food sources: drop islands
    import scipy.sparse as sp, scipy.sparse.csgraph as cg
    n = len(xy)
    A = sp.coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(n, n))
    ncomp, lab = cg.connected_components(A, directed=False)
    keep = np.isin(lab, np.unique(lab[fs]))
    remap = -np.ones(n, int); remap[keep] = np.arange(keep.sum())
    ek = keep[edges[:, 0]] & keep[edges[:, 1]]
    edges = remap[edges[ek]]; L = L[ek]; xy = xy[keep]; fs = remap[fs]
    comps = len(np.unique(lab[keep]))
    return dict(xy=xy, edges=edges, L=L, fs=fs, names=names, h=h, max_elev=max_elev, components=comps)

if __name__ == "__main__":
    import sys
    for me in (None, 250):
        m = build(h=float(sys.argv[1]) if len(sys.argv) > 1 else 1.5, max_elev=me)
        print(f"max_elev={me}: nodes={len(m['xy'])} edges={len(m['edges'])} components={m['components']} "
              f"fs_unique={len(set(m['fs']))}")
