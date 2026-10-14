"""1.0.1o (current) vs 1.1 as previewed in Sept 2026: >=4 new jokers of unknown rarity, a Lunker voucher set."""
import sim, json, os, collections
from multiprocessing import Pool
VARIANTS = {
    '1.0.1o (current)':        dict(),
    '1.1, new jokers common':  dict(extra_voucher_sets=1),
    '1.1, 2 uncommon + 2 rare': dict(uncommons=66, rares=22, extra_voucher_sets=1),
    '1.1, all 4 rare':         dict(rares=24, extra_voucher_sets=1),
}
CELLS = [(v, s, 'typical', 40000) for v in VARIANTS for s in 'AB'] + \
        [(v, s, e, 20000) for v in ('1.0.1o (current)', '1.1, 2 uncommon + 2 rare') for s in 'AB' for e in ('lean', 'rich')]
def go(c):
    v, s, e, n = c
    path = 'results/v11_' + ''.join(ch if ch.isalnum() else '_' for ch in f'{v}_{s}_{e}_{n}') + '.json'
    if os.path.exists(path):
        return json.load(open(path))
    rs = sim.simulate(s, e, n, seed=2026, params=VARIANTS[v])
    out = dict(variant=v, strat=s, econ=e, n=n, wins=sum(r.result[0] == 'naneinf' for r in rs),
               perkeo=sum('Perkeo' in r.first for r in rs),
               dead=collections.Counter(r.result[2] for r in rs if r.result[0] == 'dead'))
    json.dump(out, open(path, 'w'))
    return out
if __name__ == '__main__':
    with Pool(2) as p:
        for o in p.imap_unordered(go, CELLS):
            print(f"{o['variant']:26s} {o['strat']} {o['econ']:8s} {o['wins']/o['n']*100:6.2f}%", flush=True)
