"""Analyses governed by PREREG_v1 (paper/protocol_theory/prereg/PREREG_v1.md, sha256 53e34f1f..., frozen 11:47:06 UTC).
Runs ONLY on complete arm-sets (no interim looks): an arm-set is analysed when its planned jobs are >= 95% present
(PREREG §5 "missing or failed jobs"); otherwise it is reported as 'incomplete' with no outcome numbers.

  dose  (rule D-M, §4.2): Delta_k = logit P1(k) - logit P1(1) on the 305 set, k = 2, 4; paired by context,
        attempt-cluster bootstrap (B = 2000), 95% percentile CIs; regions at the measured D1 = logit p1 - logit p0:
        M1 < 0.3639 <= M2 < (0.7278 + D1)/2 <= M3; shape: M1 CI(Delta4) contains 0, M2 CI(Delta4 - 2 Delta2) contains 0,
        M3 P1(4) >= 0.95. Computed on the prereg primary (conditional on the next call being an edit) and on the
        unconditional ITT outcome.
        Secondary: removal (P1(k)-P4(k))/(P1(k)-p0) per k; order imitation under P4(k) (old-first share);
        edit classes per k (copy of the most recent corrupted value / copy of an earlier one / clean rewrite /
        same-content variant / new content) and the new-content slip rate per k.
  rdose : Delta for the same corrupted call + error shown r = 2, 4 times vs P1(k=1), gate 300.
  lag2  : (P_lag2 - p0) / (p1 - p0) on the lag-2 set (paired), M1 < 0.25 vs M2/M3 >= 0.5.
  p6k   : P6 at k = 1, 2, 4 on the 305 set (Delta_k as above).
  p7    : share of P7 slips using the injected '"' (gate 300).
  a2    : h = 1 - q(P5)/q(L) (and with P8a / P4'-MAP when present), context-clustered bootstrap; retry vs new split.
usage: prereg_analysis.py [B]
"""
import json, os, sys, glob, math, random, collections
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import gemma_protocol as gp
import variants as V
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
B = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
random.seed(0); np.random.seed(0)
META = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
logit = lambda p: math.log(p / (1 - p))


def wilson(k, n, z=1.96):
    if n == 0: return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4), n]


def load(files):
    R = {}
    for f in files:
        if not os.path.exists(f): continue
        for l in open(f):
            d = json.loads(l)
            if d.get('error'): continue
            R[(d['id'], d['pathway'], d['k'])] = d
    return R


def complete(R, plan_jobs, frac=0.95):
    have = sum(1 for j in plan_jobs if (j['id'], j['pathway'], j['k']) in R)
    return have >= frac * len(plan_jobs), have, len(plan_jobs)


def y(d, kind):
    j = d.get('judge') or {}
    e = j.get('is_edit', j.get('name') == 'edit_file'); m = e and bool(j.get('malformed'))
    return (int(m), int(e)) if kind == 'cond' else (int(m), 1)


def rate(rows):  # rows of (num, den)
    n = sum(r[1] for r in rows); return sum(r[0] for r in rows) / n if n else float('nan')


def cluster_boot(groups, fn):
    keys = list(groups); vals = []
    for _ in range(B):
        samp = [groups[keys[random.randrange(len(keys))]] for _ in keys]
        try: vals.append(fn([r for g in samp for r in g]))
        except (ValueError, ZeroDivisionError): pass
    return np.array([v for v in vals if v is not None and np.all(np.isfinite(v))])


def dlogit_block(R, ids, arm, ks, kind, base_p0=True):
    """Delta_k = logit P_arm(k) - logit P_arm(1), plus p0, p1, D1, per-k rates; paired over contexts with all levels."""
    lv = [(arm, k) for k in ks]
    use = [i for i in ids if all((i, a, k) in R for a, k in lv) and (not base_p0 or (i, 'P0', 0) in R)]
    groups = collections.defaultdict(list)
    for i in use:
        row = {k: y(R[(i, arm, k)], kind) for k in ks}
        row['p0'] = y(R[(i, 'P0', 0)], kind) if base_p0 else (0, 0)
        groups[META[i]['task'] if i in META else i].append(row)
    rows = [r for g in groups.values() for r in g]

    def stat(rr):
        P = {k: rate([r[k] for r in rr]) for k in ks}; p0 = rate([r['p0'] for r in rr]) if base_p0 else float('nan')
        out = [logit(P[k]) - logit(P[ks[0]]) for k in ks[1:]]
        return np.array(out + [logit(P[ks[0]]) - logit(p0) if base_p0 else 0.0] + [P[k] for k in ks] + [p0])
    est = stat(rows); bs = cluster_boot(groups, stat)
    ci = lambda j: [round(float(np.percentile(bs[:, j], 2.5)), 4), round(float(np.percentile(bs[:, j], 97.5)), 4)] if len(bs) else None
    res = {'n_contexts': len(use), 'n_attempts': len(groups), 'kind': kind}
    for jj, k in enumerate(ks[1:]): res[f'Delta_{k}'] = {'est': round(float(est[jj]), 4), 'CI': ci(jj)}
    nk = len(ks) - 1
    res['D1_logit_p1_minus_logit_p0'] = {'est': round(float(est[nk]), 4), 'CI': ci(nk)}
    for jj, k in enumerate(ks): res[f'P({arm},k={k})'] = {'est': round(float(est[nk + 1 + jj]), 4), 'CI': ci(nk + 1 + jj)}
    res['p0'] = {'est': round(float(est[-1]), 4), 'CI': ci(len(est) - 1)}
    if len(ks) >= 3 and ks[1] == 2 and ks[2] == 4:  # shape for M2: Delta4 - 2 Delta2; free curve: logit-linear in k
        sh = bs[:, 1] - 2 * bs[:, 0] if len(bs) else np.array([])
        res['Delta_4_minus_2Delta_2'] = {'est': round(float(est[1] - 2 * est[0]), 4), 'CI': [round(float(np.percentile(sh, 2.5)), 4), round(float(np.percentile(sh, 97.5)), 4)] if len(sh) else None}
        sl = bs[:, 1] / 3 if len(bs) else np.array([]); lin = bs[:, 0] - bs[:, 1] / 3 if len(bs) else np.array([])
        res['free_curve_logit_linear_in_k'] = {
            'slope_per_extra_exemplar (Delta4/3)': {'est': round(float(est[1] / 3), 4), 'CI': [round(float(np.percentile(sl, 2.5)), 4), round(float(np.percentile(sl, 97.5)), 4)] if len(sl) else None},
            'linearity_check Delta2 - Delta4/3 (0 if logit-linear in k)': {'est': round(float(est[0] - est[1] / 3), 4), 'CI': [round(float(np.percentile(lin, 2.5)), 4), round(float(np.percentile(lin, 97.5)), 4)] if len(lin) else None},
            'first_exemplar_step D1': round(float(est[nk]), 4)}
    return res


def rule_dm(blk, arm='P1'):
    """PREREG §4.2 classification (primary for the P1 dose tier; applied to P6k as a supplementary, same-form check)."""
    d2, d4 = blk['Delta_2'], blk['Delta_4']; D1 = blk['D1_logit_p1_minus_logit_p0']['est']
    b12, b23 = 0.3639, (0.7278 + D1) / 2
    lo, hi = d2['CI']
    region = 'M1' if hi < b12 else ('M2' if lo >= b12 and hi < b23 else ('M3' if lo >= b23 else None))
    shape = {'M1': (d4['CI'][0] <= 0 <= d4['CI'][1]),
             'M2': (blk['Delta_4_minus_2Delta_2']['CI'][0] <= 0 <= blk['Delta_4_minus_2Delta_2']['CI'][1]),
             'M3': (blk[f'P({arm},k=4)']['est'] >= 0.95)}
    # PREREG §4.2 applied clause by clause (all applicable clauses are reported verbatim)
    clauses = []
    if region and shape[region]: clauses.append(f'{region} supported')
    if region is None:
        straddle = [m for m, (a, b) in {'M1': (-1e9, b12), 'M2': (b12, b23), 'M3': (b23, 1e9)}.items() if not (hi < a or lo >= b)]
        clauses.append('not discriminated between ' + ' and '.join(straddle) + ' (Delta2 CI straddles a boundary)')
    if hi < 0: clauses.append('none of M1-M3 (Delta2 CI_hi < 0)')
    if not any(shape.values()): clauses.append('none of M1-M3: the shapes contradict every mechanism -> fit the free curve')
    elif region and not shape[region]: clauses.append(f'Delta2 in the {region} region but its shape is contradicted')
    return {'regions': {'M1|M2': b12, 'M2|M3': round(b23, 4), 'measured_D1': D1}, 'Delta2_CI': d2['CI'], 'shape_checks': shape,
            'verdict': '; '.join(clauses)}


def edit_class_k(R, ids, arm, k):
    """copy of the most recent corrupted value / of an earlier one / clean rewrite / same-content variant / new content."""
    cnt = collections.Counter(); mal = collections.Counter()
    for i in ids:
        d = R.get((i, arm, k))
        if not d: continue
        j = d.get('judge') or {}
        if j.get('name') != 'edit_file': continue
        msgs, _ = V.load_context(META[i]); prior = META[i]['prior'][-k:]
        vals = []
        for p in reversed(prior):  # most recent first
            a = json.loads(msgs[p['ai']]['tool_calls'][0]['function']['arguments']); order = list(a.keys()); sk = V.slip_key_for(order)
            vals.append((sk, gp.parse_args(gp.raw_args(a, order, slip_key=sk, closer='`')).get(sk), a.get(sk)))
        m = gp.TOOL_CALL_RE.search('<|tool_call>' + (d.get('s2_text') or '') + '<tool_call|>')
        ga = gp.parse_args(m.group(2)) if m else {}
        cls = 'new_content'
        for idx, (sk, inj, orig) in enumerate(vals):
            g = ga.get(sk)
            if g is None: continue
            if g == inj: cls = 'copy_most_recent' if idx == 0 else 'copy_earlier'; break
            if g == orig: cls = 'clean_rewrite'; break
            if isinstance(orig, str) and g[:40].strip() == orig[:40].strip(): cls = 'same_content_variant'; break
        cnt[cls] += 1; mal[cls] += int(bool(j.get('malformed')))
    return {c: {'n': cnt[c], 'malformed': wilson(mal[c], cnt[c])} for c in cnt}


res = {'prereg': 'PREREG_v1 sha256=53e34f1fc0c061e8d67bb559b2458419154159608f9e63cadae8eb9bcbecee38', 'B': B}
pool = sorted(glob.glob(f'{D}/out/main/r31b_old_*.jsonl'))
R = load(pool)
ids305 = [x.strip() for x in open(f'{D}/data/ids_dose_k4.txt') if x.strip()]
ids_gate = [x.strip() for x in open(f'{D}/data/ids_gate300.txt') if x.strip()]
# ---- dose tier
plan_dose = [json.loads(l) for l in open(f'{D}/data/plan_31b_T3r.jsonl')]
ok, have, tot = complete(R, plan_dose)
if ok:
    blk = {kind: dlogit_block(R, ids305, 'P1', [1, 2, 4], kind) for kind in ('cond', 'uncond')}
    dose = {'jobs_present': f'{have}/{tot}', 'P1': blk, 'rule_D-M_primary(cond)': rule_dm(blk['cond']), 'rule_D-M_uncond': rule_dm(blk['uncond'])}
    dose['P4'] = {kind: dlogit_block(R, ids305, 'P4', [1, 2, 4], kind) for kind in ('cond', 'uncond')}
    # removal per k and order imitation under P4(k)
    rem = {}; order = {}
    for k in (1, 2, 4):
        use = [i for i in ids305 if (i, 'P1', k) in R and (i, 'P4', k) in R and (i, 'P0', 0) in R]
        for kind in ('uncond', 'cond'):
            p1 = rate([y(R[(i, 'P1', k)], kind) for i in use]); p4 = rate([y(R[(i, 'P4', k)], kind) for i in use]); p0 = rate([y(R[(i, 'P0', 0)], kind) for i in use])
            rem[f'k={k}:{kind}'] = round((p1 - p4) / (p1 - p0), 4) if p1 != p0 else None
        ords = [((R[(i, 'P4', k)].get('judge') or {}).get('order')) for i in use if (R[(i, 'P4', k)].get('judge') or {}).get('name') == 'edit_file']
        order[f'k={k}'] = wilson(sum(1 for o in ords if o == 'old_first'), len(ords))
    dose['P4_removal_fraction'] = rem; dose['P4_order_imitation_old_first_share'] = order
    dose['edit_classes_P1'] = {f'k={k}': edit_class_k(R, ids305, 'P1', k) for k in (1, 2, 4)}
    res['dose_tier'] = dose
else:
    res['dose_tier'] = f'incomplete ({have}/{tot} jobs) - not analysed (PREREG: no interim looks)'
# ---- r-dose (vs P1 k=1 on the gate set)
RR = load(pool + [f'{D}/out/main/r31b_rdose.jsonl'])
plan_rd = [json.loads(l) for l in open(f'{D}/data/plan_31b_RD.jsonl')]
ok, have, tot = complete(RR, plan_rd)
if ok:
    out = {}
    for kind in ('cond', 'uncond'):
        use = [i for i in ids_gate if all((i, a, 1) in RR for a in ('P1', 'R2', 'R4')) and (i, 'P0', 0) in RR]
        groups = collections.defaultdict(list)
        for i in use: groups[META[i]['task']].append({a: y(RR[(i, a, 1)], kind) for a in ('P1', 'R2', 'R4')})
        rows = [r for g in groups.values() for r in g]
        st = lambda rr: np.array([logit(rate([r['R2'] for r in rr])) - logit(rate([r['P1'] for r in rr])),
                                  logit(rate([r['R4'] for r in rr])) - logit(rate([r['P1'] for r in rr])),
                                  rate([r['P1'] for r in rr]), rate([r['R2'] for r in rr]), rate([r['R4'] for r in rr])])
        e = st(rows); bs = cluster_boot(groups, st)
        out[kind] = {'n_contexts': len(use), 'Delta_r2': [round(float(e[0]), 4), [round(float(np.percentile(bs[:, 0], 2.5)), 4), round(float(np.percentile(bs[:, 0], 97.5)), 4)]],
                     'Delta_r4': [round(float(e[1]), 4), [round(float(np.percentile(bs[:, 1], 2.5)), 4), round(float(np.percentile(bs[:, 1], 97.5)), 4)]],
                     'P(r=1)': round(float(e[2]), 4), 'P(r=2)': round(float(e[3]), 4), 'P(r=4)': round(float(e[4]), 4)}
    res['r_dose'] = {'jobs_present': f'{have}/{tot}', **out}
else:
    res['r_dose'] = f'incomplete ({have}/{tot}) - not analysed'
# ---- lag-2
plan_l2 = [json.loads(l) for l in open(f'{D}/data/plan_31b_L2.jsonl')]
ids_l2 = [x.strip() for x in open(f'{D}/data/ids_lag2.txt') if x.strip()]
need = plan_l2 + [{'id': i, 'pathway': p, 'k': k} for i in ids_l2 for p, k in (('P0', 0), ('P1', 1))]
ok, have, tot = complete(R, need)
if ok:
    out = {}
    for kind in ('uncond', 'cond'):
        use = [i for i in ids_l2 if all(x in R for x in ((i, 'P0', 0), (i, 'P1', 1), (i, 'L2', 1)))]
        groups = collections.defaultdict(list)
        for i in use: groups[META[i]['task']].append({a: y(R[(i, a, kk)], kind) for a, kk in (('P0', 0), ('P1', 1), ('L2', 1))})
        rows = [r for g in groups.values() for r in g]
        st = lambda rr: np.array([(rate([r['L2'] for r in rr]) - rate([r['P0'] for r in rr])) / (rate([r['P1'] for r in rr]) - rate([r['P0'] for r in rr])),
                                  rate([r['P0'] for r in rr]), rate([r['P1'] for r in rr]), rate([r['L2'] for r in rr])])
        e = st(rows); bs = cluster_boot(groups, st)
        out[kind] = {'n_contexts': len(use), 'lag2_excess_share': [round(float(e[0]), 4), [round(float(np.percentile(bs[:, 0], 2.5)), 4), round(float(np.percentile(bs[:, 0], 97.5)), 4)]],
                     'p0': round(float(e[1]), 4), 'p1': round(float(e[2]), 4), 'p_lag2': round(float(e[3]), 4)}
    res['lag2'] = {'jobs_present': f'{have}/{tot}', **out, 'prediction': 'M1 < 0.25 (~0); M2/M3 >= 0.5'}
else:
    res['lag2'] = f'incomplete ({have}/{tot}) - not analysed'
# ---- P6k
plan_p6k = [json.loads(l) for l in open(f'{D}/data/plan_31b_P6k.jsonl')]
ok, have, tot = complete(R, plan_p6k)
if ok:
    p6 = {kind: dlogit_block(R, ids305, 'P6', [1, 2, 4], kind) for kind in ('cond', 'uncond')}
    res['P6k'] = {'jobs_present': f'{have}/{tot}', **p6,
                  'supplementary_rule_D-M_form(cond)': rule_dm(p6['cond'], 'P6'), 'supplementary_rule_D-M_form(uncond)': rule_dm(p6['uncond'], 'P6'),
                  'prereg_point_predictions(anchor P6(1)=0.286)': {'M1': [0.29, 0.29], 'M2': [0.45, 0.63], 'M3': [0.73, 0.99]},
                  'note': 'PREREG gives point predictions for P6k (§3.2) and makes rule D-M primary only for the P1 dose tier; the D-M form here is supplementary. '
                          'Compare the predictions as logit differences from the set\'s own P6(1) (here lower than the 0.286 anchor).'}
else:
    res['P6k'] = f'incomplete ({have}/{tot}) - not analysed'
# ---- P7 closer share (final, gate 300)
mal7 = [d for (i, p, k), d in R.items() if (p, k) == ('P7', 1) and i in set(ids_gate) and (d.get('judge') or {}).get('name') == 'edit_file' and d['judge'].get('malformed')]
wc = [d for d in mal7 if d['judge'].get('closer')]
res['P7_injected_quote_share'] = {'share_with_quote_closer': wilson(sum(1 for d in wc if '"' in d['judge']['closer']), len(wc)),
                                  'prediction': 'M1/M2 >= 0.80; M3 0.3-0.7; D point 0.55 (80% PI 0.40-0.70)'}
# ---- A2
RA = load([f'{D}/out/main/r31b_a2.jsonl'])
plan_a2 = [json.loads(l) for l in open(f'{D}/data/plan_a2_LP5.jsonl')]
ok, have, tot = complete(RA, plan_a2)
if ok:
    ids_a2 = sorted(set(j['id'] for j in plan_a2))
    out = {}
    armk = {p: k for (_, p, k) in RA if p != 'P0'}
    for Q in sorted(armk):
        kq = armk[Q]
        use = [i for i in ids_a2 if (i, 'P0', 0) in RA and (i, Q, kq) in RA]
        groups = {i: [(y(RA[(i, 'P0', 0)], 'uncond'), y(RA[(i, Q, kq)], 'uncond'))] for i in use}  # contexts are the clusters
        st = lambda rr: np.array([1 - rate([r[1] for r in rr]) / rate([r[0] for r in rr]), rate([r[0] for r in rr]), rate([r[1] for r in rr])])
        e = st([g[0] for g in groups.values()]); bs = cluster_boot(groups, st)
        out[Q] = {'n_states': len(use), 'h': [round(float(e[0]), 4), [round(float(np.percentile(bs[:, 0], 2.5)), 4), round(float(np.percentile(bs[:, 0], 97.5)), 4)]],
                  'q(L)': round(float(e[1]), 4), f'q({Q})': round(float(e[2]), 4)}
    res['A2'] = {'jobs_present': f'{have}/{tot}', 'h_by_arm (unconditional, h = 1 - q(arm)/q(L))': out,
                 'rule': 'h >= 0.7: quarantine is the dominant lever for 31B; h <= 0.4: content stickiness dominates (IPD-first)'}
else:
    res['A2'] = f'incomplete ({have}/{tot}) - not analysed'
json.dump(res, open(f'{D}/out/prereg_analysis.json', 'w'), indent=1)
print({k: (v if isinstance(v, str) else 'computed') for k, v in res.items()})
