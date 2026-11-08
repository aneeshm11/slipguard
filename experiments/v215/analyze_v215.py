"""PREREG_v2.15 analysis: does the weight audit's deficit predict TranscriptLab P1 across seven 31B checkpoints?
Written and hash-frozen with paper/protocol_theory/prereg/PREREG_v2.15_audit_predicts_copying.md BEFORE any v2.15 job;
run once after the three new runs end. Statistics block copied VERBATIM from analyze_v27_robustness.py (f68bc12d).
usage: analyze_v215.py --out <json> [--B 2000]"""
import json, sys, os, math, argparse, collections, itertools
import numpy as np
P_ = '.'
D = P_ + '/experiments/contagion'
ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--B', type=int, default=2000)
a = ap.parse_args()
CLI = P_ + '/experiments/transcriptlab_cli/'
V214 = D + '/out/confirmatory/v214_bf16_analysis.json'
BF16 = CLI + 'run_v214_bf16/gen.jsonl' if os.path.exists(V214) else D + '/out/main/rCbf16_v2.jsonl'
CAND = {'bf16': BF16, 'awq': D + '/out/main/rCawq_v26.jsonl', 'autoround': D + '/out/main/rCautoround_v26.jsonl',
        'nvnvfp4': CLI + 'run_v215_nvnvfp4/gen.jsonl', 'qat': D + '/out/main/rC31b_v2.jsonl',
        'qatawq': CLI + 'run_v215_qatawq/gen.jsonl', 'qatnvfp4': CLI + 'run_v215_qatnvfp4/gen.jsonl'}
NOTRUN = {c for c in ('nvnvfp4', 'qatawq', 'qatnvfp4') if os.path.exists(CLI + f'run_v215_{c}/NOT_RUN')}
FILES = {c: f for c, f in CAND.items() if os.path.exists(f) and c not in NOTRUN}
W_ = P_ + '/experiments/quant_margins/wsa/out/'
def _pt(v):
    while isinstance(v, (list, dict)): v = v[0] if isinstance(v, list) else v.get('point', v.get('estimate'))
    return round(float(v), 4)
_sr = json.load(open(W_ + 'sweep_report.json'))['checkpoints']
DEF = {'bf16': 0.0, 'awq': _pt(_sr['31b_awq_cyankiwi']['paired_vs_ref']['median_deficit']),
       'autoround': json.load(open(D + '/out/confirmatory/v26_audit_analysis.json'))['deficits_nats']['AR'],
       'nvnvfp4': _pt(json.load(open(W_ + 'audit_v210_31b_nvfp4_nvidia.json'))['paired_vs_reference']['median_deficit']),
       'qat': _pt(_sr['31b_qatct']['paired_vs_ref']['median_deficit']),
       'qatawq': _pt(json.load(open(W_ + 'audit_v210_31b_qatawq_cyankiwi.json'))['paired_vs_reference']['median_deficit']),
       'qatnvfp4': _pt(json.load(open(W_ + 'audit_v210_31b_qatnvfp4_melcheikh.json'))['paired_vs_reference']['median_deficit'])}
# ---------------- verbatim from analyze_v27_robustness.py (f68bc12d) ----------------
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


# ---------------- end of the verbatim block ----------------


def ranks(x):
    o = sorted(range(len(x)), key=lambda i: x[i]); r = [0.0] * len(x); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y); mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a_ - mx) * (b_ - my) for a_, b_ in zip(rx, ry))
    den = math.sqrt(sum((a_ - mx) ** 2 for a_ in rx) * sum((b_ - my) ** 2 for b_ in ry))
    return num / den if den else float('nan')


def exact_p(x, y):
    r0 = spearman(x, y); n = 0; ge = 0
    for perm in itertools.permutations(y):
        n += 1; ge += spearman(x, list(perm)) >= r0 - 1e-12
    return round(r0, 4), round(ge / n, 4), n


panel = [c for c in ('bf16', 'awq', 'autoround', 'nvnvfp4', 'qat', 'qatawq', 'qatnvfp4') if c in Y]
out = {'prereg': 'PREREG_v2.15_audit_predicts_copying.md (sha256 in PROGRESS.md at freeze)', 'B': a.B, 'files': FILES,
       'not_run': sorted(NOTRUN), 'bf16_source': 'PREREG_v2.14 run' if BF16.endswith('run_v214_bf16/gen.jsonl') else 'exploratory rCbf16_v2',
       'deficits_nats': {c: DEF[c] for c in panel},
       'missing': {c: {p: sum(1 for i in ids if (i, p) not in Y[c]) for p, _ in ARMS} for c in panel}}
out['rates'] = {c: {p: rate(c, p) for p, _ in ARMS} for c in panel}
out['copying'] = {c: flip(c) for c in panel}
out['induction'] = {c: induction(c) for c in panel}
out['removal_not_gated'] = {c: removal(c) for c in panel}
x = [DEF[c] for c in panel]; yP1 = [out['rates'][c]['P1'][0] for c in panel]; yC = [out['copying'][c]['RD_P1_minus_P0'] for c in panel]
rho, p, nperm = exact_p(x, yP1)
out['primary'] = {'panel': panel, 'deficits': x, 'P1': yP1, 'spearman_rho': rho, 'exact_one_sided_p': p, 'n_permutations': nperm,
                  'verdict': 'AUDIT PREDICTS COPYING' if (len(panel) >= 5 and rho > 0 and p < 0.05) else ('UNDERPOWERED (panel < 5)' if len(panel) < 5 else 'NOT SHOWN')}
r2, p2, _ = exact_p(x, yC); out['descriptive_rho_copying_RD'] = {'spearman_rho': r2, 'exact_one_sided_p': p2}
sec = {}
for nm, A, Bc, sign in (('S1_qatawq_above_bf16', 'qatawq', 'bf16', +1), ('S2_qatnvfp4_above_bf16', 'qatnvfp4', 'bf16', +1),
                        ('S3_nvnvfp4_below_qat', 'nvnvfp4', 'qat', -1)):
    if A in Y and Bc in Y:
        r = contrast(Bc, 'P1', A, 'P1') if sign > 0 else contrast(A, 'P1', Bc, 'P1')   # tests (lower) < (higher)
        r['tested'] = f'P1({Bc}) < P1({A})' if sign > 0 else f'P1({A}) < P1({Bc})'
        r['met'] = bool(r['RD'] < 0 and r['mcnemar_one_sided_p_RD_lt_0'] < 0.05)
        sec[nm] = r
    else:
        sec[nm] = {'met': None, 'note': 'not run'}
out['secondary_out_of_sample'] = sec
json.dump(out, open(a.out, 'w'), indent=1)
print(json.dumps({'primary': out['primary'], 'secondary': {k: (v.get('met'), v.get('RD'), v.get('mcnemar_one_sided_p_RD_lt_0')) for k, v in sec.items()},
                  'bf16_source': out['bf16_source'], 'not_run': out['not_run']}, indent=1))
