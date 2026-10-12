import json, os, pickle, numpy as np
from multiprocessing import Pool
import model, metrics, similarity
THR = 1e-5
m = pickle.load(open("runs/mesh_250.pkl", "rb"))
W, pred = metrics.geodesics(m)
P = np.array(list(json.load(open("catchments.json"))["pop"].values()), float)
WEIGHTS = {"pop": np.outer(P, P), "gravity": np.outer(P, P) / np.where(W > 0, W, np.inf)}
mst = metrics.evaluate(metrics.abstract_graph(metrics.mst_edges(W), W), range(36))
JP, JW = similarity.jr_points()
def score_D(D, extra):
    e = metrics.evaluate(metrics.physarum_graph(m, D, thr=THR), m["fs"], return_graph=True)
    if not e.get("connected"): return dict(connected=False, **extra)
    Pp, Pw = similarity.graph_points(e["graph"], m["xy"])
    s = similarity.overlap(Pp, Pw, JP, JW)
    return dict(connected=True, TLn=e["TL"] / mst["TL"], MDn=e["MD"] / mst["MD"], FT=e["FT_len"], **s, **extra)
def job(cfg):
    wname, I0, g = cfg
    tag = f"W{wname}_I{I0}_g{g}"; out = f"runs/{tag}.json"
    if os.path.exists(out): return json.load(open(out))
    D, info = model.run(m, I0=I0, gamma=g, T=200, w=WEIGHTS[wname])
    np.save(f"runs/{tag}_D.npy", D.astype(np.float32))
    r = score_D(D, dict(weights=wname, I0=I0, gamma=g, t=info["t"]))
    json.dump(r, open(out, "w")); print(tag, {k: round(v, 3) for k, v in r.items() if isinstance(v, float)}, flush=True)
    return r
if __name__ == "__main__":
    cfgs = [(wn, I0, g) for wn in ("pop", "gravity") for g in (1.2, 1.5, 1.8) for I0 in (0.3, 0.6, 1.0, 2.0, 4.0)]
    with Pool(2) as p: res = p.map(job, cfgs, chunksize=1)
    # unweighted runs, re-scored the same way
    base = []
    for g in (1.2, 1.5, 1.8):
        for I0 in (0.3, 0.6, 1.0, 2.0, 4.0):
            D = np.load(f"runs/I{I0}_g{g}_m250_s0_D.npy").astype(float)
            base.append(score_D(D, dict(weights="equal", I0=I0, gamma=g)))
    json.dump(res + base, open("runs/weighted.json", "w"), indent=0)
    print("done")
