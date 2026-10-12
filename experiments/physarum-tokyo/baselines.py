"""Engineered baseline networks on the 36 food sources, links weighted by land (geodesic) distance.

- MST, and the paper's 'MST plus shortest extra links' family up to the Delaunay triangulation
- greedy t-spanners (a classic construction that bounds detour: network distance <= t * direct distance)
- greedy bridge-covering augmentation of the MST (adds the link that removes the most unprotected
  length per km built), an engineer's heuristic for the cost / fault-tolerance trade-off
- the exact minimum-cost 2-edge-connected network (FT = 1), solved as an ILP with cut constraints
"""
import json, pickle, sys, numpy as np, networkx as nx, scipy.sparse as sp
from scipy.spatial import Delaunay
from scipy.optimize import milp, LinearConstraint, Bounds
import metrics

def all_pairs(W):
    n = len(W); return [(i, j) for i in range(n) for j in range(i + 1, n)]

def score(edges, W, label, **extra):
    r = metrics.evaluate(metrics.abstract_graph(edges, W), range(len(W)))
    r.update(label=label, n_edges=len(edges), **extra); return r

def delaunay_edges(xy):
    tri = Delaunay(xy); s = set()
    for a, b, c in tri.simplices:
        for u, v in ((a, b), (b, c), (a, c)): s.add((min(u, v), max(u, v)))
    return sorted(s)

def mst_plus(W, xy):
    tree = metrics.mst_edges(W); tset = {tuple(sorted(e)) for e in tree}
    extra = sorted((e for e in delaunay_edges(xy) if e not in tset), key=lambda e: W[e])
    out = []
    for k in range(0, len(extra) + 1, 2):
        out.append(score(tree + extra[:k], W, "mst_plus", k=k))
    return out

def greedy_spanner(W, t):
    G = nx.Graph(); G.add_nodes_from(range(len(W))); edges = []
    for i, j in sorted(all_pairs(W), key=lambda e: W[e]):
        try: d = nx.dijkstra_path_length(G, i, j)
        except nx.NetworkXNoPath: d = np.inf
        if d > t * W[i, j]:
            G.add_edge(i, j, weight=W[i, j]); edges.append((i, j))
    return edges

def bridge_len(edges, W):
    G = metrics.abstract_graph(edges, W)
    return sum(W[a, b] for a, b in nx.bridges(G))

def bridge_cover(W, candidates):
    edges = metrics.mst_edges(W); out = [score(edges, W, "bridge_cover", step=0)]
    have = {tuple(sorted(e)) for e in edges}; step = 0
    while True:
        bl = bridge_len(edges, W)
        if bl <= 1e-9: break
        best, bestv = None, 0
        for e in candidates:
            if e in have: continue
            gain = bl - bridge_len(edges + [e], W)
            v = gain / W[e]
            if v > bestv: best, bestv = e, v
        if best is None: break
        edges = edges + [best]; have.add(best); step += 1
        out.append(score(edges, W, "bridge_cover", step=step))
    return out

def min_2ec(W, candidates):
    """Exact minimum-cost 2-edge-connected spanning subgraph (cutting-plane ILP)."""
    n = len(W); E = list(candidates); m = len(E); c = np.array([W[e] for e in E])
    rows = []
    def cut_row(S):
        S = set(S); return np.array([1.0 if ((a in S) != (b in S)) else 0.0 for a, b in E])
    for v in range(n): rows.append(cut_row([v]))
    for it in range(200):
        A = np.vstack(rows)
        res = milp(c, constraints=LinearConstraint(A, lb=2, ub=np.inf), integrality=np.ones(m), bounds=Bounds(0, 1))
        x = np.round(res.x).astype(int); chosen = [E[k] for k in range(m) if x[k]]
        G = nx.Graph(); G.add_nodes_from(range(n)); G.add_edges_from(chosen)
        comps = list(nx.connected_components(G))
        if len(comps) > 1:
            for S in comps: rows.append(cut_row(S))
            continue
        br = list(nx.bridges(G))
        if not br:
            return chosen, it
        for a, b in br:
            H = G.copy(); H.remove_edge(a, b); rows.append(cut_row(nx.node_connected_component(H, a)))
    raise RuntimeError("no convergence")

if __name__ == "__main__":
    results = {}
    for me in (250, None):
        m = pickle.load(open(f"runs/mesh_{me}.pkl", "rb"))
        W, pred = metrics.geodesics(m)
        xy = m["xy"][m["fs"]]
        res = [score(metrics.mst_edges(W), W, "mst")]
        res.append(score(delaunay_edges(xy), W, "delaunay"))
        res += mst_plus(W, xy)
        for t in (1.02, 1.05, 1.1, 1.15, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0):
            res.append(score(greedy_spanner(W, t), W, "spanner", t=t))
        cand = all_pairs(W)
        res += bridge_cover(W, cand)
        e2, its = min_2ec(W, cand)
        res.append(score(e2, W, "min_2ec", cut_rounds=its, chosen=[list(map(int, e)) for e in e2]))
        results[str(me)] = res
        mst = res[0]
        print(f"mask={me}: MST TL={mst['TL']:.0f} km MD={mst['MD']:.1f} km")
        for r in res:
            if r["label"] in ("delaunay", "min_2ec") or (r["label"] == "spanner" and r["t"] in (1.1, 1.5, 2.0)):
                print(f"  {r['label']:10s} {r.get('t','')!s:5s} TL_MST={r['TL']/mst['TL']:.2f} MD_MST={r['MD']/mst['MD']:.2f} "
                      f"FT_len={r['FT_len']:.2f} FT_link={r['FT_link']:.2f} edges={r['n_edges']}")
    json.dump(results, open("runs/baselines.json", "w"))
