import json, glob, collections
R = {}
for f in glob.glob('results/*.json'):
    d = json.load(open(f)); R[(d['strat'], d['econ'], d['bridge'], d['skip'], d['immortal'])] = d
def win(d, route=None):
    return sum(v for k, v in d['win'].items() if route is None or k.endswith(route)) / d['n']
print('P(naneinf) by plan, economy, pre-Baron engine strength (log10 Mult)')
for s in 'ABH':
    for e in ('lean', 'typical', 'rich'):
        row = []
        for b in (10, 12, 14):
            d = R.get((s, e, b, False, False))
            row.append(f'{win(d)*100:5.2f}%' if d else '   ...')
        print(f'  {s} {e:8s}', *row)
for s in 'ABH':
    d = R.get((s, 'typical', 12, True, False))
    if d: print(f'  {s} typical b12 + skip-for-tags: {win(d)*100:.2f}%')
d = R.get(('H', 'typical', 12, False, False))
if d: print('  H routes:', {r: round(win(d, r)*100, 2) for r in ('Burglar', 'Perkeo')})
print()
for s in 'ABH':
    d = R.get((s, 'typical', 12, False, False))
    if not d: continue
    n = d['n']
    reasons = collections.Counter()
    for k, v in d['dead'].items():
        reasons[k.split('|')[1]] += v
    print(s, 'typical b12 failures:', {k: round(v/n*100, 1) for k, v in reasons.most_common()})
    wa = collections.Counter()
    for k, v in d['win'].items(): wa[int(k.split('|')[0])] += v
    tot = sum(wa.values())
    if tot:
        cum, med = 0, None
        for a in sorted(wa):
            cum += wa[a]
            if med is None and cum >= tot/2: med = a
        print('   naneinf ante median', med, 'range', min(wa), '-', max(wa))
    if s == 'A':
        cp = d['perkeo_cond']; bands = collections.defaultdict(lambda: [0, 0])
        for a, (nn, w) in cp.items():
            a = int(a); bands[(a-1)//4][0] += nn; bands[(a-1)//4][1] += w
        print('   P(naneinf | Perkeo found in antes):', {f'{b*4+1}-{b*4+4}': f'{w/nn*100:.0f}% (n={nn})' for b, (nn, w) in sorted(bands.items())})
print()
for s in 'AB':
    for e in ('lean', 'typical', 'rich'):
        d = R.get((s, e, 12, False, True))
        if not d: continue
        print(f'supply {s} {e}: share of runs with the piece by end of ante')
        for k in ['Perkeo', 'seed Cryptid', 'Baron', 'Mime', 'Baron+Mime', 'copies>=2', 'copies>=4', 'Showman', 'Burglar', 'Antimatter', 'Retcon', '7 slots']:
            if k not in d['first']: continue
            c = d['first'][k]
            row = [sum(c[str(x)] for x in range(1, a+1))/d['n']*100 for a in (8, 12, 16, 20, 24, 26)]
            print(f'   {k:13s}', *[f'{x:5.1f}' for x in row])
