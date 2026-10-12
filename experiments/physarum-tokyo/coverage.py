"""People living within 2 km of each network's track (2015 census, 1 km grid), total and per km of track."""
import json, pickle, numpy as np
from scipy.spatial import cKDTree
import mesh, catchment, metrics, similarity, rail, baselines, analyze
RAD = 2.0
lat, lon, pop = catchment.cells()
lo0, lo1, la0, la1 = mesh.BOX; inb = (lon >= lo0) & (lon <= lo1) & (lat >= la0) & (lat <= la1)
x, y = mesh.proj(lat[inb], lon[inb]); C = np.column_stack([x, y]); POPC = pop[inb]
TOTAL = POPC.sum()
m = pickle.load(open("runs/mesh_250.pkl", "rb")); W, pred = metrics.geodesics(m)
def covered(points):
    d, _ = cKDTree(points).query(C); return POPC[d <= RAD].sum()
def abstract_pts(edges):
    fs = list(m["fs"]); A, B = [], []
    for i, j in edges:
        P = m["xy"][metrics.path_nodes(pred[i], fs[i], fs[j])]; A.append(P[:-1]); B.append(P[1:])
    return similarity.sample(np.vstack(A), np.vstack(B))[0]
rows = json.load(open("runs/followup.json"))
mstTL = None
out = []
def rec(label, pts, TLn, km):
    cv = covered(pts); out.append(dict(label=label, TLn=round(TLn, 2), people_M=round(cv / 1e6, 2), share=round(cv / TOTAL, 3),
                                       per_km=round(cv / km)))
    print(f"{label:34s} cost {TLn:4.2f}x  {cv/1e6:5.1f}M people ({cv/TOTAL:.0%})  {cv/km:7.0f} per km")
mst_km = metrics.evaluate(metrics.abstract_graph(metrics.mst_edges(W), W), range(36))["TL"]
rec("MST", abstract_pts(metrics.mst_edges(W)), 1.0, mst_km)
for t in (2.0, 1.75, 1.5):
    ed = baselines.greedy_spanner(W, t); r = next(r for r in rows if r["kind"] == "spanner" and r.get("t") == t)
    rec(f"spanner t={t}", abstract_pts(ed), r["TLn"], r["TLn"] * mst_km)
for wname, pat in (("equal", "runs/I{I0}_g{g}_m250_s0_D.npy"), ("pop", "runs/Wpop_I{I0}_g{g}_D.npy")):
    for g, I0 in ((1.2, 0.6), (1.2, 1.0), (1.5, 2.0)):
        D = np.load(pat.format(I0=I0, g=g)).astype(float)
        e = metrics.evaluate(metrics.physarum_graph(m, D, thr=1e-5), m["fs"], return_graph=True)
        pts = similarity.graph_points(e["graph"], m["xy"])[0]
        rec(f"slime {wname} g={g} I0={I0}", pts, e["TL"] / mst_km, e["TL"])
for v in ("jr", "jr_shinkansen", "all_heavy_rail"):
    G, nodes, xy, tree, st_xy, st_name = rail.build(v); snaps = rail.snap_fs(G, nodes, xy, tree, st_xy, st_name)
    e = metrics.evaluate(G, [s["node"] for s in snaps], return_graph=True); pos = dict(zip(nodes, xy))
    a = np.array([pos[u] for u, w in e["graph"].edges()]); b = np.array([pos[w] for u, w in e["graph"].edges()])
    pts = similarity.sample(a, b)[0]; km = e["TL"] * analyze.GRID
    rec(f"rail {v}", pts, km / mst_km, km)
json.dump(dict(radius_km=RAD, total_M=round(TOTAL / 1e6, 2), rows=out), open("runs/coverage.json", "w"), indent=1)
print(f"people in box: {TOTAL/1e6:.1f}M")
