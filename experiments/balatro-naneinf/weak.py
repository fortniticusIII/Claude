import sim, json, os, collections
from multiprocessing import Pool
N = 20000
CELLS = [('B', b) for b in (3.5, 5, 8, 12)] + [('A', b) for b in (3.5, 12)] + [('Bimm', 12)]
def go(c):
    s, b = c
    path = f'results/weak_{s}_b{b}_{N}.json'
    if os.path.exists(path): return json.load(open(path))
    imm = s == 'Bimm'
    rs = sim.simulate('B' if imm else s, 'typical', N, seed=77, params=dict(bridge=b), immortal=imm)
    out = dict(strat=s, bridge=b, n=N, wins=sum(r.result[0] == 'naneinf' for r in rs),
               dead=collections.Counter(r.result[2] for r in rs if r.result[0] == 'dead'),
               dead_ante=collections.Counter(r.result[1] for r in rs if r.result[0] == 'dead'))
    if imm:
        for k in ('Burglar finish pieces', 'Burglar finish pieces + Retcon', 'Baron+Mime'):
            out[k] = {a: sum(1 for r in rs if r.first.get(k, 99) <= a) / N for a in (12, 16, 20, 24, 26, 31)}
    json.dump(out, open(path, 'w'))
    return out
if __name__ == '__main__':
    with Pool(2) as p:
        for o in p.imap_unordered(go, CELLS):
            print(o['strat'], o['bridge'], f"{o['wins']/o['n']*100:.2f}%", dict(collections.Counter(o['dead']).most_common(4)), flush=True)
            for k in ('Burglar finish pieces', 'Burglar finish pieces + Retcon', 'Baron+Mime'):
                if k in o: print('   ', k, {a: round(v*100, 1) for a, v in o[k].items()})
