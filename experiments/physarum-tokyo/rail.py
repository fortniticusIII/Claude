"""The real rail network, from MLIT National Land Numerical Information N02-23 (railway sections, 2023),
scored with the same metrics on the same 36 food sources.

Variants: JR conventional lines; JR plus Shinkansen; all heavy rail (JR, private, public, third sector).
Each food source snaps to the nearest station of the variant's network; snap distances are reported.
"""
import json, pickle, numpy as np, networkx as nx
from scipy.spatial import cKDTree
import mesh, metrics

SECTIONS = "data/n02/N02-23_RailroadSection.geojson"; STATIONS = "data/n02/N02-23_Station.geojson"
VARIANTS = {
    "jr": lambda p: p["N02_002"] == "2",
    "jr_shinkansen": lambda p: p["N02_002"] in ("1", "2"),
    "all_heavy_rail": lambda p: p["N02_001"] in ("11", "12"),
}
lo0, lo1, la0, la1 = mesh.BOX

def lines(feat):
    g = feat["geometry"]
    return [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]

def build(variant):
    keep = VARIANTS[variant]
    secs = [f for f in json.load(open(SECTIONS))["features"] if keep(f["properties"])]
    sts = [f for f in json.load(open(STATIONS))["features"] if keep(f["properties"])]
    # Rasterise every section onto a CELL-km grid (sampled every CELL/2 km), so lines drawn separately on a
    # shared corridor merge into one track; consecutive cells become 8-neighbour edges.
    G = nx.Graph(); CELL = 0.1
    acc = {}; seqs = []
    for f in secs:
        for ln in lines(f):
            c = np.array(ln)
            if not ((c[:, 0] >= lo0) & (c[:, 0] <= lo1) & (c[:, 1] >= la0) & (c[:, 1] <= la1)).any(): continue
            x, y = mesh.proj(c[:, 1], c[:, 0])
            P = [(x[0], y[0])]
            for k in range(len(x) - 1):
                seg = np.hypot(x[k + 1] - x[k], y[k + 1] - y[k]); ns = max(1, int(np.ceil(seg / (CELL / 2))))
                for s_ in range(1, ns + 1):
                    P.append((x[k] + (x[k + 1] - x[k]) * s_ / ns, y[k] + (y[k + 1] - y[k]) * s_ / ns))
            P = [p for p in P if lo0 <= mesh.unproj(*p)[1] <= lo1 and la0 <= mesh.unproj(*p)[0] <= la1]
            cells = [(int(round(px / CELL)), int(round(py / CELL))) for px, py in P]
            for cl, p in zip(cells, P):
                a = acc.setdefault(cl, [0.0, 0.0, 0]); a[0] += p[0]; a[1] += p[1]; a[2] += 1
            seqs.append(cells)
    # each cell is represented by the mean of the track points inside it, so edge lengths follow the
    # real track instead of the grid (no stair-step inflation); shared corridors still merge
    rep = {cl: (a[0] / a[2], a[1] / a[2]) for cl, a in acc.items()}
    for cells in seqs:
        for a, b in zip(cells, cells[1:]):
            if a != b:
                G.add_edge(a, b, weight=float(np.hypot(rep[a][0] - rep[b][0], rep[a][1] - rep[b][1])))
    nodes = list(G); xy = np.array([rep[n] for n in nodes], float).reshape(-1, 2)
    tree = cKDTree(xy)
    # station points (midpoint of each station's platform line) snapped to the graph
    st_xy = []; st_name = []
    for f in sts:
        c = np.array(lines(f)[0]).mean(axis=0)
        if lo0 <= c[0] <= lo1 and la0 <= c[1] <= la1:
            st_xy.append(mesh.proj(c[1], c[0])); st_name.append((f["properties"]["N02_005"], f["properties"]["N02_003"]))
    st_xy = np.array(st_xy).reshape(-1, 2)
    return G, nodes, xy, tree, st_xy, st_name

def snap_fs(G, nodes, xy, tree, st_xy, st_name):
    cities = json.load(open("cities.json"))["cities"]
    fsx = np.array([mesh.proj(*cities[n]) for n in cities]).reshape(-1, 2)
    st_tree = cKDTree(st_xy); out = []
    for n, p in zip(cities, fsx):
        d, k = st_tree.query(p)
        dn, kn = tree.query(st_xy[k])
        out.append(dict(fs=n, station=st_name[k][0], line=st_name[k][1], snap_km=float(d), node=nodes[kn]))
    return out

if __name__ == "__main__":
    W, _ = metrics.geodesics(pickle.load(open("runs/mesh_250.pkl", "rb")))
    mst = metrics.evaluate(metrics.abstract_graph(metrics.mst_edges(W), W), range(36))
    res = {}
    for v in VARIANTS:
        G, nodes, xy, tree, st_xy, st_name = build(v)
        snaps = snap_fs(G, nodes, xy, tree, st_xy, st_name)
        terms = [s["node"] for s in snaps]
        if len(set(terms)) < len(terms):
            print("warning: FS share a node", v)
        r = metrics.evaluate(G, terms)
        r.update(variant=v, snaps=[{k: s[k] for k in ("fs", "station", "line", "snap_km")} for s in snaps],
                 raw_km=G.size(weight="weight"))
        res[v] = r
        far = [f"{s['fs']}→{s['station']} {s['snap_km']:.1f}km" for s in snaps if s["snap_km"] > 2]
        if r.get("connected"):
            print(f"{v:15s} TL_MST={r['TL']/mst['TL']:.2f} MD_MST={r['MD']/mst['MD']:.2f} FT_len={r['FT_len']:.3f} "
                  f"FT_link={r['FT_link']:.3f} links={r['links']} (rail in box {r['raw_km']:.0f} km)  far snaps: {far}")
        else:
            print(v, "not connected", far)
    json.dump(res, open("runs/rail.json", "w"), ensure_ascii=False, indent=1)
