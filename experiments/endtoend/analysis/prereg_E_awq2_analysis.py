"""PREREG_E_awq2 analysis (frozen with experiments/endtoend/PREREG_E_awq2.md before any E_awq2 episode). Run ONCE.
Imports PREREG_E's frozen analysis/prereg_analysis.py unchanged; every bootstrap seed is an explicit integer.
Episodes are paired by (task, replicate) -- each replicate is loaded separately -- as in prereg_E_ext_analysis.py.
usage: prereg_E_awq2_analysis.py --out analysis/prereg_E_awq2.json [--first 3 --last 8] [--status_only]
  --status_only: completeness of each replicate (operational QA; reads only per_task.jsonl line counts)."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


F = _load('prereg_frozen', HERE / 'prereg_analysis.py')
HALF = {h: [t for t in open(E / f'configs/eligible_113_half{h}.txt').read().split() if t] for h in (0, 1)}
TASKS = [t for t in open(E / 'configs/eligible_113.txt').read().split() if t]


def run_dir(prefix, k, h, arm):
    return E / f'runs/{prefix}{k}s{h}_H_{arm}'


def complete(k, prefix='popAWQr'):
    for h in (0, 1):
        for arm in ('base', 'fullp'):
            p = run_dir(prefix, k, h, arm) / 'per_task.jsonl'
            if not p.exists():
                return False
            done = {json.loads(l)['id'] for l in open(p) if l.strip()}
            if not set(HALF[h]) <= done:
                return False
    return True


def load_rep(prefix, k):
    by = F.load_proxy([str(E / f'logs/proxy_{prefix}{k}s{h}') for h in (0, 1)])
    return {arm: F.load_arm('+'.join(str(run_dir(prefix, k, h, arm)) for h in (0, 1)), by) for arm in ('base', 'fullp')}


def pairs_for(prefix, reps):
    """-> {task: [(base_episode, fullp_episode, k), ...]}, infra-error pairs excluded."""
    out, excl = {t: [] for t in TASKS}, []
    for k in reps:
        R = load_rep(prefix, k)
        for t in TASKS:
            b, f = R['base'].get(t), R['fullp'].get(t)
            if not b or not f:
                excl.append([t, k, 'missing'])
                continue
            b, f = b[0], f[0]
            if b['infra_error'] or f['infra_error']:
                excl.append([t, k, 'infra'])
                continue
            out[t].append((b, f, k))
    return {t: v for t, v in out.items() if v}, excl


def arm_means(P, arm, key):
    i = 0 if arm == 'base' else 1
    return {t: sum(p[i][key] for p in v) / len(v) for t, v in P.items()}


def contrast(XA, XB, seed):
    """A vs B task means (A = treatment); ratio A/B with boot_ratio (seed 1), diff A - B with boot_paired(seed)."""
    ts = [t for t in TASKS if t in XA and t in XB]
    a = [XA[t] for t in ts]; b = [XB[t] for t in ts]
    return {'n_tasks': len(ts), 'A_mean': round(sum(a) / len(a), 4), 'B_mean': round(sum(b) / len(b), 4),
            'ratio_A_over_B': F.boot_ratio(b, a, seed=1),
            'diff_A_minus_B': F.boot_paired([x - y for x, y in zip(a, b)], seed=seed)}


def within(P, key, seed):
    return contrast(arm_means(P, 'fullp', key), arm_means(P, 'base', key), seed)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--first', type=int, default=3)
    ap.add_argument('--last', type=int, default=8); ap.add_argument('--status_only', action='store_true')
    a = ap.parse_args()
    status = {k: complete(k) for k in range(a.first, a.last + 1)}
    K = a.first - 1
    while K + 1 <= a.last and status[K + 1]:
        K += 1
    reps = list(range(a.first, K + 1))
    out = {'prereg': 'PREREG_E_awq2.md (sha256 in PROGRESS.md at freeze)', 'B': F.B, 'replicate_complete': status,
           'analysis_set': reps}
    if a.status_only:
        print(json.dumps(out)); return 0
    P, excl = pairs_for('popAWQr', reps)
    out['n_tasks'] = len(P); out['n_episode_pairs'] = sum(len(v) for v in P.values()); out['excluded_pairs'] = excl
    prim = within(P, 'Y1', 20261114)
    ci = prim['diff_A_minus_B'].get('ci95')
    if len(reps) < 3:
        prim['verdict'] = 'UNDERPOWERED (fewer than 3 fresh replicates complete)'
    else:
        prim['verdict'] = "SLIPGUARD STILL REDUCES MALFORMED CALLS ON THE AUDIT'S PICK" if (ci and ci[1] < 0) else 'NOT SHOWN'
    out['primary_P2_awq_fullp_vs_awq_base'] = prim
    sec = {'S1_Y2': within(P, 'Y2', 20261115)}
    sb = [(b['stuck'], f['stuck']) for v in P.values() for b, f, _ in v]
    sec['S2_stuck'] = {'base': [sum(x for x, _ in sb), len(sb)], 'fullp': [sum(y for _, y in sb), len(sb)],
                       'mcnemar_p': F.mcnemar(sum(1 for x, y in sb if x and not y), sum(1 for x, y in sb if y and not x))}
    d = [sum(f['resolved'] - b['resolved'] for b, f, _ in v) / len(v) for v in P.values()]
    r = F.boot_paired(d, seed=20261116)
    r['non_inferior_at_-3pp_descriptive'] = bool(r.get('ci95') and r['ci95'][0] > -0.03)
    r['resolved_base_fullp_of'] = [sum(b['resolved'] for v in P.values() for b, _, _ in v),
                                   sum(f['resolved'] for v in P.values() for _, f, _ in v), sum(len(v) for v in P.values())]
    sec['S3_resolve'] = r
    Q, _ = pairs_for('pop31r', list(range(1, 11)))
    s4 = contrast(arm_means(P, 'base', 'Y1'), arm_means(Q, 'base', 'Y1'), 20261117)
    c4 = s4['diff_A_minus_B'].get('ci95')
    s4['verdict'] = 'REPLICATES' if (c4 and c4[1] < 0) else 'DOES NOT REPLICATE'
    s4['comparator'] = 'QAT base, pop31 r1..r10'
    sec['S4_awq_base_vs_qat_base_fresh'] = s4
    out['secondary'] = sec
    Pall, _ = pairs_for('popAWQr', [1, 2] + reps)
    out['descriptive_all_awq_replicates'] = {'replicates': [1, 2] + reps, 'P2': within(Pall, 'Y1', 20261118)}
    json.dump(out, open(a.out if Path(a.out).is_absolute() else E / a.out, 'w'), indent=1)
    print(json.dumps({'analysis_set': reps, 'primary': prim, 'stuck': sec['S2_stuck'], 'S4': s4['verdict']}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
