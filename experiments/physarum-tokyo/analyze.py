"""Collect every network, normalise by the MST, and test Pareto dominance on (cost, transport, fault tolerance)."""
import json, glob, pickle, numpy as np
import metrics

GRID = 1.0505   # mean octile-grid inflation of land distances (measured); rail is in true geometry
meshes = {m: pickle.load(open(f"runs/mesh_{m}.pkl", "rb")) for m in ("250", "None")}

def physarum_rows():
    rows = []
    for p in sorted(glob.glob("runs/I*_s*.json")):
        r = json.load(open(p))
        tag = p[5:-5]; m = meshes[str(r["mask"]) if r["mask"] is not None else "None"]
        D = np.load(f"runs/{tag}_D.npy").astype(float)
        e = metrics.evaluate(metrics.physarum_graph(m, D), m["fs"])     # re-score with current metrics
        if not e.get("connected"): continue
        e.update(kind="physarum", I0=r["I0"], gamma=r["gamma"], mask=r["mask"], seed=r["seed"], tag=tag)
        rows.append(e)
    return rows

def load_all():
    base = json.load(open("runs/baselines.json"))["250"]
    mst = next(b for b in base if b["label"] == "mst")
    rows = []
    for b in base:
        b = dict(b); b["kind"] = b.pop("label"); rows.append(b)
    for r in physarum_rows(): rows.append(r)
    rail = json.load(open("runs/rail.json"))
    for v, r in rail.items():
        r = dict(r); r["kind"] = "rail"; r["variant"] = v
        r["TL"] *= GRID; r["MD"] *= GRID; rows.append(r)
    for r in rows:
        r["TLn"] = r["TL"] / mst["TL"]; r["MDn"] = r["MD"] / mst["MD"]; r["FT"] = r["FT_len"]
        r["alpha"] = r["FT"] / r["TLn"]
    return rows, mst

def dominates(a, b, eps=1e-9):
    """a at least as good as b on all three and strictly better on one (lower TL, lower MD, higher FT)."""
    ge = a["TLn"] <= b["TLn"] + eps and a["MDn"] <= b["MDn"] + eps and a["FT"] >= b["FT"] - eps
    gt = a["TLn"] < b["TLn"] - eps or a["MDn"] < b["MDn"] - eps or a["FT"] > b["FT"] + eps
    return ge and gt

if __name__ == "__main__":
    rows, mst = load_all()
    phys = [r for r in rows if r["kind"] == "physarum"]
    eng = [r for r in rows if r["kind"] in ("spanner", "bridge_cover", "mst_plus", "min_2ec", "delaunay", "mst")]
    rail = [r for r in rows if r["kind"] == "rail"]
    print(f"MST: {mst['TL']:.0f} km, MD {mst['MD']:.1f} km; {len(phys)} Physarum networks, {len(eng)} engineered")
    print("\nPhysarum (mask=250) by gamma, I0:")
    for r in sorted(phys, key=lambda r: (str(r["mask"]), r["gamma"], r["I0"])):
        dom_by = [f"{e['kind']}{'(t=' + str(e['t']) + ')' if 't' in e else ''}" for e in eng if dominates(e, r)]
        print(f"  mask={str(r['mask']):4s} g={r['gamma']:.1f} I0={r['I0']:5.1f}  TL={r['TLn']:.2f} MD={r['MDn']:.2f} FT={r['FT']:.2f} "
              f"alpha={r['alpha']:.2f}  dominated by {len(dom_by)}: {sorted(set(dom_by))[:4]}")
    print("\nRail:")
    for r in rail:
        dp = [p["tag"] for p in phys if dominates(p, r)]
        de = [e["kind"] + (f"(t={e['t']})" if "t" in e else "") for e in eng if dominates(e, r)]
        print(f"  {r['variant']:15s} TL={r['TLn']:.2f} MD={r['MDn']:.2f} FT={r['FT']:.2f} alpha={r['alpha']:.2f} "
              f"dominated by {len(dp)} Physarum {dp[:5]} and {len(de)} engineered {de[:5]}")
    # which Physarum networks are on the Pareto front of everything?
    allnets = phys + eng + rail
    front = [r for r in allnets if not any(dominates(o, r) for o in allnets if o is not r)]
    print(f"\nPareto front over all {len(allnets)} networks: {len(front)}")
    from collections import Counter
    print(Counter(r["kind"] for r in front))
    json.dump([{k: v for k, v in r.items() if k not in ("snaps", "chosen")} for r in rows],
              open("runs/all_rows.json", "w"), indent=0, default=str)
