# Tokyo slime mold rerun

A replication and extension of Tero et al., "Rules for biologically inspired adaptive network design", *Science* 327:439 (2010). Done Oct 12, 2026 as self-directed work. Write-up: https://claude.ai/artifact/PCMvYWnXTY2GJpNUhcJr9z (source in `pages/tokyo-slime-mold-rerun/`).

## Question

The paper says *Physarum* and its flow model build networks comparable to the Tokyo rail system on cost (TL/MST), transport (MD/MST) and fault tolerance (FT). Does that hold when (a) the model runs on a real coastline and terrain, (b) the real rail network is measured from government data on the same map, and (c) both are set against textbook network constructions?

## Findings (mask = ground above 250 m excluded)

- The model reproduces the paper's trade-off: I0 up means more loops, cost and FT; gamma up pushes toward a tree. At gamma 2.2 and low I0 it finds a tree 0.6% shorter than the MST (Steiner junctions).
- Real JR conventional lines on this map: TL 2.25, MD 0.80, FT 0.85 (with 5% grid correction; 2.14, 0.76, 0.85 without it, and 4 of the 5 slime runs still dominate). The paper's rail map: 1.8, 0.85, 0.96. JR + Shinkansen: 2.79, 0.79, 0.92. All heavy rail: 6.17, 0.76, 0.97.
- 5 of 28 masked slime runs beat JR on all three at once, e.g. gamma 1.2, I0 0.6: 1.54, 0.74, 0.93.
- Greedy spanners (t = 1.5, 1.75) and dense MST+links also beat JR on all three. The three measures ignore demand, intermediate stations, gradients and history.
- Below 3x MST, 18 of 20 masked slime networks are not dominated by any of 58 engineered networks; the slime dominates 11 of them (mostly MST+links, where it wins on FT at equal cost).
- The paper's alpha = FT/TL is gamed by the exact min-cost 2-edge-connected network (a near-ring: 1.26, MD 1.72, FT 1, alpha 0.79, best of all). Greedy bridge-covering reaches FT 1 at TL 1.51 with MD 0.85: it beats the paper's rail point on all three and comes close to the paper's best simulation (alpha 0.66 vs 0.7 at the same MD).
- Robustness: 3 seeds vary TL by up to 8%; the stochastic one-pair-per-step dynamics land within ~10% on every measure; a 1.0 km mesh gives 1.76/0.71/0.99 vs 1.75/0.73/0.98 at 1.5 km.

## Files

- `mesh.py` land mesh (Natural Earth land, lakes from bathymetry < -1.5 m, optional elevation mask); `cities.py`, `cities.json` the 36 food sources (7 Tokyo hubs + 29 cities, my reconstruction).
- `model.py` mean-field Tero model: one sparse factorisation per step, all 630 FS pairs by linearity; solves only on live tubes.
- `metrics.py` TL, MD, FT (per km and per link), bridge-tree pruning of spurs that serve no FS.
- `baselines.py` MST, MST+shortest Delaunay links, greedy spanners, greedy bridge-covering, exact min-cost 2-edge-connected subgraph (scipy milp with cut constraints).
- `rail.py` MLIT N02-23 rail: 100 m corridor merge with point-mean cell positions (no stair-step inflation), nearest-station snapping.
- `sweep.py`, `robust.py`, `analyze.py`, `export.py` the runs, checks, dominance analysis and page data.
- `runs/all_rows.json` every network re-scored with the final metrics (use this; `sweep.json` holds the first-pass scores).
- `fetch_data.sh` downloads the inputs not kept here.

## Gotchas met on the way

- Natural Earth 10 m lakes has no Kasumigaura; Terrarium bathymetry does. Tokyo's below-sea-level wards read positive in Terrarium, so a < -1.5 m threshold is safe.
- MLIT draws each line separately on shared corridors (~5% duplicate length). Leaf-only pruning fails on raster spurs that end in tiny loops; prune on the bridge tree instead.
- Octile-grid distances run ~5% long (measured over 448 land pairs); rail is in true geometry, so rail TL and MD are scaled by 1.05.
- Wikipedia's API and Open-Meteo rate-limit the shared egress IP (429); Overpass resets the tunnel.
