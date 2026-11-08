"""PREREG_E_awq analysis (frozen with PREREG_E_awq.md before any E_awq episode). Run ONCE.
Imports PREREG_E's frozen prereg_analysis.py unchanged; explicit integer seeds.
usage: prereg_E_awq_analysis.py --qat_reps 1 2 3 ... --out analysis/prereg_E_awq.json"""
import argparse, importlib.util, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; E = HERE.parent
spec = importlib.util.spec_from_file_location('prereg_frozen', HERE / 'prereg_analysis.py'); F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
TASKS = [t for t in open(E / 'configs/eligible_113.txt').read().split() if t]


def arm(tags, arm_, logs):
    by = F.load_proxy([str(E / f'logs/proxy_{l}') for l in logs])
    return F.load_arm('+'.join(str(E / f'runs/{t}_H_{arm_}') for t in tags), by)


def tmeans(A, key, tasks):
    return {t: F.task_mean([e for e in A.get(t, []) if not e['infra_error']], key) for t in tasks}


def contrast(XA, XB, seed):
    ts = [t for t in TASKS if XA.get(t) is not None and XB.get(t) is not None]
    a = [XA[t] for t in ts]; b = [XB[t] for t in ts]
    return {'n_tasks': len(ts), 'A_mean': round(sum(a) / len(a), 4), 'B_mean': round(sum(b) / len(b), 4),
            'ratio_A_over_B': F.boot_ratio(b, a, seed=1), 'diff_A_minus_B': F.boot_paired([x - y for x, y in zip(a, b)], seed=seed)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--qat_reps', type=int, nargs='+', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    qtags = [f'pop31r{k}s{h}' for k in a.qat_reps for h in (0, 1)]
    awq = ['popAWQr1s0', 'popAWQr1s1', 'popAWQr2s0', 'popAWQr2s1']
    AW = {c: arm(awq, c, awq) for c in ('base', 'fullp')}
    QT = {c: arm(qtags, c, qtags) for c in ('base', 'fullp')}
    out = {'prereg': 'PREREG_E_awq.md (sha256 in PROGRESS.md at freeze)', 'qat_replicates': a.qat_reps}
    Y = {k: tmeans(v, 'Y1', TASKS) for k, v in (('awq_base', AW['base']), ('awq_fullp', AW['fullp']), ('qat_base', QT['base']), ('qat_fullp', QT['fullp']))}
    p = contrast(Y['awq_base'], Y['qat_base'], 20261111)
    p['verdict'] = 'AUDIT PICK REDUCES MALFORMED CALLS END TO END' if p['diff_A_minus_B'].get('ci95') and p['diff_A_minus_B']['ci95'][1] < 0 else 'NOT SHOWN'
    out['primary_awq_base_vs_qat_base'] = p
    out['S_a_awq_fullp_vs_awq_base'] = contrast(Y['awq_fullp'], Y['awq_base'], 20261112)
    out['S_b_awq_fullp_vs_qat_fullp'] = contrast(Y['awq_fullp'], Y['qat_fullp'], 20261113)
    for nm, A in (('awq_base', AW['base']), ('awq_fullp', AW['fullp']), ('qat_base', QT['base']), ('qat_fullp', QT['fullp'])):
        eps = [e for v in A.values() for e in v if not e['infra_error']]
        out.setdefault('S_c_stuck', {})[nm] = [sum(e['stuck'] for e in eps), len(eps)]
        out.setdefault('S_d_resolved', {})[nm] = [sum(e['resolved'] for e in eps), len(eps)]
    json.dump(out, open(a.out if Path(a.out).is_absolute() else E / a.out, 'w'), indent=1)
    print(json.dumps({'primary': p, 'S_a': out['S_a_awq_fullp_vs_awq_base']['ratio_A_over_B'], 'stuck': out['S_c_stuck']}, indent=1))


if __name__ == '__main__':
    sys.exit(main())
