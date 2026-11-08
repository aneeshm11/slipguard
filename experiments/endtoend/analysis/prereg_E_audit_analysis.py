"""PREREG_E_audit analysis (frozen with experiments/endtoend/PREREG_E_audit.md before any E_audit episode). Run ONCE.
Does slipguard's weight audit predict malformed calls end to end? Uses prereg_cov_common.py (frozen with this file).
usage: prereg_E_audit_analysis.py --out analysis/prereg_E_audit.json [--status_only]"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prereg_cov_common as C  # noqa: E402

P = HERE.parent.parent.parent
W = P / 'experiments/quant_margins/wsa/out'
NEW = {'bf16': 'popBF16r', 'nvnvfp4': 'popNVr', 'qatawq': 'popQAWQr', 'qatnvfp4': 'popQNVr'}
FIRST, LAST = 3, 8


def deficit(name):
    if name == 'bf16':
        return 0.0   # the audit's reference model, by definition
    if name in ('qat', 'awq'):
        key = {'qat': '31b_qatct', 'awq': '31b_awq_cyankiwi'}[name]
        v = json.load(open(W / 'sweep_report.json'))['checkpoints'][key]['paired_vs_ref']['median_deficit']
    else:
        f = {'nvnvfp4': 'audit_v210_31b_nvfp4_nvidia.json', 'qatawq': 'audit_v210_31b_qatawq_cyankiwi.json',
             'qatnvfp4': 'audit_v210_31b_qatnvfp4_melcheikh.json'}[name]
        v = json.load(open(W / f))['paired_vs_reference']['median_deficit']
    while isinstance(v, (list, dict)):   # point estimate: first element of [point, lo, hi] or the 'point' field
        v = v[0] if isinstance(v, list) else v.get('point', v.get('estimate'))
    return round(float(v), 4)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--status_only', action='store_true')
    a = ap.parse_args()
    sets = {c: C.prefix_set(p, ('base', 'fullp'), FIRST, LAST) for c, p in NEW.items()}
    _, awq_reps = C.prefix_set('popAWQr', ('base', 'fullp'), 1, 8)
    out = {'prereg': 'PREREG_E_audit.md (sha256 in PROGRESS.md at freeze)', 'B': C.F.B,
           'replicate_complete': {c: s[0] for c, s in sets.items()}, 'analysis_sets': {c: s[1] for c, s in sets.items()},
           'awq_comparator_replicates': awq_reps}
    if a.status_only:
        print(json.dumps(out)); return 0
    ck, tests = {}, {}
    # each new checkpoint, salt-paired with QAT (pop31r<k>) on the same replicates
    for c, pre in NEW.items():
        reps = sets[c][1]
        if not reps:
            ck[c] = {'analysis_set': [], 'note': 'no complete replicate'}; continue
        Pq, excl = C.episodes([('c_base', pre, 'base'), ('c_fullp', pre, 'fullp'), ('q_base', 'pop31r', 'base')], reps)
        r = {'analysis_set': reps, 'n_tasks': len(Pq), 'n_episode_sets': sum(len(v) for v in Pq.values()), 'excluded': excl,
             'deficit_nats': deficit(c)}
        for lab in ('c_base', 'c_fullp', 'q_base'):
            r[lab] = C.counts(Pq, lab)
        r['base_vs_qat_base'] = C.contrast(C.tmeans(Pq, 'c_base', 'Y1'), C.tmeans(Pq, 'q_base', 'Y1'), 20261121)
        r['fullp_vs_base'] = C.contrast(C.tmeans(Pq, 'c_fullp', 'Y1'), C.tmeans(Pq, 'c_base', 'Y1'), 20261122)
        r['resolve_base_vs_qat_base'] = C.F.boot_paired(
            [C.tmeans(Pq, 'c_base', 'resolved')[t] - C.tmeans(Pq, 'q_base', 'resolved')[t] for t in Pq], seed=20261123)
        ck[c] = r
    # AWQ comparator (task-paired across runs; salts differ) for the flagged checkpoints
    Pa = None
    if awq_reps:
        Pa, _ = C.episodes([('a_base', 'popAWQr', 'base')], awq_reps)
        XA = C.tmeans(Pa, 'a_base', 'Y1')
        for c in ('qatawq', 'qatnvfp4'):
            if sets[c][1]:
                Pc, _ = C.episodes([('c_base', NEW[c], 'base')], sets[c][1])
                ck[c]['base_vs_awq_base'] = C.contrast(C.tmeans(Pc, 'c_base', 'Y1'), XA, 20261124)
    # primary family (Holm over the tests that could run); direction must match the prediction
    spec = [('T1_bf16_below_qat', 'bf16', 'base_vs_qat_base', -1), ('T2_nvnvfp4_below_qat', 'nvnvfp4', 'base_vs_qat_base', -1),
            ('T3_qatawq_above_awq', 'qatawq', 'base_vs_awq_base', +1), ('T4_qatnvfp4_above_awq', 'qatnvfp4', 'base_vs_awq_base', +1)]
    ran = [(nm, c, k, s) for nm, c, k, s in spec if k in ck.get(c, {}) and ck[c][k].get('diff_A_minus_B', {}).get('n')]
    adj = C.holm([ck[c][k]['diff_A_minus_B']['p_boot'] for _, c, k, _ in ran]) if ran else []
    for (nm, c, k, s), pa in zip(ran, adj):
        d = ck[c][k]['diff_A_minus_B']
        tests[nm] = {'diff': d['mean_diff'], 'ci95': d['ci95'], 'p_boot': d['p_boot'], 'p_holm': pa,
                     'pass': bool(pa < 0.05 and d['mean_diff'] * s > 0)}
    for nm, c, k, s in spec:
        tests.setdefault(nm, {'pass': None, 'note': 'not run (no complete replicate)'})
    npass = sum(1 for v in tests.values() if v['pass']); nrun = sum(1 for v in tests.values() if v['pass'] is not None)
    if nrun < 4:
        verdict = f'INCOMPLETE ({nrun} of 4 tests could run; {npass} passed)'
    elif npass == 4:
        verdict = 'AUDIT PREDICTS END-TO-END MALFORMED CALLS'
    elif npass == 0:
        verdict = 'NOT SHOWN'
    else:
        verdict = f'PARTLY ({npass} of 4 tests passed)'
    out['primary'] = {'tests': tests, 'verdict': verdict}
    out['checkpoints'] = ck
    # descriptive: rank correlation of audit deficit with base Y1 over every checkpoint with end-to-end data
    rows = []
    for c in NEW:
        if sets[c][1]:
            Pc, _ = C.episodes([('x', NEW[c], 'base')], sets[c][1]); m = C.tmeans(Pc, 'x', 'Y1')
            rows.append([c, deficit(c), round(sum(m.values()) / len(m), 4)])
    Pq10, _ = C.episodes([('x', 'pop31r', 'base')], list(range(1, 11))); m = C.tmeans(Pq10, 'x', 'Y1')
    rows.append(['qat', deficit('qat'), round(sum(m.values()) / len(m), 4)])
    if Pa is not None:
        m = C.tmeans(Pa, 'a_base', 'Y1'); rows.append(['awq', deficit('awq'), round(sum(m.values()) / len(m), 4)])
    out['descriptive_rank'] = {'rows_checkpoint_deficit_baseY1': rows,
                               'spearman': C.spearman([r[1] for r in rows], [r[2] for r in rows]) if len(rows) >= 3 else None}
    json.dump(out, open(a.out if Path(a.out).is_absolute() else HERE.parent / a.out, 'w'), indent=1)
    print(json.dumps({'analysis_sets': out['analysis_sets'], 'primary': out['primary'], 'rank': out['descriptive_rank']}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
