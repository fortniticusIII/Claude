"""Tero et al. (2010) tube-adaptation model, mean-field form.

Paper: each step one random food source (FS) injects I0, another withdraws it; fluxes follow Kirchhoff with
Q_ij = D_ij/L_ij (p_i - p_j), and conductivities evolve as dD/dt = f(|Q|) - D with f(q) = q^g / (1 + q^g).
Here, with a small time step, the random source/sink choice is replaced by its average over all FS pairs:
dD/dt = E_pairs[ f(|Q^(s,t)|) ] - D. One sparse factorisation per step gives every pair by linearity.
"""
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla, scipy.sparse.csgraph as csgraph, time

def incidence(edges, n):
    E = len(edges)
    r = np.repeat(np.arange(E), 2); c = edges.ravel(); v = np.tile([1.0, -1.0], E)
    return sp.csr_matrix((v, (r, c)), shape=(E, n))

def run(m, I0=1.0, gamma=1.8, dt=0.2, T=300.0, seed=0, Dmin=1e-9, noise=0.2, log_every=None, tol=1e-6, w=None):
    """w: optional FS x FS pair weights (e.g. population products); default treats every pair equally."""
    rng = np.random.default_rng(seed)
    n = len(m["xy"]); edges = m["edges"]; L = m["L"]; fs = np.asarray(m["fs"])
    B = incidence(edges, n); BT = B.T.tocsr()
    D = 1.0 + noise * (rng.random(len(edges)) - 0.5)
    ref = fs[0]; keep = np.ones(n, bool); keep[ref] = False
    kidx = np.flatnonzero(keep); pos = -np.ones(n, int); pos[kidx] = np.arange(len(kidx))
    rhs = np.zeros((len(kidx), len(fs)))
    for k, f in enumerate(fs):
        if f != ref: rhs[pos[f], k] = 1.0
    npair = len(fs) * (len(fs) - 1) // 2
    if w is not None:
        w = np.asarray(w, float); npair = np.triu(w, 1).sum()
    hist = []; t = 0.0; t0 = time.time(); steps = int(round(T / dt))
    full_nodes = np.arange(n)
    for step in range(steps):
        # Tubes at the floor carry no flow and cannot regrow (f(0) = 0), so solve only on live tubes.
        act = np.flatnonzero(D > 10 * Dmin)
        # keep only the live component that holds the food sources (cut-off loops carry no flow)
        A = sp.coo_matrix((np.ones(len(act)), (edges[act, 0], edges[act, 1])), shape=(n, n))
        _, lab = csgraph.connected_components(A, directed=False)
        if not np.all(lab[fs] == lab[ref]):
            raise RuntimeError("food sources disconnected")
        act = act[lab[edges[act, 0]] == lab[ref]]
        ea = edges[act]
        nodes = np.unique(np.concatenate([ea.ravel(), fs]))
        loc = -np.ones(n, int); loc[nodes] = np.arange(len(nodes))
        Ba = incidence(loc[ea], len(nodes)); g = D[act] / L[act]
        Kf = (Ba.T @ sp.diags(g) @ Ba).tocsc()
        r = loc[ref]; kk = np.ones(len(nodes), bool); kk[r] = False; kid = np.flatnonzero(kk)
        lu = spla.splu(Kf[kid][:, kid].tocsc(), permc_spec="MMD_AT_PLUS_A")
        rhs = np.zeros((len(kid), len(fs))); pos = -np.ones(len(nodes), int); pos[kid] = np.arange(len(kid))
        for k, f in enumerate(fs):
            if f != ref: rhs[pos[loc[f]], k] = 1.0
        phi = np.zeros((len(nodes), len(fs))); phi[kid] = lu.solve(rhs)
        G = (g[:, None] * (Ba @ phi)) * I0          # live edges x FS: flux when FS k injects I0 at the reference
        acc = np.zeros(len(act))
        for s in range(len(fs) - 1):
            q = np.abs(G[:, s:s + 1] - G[:, s + 1:])
            qg = q ** gamma
            fq = qg / (1.0 + qg)
            acc += fq.sum(axis=1) if w is None else fq @ w[s, s + 1:]
        F = np.zeros(len(edges)); F[act] = acc / npair
        Dn = np.maximum(D + dt * (F - D), Dmin)
        change = np.abs(Dn - D).max(); D = Dn; t += dt
        if log_every and (step % log_every == 0 or step == steps - 1):
            alive = int((D > 1e-3).sum())
            hist.append((round(t, 2), alive, float(change)))
            print(f"t={t:7.1f} alive={alive:6d} maxchange={change:.2e} elapsed={time.time()-t0:6.1f}s", flush=True)
        if change < tol * dt and t > 20:
            break
    return D, dict(t=t, hist=hist, I0=I0, gamma=gamma, dt=dt, seed=seed)

if __name__ == "__main__":
    import mesh, sys
    m = mesh.build(1.5, 250)
    D, info = run(m, I0=float(sys.argv[1]) if len(sys.argv) > 1 else 1.0,
                  gamma=float(sys.argv[2]) if len(sys.argv) > 2 else 1.8, T=40, log_every=10)
