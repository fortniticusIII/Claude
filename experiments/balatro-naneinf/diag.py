import sim, collections, sys
strat, econ, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
rs = sim.simulate(strat, econ, n, seed=7, immortal=True)
keys = ['a Soul','Perkeo','seed Cryptid','Baron','Mime','Baron+Mime','copies>=1','copies>=2','copies>=3','copies>=4',
        'Showman','Burglar','Antimatter',"Director's Cut",'Retcon','Paint Brush','Palette','Grabber','Nacho Tong','7 slots']
print(f'{strat} {econ}: share of runs that have each piece by the end of ante X (every blind played, no deaths)')
print('piece'.ljust(16), *[str(a).rjust(5) for a in (4,8,12,16,20,24,28,31)])
for k in keys:
    row=[sum(1 for r in rs if r.first.get(k,99)<=a)/n for a in (4,8,12,16,20,24,28,31)]
    if max(row)>0: print(k.ljust(16), *[f'{x*100:5.1f}' for x in row])
