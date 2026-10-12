import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import mesh
fig, axs = plt.subplots(1, 2, figsize=(14, 7))
for ax, me in zip(axs, (None, 250)):
    m = mesh.build(1.5, me)
    ax.scatter(m["xy"][:, 0], m["xy"][:, 1], s=1, c="#9bb")
    f = m["xy"][m["fs"]]; ax.scatter(f[:, 0], f[:, 1], s=25, c="crimson")
    for n, (x, y) in zip(m["names"], f): ax.annotate(n, (x, y), fontsize=7)
    ax.set_aspect("equal"); ax.set_title(f"max_elev={me}  nodes={len(m['xy'])}")
plt.tight_layout(); plt.savefig("mesh.png", dpi=80)
