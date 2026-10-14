import sim, collections, sys
strat, econ, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
rs = sim.simulate(strat, econ, n, seed=11)
got = [r for r in rs if 'Perkeo' in r.first]
print(f'{strat} {econ}: runs that found Perkeo {len(got)/n*100:.2f}%')
by = collections.defaultdict(list)
for r in got:
    a = r.first['Perkeo']; band = (a-1)//4*4+1
    by[band].append(r)
for band in sorted(by):
    g = by[band]; w = sum(1 for r in g if r.result[0]=='naneinf' and r.result[2]=='Perkeo')
    why = collections.Counter(r.result[2] for r in g if r.result[0]=='dead')
    print(f'  Perkeo found antes {band}-{band+3}: n={len(g):4d}  naneinf via Perkeo {w/len(g)*100:5.1f}%  fails:', dict(why.most_common(3)))
