"""PREREG_E_ext analysis (frozen with experiments/endtoend/PREREG_E_ext.md before any E_ext episode). Run ONCE.
Imports PREREG_E's frozen analysis/prereg_analysis.py unchanged; every bootstrap seed is an explicit integer.
Episodes are paired by (task, replicate) -- each replicate is loaded separately -- so a missing episode can never
misalign the arms.
usage: prereg_E_ext_analysis.py --out analysis/prereg_E_ext.json [--first 3 --last 10] [--status_only]
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


def run_dir(k, h, arm):
    return E / f'runs/pop31r{k}s{h}_H_{arm}'


def complete(k):
    for h in (0, 1):
        for arm in ('base', 'fullp'):
            p = run_dir(k, h, arm) / 'per_task.jsonl'
            if not p.exists():
                return False
            done = {json.loads(l)['id'] for l in open(p) if l.strip()}
            if not set(HALF[h]) <= done:
                return False
    return True


def load_rep(k):
    by = F.load_proxy([str(E / f'logs/proxy_pop31r{k}s{h}') for h in (0, 1)])
    return {arm: F.load_arm('+'.join(str(run_dir(k, h, arm)) for h in (0, 1)), by) for arm in ('base', 'fullp')}


def pairs_for(reps):
    """-> {task: [(base_episode, fullp_episode, k), ...]} over the given replicates, infra-error pairs excluded."""
    out, excl = {t: [] for t in TASKS}, []
    for k in reps:
        R = load_rep(k)
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


def ni_stat(P, seed):
    d = [sum(f['resolved'] - b['resolved'] for b, f, _ in v) / len(v) for v in P.values()]
    r = F.boot_paired(d, seed=seed)
    r['non_inferior_at_-3pp'] = bool(r.get('ci95') and r['ci95'][0] > -0.03)
    nb = sum(b['resolved'] for v in P.values() for b, _, _ in v); nf = sum(f['resolved'] for v in P.values() for _, f, _ in v)
    n = sum(len(v) for v in P.values())
    r['resolved_base_fullp_of'] = [nb, nf, n]
    return r


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--first', type=int, default=3)
    ap.add_argument('--last', type=int, default=10); ap.add_argument('--status_only', action='store_true')
    a = ap.parse_args()
    status = {k: complete(k) for k in range(a.first, a.last + 1)}
    K = a.first - 1
    while K + 1 <= a.last and status[K + 1]:
        K += 1
    reps = list(range(a.first, K + 1))
    out = {'prereg': 'PREREG_E_ext.md (sha256 in PROGRESS.md at freeze)', 'B': F.B, 'replicate_complete': status,
           'analysis_set': reps}
    if a.status_only:
        print(json.dumps(out)); return 0
    if len(reps) < 4:
        out['primary_verdict'] = 'UNDERPOWERED (fewer than 4 fresh replicates complete)'
    P, excl = pairs_for(reps)
    out['n_tasks'] = len(P); out['n_episode_pairs'] = sum(len(v) for v in P.values()); out['excluded_pairs'] = excl
    prim = ni_stat(P, 20261107)
    out['primary_resolve'] = prim
    if len(reps) >= 4:
        out['primary_verdict'] = 'RESOLVE NON-INFERIOR' if prim['non_inferior_at_-3pp'] else 'NI NOT SHOWN'
    sec = {}
    for key, seed in (('Y1', 20261108), ('Y2', 20261109)):
        xb = [sum(b[key] for b, _, _ in v) / len(v) for v in P.values()]
        xf = [sum(f[key] for _, f, _ in v) / len(v) for v in P.values()]
        sec[key] = {'base_mean': round(sum(xb) / len(xb), 4), 'fullp_mean': round(sum(xf) / len(xf), 4),
                    'ratio_fullp_over_base': F.boot_ratio(xb, xf, seed=1),
                    'diff_fullp_minus_base': F.boot_paired([f - b for b, f in zip(xb, xf)], seed=seed)}
    r1 = sec['Y1']['ratio_fullp_over_base']['ratio']; ci1 = sec['Y1']['diff_fullp_minus_base'].get('ci95')
    sec['Y1']['verdict'] = 'REPLICATES' if (r1 is not None and r1 <= 0.30 and ci1 and ci1[1] < 0) else 'DOES NOT REPLICATE'
    sb = [(b['stuck'], f['stuck']) for v in P.values() for b, f, _ in v]
    sec['stuck'] = {'base': [sum(x for x, _ in sb), len(sb)], 'fullp': [sum(y for _, y in sb), len(sb)],
                    'mcnemar_p': F.mcnemar(sum(1 for x, y in sb if x and not y), sum(1 for x, y in sb if y and not x))}
    out['secondary'] = sec
    # descriptive, sequential: all replicates r1..rK
    P10, _ = pairs_for([1, 2] + reps)
    out['descriptive_all_replicates'] = {'replicates': [1, 2] + reps, 'resolve': ni_stat(P10, 20261110)}
    json.dump(out, open(HERE.parent / a.out if not Path(a.out).is_absolute() else a.out, 'w'), indent=1)
    print(json.dumps({'analysis_set': reps, 'primary_verdict': out.get('primary_verdict'), 'primary_resolve': prim,
                      'Y1': sec['Y1'], 'stuck': sec['stuck']}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
