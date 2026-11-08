"""12B replication of the r-dose and lag-2 analyses (same estimators as prereg_analysis.py; 12B is not governed by
PREREG_v1's numeric predictions, the rules are applied for comparison). Attempt-cluster bootstrap B.
usage: rep_12b.py out.json [B]"""
import os  # added by the repo export (paths are env/config driven)
import json, sys, math, random, collections
import numpy as np
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
B = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
random.seed(0)
META = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
logit = lambda p: math.log(p / (1 - p))


def load(fs):
    R = {}
    for f in fs:
        for l in open(f):
            d = json.loads(l)
            if not d.get('error'): R[(d['id'], d['pathway'], d['k'])] = d
    return R


def y(d, kind):
    j = d.get('judge') or {}; e = j.get('name') == 'edit_file'; m = e and bool(j.get('malformed'))
    return (int(m), int(e)) if kind == 'cond' else (int(m), 1)


rate = lambda rows: sum(r[0] for r in rows) / max(1, sum(r[1] for r in rows))


def boot(groups, st):
    keys = list(groups); out = []
    for _ in range(B):
        rr = [r for _ in keys for r in groups[keys[random.randrange(len(keys))]]]
        try: out.append(st(rr))
        except (ValueError, ZeroDivisionError): pass
    return np.array([o for o in out if np.all(np.isfinite(o))])


M = f'{D}/out/main'
R = load([f'{M}/r12b_old_t1.jsonl', f'{M}/r12b_old_A1.jsonl', f'{M}/r12b_rdose.jsonl'])
gate = [x.strip() for x in open(f'{D}/data/ids_gate300.txt') if x.strip()]
l2ids = [x.strip() for x in open(f'{D}/data/ids_lag2.txt') if x.strip()]
res = {}
for kind in ('cond', 'uncond'):
    use = [i for i in gate if all((i, a, 1) in R for a in ('P1', 'R2', 'R4'))]
    g = collections.defaultdict(list)
    for i in use: g[META[i]['task']].append({a: y(R[(i, a, 1)], kind) for a in ('P1', 'R2', 'R4')})
    st = lambda rr: np.array([logit(rate([r['R2'] for r in rr])) - logit(rate([r['P1'] for r in rr])), logit(rate([r['R4'] for r in rr])) - logit(rate([r['P1'] for r in rr])),
                              rate([r['P1'] for r in rr]), rate([r['R2'] for r in rr]), rate([r['R4'] for r in rr])])
    rows = [r for v in g.values() for r in v]; e = st(rows); bs = boot(g, st)
    ci = lambda j: [round(float(np.percentile(bs[:, j], 2.5)), 4), round(float(np.percentile(bs[:, j], 97.5)), 4)]
    res[f'r_dose_{kind}'] = {'n_contexts': len(use), 'Delta_r2': [round(float(e[0]), 4), ci(0)], 'Delta_r4': [round(float(e[1]), 4), ci(1)],
                             'P(r=1)': round(float(e[2]), 4), 'P(r=2)': round(float(e[3]), 4), 'P(r=4)': round(float(e[4]), 4)}
    use = [i for i in l2ids if all(x in R for x in ((i, 'P0', 0), (i, 'P1', 1), (i, 'L2', 1)))]
    g = collections.defaultdict(list)
    for i in use: g[META[i]['task']].append({a: y(R[(i, a, kk)], kind) for a, kk in (('P0', 0), ('P1', 1), ('L2', 1))})
    st = lambda rr: np.array([(rate([r['L2'] for r in rr]) - rate([r['P0'] for r in rr])) / (rate([r['P1'] for r in rr]) - rate([r['P0'] for r in rr])),
                              rate([r['P0'] for r in rr]), rate([r['P1'] for r in rr]), rate([r['L2'] for r in rr])])
    rows = [r for v in g.values() for r in v]; e = st(rows); bs = boot(g, st)
    res[f'lag2_{kind}'] = {'n_contexts': len(use), 'excess_share': [round(float(e[0]), 4), [round(float(np.percentile(bs[:, 0], 2.5)), 4), round(float(np.percentile(bs[:, 0], 97.5)), 4)]],
                           'p0': round(float(e[1]), 4), 'p1': round(float(e[2]), 4), 'p_lag2': round(float(e[3]), 4)}
json.dump(res, open(sys.argv[1], 'w'), indent=1); print(json.dumps(res, indent=1))
