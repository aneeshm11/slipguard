"""PREREG_v2.8_cli analysis: does the released TranscriptLab CLI reproduce C1? Written and hash-frozen with
paper/protocol_theory/prereg/PREREG_v2.8_cli.md BEFORE the first v2.8 job; run once after the CLI run (and its resume
pass) completed. The statistics block below is copied VERBATIM from analyze_v27_robustness.py (frozen f68bc12d).
usage: analyze_v28_cli.py --cli_gen <run_dir>/gen.jsonl --out <json> [--B 2000]"""
import json, sys, os, math, argparse, collections
import numpy as np
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser(); ap.add_argument('--cli_gen', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--B', type=int, default=2000)
a = ap.parse_args()
FILES = {'CLI': a.cli_gen, 'QAT': f'{D}/out/main/rC31b_v2.jsonl'}
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


out = {'prereg': 'PREREG_v2.8_cli.md (sha256 in PROGRESS.md at freeze)', 'B': a.B,
       'missing': {c: {p: sum(1 for i in ids if (i, p) not in Y[c]) for p, _ in ARMS} for c in Y},
       'servers': {c: dict(collections.Counter(d.get('server') for d in R[c].values())) for c in R},
       'temps': {c: dict(collections.Counter(d.get('temp') for d in R[c].values())) for c in R}}
out['rates'] = {c: {p: rate(c, p) for p, _ in ARMS} for c in Y}
out['copying'] = {c: flip(c) for c in ('CLI', 'QAT')}
out['induction'] = {c: induction(c) for c in ('CLI', 'QAT')}
out['removal'] = {c: removal(c) for c in ('CLI', 'QAT')}
p1 = contrast('CLI', 'P1', 'QAT', 'P1')
n10, n01 = p1['discordant_B_only_A_only']
p1['mcnemar_two_sided_p'] = float(f'{mcnemar_two_sided(n10, n01):.4g}')
out['P1_CLI_vs_C1'] = p1
A1 = set(ids); both = [k for k in R['CLI'] if k in R['QAT'] and k[0] in A1]  # the 300 S1_A1 states x 4 arms only
same_y = sum(1 for k in both if Y['CLI'][k] == Y['QAT'][k])
txt = lambda d: (d.get('s1_text') or '') + '\x00' + (d.get('s2_text') or '')
same_t = sum(1 for k in both if txt(R['CLI'][k]) == txt(R['QAT'][k]))
out['job_agreement'] = {'n_jobs_both': len(both), 'same_judged_outcome': [same_y, round(same_y / len(both), 4) if both else None],
                        'identical_generated_text': [same_t, round(same_t / len(both), 4) if both else None]}
C1_CI = [0.1361, 0.2316]
rd = out['copying']['CLI']['RD_P1_minus_P0']; rm = out['removal']['CLI']['point']
cond = {'a_copying_in_C1_CI': C1_CI[0] <= rd <= C1_CI[1], 'b_removal_ge_0.90': rm is not None and rm >= 0.90,
        'c_P1_mcnemar_two_sided_p_ge_0.05': p1['mcnemar_two_sided_p'] >= 0.05}
out['conditions'] = cond
out['verdict'] = 'CLI REPRODUCES' if all(cond.values()) else 'DOES NOT REPRODUCE: ' + ', '.join(k for k, v in cond.items() if not v)
json.dump(out, open(a.out, 'w'), indent=1)
print(json.dumps({'verdict': out['verdict'], 'conditions': cond, 'copying': out['copying'], 'removal': out['removal'],
                  'P1_CLI_vs_C1': p1, 'job_agreement': out['job_agreement']}, indent=1))
