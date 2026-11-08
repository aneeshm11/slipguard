"""PREREG_v2.7_robustness analysis (temperature, dtype, test-retest). Written and hash-frozen BEFORE the first v2.7 job;
run once, after every runner log has a 'finished' line (or a run is declared NOT RUN in PREREG_DEVIATIONS.md).
Statistics are those of analyze_v26_audit.py (frozen a8471999) unchanged: ITT malformed-edit indicator from A's
frozen judge as stored at run time; task-cluster percentile bootstrap (multinomial weights over tasks), here
B = 2000 with seed 20261106; exact one-sided McNemar on per-state discordant pairs; Holm over the evaluable set.
Runs (P0/P1/P6/P8a x 300 S1_A1 states):
  RT06  QAT-ct T=0.6         out/main/rT06_v27.jsonl        logs/ctg-T06v27.log
  RT00  QAT-ct greedy        out/main/rT00_v27.jsonl        logs/ctg-T00v27.log
  RD16  AWQ (bf16 dtype)     out/main/rAWQbf16_v27.jsonl    logs/ctg-AWQbf16v27.log
  RSA   QAT-ct seed set A    out/main/rSA_v27.jsonl         logs/ctg-SAv27.log
  RSB   QAT-ct seed set B    out/main/rSB_v27.jsonl         logs/ctg-SBv27.log
  QAT   C1 (reused)          out/main/rC31b_v2.jsonl
  AWQ16 v2.6 AWQ float16     out/main/rCawq_v26.jsonl       (reused; descriptive dtype contrast only)
usage: analyze_v27_robustness.py --out <json> [--B 2000] [--not_run RD16,...]
"""
import json, sys, os, math, argparse, collections
import numpy as np
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--B', type=int, default=2000)
ap.add_argument('--not_run', default='', help='comma-separated runs declared NOT RUN (logged deviation)')
ap.add_argument('--smoke', action='store_true', help='SMOKE ONLY: every new run reads an existing file (C1 / v2.6 AWQ); no log check')
a = ap.parse_args()
NEW = {'RT06': ('rT06_v27', 'ctg-T06v27'), 'RT00': ('rT00_v27', 'ctg-T00v27'), 'RD16': ('rAWQbf16_v27', 'ctg-AWQbf16v27'),
       'RSA': ('rSA_v27', 'ctg-SAv27'), 'RSB': ('rSB_v27', 'ctg-SBv27')}
NOT_RUN = {x for x in a.not_run.split(',') if x}
FILES = {k: f'{D}/out/main/{f}.jsonl' for k, (f, _) in NEW.items() if k not in NOT_RUN}
if a.smoke:
    FILES = {k: f'{D}/out/main/' + ('rCawq_v26' if k == 'RD16' else 'rC31b_v2') + '.jsonl' for k in FILES}
for k, (_, lg) in NEW.items():
    if k in NOT_RUN or a.smoke:
        continue
    p = f'{D}/logs/{lg}.log'
    if not (os.path.exists(p) and any(l.startswith('finished') for l in open(p))):
        sys.exit(f"{k}: runner log {p} has no 'finished' line -> not analysed")
FILES.update({'QAT': f'{D}/out/main/rC31b_v2.jsonl', 'AWQ16': f'{D}/out/main/rCawq_v26.jsonl'})
META = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/confirmatory/meta_S1.jsonl')}
ids = [json.loads(l)['context_id'] for l in open(f'{D}/data/confirmatory/pools/S1_A1.jsonl')]
ARMS = [('P0', 0), ('P1', 1), ('P6', 1), ('P8a', 1)]


def load(f):
    R = {}
    for l in open(f):
        try: d = json.loads(l)
        except Exception: continue
        if not d.get('error') and (d['pathway'], d['k']) in ARMS: R[(d['id'], d['pathway'])] = d
    return R


def y(d):
    j = d.get('judge') or {}; e = bool(j.get('is_edit', j.get('name') == 'edit_file')); return int(e and bool(j.get('malformed')))


R = {c: load(f) for c, f in FILES.items()}
Y = {c: {(i, p): y(d) for (i, p), d in R[c].items()} for c in R}
cl = sorted(set(META[i]['task'] for i in ids)); ci_ = {c: j for j, c in enumerate(cl)}
rng = np.random.default_rng(20261106); W = rng.multinomial(len(cl), np.full(len(cl), 1 / len(cl)), size=a.B).astype(float)


def pct(x): x = x[np.isfinite(x)]; return [round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4)]


def vec(pairs):
    S = np.zeros(len(cl)); N = np.zeros(len(cl))
    for i, v in pairs: S[ci_[META[i]['task']]] += v; N[ci_[META[i]['task']]] += 1
    return S, N


def contrast(cA, armA, cB, armB):
    """RD = rate(cA, armA) - rate(cB, armB), paired over states complete in both; exact one-sided McNemar for RD < 0."""
    st = [i for i in ids if (i, armA) in Y[cA] and (i, armB) in Y[cB]]
    a_ = [Y[cA][(i, armA)] for i in st]; b_ = [Y[cB][(i, armB)] for i in st]
    SA, N = vec(zip(st, a_)); SB, _ = vec(zip(st, b_))
    d = (W @ SA - W @ SB) / (W @ N)
    n10 = sum(1 for x, z in zip(a_, b_) if x == 0 and z == 1); n01 = sum(1 for x, z in zip(a_, b_) if x == 1 and z == 0)
    p = sum(math.comb(n10 + n01, k) for k in range(n10, n10 + n01 + 1)) / 2 ** (n10 + n01) if n10 + n01 else 1.0
    return {'n_states': len(st), 'A': round(sum(a_) / len(st), 4), 'B': round(sum(b_) / len(st), 4), 'RD': round((sum(a_) - sum(b_)) / len(st), 4),
            'RD_CI': pct(d), 'discordant_B_only_A_only': [n10, n01], 'mcnemar_one_sided_p_RD_lt_0': float(f'{p:.4g}')}


def rate(c, arm):
    st = [i for i in ids if (i, arm) in Y[c]]; v = [Y[c][(i, arm)] for i in st]
    S, N = vec(zip(st, v)); return [round(sum(v) / len(v), 4)] + pct((W @ S) / (W @ N)) + [len(v)] if v else None


def flip(c):  # RD(P1 - P0) as a positive contagion contrast: test P0 - P1 < 0
    r = contrast(c, 'P0', c, 'P1')
    return {'RD_P1_minus_P0': -r['RD'], 'CI': [-r['RD_CI'][1], -r['RD_CI'][0]], 'p': r['mcnemar_one_sided_p_RD_lt_0'], 'n_states': r['n_states'],
            'discordant': r['discordant_B_only_A_only']}


def removal(c):
    st = [i for i in ids if all((i, p) in Y[c] for p in ('P0', 'P1', 'P8a'))]
    S1, N = vec([(i, Y[c][(i, 'P1')]) for i in st]); S8, _ = vec([(i, Y[c][(i, 'P8a')]) for i in st]); S0, _ = vec([(i, Y[c][(i, 'P0')]) for i in st])
    r1, r8, r0 = (W @ S1) / (W @ N), (W @ S8) / (W @ N), (W @ S0) / (W @ N)
    den = r1 - r0; rem = np.where(den > 0, (r1 - r8) / np.where(den > 0, den, 1), np.nan)
    e1, e8, e0 = S1.sum() / N.sum(), S8.sum() / N.sum(), S0.sum() / N.sum()
    return {'point': round(float((e1 - e8) / (e1 - e0)), 4) if e1 - e0 > 0 else None, 'CI': pct(rem) if np.mean(den > 0) >= 0.975 else None,
            'undefined_draw_frac': round(float(np.mean(den <= 0)), 4)}


def induction(c):
    r = contrast(c, 'P0', c, 'P6'); return {'RD_P6_minus_P0': -r['RD'], 'CI': [-r['RD_CI'][1], -r['RD_CI'][0]]}


out = {'prereg': 'PREREG_v2.7_robustness.md (sha256 in PROGRESS.md at freeze)', 'B': a.B, 'not_run': sorted(NOT_RUN),
       'missing': {c: {p: sum(1 for i in ids if (i, p) not in Y[c]) for p, _ in ARMS} for c in Y},
       'servers': {c: dict(collections.Counter(d.get('server') for d in R[c].values())) for c in R},
       'temps': {c: dict(collections.Counter(d.get('temp') for d in R[c].values())) for c in R}}
out['rates'] = {c: {p: rate(c, p) for p, _ in ARMS} for c in Y}
runs = [c for c in ('RT06', 'RT00', 'RD16', 'RSA', 'RSB', 'QAT', 'AWQ16') if c in Y]
out['copying'] = {c: flip(c) for c in runs}
out['induction'] = {c: induction(c) for c in runs}
out['removal'] = {c: removal(c) for c in runs}
ps = {}
if 'RT06' in Y: ps['T1'] = out['copying']['RT06']['p']
if 'RT00' in Y: ps['T2'] = out['copying']['RT00']['p']
ev = {'T3': 'RT06' in Y and out['copying']['RT06']['CI'][0] > 0, 'T4': 'RT00' in Y and out['copying']['RT00']['CI'][0] > 0}
h = {}
if ev['T3']: h['T3'] = contrast('RT06', 'P8a', 'RT06', 'P1'); ps['T3'] = h['T3']['mcnemar_one_sided_p_RD_lt_0']
if ev['T4']: h['T4'] = contrast('RT00', 'P8a', 'RT00', 'P1'); ps['T4'] = h['T4']['mcnemar_one_sided_p_RD_lt_0']
if 'RD16' in Y: h['D1'] = contrast('RD16', 'P1', 'QAT', 'P1'); ps['D1'] = h['D1']['mcnemar_one_sided_p_RD_lt_0']
if 'RSA' in Y: ps['S1'] = out['copying']['RSA']['p']
if 'RSB' in Y: ps['S2'] = out['copying']['RSB']['p']
order = sorted(ps, key=lambda k: ps[k]); holm = {}; run_ = 0.0
for r, k in enumerate(order): run_ = max(run_, min(1.0, (len(order) - r) * ps[k])); holm[k] = float(f'{run_:.4g}')
out['holm_family'] = {k: {'p': ps[k], 'holm_p': holm[k]} for k in ps}
V = {}
for t, c, q in (('T1', 'RT06', 'T3'), ('T2', 'RT00', 'T4')):
    if c not in Y: continue
    rd = out['copying'][c]['RD_P1_minus_P0']
    V[c + '_copying'] = 'COPYING PERSISTS' if holm[t] < 0.05 and rd >= 0.05 else 'ATTENUATED' if holm[t] < 0.05 else 'NOT DETECTED'
    rm = out['removal'][c]
    if not ev[q]: V[c + '_quarantine'] = 'NOT EVALUABLE'
    elif holm[q] < 0.05 and rm['point'] is not None and rm['CI'] and rm['point'] >= 0.90 and rm['CI'][0] >= 0.50: V[c + '_quarantine'] = 'QUARANTINE WORKS'
    elif holm[q] < 0.05 and rm['point'] is not None and rm['CI'] and rm['point'] >= 0.70 and rm['CI'][0] >= 0.50: V[c + '_quarantine'] = 'WORKS (attenuated)'
    else: V[c + '_quarantine'] = 'NOT SHOWN'
if 'RD16' in Y:
    rd = h['D1']['RD']
    V['D1'] = 'AUDIT PICK REPLICATES AT MATCHED DTYPE' if holm['D1'] < 0.05 and rd <= -0.05 else 'SMALLER CUT' if holm['D1'] < 0.05 and rd < 0 else 'NOT SHOWN'
    out['dtype_descriptive_RD16_minus_AWQ16_P1'] = contrast('RD16', 'P1', 'AWQ16', 'P1')
else:
    V['D1'] = 'NOT RUN'
if 'RSA' in Y and 'RSB' in Y:
    c1 = out['copying']['QAT']['RD_P1_minus_P0']; crit = {}
    for s, c in (('S1', 'RSA'), ('S2', 'RSB')):
        rm = out['removal'][c]
        crit[c] = {'copying_holm_sig': holm[s] < 0.05, 'induction_point_pos': out['induction'][c]['RD_P6_minus_P0'] > 0,
                   'removal_ge_0.90': bool(rm['point'] is not None and rm['point'] >= 0.90),
                   'copying_within_6pp_of_C1': abs(out['copying'][c]['RD_P1_minus_P0'] - c1) <= 0.06}
    allc = all(all(v.values()) for v in crit.values()); sig = all(v['copying_holm_sig'] for v in crit.values())
    V['test_retest'] = 'STABLE' if allc else 'PARTLY STABLE' if sig else 'UNSTABLE'
    out['test_retest_criteria'] = crit
    out['test_retest_spread'] = {p: {'rates_C1_A_B': [out['rates'][c][p][0] for c in ('QAT', 'RSA', 'RSB')],
                                     'sd': round(float(np.std([out['rates'][c][p][0] for c in ('QAT', 'RSA', 'RSB')], ddof=1)), 4)} for p, _ in ARMS}
out['contrasts'] = h; out['verdicts'] = V
json.dump(out, open(a.out, 'w'), indent=1)
print(json.dumps({'verdicts': V, 'holm': out['holm_family']}, indent=1))
