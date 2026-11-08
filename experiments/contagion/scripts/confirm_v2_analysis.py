"""PREREG_v2 §3.1 confirmatory analysis of A's arms on workstream P's corpus (C1-C11 + §3.4 global statements).
Written and hashed BEFORE any P outcome existed. Primary estimand: unconditional P(next call is a malformed edit);
conditional beside it. Contrasts paired by context; episode-cluster percentile bootstrap (B = 2000). Halves H1/H2
(pool ranks 1-150 / 151-300) reported beside the full sample. Holm within F1c = {C1, C2, C5, C4} using one-sided
bootstrap p-values (C1, C2: H0 RD <= 0; C4, C5: H0 removal <= 0.5 — our operationalisation, stated here before data).
Arm-sets are analysed only when >= 95% of their planned jobs are present (no interim looks).
usage: confirm_v2_analysis.py --pools <dir> --meta <P meta.jsonl> --res31 <files> [--res12 <files>] [--rese4 <files>] --out <json>
"""
import json, sys, math, random, argparse, collections
import numpy as np
ap = argparse.ArgumentParser()
ap.add_argument('--pools', required=True); ap.add_argument('--meta', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--res31', nargs='+', default=[]); ap.add_argument('--res12', nargs='+', default=[]); ap.add_argument('--rese4', nargs='+', default=[])
ap.add_argument('--B', type=int, default=2000)
a = ap.parse_args()
random.seed(20261105); np.random.seed(20261105)
logit = lambda p: math.log(p / (1 - p))
META = {json.loads(l)['id']: json.loads(l) for l in open(a.meta)}


def pool(name):
    try: return [json.loads(l) for l in open(f'{a.pools}/S1_{name}.jsonl')]
    except FileNotFoundError: return []


def load(files):
    R = {}
    for f in files:
        for l in open(f):
            d = json.loads(l)
            if not d.get('error'): R[(d['id'], d['pathway'], d['k'])] = d
    return R


def y(d, kind):
    j = d.get('judge') or {}; e = bool(j.get('is_edit', j.get('name') == 'edit_file')); m = e and bool(j.get('malformed'))
    return (int(m), int(e)) if kind == 'cond' else (int(m), 1)


def rate(rows, idx):
    n = sum(r[idx][1] for r in rows); return sum(r[idx][0] for r in rows) / n if n else float('nan')


def boot(groups, stat):
    keys = list(groups); out = []
    for _ in range(a.B):
        rr = [r for _ in keys for r in groups[keys[random.randrange(len(keys))]]]
        try: out.append(stat(rr))
        except (ValueError, ZeroDivisionError): pass
    return np.array([o for o in out if np.all(np.isfinite(o))])


def complete(R, ids, arms, frac=0.95):
    need = [(i, p, k) for i in ids for (p, k) in arms]; have = sum(1 for x in need if x in R)
    return have >= frac * len(need), have, len(need)


def paired(R, ids, arm, base=('P0', 0), kind='uncond'):
    use = [i for i in ids if (i,) + arm in R and (i,) + base in R]
    g = collections.defaultdict(list)
    for i in use: g[META[i]['task']].append((y(R[(i,) + arm], kind), y(R[(i,) + base], kind)))
    rows = [r for v in g.values() for r in v]
    st = lambda rr: np.array([rate(rr, 0) - rate(rr, 1), rate(rr, 0), rate(rr, 1)])
    e = st(rows); bs = boot(g, st)
    return {'n_contexts': len(use), 'n_episodes': len(g), 'arm': round(float(e[1]), 4), 'base': round(float(e[2]), 4), 'RD': round(float(e[0]), 4),
            'RD_CI': [round(float(np.percentile(bs[:, 0], 2.5)), 4), round(float(np.percentile(bs[:, 0], 97.5)), 4)],
            'p_one_sided_RD_le_0': round(float(np.mean(bs[:, 0] <= 0)), 5)}


def removal(R, ids, Q, kind='uncond'):
    use = [i for i in ids if all(x in R for x in ((i, 'P1', 1), (i, Q, 1), (i, 'P0', 0)))]
    g = collections.defaultdict(list)
    for i in use: g[META[i]['task']].append((y(R[(i, 'P1', 1)], kind), y(R[(i, Q, 1)], kind), y(R[(i, 'P0', 0)], kind)))
    rows = [r for v in g.values() for r in v]
    st = lambda rr: np.array([(rate(rr, 0) - rate(rr, 1)) / (rate(rr, 0) - rate(rr, 2))])
    e = st(rows); bs = boot(g, st)
    ci = [round(float(np.percentile(bs[:, 0], 2.5)), 3), round(float(np.percentile(bs[:, 0], 97.5)), 3)] if len(bs) else [None, None]
    return {'n_contexts': len(use), 'removal': round(float(e[0]), 3), 'CI': ci, 'p_one_sided_removal_le_0.5': round(float(np.mean(bs[:, 0] <= 0.5)), 5) if len(bs) else None}


def rd_rule(x, theta_D):
    lo = x['RD_CI'][0]
    return 'FAILS' if lo <= 0 else ('REPLICATES' if x['RD'] >= 0.5 * theta_D else 'ATTENUATED')


def rm_rule(x):
    if x['removal'] >= 0.70 and x['CI'][0] is not None and x['CI'][0] >= 0.50: v = 'REPLICATES'
    elif x['removal'] >= 0.40 and x['CI'][0] is not None and x['CI'][0] > 0: v = 'ATTENUATED'
    else: v = 'FAILS'
    if v == 'FAILS' and x['CI'][0] is not None and (x['CI'][1] - x['CI'][0]) > 1: v = 'FAILS (underpowered: CI width > 1)'
    return v


def dose(R, ids, ks, kind):
    use = [i for i in ids if all((i, 'P6', k) in R for k in ks)]
    g = collections.defaultdict(list)
    for i in use: g[META[i]['task']].append(tuple(y(R[(i, 'P6', k)], kind) for k in ks))
    rows = [r for v in g.values() for r in v]
    st = lambda rr: np.array([logit(rate(rr, j)) - logit(rate(rr, 0)) for j in range(1, len(ks))] + [rate(rr, j) for j in range(len(ks))])
    e = st(rows); bs = boot(g, st)
    out = {'n_contexts': len(use), 'kind': kind, 'rates': {f'k={k}': round(float(e[len(ks) - 1 + j]), 4) for j, k in enumerate(ks)}}
    for j, k in enumerate(ks[1:]): out[f'Delta_{k}'] = [round(float(e[j]), 4), [round(float(np.percentile(bs[:, j], 2.5)), 4), round(float(np.percentile(bs[:, j], 97.5)), 4)]]
    if 2 in ks and 4 in ks:
        sh = bs[:, ks.index(4) - 1] - 2 * bs[:, ks.index(2) - 1]
        out['Delta4_minus_2Delta2'] = [round(float(e[ks.index(4) - 1] - 2 * e[ks.index(2) - 1]), 4), [round(float(np.percentile(sh, 2.5)), 4), round(float(np.percentile(sh, 97.5)), 4)]]
    return out


def c3_rule(d):
    d2, d4 = d.get('Delta_2'), d.get('Delta_4')
    if not d4: return 'NOT EVALUABLE'
    if d4[1][0] <= 0: return 'FAILS'
    if d2 and d2[1][0] > 0 and d2[0] >= 0.92 and d4[0] > d2[0]: return 'REPLICATES'
    return 'ATTENUATED'


A1 = pool('A1'); A2 = pool('A2'); A1k2 = pool('A1k2')
ids = [r['context_id'] for r in A1]; H = {'H1': [r['context_id'] for r in A1 if r['half'] == 'H1'], 'H2': [r['context_id'] for r in A1 if r['half'] == 'H2']}
res = {'prereg': 'PREREG_v2', 'pools': {'A1': len(A1), 'A2': len(A2), 'A1k2': len(A1k2)}, 'B': a.B}
R31 = load(a.res31)
arms31 = [('P0', 0), ('P1', 1), ('P5', 1), ('P6', 1), ('P8a', 1), ('P8b', 1), ('P9', 1)]
ok, have, tot = complete(R31, ids, arms31)
if ok:
    C = {}
    for scope, sids in (('full', ids), ('H1', H['H1']), ('H2', H['H2'])):
        s = {}
        s['C1'] = {k: paired(R31, sids, ('P1', 1), kind=k) for k in ('uncond', 'cond')}; s['C1']['verdict'] = rd_rule(s['C1']['uncond'], 0.333)
        s['C2'] = {k: paired(R31, sids, ('P6', 1), kind=k) for k in ('uncond', 'cond')}; s['C2']['verdict'] = rd_rule(s['C2']['uncond'], 0.213)
        s['C2']['plan_induction_threshold(>=+5pp, CI_lo>0)'] = bool(s['C2']['uncond']['RD'] >= 0.05 and s['C2']['uncond']['RD_CI'][0] > 0)
        for c, Q in (('C4', 'P5'), ('C5', 'P8a'), ('C6', 'P8b')):
            s[c] = {k: removal(R31, sids, Q, k) for k in ('uncond', 'cond')}; s[c]['verdict'] = rm_rule(s[c]['uncond'])
        p9 = paired(R31, sids, ('P9', 1)); p1 = s['C1']['uncond']
        ret = (p9['RD'] / p1['RD']) if p1['RD'] else float('nan')
        s['C7'] = {'RD_P9_P0': p9, 'retention_point': round(ret, 3),
                   'verdict': 'FAILS' if p9['RD_CI'][0] <= 0 else ('REPLICATES' if ret >= 0.50 else 'ATTENUATED'),
                   'note': 'retention = RD(P9-P0)/RD(P1-P0); the CI_lo >= 0.25 part is checked from removal(P9) = 1 - retention'}
        rm9 = removal(R31, sids, 'P9'); s['C7']['retention_CI_from_removal'] = [round(1 - rm9['CI'][1], 3), round(1 - rm9['CI'][0], 3)] if rm9['CI'][0] is not None else None
        if s['C7']['verdict'] == 'REPLICATES' and s['C7']['retention_CI_from_removal'] and s['C7']['retention_CI_from_removal'][0] < 0.25: s['C7']['verdict'] = 'ATTENUATED (retention CI_lo < 0.25)'
        C[scope] = s
    # Holm within F1c on the full sample
    ps = {'C1': C['full']['C1']['uncond']['p_one_sided_RD_le_0'], 'C2': C['full']['C2']['uncond']['p_one_sided_RD_le_0'],
          'C5': C['full']['C5']['uncond']['p_one_sided_removal_le_0.5'], 'C4': C['full']['C4']['uncond']['p_one_sided_removal_le_0.5']}
    order = sorted(ps, key=lambda c: (ps[c] if ps[c] is not None else 1)); holm = {}; running = 0
    for r, c in enumerate(order):
        adj = min(1.0, (len(order) - r) * (ps[c] if ps[c] is not None else 1)); running = max(running, adj); holm[c] = round(running, 5)
    res['31B'] = {'jobs_present': f'{have}/{tot}', **C, 'holm_F1c_adjusted_p': holm}
    # C3 (P6k): pool A2 at k = 1, 2, 4, or the shortfall design
    if len(A2) >= 150:
        res['31B']['C3'] = {k: dose(R31, [r['context_id'] for r in A2], [1, 2, 4], k) for k in ('uncond', 'cond')}
    else:
        res['31B']['C3'] = {'shortfall': True, 'k12_on_A1k2': {k: dose(R31, [r['context_id'] for r in A1k2], [1, 2], k) for k in ('uncond', 'cond')},
                            'k124_on_A2_underpowered': {k: dose(R31, [r['context_id'] for r in A2], [1, 2, 4], k) for k in ('uncond', 'cond')}}
    c3 = res['31B']['C3']['uncond'] if 'uncond' in res['31B']['C3'] else None
    res['31B']['C3_verdict'] = c3_rule(c3) if c3 else 'see shortfall design'
    g = res['31B']['full']
    v = [g['C1']['verdict'], g['C2']['verdict'], g['C5']['verdict']]
    res['global'] = {'laundering_loop': ('replicates on a public corpus' if all(x == 'REPLICATES' for x in v) else
                                         'replicates with attenuation' if all(x in ('REPLICATES', 'ATTENUATED') for x in v) else 'partially replicates'),
                     'claims': dict(zip(['C1', 'C2', 'C5'], v))}
else:
    res['31B'] = f'incomplete ({have}/{tot}) - not analysed'
for tag, files, c_id, theta in (('12B', a.res12, 'C8', 0.050), ('E4B', a.rese4, 'C9', 0.032)):
    if not files: continue
    Rm = load(files); armsm = [('P0', 0), ('P1', 1), ('P5', 1), ('P6', 1), ('P8a', 1)]
    ok, have, tot = complete(Rm, ids, armsm)
    if not ok: res[tag] = f'incomplete ({have}/{tot}) - not analysed'; continue
    x = {k: paired(Rm, ids, ('P1', 1), kind=k) for k in ('uncond', 'cond')}
    p6 = paired(Rm, ids, ('P6', 1)); d61 = paired(Rm, ids, ('P6', 1), base=('P1', 1))
    res[tag] = {c_id: {**x, 'verdict': rd_rule(x['uncond'], theta)},
                'C10': {'RD_P6_P1': d61, 'RD_P6_P0': p6, 'verdict': 'REPLICATES' if (d61['RD'] >= 0 and p6['RD_CI'][0] > 0) else 'FAILS'},
                'C11': {Q: (lambda r_: {**r_, 'verdict': rm_rule(r_)})(removal(Rm, ids, Q)) for Q in ('P5', 'P8a')}}
json.dump(res, open(a.out, 'w'), indent=1)
print(json.dumps({k: (v if isinstance(v, str) else 'computed') for k, v in res.items()}, indent=None))
