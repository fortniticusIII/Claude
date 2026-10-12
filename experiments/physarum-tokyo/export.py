"""Export map geometry and chart rows for the write-up page (page_data.json)."""
import json, pickle, numpy as np, networkx as nx, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import mesh, metrics, baselines, rail, analyze

def rdp(P, eps):
    P = np.asarray(P)
    if len(P) < 3: return P
    a, b = P[0], P[-1]; ab = b - a; n = np.hypot(*ab)
    d = np.abs(ab[0] * (P[:, 1] - a[1]) - ab[1] * (P[:, 0] - a[0])) / n if n > 0 else np.hypot(*(P - a).T)
    k = int(np.argmax(d))
    if d[k] > eps:
        return np.vstack([rdp(P[:k + 1], eps)[:-1], rdp(P[k:], eps)])
    return np.vstack([a, b])

def chains(G, pos, keep):
    """Split a graph into polylines between junctions; flag chains that are bridges."""
    br = {frozenset(e) for e in nx.bridges(G)}
    junction = {v for v in G if G.degree(v) != 2 or v in keep}
    if not junction: junction = {next(iter(G))}
    seen = set(); out = []
    for a in junction:
        for b in G.neighbors(a):
            if frozenset((a, b)) in seen: continue
            path = [a, b]; seen.add(frozenset((a, b)))
            while path[-1] not in junction:
                nxt = [w for w in G.neighbors(path[-1]) if w != path[-2]][0]
                seen.add(frozenset((path[-1], nxt))); path.append(nxt)
            P = rdp(np.array([pos[v] for v in path]), 0.25)
            out.append(dict(b=frozenset((a, b)) in br, p=np.round(P, 1).tolist()))
    return out

def land_paths():
    h = 0.5; lo0, lo1, la0, la1 = mesh.BOX
    x0, y0 = mesh.proj(la0, lo0); x1, y1 = mesh.proj(la1, lo1)
    xs = np.arange(x0, x1 + h, h); ys = np.arange(y0, y1 + h, h); X, Y = np.meshgrid(xs, ys)
    lat, lon = mesh.unproj(X.ravel(), Y.ravel())
    land = mesh.inside(mesh._rings("data/ne_10m_land.geojson", mesh.BOX), lon, lat)
    elev, el, ea = mesh.load_elev(); e = np.full(len(lat), 0.0); e[land] = mesh.elev_at(lat[land], lon[land], elev, el, ea, 2)
    land &= ~(e < -1.5)
    Z = land.reshape(X.shape).astype(float)
    cs = plt.contourf(X, Y, Z, levels=[0.5, 1.5])
    paths = []
    for p in cs.get_paths():
        for poly in p.to_polygons():
            if len(poly) < 8: continue
            paths.append(np.round(rdp(poly, 0.3), 1).tolist())
    plt.close("all")
    return paths

def abstract_polylines(edges, m, pred, W):
    """Draw each abstract link along its land geodesic on the mesh."""
    fs = list(m["fs"]); G = nx.Graph(); pos = {}
    for i, j in edges:
        nodes = metrics.path_nodes(pred[i], fs[i], fs[j])
        for a, b in zip(nodes, nodes[1:]):
            G.add_edge((i, j, a), (i, j, b)) if False else None
    # bridges are decided on the abstract graph; draw link by link
    A = metrics.abstract_graph(edges, W); br = {frozenset(e) for e in nx.bridges(A)}
    out = []
    for i, j in edges:
        nodes = metrics.path_nodes(pred[i], fs[i], fs[j])
        P = rdp(m["xy"][nodes], 0.25)
        out.append(dict(b=frozenset((i, j)) in br, p=np.round(P, 1).tolist()))
    return out

if __name__ == "__main__":
    m = pickle.load(open("runs/mesh_250.pkl", "rb")); W, pred = metrics.geodesics(m)
    rows, mst = analyze.load_all()
    def find(**kw): return next(r for r in rows if all(r.get(k) == v for k, v in kw.items()))
    maps = []
    def stats(r): return dict(TL=round(r["TLn"], 2), MD=round(r["MDn"], 2), FT=round(r["FT"], 2), km=round(r["TL"]))
    for title, I0, g in (("Slime model, lean", 1.0, 1.8), ("Slime model, rail-like", 0.6, 1.2)):
        D = np.load(f"runs/I{I0}_g{g}_m250_s0_D.npy").astype(float)
        e = metrics.evaluate(metrics.physarum_graph(m, D), m["fs"], return_graph=True)
        pos = {v: m["xy"][v] for v in e["graph"]}
        maps.append(dict(id=f"phys_{g}_{I0}", title=title, sub=f"γ = {g}, I₀ = {I0}", kind="physarum",
                         lines=chains(e["graph"], pos, set(m["fs"])), **stats(find(kind="physarum", I0=I0, gamma=g, mask=250))))
    # real JR
    G, nodes, xy, tree, st_xy, st_name = rail.build("jr")
    snaps = rail.snap_fs(G, nodes, xy, tree, st_xy, st_name)
    e = metrics.evaluate(G, [s["node"] for s in snaps], return_graph=True)
    pos = dict(zip(nodes, xy))
    maps.append(dict(id="jr", title="Real JR lines", sub="MLIT N02, 2023", kind="rail",
                     lines=chains(e["graph"], pos, {s["node"] for s in snaps}), **stats(find(kind="rail", variant="jr"))))
    # engineered
    sp = baselines.greedy_spanner(W, 1.75)
    maps.append(dict(id="spanner", title="Greedy spanner", sub="detour ≤ 1.75×", kind="engineered",
                     lines=abstract_polylines(sp, m, pred, W), **stats(find(kind="spanner", t=1.75))))
    bc = baselines.bridge_cover(W, baselines.all_pairs(W))
    # rebuild the final bridge-cover edge set
    edges = metrics.mst_edges(W); have = {tuple(sorted(x)) for x in edges}
    while baselines.bridge_len(edges, W) > 1e-9:
        bl = baselines.bridge_len(edges, W); best, bv = None, 0
        for c in baselines.all_pairs(W):
            if c in have: continue
            v = (bl - baselines.bridge_len(edges + [c], W)) / W[c]
            if v > bv: best, bv = c, v
        edges.append(best); have.add(best)
    maps.append(dict(id="bridge", title="Bridge-covering", sub="MST + protecting links", kind="engineered",
                     lines=abstract_polylines(edges, m, pred, W), **stats(find(kind="bridge_cover", step=len(bc) - 1))))
    ring = [tuple(e) for e in find(kind="min_2ec")["chosen"]] if "chosen" in find(kind="min_2ec") else None
    if ring is None:
        ring = baselines.min_2ec(W, baselines.all_pairs(W))[0]
    maps.append(dict(id="ring", title="Cheapest fault-proof", sub="exact, by integer program", kind="engineered",
                     lines=abstract_polylines(ring, m, pred, W), **stats(find(kind="min_2ec"))))
    names = json.load(open("cities.json"))["cities"]
    fs = [dict(n=n, x=round(float(p[0]), 1), y=round(float(p[1]), 1)) for n, p in zip(names, m["xy"][m["fs"]])]
    pts = []
    for r in rows:
        if r["kind"] == "physarum" and r["mask"] != 250: continue
        if r["kind"] == "mst_plus" and r["k"] % 4: continue
        d = dict(kind=r["kind"], TL=round(r["TLn"], 3), MD=round(r["MDn"], 3), FT=round(r["FT"], 3))
        for k in ("gamma", "I0", "t", "step", "k", "variant"):
            if k in r: d[k] = r[k]
        pts.append(d)
    data = dict(maps=maps, land=land_paths(), fs=fs, points=pts, mst_km=round(mst["TL"]), mst_md=round(mst["MD"], 1),
                paper=dict(rail=dict(TL=1.8, MD=0.85, FT=0.96), physarum=dict(TL=1.75, MD=0.85, FT=0.80)))
    json.dump(data, open("page_data.json", "w"), separators=(",", ":"))
    import os; print("page_data.json", os.path.getsize("page_data.json") // 1024, "KB;", {mp["id"]: len(mp["lines"]) for mp in maps})
