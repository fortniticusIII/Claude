"""How closely a network follows the real JR track: share of each network's length within R km of the other."""
import pickle, os, numpy as np
from scipy.spatial import cKDTree
import rail, metrics
R = 2.5
def segs_from_graph(G, pos):
    a = np.array([pos[u] for u, v in G.edges()]); b = np.array([pos[v] for u, v in G.edges()])
    return a, b
def sample(a, b, step=0.25):
    pts, wts = [], []
    for p, q in zip(a, b):
        L = float(np.hypot(*(q - p))); n = max(1, int(np.ceil(L / step)))
        t = (np.arange(n) + 0.5) / n
        pts.append(p + (q - p) * t[:, None]); wts.append(np.full(n, L / n))
    return np.vstack(pts), np.concatenate(wts)
def jr_points():
    p = "runs/jr_points.npz"
    if not os.path.exists(p):
        G, nodes, xy, tree, st_xy, st_name = rail.build("jr")
        snaps = rail.snap_fs(G, nodes, xy, tree, st_xy, st_name)
        e = metrics.evaluate(G, [s["node"] for s in snaps], return_graph=True)
        pos = dict(zip(nodes, xy)); a, b = segs_from_graph(e["graph"], pos)
        P, W = sample(a, b); np.savez(p, P=P, W=W)
    z = np.load(p); return z["P"], z["W"]
def overlap(P, W, Q, V, r=R):
    """precision: share of network P within r of Q; recall: share of Q within r of P."""
    dp, _ = cKDTree(Q).query(P); dq, _ = cKDTree(P).query(Q)
    prec = float(W[dp <= r].sum() / W.sum()); rec = float(V[dq <= r].sum() / V.sum())
    return dict(precision=prec, recall=rec, f1=2 * prec * rec / (prec + rec) if prec + rec else 0.0)
def graph_points(G, xy):
    a = np.array([xy[u] for u, v in G.edges()]); b = np.array([xy[v] for u, v in G.edges()])
    return sample(a, b)
