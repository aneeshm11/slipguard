"""PREREG_v2.6_auditBehaviour (sha256 ed19a6d0...) analysis. Written and hash-frozen BEFORE the first job of either new
checkpoint; run once, after both runners have logged 'finished'.

Conditions on the 300 PREREG_v2 S1_A1 states, arms P0/P1/P6/P8a:
  AWQ   cyankiwi AWQ-4bit         out/main/rCawq_v26.jsonl        (new)
  AR    Intel AutoRound int4      out/main/rCautoround_v26.jsonl  (new)
  QAT   Google QAT-ct (C1)        out/main/rC31b_v2.jsonl         (reused, confirmatory)
  BF16  31B bf16 (exploratory)    out/main/rCbf16_v2.jsonl        (reused; descriptive ordering only)
Outcome: ITT malformed-edit indicator per state, using A's frozen judge as stored at run time (judge.is_edit and
judge.malformed), as in C1.
Tests (one-sided, exact McNemar on per-state discordant pairs; Holm over the evaluable set):
  H1  P1(AWQ) < P1(QAT)
  H2  P1(AR) < P1(QAT)
  H3  P8a(AWQ) < P1(AWQ); only if RD(P1 - P0 | AWQ) has bootstrap CI_lo > 0, else NOT EVALUABLE and dropped from Holm
CIs: episode-cluster percentile bootstrap (B = 2000, seed 20261105), paired by state; contrasts use states complete in
both conditions.
Removal (H3) = (P1 - P8a)/(P1 - P0) under AWQ.
No-harm: P0(cond) - P0(QAT), point <= 0 and CI_hi <= +2 pp (AWQ is the verdict; AR is reported).
"Ordered" (descriptive): P1(QAT) >= P1(AR) - 1.5 pp and P1(AR) >= max(P1(BF16), P1(AWQ)) - 1.5 pp.
Spearman rho of P1 against deficits (BF16 0, AWQ 0.02, AR 0.63, QAT 5.13), with the exact one-sided p over all 24
permutations (P(rho* >= rho)).
Verdicts and paper sentences follow PREREG_v2.6 §4-§5 verbatim.
usage: analyze_v26_audit.py --out <json> [--B 2000]
"""
import json, sys, os, math, argparse, itertools, collections
import numpy as np
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--B', type=int, default=2000)
ap.add_argument('--force_incomplete', action='store_true')
ap.add_argument('--smoke_awq', default=''); ap.add_argument('--smoke_ar', default='')   # SMOKE ONLY: stand-in files
a = ap.parse_args()
FILES = {'AWQ': (f'{D}/out/main/rCawq_v26.jsonl', f'{D}/logs/ctg-Cawq26.log'), 'AR': (f'{D}/out/main/rCautoround_v26.jsonl', f'{D}/logs/ctg-Car26.log'),
         'QAT': (f'{D}/out/main/rC31b_v2.jsonl', None), 'BF16': (f'{D}/out/main/rCbf16_v2.jsonl', None)}
DEFICIT = {'BF16': 0.0, 'AWQ': 0.02, 'AR': 0.63, 'QAT': 5.13}
if a.smoke_awq: FILES['AWQ'] = (a.smoke_awq, None)
if a.smoke_ar: FILES['AR'] = (a.smoke_ar, None)
for c in ('AWQ', 'AR'):
    if not a.force_incomplete and not (FILES[c][1] and os.path.exists(FILES[c][1]) and any(l.startswith('finished') for l in open(FILES[c][1]))):
        sys.exit(f"{c}: runner log has no 'finished' line -> not analysed")
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


R = {c: load(f) for c, (f, _) in FILES.items()}
Y = {c: {(i, p): y(d) for (i, p), d in R[c].items()} for c in R}
cl = sorted(set(META[i]['task'] for i in ids)); ci_ = {c: j for j, c in enumerate(cl)}
rng = np.random.default_rng(20261105); W = rng.multinomial(len(cl), np.full(len(cl), 1 / len(cl)), size=a.B).astype(float)


def pct(x): x = x[np.isfinite(x)]; return [round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4)]


def vec(pairs):
    """pairs: list of (state, value) -> cluster sums and counts."""
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
            'RD_CI': pct(d), 'discordant_B_only_A_only': [n10, n01], 'mcnemar_one_sided_p_RD_lt_0': round(p, 6)}


def rate(c, arm):
    st = [i for i in ids if (i, arm) in Y[c]]; v = [Y[c][(i, arm)] for i in st]
    S, N = vec(zip(st, v)); return [round(sum(v) / len(v), 4)] + pct((W @ S) / (W @ N)) + [len(v)] if v else None


out = {'prereg': 'PREREG_v2.6_auditBehaviour.md sha256 ed19a6d07734afe795f63e7c9c5b6c3d1285d21deff828557ca28b1e333520f6', 'B': a.B,
       'missing': {c: {p: sum(1 for i in ids if (i, p) not in Y[c]) for p, _ in ARMS} for c in Y},
       'servers': {c: dict(collections.Counter(d.get('server') for d in R[c].values())) for c in R}, 'deficits_nats': DEFICIT}
out['rates'] = {c: {p: rate(c, p) for p, _ in ARMS} for c in Y}
h1 = contrast('AWQ', 'P1', 'QAT', 'P1'); h2 = contrast('AR', 'P1', 'QAT', 'P1')
awq_rd = contrast('AWQ', 'P0', 'AWQ', 'P1')            # P0 - P1 under AWQ (negative = contagion)
evaluable = awq_rd['RD_CI'][1] < 0                      # RD(P1 - P0) CI_lo > 0
h3 = contrast('AWQ', 'P8a', 'AWQ', 'P1')
st = [i for i in ids if all((i, p) in Y['AWQ'] for p in ('P0', 'P1', 'P8a'))]
S1, N = vec([(i, Y['AWQ'][(i, 'P1')]) for i in st]); S8, _ = vec([(i, Y['AWQ'][(i, 'P8a')]) for i in st]); S0, _ = vec([(i, Y['AWQ'][(i, 'P0')]) for i in st])
r1, r8, r0 = (W @ S1) / (W @ N), (W @ S8) / (W @ N), (W @ S0) / (W @ N)
den = r1 - r0; rem = np.where(den > 0, (r1 - r8) / np.where(den > 0, den, 1), np.nan)
e1, e8, e0 = S1.sum() / N.sum(), S8.sum() / N.sum(), S0.sum() / N.sum()
removal = {'point': round(float((e1 - e8) / (e1 - e0)), 4) if e1 - e0 > 0 else None, 'CI': pct(rem) if np.mean(den > 0) >= 0.975 else None,
           'undefined_draw_frac': round(float(np.mean(den <= 0)), 4)}
ps = {'H1': h1['mcnemar_one_sided_p_RD_lt_0'], 'H2': h2['mcnemar_one_sided_p_RD_lt_0']}
if evaluable: ps['H3'] = h3['mcnemar_one_sided_p_RD_lt_0']
order = sorted(ps, key=lambda k: ps[k]); holm = {}; run = 0.0
for r, k in enumerate(order): run = max(run, min(1.0, (len(order) - r) * ps[k])); holm[k] = round(run, 6)
P1 = {c: out['rates'][c]['P1'][0] for c in Y}
ordered = P1['QAT'] >= P1['AR'] - 0.015 and P1['AR'] >= max(P1['BF16'], P1['AWQ']) - 0.015
conds = ['BF16', 'AWQ', 'AR', 'QAT']


def rank(v):
    s = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]: j += 1
        for t in range(i, j + 1): r[s[t]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, yv):
    rx, ry = rank(x), rank(yv); mx, my = sum(rx) / 4, sum(ry) / 4
    num = sum((p - mx) * (q - my) for p, q in zip(rx, ry)); den_ = math.sqrt(sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry))
    return num / den_ if den_ else float('nan')


xv = [DEFICIT[c] for c in conds]; yv = [P1[c] for c in conds]; rho = spearman(xv, yv)
perm = [spearman(xv, list(p)) for p in itertools.permutations(yv)]
p_rho = sum(1 for r in perm if r >= rho - 1e-12) / len(perm)
nh = {c: contrast(c, 'P0', 'QAT', 'P0') for c in ('AWQ', 'AR')}
for c in nh: nh[c]['verdict'] = 'HOLDS' if (nh[c]['RD'] <= 0 and nh[c]['RD_CI'][1] <= 0.02) else 'FAILS'
v1 = ('AUDIT PICK CUTS CONTAGION' if holm['H1'] < 0.05 and h1['RD'] <= -0.05 else 'SMALLER CUT' if holm['H1'] < 0.05 and h1['RD'] < 0 else 'NOT SHOWN')
hp2 = holm['H2'] < 0.05
v2 = 'DOSE-RESPONSE SUPPORTED' if (hp2 and ordered) else ('PARTIAL' if (hp2 != ordered) else 'NOT SHOWN')
if not evaluable: v3 = 'NOT EVALUABLE'
elif holm['H3'] < 0.05 and removal['point'] is not None and removal['CI'] and removal['point'] >= 0.90 and removal['CI'][0] >= 0.50: v3 = 'QUARANTINE STILL NEEDED AND WORKS'
elif holm['H3'] < 0.05 and removal['point'] is not None and removal['CI'] and removal['point'] >= 0.70 and removal['CI'][0] >= 0.50: v3 = 'WORKS (attenuated)'
else: v3 = 'NOT SHOWN'
fmt = lambda c: f"{100 * out['rates'][c]['P1'][0]:.1f}% [{100 * out['rates'][c]['P1'][1]:.1f}, {100 * out['rates'][c]['P1'][2]:.1f}]"
sent = []
if v1 == 'AUDIT PICK CUTS CONTAGION' and nh['AWQ']['verdict'] == 'HOLDS':
    sent.append(f"Serving the audit's top-ranked 4-bit checkpoint (AWQ, deficit 0.02 nats) instead of Google's QAT checkpoint (5.13 nats) cuts contagion after a laundered slip from 19.7% to {fmt('AWQ')} at the same 4-bit weight precision, on 300 public states.")
elif v1 == 'SMALLER CUT':
    sent.append(f"Serving the audit's top-ranked 4-bit checkpoint (AWQ, deficit 0.02 nats) instead of Google's QAT checkpoint (5.13 nats) reduces contagion from 19.7% to {fmt('AWQ')}, on 300 public states.")
elif v1 == 'NOT SHOWN':
    sent.append("No ranking claim. Limitations: the audit's deficit did not predict contagion in a registered test.")
if v2 == 'DOSE-RESPONSE SUPPORTED':
    sent.append(f"Contagion rises with the audit deficit (bf16/AWQ ≈ 0 → AutoRound 0.63 → QAT 5.13 nats: {fmt('AWQ')} → {fmt('AR')} → 19.7%).")
elif v2 == 'PARTIAL':
    sent.append('H2 PARTIAL: state only the supported half (' + ('AutoRound below QAT-ct, Holm p < 0.05' if hp2 else 'the four points are Ordered') + ') with the n = 4 caveat.')
if v3 == 'QUARANTINE STILL NEEDED AND WORKS':
    sent.append(f"Even on the best-ranked checkpoint, the history guard removes {100 * removal['point']:.0f}% of the remaining contagion: checkpoint choice and slipguard are complementary.")
elif v3 == 'NOT EVALUABLE':
    sent.append('No contagion was detected under AWQ, so there was nothing for the guard to remove.')
out.update({'H1': {**h1, 'contrast': 'P1(AWQ) - P1(QAT)', 'holm_p': holm['H1'], 'verdict': v1, 'D_80PI_RD': '-10 pp [-16, -4]'},
            'H2': {**h2, 'contrast': 'P1(AR) - P1(QAT)', 'holm_p': holm['H2'], 'ordered': ordered, 'verdict': v2, 'D_80PI_RD': '-9 pp [-15, -2]'},
            'H3': {**h3, 'contrast': 'P8a(AWQ) - P1(AWQ)', 'evaluable': evaluable, 'AWQ_RD_P1_minus_P0': {'RD': -awq_rd['RD'], 'CI': [-awq_rd['RD_CI'][1], -awq_rd['RD_CI'][0]]},
                   'removal': removal, 'holm_p': holm.get('H3'), 'verdict': v3, 'D_80PI_removal': '1.00 [0.85, 1.10]'},
            'holm_family': list(ps), 'no_harm_P0_vs_QAT': nh,
            'descriptive_ordering': {'P1_by_condition': {c: P1[c] for c in conds}, 'deficits': DEFICIT, 'ordered': ordered, 'spearman_rho': round(rho, 4), 'exact_one_sided_p': round(p_rho, 4)},
            'P6_descriptive': {c: out['rates'][c]['P6'] for c in conds}, 'paper_sentences': sent})
json.dump(out, open(a.out, 'w'), indent=1)
print(json.dumps({k: out[k]['verdict'] for k in ('H1', 'H2', 'H3')} | {'no_harm_AWQ': nh['AWQ']['verdict'], 'ordered': ordered}, indent=1))
