"""Robustness checks for the headline networks:
1. seeds (initial noise in D)
2. mesh resolution (1.0 km instead of 1.5 km)
3. the paper's stochastic dynamics (one random source/sink pair per step) instead of the pair average
"""
import json, pickle, sys, numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla, scipy.sparse.csgraph as csgraph
import mesh, model, metrics

def stochastic(m, I0, gamma, dt=0.02, T=200.0, seed=0, Dmin=1e-9):
    rng = np.random.default_rng(seed); n = len(m["xy"]); edges = m["edges"]; L = m["L"]; fs = np.asarray(m["fs"])
    D = 1.0 + 0.2 * (rng.random(len(edges)) - 0.5); steps = int(T / dt)
    # smoothed record of D over the last 20% of time, since single-pair noise makes D flicker
    Dacc = np.zeros(len(edges)); nacc = 0
    for step in range(steps):
        s, t = rng.choice(len(fs), 2, replace=False)
        act = np.flatnonzero(D > 10 * Dmin)
        A = sp.coo_matrix((np.ones(len(act)), (edges[act, 0], edges[act, 1])), shape=(n, n))
        _, lab = csgraph.connected_components(A, directed=False)
        act = act[lab[edges[act, 0]] == lab[fs[s]]]
        ea = edges[act]; nodes = np.unique(np.concatenate([ea.ravel(), fs]))
        loc = -np.ones(n, int); loc[nodes] = np.arange(len(nodes))
        B = model.incidence(loc[ea], len(nodes)); g = D[act] / L[act]
        K = (B.T @ sp.diags(g) @ B).tocsc()
        r = loc[fs[t]]; kk = np.ones(len(nodes), bool); kk[r] = False; kid = np.flatnonzero(kk)
        b = np.zeros(len(nodes)); b[loc[fs[s]]] = I0
        p = np.zeros(len(nodes)); p[kid] = spla.spsolve(K[kid][:, kid].tocsc(), b[kid])
        Q = np.abs(g * (B @ p)); F = np.zeros(len(edges)); qg = Q ** gamma; F[act] = qg / (1 + qg)
        D = np.maximum(D + dt * (F - D), Dmin)
        if step >= 0.8 * steps: Dacc += D; nacc += 1
    return Dacc / nacc

def row(m, D, mst, label):
    r = metrics.evaluate(metrics.physarum_graph(m, D), m["fs"])
    if not r.get("connected"): return dict(label=label, connected=False)
    return dict(label=label, TLn=r["TL"] / mst["TL"], MDn=r["MD"] / mst["MD"], FT=r["FT_len"])

if __name__ == "__main__":
    which = sys.argv[1]
    m15 = pickle.load(open("runs/mesh_250.pkl", "rb")); W, _ = metrics.geodesics(m15)
    mst15 = metrics.evaluate(metrics.abstract_graph(metrics.mst_edges(W), W), range(36))
    out = []
    configs = [(1.0, 1.2), (2.0, 1.5), (2.0, 1.8)]
    if which == "seeds":
        for I0, g in configs:
            for seed in (1, 2, 3):
                D, _ = model.run(m15, I0=I0, gamma=g, T=200, seed=seed)
                out.append(dict(I0=I0, gamma=g, seed=seed, **row(m15, D, mst15, "seed")))
                print(out[-1], flush=True)
    elif which == "mesh":
        m10 = mesh.build(1.0, 250); W10, _ = metrics.geodesics(m10)
        mst10 = metrics.evaluate(metrics.abstract_graph(metrics.mst_edges(W10), W10), range(36))
        for I0, g in configs:
            # flux per edge scales with mesh spacing at fixed I0; report as-is (I0 is not portable across meshes)
            for I0x in (I0, I0 * 1.5):
                D, _ = model.run(m10, I0=I0x, gamma=g, T=200)
                out.append(dict(I0=I0x, gamma=g, h=1.0, **row(m10, D, mst10, "mesh1.0")))
                print(out[-1], flush=True)
    elif which == "stochastic":
        for I0, g in configs:
            D = stochastic(m15, I0, g)
            out.append(dict(I0=I0, gamma=g, **row(m15, D, mst15, "stochastic")))
            print(out[-1], flush=True)
    json.dump(out, open(f"runs/robust_{which}.json", "w"), indent=1)
