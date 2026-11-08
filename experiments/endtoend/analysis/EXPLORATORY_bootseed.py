"""EXPLORATORY (not pre-registered; PI, 2026-11-06 ~15:35 UTC, after unblinding). Reproducibility audit of the FROZEN
analysis/prereg_analysis.py, found while writing REPRODUCE.md: its paired-difference bootstrap is seeded with
`hash(key) % 1000` (key = 'Y1'/'Y2' for the population analysis, the arm name 'quar'/'ipd'/'fullp' for branches).
Python randomises str hashes per process (PYTHONHASHSEED), so the released diff CIs / bootstrap p-values are ONE of 1,000
possible Monte-Carlo draws; point estimates and the ratio CIs (fixed seed 1) are deterministic.

This script does not modify the frozen code. It rebuilds exactly the registered inputs with the frozen functions
(same data path as EXPLORATORY_distributions.py), evaluates the frozen boot_paired() for EVERY possible seed 0..999, and
reports (a) which seeds reproduce the released numbers, (b) the range of the CI bounds and p over all seeds, and (c)
whether every registered verdict that uses these CIs holds for all 1,000 seeds.
Usage: EXPLORATORY_bootseed.py --out analysis/EXPLORATORY_bootseed.json [--procs 6]"""
import argparse
import importlib.util
import json
import multiprocessing as mp
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


X = _load('expl_dist', HERE / 'EXPLORATORY_distributions.py')  # reuses its frozen-module loading and the registered inputs
F, W = X.F, X.W


def pop_diffs(cfg):
    by = F.load_proxy([str(E / d) for d in cfg['logs']])
    tasks = [t for t in open(E / 'configs/eligible_113.txt').read().split() if t]
    arms = {k: F.load_arm('+'.join(str(E / d) for d in cfg[k].split('+')), by) for k in ('base', 'fullp')}
    excl = {t for t in tasks if any(e['infra_error'] for arm in arms.values() for e in arm.get(t, []))}
    common = [t for t in tasks if t in arms['base'] and t in arms['fullp'] and t not in excl]
    out = {}
    for key in ('Y1', 'Y2'):  # exactly as F.population()
        xb = [F.task_mean(arms['base'][t], key) for t in common]
        xf = [F.task_mean(arms['fullp'][t], key) for t in common]
        out[key] = {'diffs': [f - b for b, f in zip(xb, xf)], 'ratio': F.boot_ratio(xb, xf)}
    return out


def branch_arms_ids():
    """Registered branch inputs: the same steps as EXPLORATORY_distributions.branches31() (itself a copy of F.branches()
    id selection under the pre-outcome corrected-fidelity wrapper W), stopping before any summary."""
    groups = X.BR31['groups']
    cmap = W.corrected_map([g.replace('plan=', f'plan={E}/').replace('=runs/', f'={E}/runs/') for g in groups])
    by = F.load_proxy([str(E / d) for d in X.BR31['logs']])
    for key, recs in by.items():  # identical to the wrapper's patch of load_proxy
        rundir = key.split('/')[0]
        if rundir not in cmap:
            continue
        _, verdict = cmap[rundir]
        tid = key.split(':')[-1]
        for r in recs:
            if r.get('replayed'):
                r['replay'] = {**(r.get('replay') or {}), 'fidelity': 'ok' if verdict.get(tid) == 'ok' else 'mismatch'}
    plan, arms = {}, defaultdict(dict)
    for gi, g in enumerate(groups):
        kv = dict(x.split('=', 1) for x in g.split(','))
        pl = json.loads((E / kv.pop('plan')).read_text())['branches']
        for t, e in pl.items():
            plan[f'{gi}:{t}'] = e
        for name, rd in kv.items():
            rd = E / rd
            rc = json.loads((rd / 'run_cfg.json').read_text())
            pref = f"{rc.get('tag', rd.name)}/{rc['cfg']}:"
            for line in open(rd / 'per_task.jsonl'):
                p = json.loads(line)
                reqs = by.get(pref + p['id'], [])
                fid_bad = any((r.get('replay') or {}).get('fidelity') == 'mismatch' for r in reqs)
                arms[name][f'{gi}:{p["id"]}'] = {**F.episode(reqs, p, after_index=pl[p['id']]['b'] if p['id'] in pl else None),
                                                 'fidelity_mismatch': fid_bad}
    ids = sorted(set.intersection(*[set(v) for v in arms.values()]) & set(plan))
    excl = [t for t in ids if any(arms[k][t]['fidelity_mismatch'] or arms[k][t]['infra_error'] for k in arms)]
    return arms, [t for t in ids if t not in excl]


def branch_diffs():
    arms, ids = branch_arms_ids()
    base = [arms['base'][t]['post']['malformed'] for t in ids]
    out = {}
    for k in arms:
        if k == 'base': continue
        x = [arms[k][t]['post']['malformed'] for t in ids]
        out[k] = {'diffs': [y - b0 for b0, y in zip(base, x)], 'ratio': F.boot_ratio(base, x)}
    return out, len(ids)


def _run(args):
    diffs, seed = args
    return seed, F.boot_paired(diffs, seed=seed)


def scan(diffs, procs):
    with mp.Pool(procs) as pool:
        res = dict(pool.map(_run, [(diffs, s) for s in range(1000)], chunksize=10))
    return res


def summarise(res, released, rule_hi_lt0=True):
    lo = [r['ci95'][0] for r in res.values()]; hi = [r['ci95'][1] for r in res.values()]; p = [r['p_boot'] for r in res.values()]
    match = [s for s, r in res.items() if r['ci95'] == released.get('ci95') and r['p_boot'] == released.get('p_boot')]
    return {'released': {'ci95': released.get('ci95'), 'p_boot': released.get('p_boot')},
            'seeds_reproducing_released': match,
            'ci_lo_range': [min(lo), max(lo)], 'ci_hi_range': [min(hi), max(hi)], 'p_boot_max': max(p),
            'ci_hi_lt_0_for_all_seeds': all(h < 0 for h in hi) if rule_hi_lt0 else None}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--procs', type=int, default=6)
    a = ap.parse_args()
    out = {'_status': 'EXPLORATORY reproducibility audit (frozen boot_paired evaluated at all 1,000 possible seeds); see docstring',
           'B': F.B}
    reg = json.load(open(E / 'analysis/prereg_pop31.json'))
    pd = pop_diffs(X.POPS['31B'])
    out['population_31B'] = {}
    for key in ('Y1', 'Y2'):
        rel = reg['co_primary'][key]['diff_fullp_minus_base']
        s = summarise(scan(pd[key]['diffs'], a.procs), rel)
        s['ratio_deterministic'] = pd[key]['ratio']; s['ratio_released'] = reg['co_primary'][key]['ratio_fullp_over_base']
        out['population_31B'][key] = s
    y1 = out['population_31B']['Y1']
    out['population_31B']['success_rule_holds_for_all_seeds'] = bool(
        y1['ratio_deterministic']['ratio'] <= 0.30 and y1['ci_hi_lt_0_for_all_seeds'])
    regb = json.load(open(E / 'analysis/prereg_br31.json'))
    bd, n = branch_diffs()
    out['branches_31B'] = {'n_branch_points': n, 'released_n': regb['n_branch_points']}
    for k, v in bd.items():
        rel = regb['post_onset'][k]['diff_vs_base']
        s = summarise(scan(v['diffs'], a.procs), rel)
        s['ratio_deterministic'] = v['ratio']; s['ratio_released'] = regb['post_onset'][k]['ratio_vs_base']
        s['success_reduction_ge_50pct_holds_for_all_seeds'] = bool(v['ratio']['ratio'] is not None and v['ratio']['ratio'] <= 0.5
                                                                   and s['ci_hi_lt_0_for_all_seeds'])
        out['branches_31B'][k] = s
    json.dump(out, open(a.out, 'w'), indent=1)
    print(json.dumps(out, indent=1)[:4000])


if __name__ == '__main__':
    sys.exit(main())
