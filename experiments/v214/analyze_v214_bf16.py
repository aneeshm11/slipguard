"""PREREG_v2.14 analysis: Gemma-4-31B bf16 on TranscriptLab via the released CLI. (A) copying without quantization;
(B) bf16 P1 below QAT C1's P1 (exact one-sided McNemar). Written and hash-frozen with
paper/protocol_theory/prereg/PREREG_v2.14_bf16_cli.md BEFORE the first v2.14 job; run once. The statistics block is copied
VERBATIM from analyze_v27_robustness.py (frozen f68bc12d), via analyze_v211_masked.py.
usage: analyze_v214_bf16.py --cli_gen <run_dir>/gen.jsonl --out <json> [--B 2000]"""
import json, sys, os, math, argparse, collections
import numpy as np
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser(); ap.add_argument('--cli_gen', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--B', type=int, default=2000)
a = ap.parse_args()
FILES = {'CLI': a.cli_gen, 'QAT': f'{D}/out/main/rC31b_v2.jsonl', 'BF16X': f'{D}/out/main/rCbf16_v2.jsonl'}
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


def mcnemar_two_sided(n10, n01):
    n = n10 + n01
    if not n: return 1.0
    k = min(n10, n01)
    return min(1.0, 2 * sum(math.comb(n, j) for j in range(0, k + 1)) / 2 ** n)


def copy_diff(cA, cB):
    """bootstrap CI of copying RD(cA) - copying RD(cB), states complete in all four (arm, run) cells."""
    st = [i for i in ids if all((i, p) in Y[c] for c in (cA, cB) for p in ('P0', 'P1'))]
    v = {}
    for c in (cA, cB):
        for p in ('P0', 'P1'):
            v[(c, p)], N = vec([(i, Y[c][(i, p)]) for i in st])
    d = ((W @ v[(cA, 'P1')] - W @ v[(cA, 'P0')]) - (W @ v[(cB, 'P1')] - W @ v[(cB, 'P0')])) / (W @ N)
    pt = ((v[(cA, 'P1')].sum() - v[(cA, 'P0')].sum()) - (v[(cB, 'P1')].sum() - v[(cB, 'P0')].sum())) / N.sum()
    return {'n_states': len(st), 'diff': round(float(pt), 4), 'CI': pct(d)}


out = {'prereg': 'PREREG_v2.14_bf16_cli.md (sha256 in PROGRESS.md at freeze)', 'B': a.B,
       'missing': {c: {p: sum(1 for i in ids if (i, p) not in Y[c]) for p, _ in ARMS} for c in Y},
       'servers': {c: dict(collections.Counter(d.get('server') for d in R[c].values())) for c in R}}
out['rates'] = {c: {p: rate(c, p) for p, _ in ARMS} for c in ('CLI', 'QAT', 'BF16X')}
out['copying'] = {c: flip(c) for c in ('CLI', 'QAT', 'BF16X')}
out['induction'] = {c: induction(c) for c in ('CLI', 'QAT', 'BF16X')}
out['removal_not_gated'] = {c: removal(c) for c in ('CLI', 'QAT', 'BF16X')}
B_ = contrast('CLI', 'P1', 'QAT', 'P1')
out['B_bf16_P1_vs_QAT_P1'] = B_
ag = contrast('CLI', 'P1', 'BF16X', 'P1'); n10, n01 = ag['discordant_B_only_A_only']
ag['mcnemar_two_sided_p'] = float(f'{mcnemar_two_sided(n10, n01):.4g}')
out['descriptive_agreement_with_exploratory_bf16'] = ag
out['descriptive_copying_diff_bf16_minus_QAT'] = copy_diff('CLI', 'QAT')
A_ok = out['copying']['CLI']['CI'][0] > 0
B_ok = B_['mcnemar_one_sided_p_RD_lt_0'] < 0.05 and B_['RD'] < 0
out['verdict_A'] = 'COPYING WITHOUT QUANTIZATION' if A_ok else 'NOT DETECTED'
out['verdict_B'] = 'QAT AMPLIFIES COPYING' if B_ok else 'NOT SHOWN'
json.dump(out, open(a.out, 'w'), indent=1)
print(json.dumps({k: out[k] for k in ('verdict_A', 'verdict_B', 'copying', 'B_bf16_P1_vs_QAT_P1', 'missing')}, indent=1))
