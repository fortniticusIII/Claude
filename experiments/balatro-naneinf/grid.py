import sim, json, os, sys, collections, itertools
from multiprocessing import Pool
N = int(os.environ.get('N', 20000))
OUT = 'results'
os.makedirs(OUT, exist_ok=True)

def cell(args):
    strat, econ, bridge, skip, immortal = args
    key = f'{strat}_{econ}_b{bridge}_skip{int(skip)}_imm{int(immortal)}_n{N}'
    path = f'{OUT}/{key}.json'
    if os.path.exists(path):
        return key
    os.environ['OMP_NUM_THREADS'] = '1'
    seed = hash((strat, econ, bridge, skip, immortal)) % 10**6
    rs = sim.simulate(strat, econ, N, seed=seed, params=dict(bridge=bridge, skip_hunt=skip), immortal=immortal)
    out = dict(strat=strat, econ=econ, bridge=bridge, skip=skip, immortal=immortal, n=N)
    out['first'] = {}
    keys = set(k for r in rs for k in r.first)
    for k in keys:
        c = collections.Counter(r.first[k] for r in rs if k in r.first)
        out['first'][k] = {a: c.get(a, 0) for a in range(1, 39)}
    if not immortal:
        out['win'] = collections.Counter(f'{r.result[1]}|{r.result[2]}' for r in rs if r.result[0] == 'naneinf')
        out['dead'] = collections.Counter(f'{r.result[1]}|{r.result[2]}' for r in rs if r.result[0] == 'dead')
        # conditional on Perkeo: ante found -> [n, wins]
        cp = collections.defaultdict(lambda: [0, 0])
        for r in rs:
            if 'Perkeo' in r.first:
                cp[r.first['Perkeo']][0] += 1
                cp[r.first['Perkeo']][1] += r.result[0] == 'naneinf' and r.result[2] == 'Perkeo'
        out['perkeo_cond'] = dict(cp)
        # B pieces at the window: share of live runs at ante 26 that have each piece
    json.dump(out, open(path, 'w'))
    return key

if __name__ == '__main__':
    cells = [(s, e, b, False, False) for s in 'ABH' for e in ('lean', 'typical', 'rich') for b in (10, 12, 14)]
    cells += [(s, 'typical', 12, True, False) for s in 'ABH']
    cells += [(s, e, 12, False, True) for s in 'AB' for e in ('lean', 'typical', 'rich')]
    with Pool(2) as p:
        for k in p.imap_unordered(cell, cells):
            print('done', k, flush=True)
