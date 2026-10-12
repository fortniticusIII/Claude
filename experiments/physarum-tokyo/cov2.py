"""Cost-matched comparison for JR (2.25x): slime and spanner networks near that cost."""
import json, pickle, numpy as np
from scipy.spatial import cKDTree
import mesh, catchment, metrics, similarity, baselines
lat, lon, pop = catchment.cells()
lo0, lo1, la0, la1 = mesh.BOX; inb = (lon >= lo0) & (lon <= lo1) & (lat >= la0) & (lat <= la1)
x, y = mesh.proj(lat[inb], lon[inb]); C = np.column_stack([x, y]); P = pop[inb]; T = P.sum()
m = pickle.load(open("runs/mesh_250.pkl", "rb")); W, pred = metrics.geodesics(m)
mst_km = metrics.evaluate(metrics.abstract_graph(metrics.mst_edges(W), W), range(36))["TL"]
def cov(pts): d, _ = cKDTree(pts).query(C); return P[d <= 2.0].sum()
res = json.load(open("runs/coverage.json"))
for wname, pat, g, I0 in (("equal", "runs/I{I0}_g{g}_m250_s0_D.npy", 1.5, 4.0), ("equal", "runs/I{I0}_g{g}_m250_s0_D.npy", 1.8, 4.0),
                          ("pop", "runs/Wpop_I{I0}_g{g}_D.npy", 1.8, 4.0), ("gravity", "runs/Wgravity_I{I0}_g{g}_D.npy", 1.8, 4.0)):
    D = np.load(pat.format(I0=I0, g=g)).astype(float)
    e = metrics.evaluate(metrics.physarum_graph(m, D, thr=1e-5), m["fs"], return_graph=True)
    c = cov(similarity.graph_points(e["graph"], m["xy"])[0])
    row = dict(label=f"slime {wname} g={g} I0={I0}", TLn=round(e["TL"] / mst_km, 2), people_M=round(c / 1e6, 2), share=round(c / T, 3), per_km=round(c / e["TL"]))
    res["rows"].append(row); print(row)
for t in (1.4,):
    ed = baselines.greedy_spanner(W, t); fs = list(m["fs"]); A, B = [], []
    for i, j in ed:
        Q = m["xy"][metrics.path_nodes(pred[i], fs[i], fs[j])]; A.append(Q[:-1]); B.append(Q[1:])
    c = cov(similarity.sample(np.vstack(A), np.vstack(B))[0]); km = sum(W[i, j] for i, j in ed)
    row = dict(label=f"spanner t={t}", TLn=round(km / mst_km, 2), people_M=round(c / 1e6, 2), share=round(c / T, 3), per_km=round(c / km)); res["rows"].append(row); print(row)
json.dump(res, open("runs/coverage.json", "w"), indent=1)
