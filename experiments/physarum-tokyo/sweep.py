import sys, json, os, pickle, itertools, numpy as np
from multiprocessing import Pool
import mesh, model, metrics
os.makedirs("runs", exist_ok=True)
def get_mesh(me):
    p = f"runs/mesh_{me}.pkl"
    if not os.path.exists(p):
        pickle.dump(mesh.build(1.5, me), open(p, "wb"))
    return pickle.load(open(p, "rb"))
def job(cfg):
    I0, gam, me, seed = cfg
    tag = f"I{I0}_g{gam}_m{me}_s{seed}"
    out = f"runs/{tag}.json"
    if os.path.exists(out): return json.load(open(out))
    m = get_mesh(me)
    D, info = model.run(m, I0=I0, gamma=gam, T=200, seed=seed)
    r = metrics.evaluate(metrics.physarum_graph(m, D), m["fs"])
    r.update(I0=I0, gamma=gam, mask=me, seed=seed, t=info["t"])
    np.save(f"runs/{tag}_D.npy", D.astype(np.float32))
    json.dump(r, open(out, "w"))
    print(tag, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k in ("TL", "MD", "FT_len", "t", "connected")}, flush=True)
    return r
if __name__ == "__main__":
    for me in (250, "none"):
        get_mesh(None if me == "none" else me)
    I0s = [0.3, 0.6, 1.0, 2.0, 4.0, 8.0, 16.0]; gams = [1.2, 1.5, 1.8, 2.2]
    cfgs = [(I0, g, me, s) for me in (250, None) for g in gams for I0 in I0s for s in (0,)]
    with Pool(2) as p:
        res = p.map(job, cfgs, chunksize=1)
    json.dump(res, open("runs/sweep.json", "w"))
