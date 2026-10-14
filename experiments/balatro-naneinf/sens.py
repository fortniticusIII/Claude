import sim, json, os
from multiprocessing import Pool
N = 10000
cases = [('B', dict(diet_cola=False)), ('A', dict(diet_cola=False)), ('A', dict(max_ecto=1)), ('B', dict(smart_ecto=False)),
         ('B', dict(bridge=16)), ('A', dict(bridge=16)), ('A', dict(bridge=16, max_ecto=1))]
def go(c):
    s, p = c
    rs = sim.simulate(s, 'typical', N, seed=99, params=p)
    w = sum(r.result[0] == 'naneinf' for r in rs) / N
    return s, p, w
if __name__ == '__main__':
    with Pool(2) as pool:
        out = pool.map(go, cases)
    for s, p, w in out:
        print(s, p, f'{w*100:.2f}%')
    json.dump([[s, p, w] for s, p, w in out], open('results/sensitivity_typical_n10000.json', 'w'))
