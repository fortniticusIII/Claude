"""Hours per naneinf under reset policies (Oct 14, 2026).

A reset policy abandons a run at the end of an ante when its state is worth less per minute than
starting over. The best such policy is found by optimal stopping on simulated runs: the reward
rate lam is fixed, each (ante, state) group continues only if its runs' future wins outweigh
lam x their future minutes (backward induction over antes), then lam is set to the policy's
own rate and the search repeats until it settles (Dinkelbach). Fitted on one half of the runs,
scored on the other half.

The Charm Tag reset: start a Ghost run, look at ante 1's two tags (15 possible), reset unless
one is a Charm Tag; skip for it, open the free Mega Arcana (5 cards, 0.3% each to be The Soul,
1 in 5 Souls is Perkeo); reset unless Perkeo. Then play the run out.
"""
import sim, pickle, os, sys, collections
from multiprocessing import Pool

N = int(os.environ.get('N', 40000))
TIME = {   # minutes per ante by band, and seconds per reset look
    'fast':    dict(bands=[(8, 3), (16, 5), (24, 7), (99, 10)], reset_s=6, open_s=20),
    'typical': dict(bands=[(8, 4), (16, 7), (24, 10), (99, 14)], reset_s=10, open_s=30),
    'slow':    dict(bands=[(8, 5), (16, 9), (24, 14), (99, 20)], reset_s=15, open_s=45),
}


def cum_minutes(tm):
    out, t = [0.0], 0.0
    for a in range(1, 40):
        t += next(m for top, m in tm['bands'] if a <= top)
        out.append(t)
    return out          # out[a] = minutes to finish ante a


def runs(strat, params, seed):
    path = f'results/timing_{strat}_{"_".join(f"{k}{v}" for k, v in sorted(params.items()))}_{N}.pkl'
    if os.path.exists(path):
        return pickle.load(open(path, 'rb'))
    rs = sim.simulate(strat, 'typical', N, seed=seed, params=params)
    slim = [(r.result[0] == 'naneinf', r.result[1], r.trace) for r in rs]
    pickle.dump(slim, open(path, 'wb'))
    return slim


def state(t):
    ante, boost, engine, baron, mime, perkeo, seed, slots7, retcon, showman, cryptids = t
    return (boost, engine, baron, mime, perkeo, seed, slots7, retcon, showman, min(cryptids // 10, 4))


def evaluate(data, cum, policy):
    """Wins and minutes when abandoning at the end of ante a whenever policy says stop."""
    wins = minutes = 0.0
    for win, end, trace in data:
        stopped = False
        for t in trace:
            a = t[0]
            if a >= end:
                break
            if policy.get((a, state(t)), True) is False:
                minutes += cum[a]
                stopped = True
                break
        if not stopped:
            minutes += cum[end]
            wins += win
    return wins, minutes


def fit(data, cum, lam, min_group=40):
    """Backward induction. W[i] = value (wins - lam*minutes) of run i from the end of ante a if it
    continues there, given the policy already fixed for later antes."""
    policy = {}
    W = [None] * len(data)
    for a in range(38, 0, -1):
        newW = [None] * len(data)
        groups = collections.defaultdict(list)
        for i, (win, end, trace) in enumerate(data):
            if a >= end:
                continue
            if a + 1 >= end:
                w = win - lam * (cum[end] - cum[a])
            else:
                cont_next = policy.get((a + 1, state(trace[a])), True)
                w = -lam * (cum[a + 1] - cum[a]) + (W[i] if cont_next else 0.0)
            newW[i] = w
            groups[state(trace[a - 1])].append(i)
        for s, idx in groups.items():
            v = sum(newW[i] for i in idx) / len(idx)
            policy[(a, s)] = v > 0 or len(idx) < min_group
        W = newW
    return policy


def best_policy(data, cum, iters=8, overhead=0.0, min_group=40):
    w, m = evaluate(data, cum, {})
    lam = w / (m + overhead * len(data))
    pol = {}
    for _ in range(iters):
        pol = fit(data, cum, lam, min_group)
        w, m = evaluate(data, cum, pol)
        new = w / (m + overhead * len(data))
        if abs(new - lam) < 1e-9:
            break
        lam = new
    return pol


def hours_per_win(wins, minutes):
    return float('inf') if wins == 0 else minutes / wins / 60


def report(name, data, cum, min_group=40):
    half = len(data) // 2
    train, test = data[:half], data[half:]
    w0, m0 = evaluate(test, cum, {})
    pol = best_policy(train, cum, min_group=min_group)
    w1, m1 = evaluate(test, cum, pol)
    stops = sum(1 for v in pol.values() if v is False)
    return dict(plan=name, commit_pct=w0 / len(test) * 100, commit_h=hours_per_win(w0, m0),
                reset_pct=w1 / len(test) * 100, reset_h=hours_per_win(w1, m1), stop_rules=stops,
                attempts_min=m1 / len(test)), pol


def charm_reset(start_data, cum, tm, pol=None):
    p_charm = 2 / 15 + 1 / 225                 # either ante-1 tag is Charm, or Double then Charm
    p_perkeo_pack = (1 - 0.997 ** 5) / 5
    per_reset_min = tm['reset_s'] / 60 + p_charm * tm['open_s'] / 60
    p_perkeo = p_charm * p_perkeo_pack
    min_per_perkeo = per_reset_min / p_perkeo
    w, m = evaluate(start_data, cum, pol or {})
    p_win = w / len(start_data)
    run_min = m / len(start_data)
    return dict(p_perkeo_per_reset=p_perkeo, resets_per_perkeo=1 / p_perkeo, hours_per_perkeo=min_per_perkeo / 60,
                p_win_given_perkeo=p_win * 100, run_hours=run_min / 60,
                hours_per_win=(min_per_perkeo + run_min) / p_win / 60 if p_win else float('inf'))


if __name__ == '__main__':
    with Pool(2) as pool:
        jobs = {'A': pool.apply_async(runs, ('A', {}, 101)), 'B': pool.apply_async(runs, ('B', {}, 202)),
                'A1': pool.apply_async(runs, ('A', {'start_perkeo': True}, 303))}
        data = {k: j.get() for k, j in jobs.items()}
    out = {}
    for tname, tm in TIME.items():
        cum = cum_minutes(tm)
        ra, pa = report('Perkeo Ghost', data['A'], cum)
        rb, pb = report('Plasma Burglar', data['B'], cum)
        rb2, _ = report('Plasma (coarse)', data['B'], cum, min_group=400)
        half = len(data['A1']) // 2
        rc = charm_reset(data['A1'][half:], cum, tm)
        overhead = rc['hours_per_perkeo'] * 60
        pa1 = best_policy(data['A1'][:half], cum, overhead=overhead)
        rc2 = charm_reset(data['A1'][half:], cum, tm, pa1)
        out[tname] = dict(A=ra, B=rb, B_coarse=rb2, charm=rc, charm_plus_resets=rc2)
        # what the Perkeo-run reset rule does: first ante it stops runs, by state
        stops = sorted((a, s) for (a, s), v in pa1.items() if v is False)
        print('  Perkeo-run stop rules (ante, state):', stops[:12], '...' if len(stops) > 12 else '')
        print(f'== time model: {tname}  ({tm["bands"]}, reset look {tm["reset_s"]}s)')
        for r in (ra, rb, rb2):
            print(f"  {r['plan']:15s} commit: {r['commit_pct']:.2f}% of runs, {r['commit_h']:.0f} h per naneinf | "
                  f"best resets: {r['reset_pct']:.2f}% of attempts, {r['reset_h']:.0f} h per naneinf, "
                  f"{r['attempts_min']:.0f} min per attempt")
        for nm, r in (('Charm-reset Ghost', rc), ('Charm-reset + later resets', rc2)):
            print(f"  {nm:26s} {r['resets_per_perkeo']:.0f} resets ({r['hours_per_perkeo']:.1f} h) per Perkeo; "
                  f"wins {r['p_win_given_perkeo']:.1f}% of those runs, {r['run_hours']:.1f} h per run -> "
                  f"{r['hours_per_win']:.0f} h per naneinf")
    import json
    json.dump(out, open(f'results/timing_summary_{N}.json', 'w'), indent=1)
