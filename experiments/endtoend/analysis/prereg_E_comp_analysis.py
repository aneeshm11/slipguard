"""PREREG_E_comp analysis (frozen with experiments/endtoend/PREREG_E_comp.md before any E_comp episode). Run ONCE.
Which slipguard component carries the end-to-end gain? Quarantine-only and IPD-only arms (compr<k>), salt-paired with
the registered base and fullp episodes of PREREG_E_ext replicate k (pop31r<k>). Uses prereg_cov_common.py.
usage: prereg_E_comp_analysis.py --out analysis/prereg_E_comp.json [--status_only]"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prereg_cov_common as C  # noqa: E402

FIRST, LAST = 3, 8


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--status_only', action='store_true')
    a = ap.parse_args()
    st, reps = C.prefix_set('compr', ('quar', 'ipd'), FIRST, LAST)
    out = {'prereg': 'PREREG_E_comp.md (sha256 in PROGRESS.md at freeze)', 'B': C.F.B, 'replicate_complete': st,
           'analysis_set': reps}
    if a.status_only:
        print(json.dumps(out)); return 0
    if len(reps) < 2:
        out['primary'] = {'verdict': 'UNDERPOWERED (fewer than 2 replicates complete)'}
    spec = [('base', 'pop31r', 'base'), ('fullp', 'pop31r', 'fullp'), ('quar', 'compr', 'quar'), ('ipd', 'compr', 'ipd')]
    P, excl = C.episodes(spec, reps)
    out['n_tasks'] = len(P); out['n_episode_sets'] = sum(len(v) for v in P.values()); out['excluded'] = excl
    Y = {lab: C.tmeans(P, lab, 'Y1') for lab, _, _ in spec}
    q1 = C.contrast(Y['quar'], Y['base'], 20261131)
    q2 = C.contrast(Y['ipd'], Y['base'], 20261132)
    adj = C.holm([q1['diff_A_minus_B']['p_boot'], q2['diff_A_minus_B']['p_boot']])
    tests = {}
    for nm, q, pa, msg in (('Q1_quarantine_alone', q1, adj[0], 'QUARANTINE ALONE REDUCES MALFORMED CALLS END TO END'),
                           ('Q2_ipd_alone', q2, adj[1], 'IPD ALONE REDUCES MALFORMED CALLS END TO END')):
        d = q['diff_A_minus_B']; ok = bool(pa < 0.05 and d['mean_diff'] < 0)
        tests[nm] = {**q, 'p_holm': pa, 'verdict': msg if ok else 'NOT SHOWN'}
    if len(reps) >= 2:
        out['primary'] = tests
    sec = {'fullp_vs_quar': C.contrast(Y['fullp'], Y['quar'], 20261133),
           'fullp_vs_ipd': C.contrast(Y['fullp'], Y['ipd'], 20261134),
           'quar_vs_ipd': C.contrast(Y['quar'], Y['ipd'], 20261135)}
    for lab, _, _ in spec:
        sec.setdefault('counts', {})[lab] = C.counts(P, lab)
    sb = [(r['base']['stuck'], r['quar']['stuck']) for v in P.values() for r in v.values()]
    sec['stuck_quar_vs_base_mcnemar_p'] = C.F.mcnemar(sum(1 for x, y in sb if x and not y), sum(1 for x, y in sb if y and not x))
    sb = [(r['base']['stuck'], r['ipd']['stuck']) for v in P.values() for r in v.values()]
    sec['stuck_ipd_vs_base_mcnemar_p'] = C.F.mcnemar(sum(1 for x, y in sb if x and not y), sum(1 for x, y in sb if y and not x))
    R = {lab: C.tmeans(P, lab, 'resolved') for lab, _, _ in spec}
    for k, seed in (('quar', 20261136), ('ipd', 20261137)):
        r = C.F.boot_paired([R[k][t] - R['base'][t] for t in P], seed=seed)
        r['non_inferior_at_-3pp_descriptive'] = bool(r.get('ci95') and r['ci95'][0] > -0.03)
        sec[f'resolve_{k}_minus_base'] = r
    sec['Y2'] = {k: C.contrast(C.tmeans(P, k, 'Y2'), C.tmeans(P, 'base', 'Y2'), s) for k, s in (('quar', 20261138), ('ipd', 20261139))}
    out['secondary'] = sec
    json.dump(out, open(a.out if Path(a.out).is_absolute() else HERE.parent / a.out, 'w'), indent=1)
    print(json.dumps({'analysis_set': reps, 'primary': {k: v.get('verdict') for k, v in tests.items()},
                      'means': {k: round(sum(v.values()) / len(v), 4) for k, v in Y.items()}}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
