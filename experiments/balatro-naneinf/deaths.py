import sim, collections, sys
strat, econ, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
extra = eval(sys.argv[4]) if len(sys.argv) > 4 else None
rs = sim.simulate(strat, econ, n, seed=11, params=extra)
win = [r for r in rs if r.result[0]=='naneinf']
print(f'{strat} {econ} {extra or ""}: naneinf {len(win)/n*100:.2f}%  ', collections.Counter(r.result[2] for r in win))
print('  naneinf ante:', sorted(collections.Counter(r.result[1] for r in win).items()))
dead = collections.Counter((r.result[1], r.result[2]) for r in rs if r.result[0]=='dead')
byreason = collections.Counter(r.result[2] for r in rs if r.result[0]=='dead')
for why, c in byreason.most_common():
    antes = collections.Counter(r.result[1] for r in rs if r.result[0]=='dead' and r.result[2]==why)
    print(f'  dead: {why:32s} {c/n*100:5.1f}%  antes', sorted(antes.items())[:14])
