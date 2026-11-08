"""EXPLORATORY (not registered; written 2026-11-07 after PREREG_E and PREREG_E_ext were analysed).
Which episodes still get stuck under the full proxy (fullp), and why? For every stuck fullp episode in pop31 r1..r10:
its Y1, the paired base episode's Y1, and, from the proxy log, how many delivered malformed calls IPD found no slip
site for ('no_site': the malformation is not a mistyped delimiter, so there is nothing to repair), the judge's reasons,
and whether quarantine was active. Also: the share of all fullp Y1 carried by these episodes.
usage: EXPLORATORY_fullp_loops.py --out analysis/EXPLORATORY_fullp_loops.json"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(HERE))
import prereg_cov_common as C  # noqa: E402


def proxy_detail(task, k):
    h = 0 if task in C.HALF[0] else 1
    f = E / f'logs/proxy_pop31r{k}s{h}/proxy_fullp.jsonl'
    recs = sorted([r for r in (json.loads(l) for l in open(f) if task in l) if r.get('task', '').endswith(':' + task)],
                  key=lambda r: r['t'])
    bad = [r for r in recs if any(not c.get('ok_delivered', True) for c in (r.get('calls') or []))]
    why = collections.Counter(w for r in bad for c in r['calls'] if not c.get('ok_delivered', True) for w in (c.get('why') or []))
    return {'requests': len(recs), 'turns_with_malformed_delivered': len(bad),
            'ipd_invalid': sum((r.get('ipd') or {}).get('invalid', 0) for r in bad),
            'ipd_no_site': sum((r.get('ipd') or {}).get('no_site', 0) for r in bad),
            'why': why.most_common(), 'quarantine_active_turns': sum(1 for r in recs if (r.get('quarantine') or {}) not in ({}, None, 0))}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); a = ap.parse_args()
    P, _ = C.episodes([('base', 'pop31r', 'base'), ('fullp', 'pop31r', 'fullp')], list(range(1, 11)))
    total = sum(e['fullp']['Y1'] for v in P.values() for e in v.values())
    stuck = [(t, k, e) for t, v in P.items() for k, e in v.items() if e['fullp']['stuck']]
    rows = [{'task': t, 'replicate': k, 'fullp_Y1': e['fullp']['Y1'], 'fullp_calls': e['fullp']['calls'],
             'base_Y1': e['base']['Y1'], 'base_stuck': e['base']['stuck'], 'resolved_fullp': e['fullp']['resolved'],
             **proxy_detail(t, k)} for t, k, e in sorted(stuck, key=lambda x: (x[1], x[0]))]
    out = {'label': 'EXPLORATORY (post hoc; not registered)', 'n_fullp_episodes': sum(len(v) for v in P.values()),
           'fullp_Y1_total': total, 'stuck_fullp_episodes': rows,
           'share_of_fullp_Y1_in_stuck_episodes': round(sum(r['fullp_Y1'] for r in rows) / total, 4) if total else None}
    json.dump(out, open(a.out if Path(a.out).is_absolute() else E / a.out, 'w'), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != 'stuck_fullp_episodes'}))
    for r in rows:
        print(r['task'], r['replicate'], 'fullpY1', r['fullp_Y1'], 'baseY1', r['base_Y1'], 'no_site', r['ipd_no_site'], 'of', r['ipd_invalid'], r['why'][:2])
    return 0


if __name__ == '__main__':
    sys.exit(main())
