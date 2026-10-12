"""Follow-up: does population weighting pull the slime model toward JR, and does JR look better once trips are
weighted by how many people make them?

For every network: TL/MST, MD/MST (all pairs equal), MDw/MST (pairs weighted by catchment population
product), FT, and overlap with the real JR track (precision, recall, F1 within 2.5 km)."""
import json, pickle, numpy as np, networkx as nx
import metrics, baselines, rail, similarity, analyze

THR = 1e-5; GRID = analyze.GRID
m = pickle.load(open("runs/mesh_250.pkl", "rb")); W, pred = metrics.geodesics(m)
POP = np.array(list(json.load(open("catchments.json"))["pop"].values()), float)
WP = np.outer(POP, POP); iu = np.triu_indices(36, 1)
JP, JW = similarity.jr_points()

def fs_dist(G, terms):
    D = np.zeros((36, 36))
    for i, t in enumerate(terms):
        d = nx.single_source_dijkstra_path_length(G, t, weight="weight")
        D[i] = [d[u] for u in terms]
    return D

def summarize(G, terms, scale=1.0):
    e = metrics.evaluate(G, terms, return_graph=True)
    H = e["graph"]; D = fs_dist(H, terms) * scale
    return e, H, dict(TL=e["TL"] * scale, MD=D[iu].mean(), MDw=(D[iu] * WP[iu]).sum() / WP[iu].sum(), FT=e["FT_len"])

def geo_points_abstract(edges):
    fs = list(m["fs"]); segs_a, segs_b = [], []
    for i, j in edges:
        nodes = metrics.path_nodes(pred[i], fs[i], fs[j]); P = m["xy"][nodes]
        segs_a.append(P[:-1]); segs_b.append(P[1:])
    return similarity.sample(np.vstack(segs_a), np.vstack(segs_b))

rows = []
mst_e, _, mst = summarize(metrics.abstract_graph(metrics.mst_edges(W), W), list(range(36)))
def add(kind, base, pts, **kw):
    r = dict(kind=kind, TLn=base["TL"] / mst["TL"], MDn=base["MD"] / mst["MD"], MDwn=base["MDw"] / mst["MDw"], FT=base["FT"], **kw)
    if pts is not None: r.update(similarity.overlap(*pts, JP, JW))
    rows.append(r); return r

# engineered
add("mst", mst, geo_points_abstract(metrics.mst_edges(W)))
for t in (1.3, 1.5, 1.75, 2.0, 2.5, 3.0):
    ed = baselines.greedy_spanner(W, t); _, _, s = summarize(metrics.abstract_graph(ed, W), list(range(36)))
    add("spanner", s, geo_points_abstract(ed), t=t)
ring = [tuple(e) for e in next(b for b in json.load(open("runs/baselines.json"))["250"] if b["label"] == "min_2ec")["chosen"]]
_, _, s = summarize(metrics.abstract_graph(ring, W), list(range(36))); add("min_2ec", s, geo_points_abstract(ring))
edges = metrics.mst_edges(W); have = {tuple(sorted(x)) for x in edges}; step = 0
while baselines.bridge_len(edges, W) > 1e-9:
    bl = baselines.bridge_len(edges, W); best, bv = None, 0
    for c in baselines.all_pairs(W):
        if c in have: continue
        v = (bl - baselines.bridge_len(edges + [c], W)) / W[c]
        if v > bv: best, bv = c, v
    edges.append(best); have.add(best); step += 1
    if step % 3 == 0 or baselines.bridge_len(edges, W) <= 1e-9:
        _, _, s = summarize(metrics.abstract_graph(edges, W), list(range(36))); add("bridge_cover", s, geo_points_abstract(edges), step=step)

# slime model: equal, population and gravity weights (mask 250)
for wname, pat in (("equal", "runs/I{I0}_g{g}_m250_s0_D.npy"), ("pop", "runs/Wpop_I{I0}_g{g}_D.npy"), ("gravity", "runs/Wgravity_I{I0}_g{g}_D.npy")):
    for g in (1.2, 1.5, 1.8):
        for I0 in (0.3, 0.6, 1.0, 2.0, 4.0):
            D = np.load(pat.format(I0=I0, g=g)).astype(float)
            e, H, s = summarize(metrics.physarum_graph(m, D, thr=THR), list(m["fs"]))
            if not e.get("connected"): continue
            add("physarum", s, similarity.graph_points(H, m["xy"]), weights=wname, I0=I0, gamma=g)

# real rail
for v in ("jr", "jr_shinkansen", "all_heavy_rail"):
    G, nodes, xy, tree, st_xy, st_name = rail.build(v)
    snaps = rail.snap_fs(G, nodes, xy, tree, st_xy, st_name)
    e, H, s = summarize(G, [sn["node"] for sn in snaps], scale=GRID)
    pos = dict(zip(nodes, xy))
    a = np.array([pos[u] for u, w in H.edges()]); b = np.array([pos[w] for u, w in H.edges()])
    add("rail", s, similarity.sample(a, b), variant=v)

json.dump(rows, open("runs/followup.json", "w"), indent=0)
print(f"MST: MD {mst['MD']:.1f} km, demand-weighted MD {mst['MDw']:.1f} km")
for r in rows:
    tag = r["kind"] + " " + " ".join(f"{k}={r[k]}" for k in ("weights", "gamma", "I0", "t", "step", "variant") if k in r)
    print(f"{tag:42s} TL={r['TLn']:.2f} MD={r['MDn']:.2f} MDw={r['MDwn']:.2f} FT={r['FT']:.2f} "
          f"prec={r.get('precision', 0):.2f} rec={r.get('recall', 0):.2f} F1={r.get('f1', 0):.2f}")
