import pickle, json, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, networkx as nx
import rail, metrics
m = pickle.load(open("runs/mesh_250.pkl", "rb"))
fig, axs = plt.subplots(1, 3, figsize=(18, 6.5))
for ax, v in zip(axs, rail.VARIANTS):
    G, nodes, xy, tree, st_xy, st_name = rail.build(v)
    snaps = rail.snap_fs(G, nodes, xy, tree, st_xy, st_name)
    r = metrics.evaluate(G, [s["node"] for s in snaps], return_graph=True)
    pos = {n: p for n, p in zip(nodes, xy)}
    ax.scatter(m["xy"][:, 0], m["xy"][:, 1], s=0.2, c="#e4e4e4")
    for a, b in G.edges(): ax.plot(*np.array([pos[a], pos[b]]).T, c="#ccc", lw=0.4)
    P = r["graph"]
    for a, b in P.edges(): ax.plot(*np.array([pos[a], pos[b]]).T, c="#2a6", lw=1.0)
    # highlight bridge corridors: edges of P whose removal disconnects (approx: edges in a bridge chain)
    br = set(nx.bridges(P))
    for a, b in br: ax.plot(*np.array([pos[a], pos[b]]).T, c="#d33", lw=1.6)
    f = np.array([pos[s["node"]] for s in snaps]); ax.scatter(f[:, 0], f[:, 1], s=14, c="k", zorder=3)
    ax.set_aspect("equal"); ax.set_title(f"{v}: TL={r['TL']:.0f} km FT_len={r['FT_len']:.2f}")
plt.tight_layout(); plt.savefig("rail.png", dpi=70)
