"""EXPLORATORY (not registered; written 2026-11-07 after PREREG_E and PREREG_E_ext were analysed).
Why is the fresh replication's malformed-call cut (0.21x, r3-r10) weaker than PREREG_E's (0.11x, r1-r2)?
Per-replicate Y1 means and ratios, the pooled 10-replicate ratio, Y1 without episode pairs whose base episode got
stuck (the heavy tail), and the share of base Y1 carried by stuck episodes. Uses PREREG_E's frozen functions via
prereg_cov_common.py; fixed seeds.
usage: EXPLORATORY_ext_replicates.py --out analysis/EXPLORATORY_ext_replicates.json"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prereg_cov_common as C  # noqa: E402


def summ(P):
    xb, xf = C.tmeans(P, 'base', 'Y1'), C.tmeans(P, 'fullp', 'Y1')
    r = C.contrast(xf, xb, 20261141)
    eps = [(e['base'], e['fullp']) for v in P.values() for e in v.values()]
    yb_all = sum(b['Y1'] for b, _ in eps)
    yb_stuck = sum(b['Y1'] for b, _ in eps if b['stuck'])
    keep = {t: {k: e for k, e in v.items() if not e['base']['stuck']} for t, v in P.items()}
    keep = {t: v for t, v in keep.items() if v}
    rk = C.contrast(C.tmeans(keep, 'fullp', 'Y1'), C.tmeans(keep, 'base', 'Y1'), 20261142)
    return {'n_pairs': len(eps), 'base_mean': r['B_mean'], 'fullp_mean': r['A_mean'], 'ratio': r['ratio_A_over_B'],
            'diff': r['diff_A_minus_B'], 'base_stuck_pairs': sum(b['stuck'] for b, _ in eps),
            'share_of_base_Y1_in_stuck_episodes': round(yb_stuck / yb_all, 4) if yb_all else None,
            'excluding_base_stuck_pairs': {'n_pairs': sum(len(v) for v in keep.values()), 'base_mean': rk['B_mean'],
                                           'fullp_mean': rk['A_mean'], 'ratio': rk['ratio_A_over_B']}}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); a = ap.parse_args()
    spec = [('base', 'pop31r', 'base'), ('fullp', 'pop31r', 'fullp')]
    out = {'label': 'EXPLORATORY (post hoc; not registered)', 'per_replicate': {}}
    for k in range(1, 11):
        P, _ = C.episodes(spec, [k])
        out['per_replicate'][k] = summ(P)
    for name, reps in (('r1_r2', [1, 2]), ('r3_r10', list(range(3, 11))), ('r1_r10', list(range(1, 11)))):
        P, _ = C.episodes(spec, reps)
        out[name] = summ(P)
    json.dump(out, open(a.out if Path(a.out).is_absolute() else HERE.parent / a.out, 'w'), indent=1)
    for k, v in out['per_replicate'].items():
        print(k, v['base_mean'], v['fullp_mean'], v['ratio']['ratio'], 'stuck', v['base_stuck_pairs'],
              'stuck share', v['share_of_base_Y1_in_stuck_episodes'], 'excl', v['excluding_base_stuck_pairs']['base_mean'],
              v['excluding_base_stuck_pairs']['fullp_mean'])
    for n in ('r1_r2', 'r3_r10', 'r1_r10'):
        v = out[n]; print(n, v['base_mean'], v['fullp_mean'], v['ratio'], 'excl-stuck', v['excluding_base_stuck_pairs'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
