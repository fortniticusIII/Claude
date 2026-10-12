import sys, json, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import mesh, model, metrics
I0 = float(sys.argv[1]); gam = float(sys.argv[2]); me = None if sys.argv[3] == "none" else float(sys.argv[3])
m = mesh.build(1.5, me)
W, pred = metrics.geodesics(m)
mst = metrics.evaluate(metrics.abstract_graph(metrics.mst_edges(W), W), range(36))
D, info = model.run(m, I0=I0, gamma=gam, T=150, log_every=100)
r = metrics.evaluate(metrics.physarum_graph(m, D), m["fs"])
print("MST", mst); print("Physarum", r)
if r.get("connected"):
    print(f"TL_MST={r['TL']/mst['TL']:.2f} MD_MST={r['MD']/mst['MD']:.2f} FT_len={r['FT_len']:.2f} FT_link={r['FT_link']:.2f} t={info['t']:.0f}")
fig, ax = plt.subplots(figsize=(7, 7))
ax.scatter(m["xy"][:, 0], m["xy"][:, 1], s=0.3, c="#ddd")
e = m["edges"]; a = D > 1e-3
for (u, v), d in zip(e[a], D[a]):
    ax.plot(*m["xy"][[u, v]].T, c="#c60", lw=0.6 + 3 * d)
f = m["xy"][m["fs"]]; ax.scatter(f[:, 0], f[:, 1], s=18, c="k", zorder=3)
ax.set_aspect("equal"); ax.set_title(f"I0={I0} gamma={gam} mask={me}")
plt.savefig(f"run_{I0}_{gam}_{me}.png", dpi=80, bbox_inches="tight")
