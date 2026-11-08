"""PREREG_v2.7 §4 registered DESCRIPTIVE quantity omitted by the frozen analyze_v27_robustness.py (f68bc12d): the pooled
900-sample-per-arm estimate over C1 + RSA + RSB. Computed afterwards (2026-11-06, after R2 review M9) with the frozen
script's definitions copied verbatim (load, y, task-cluster multinomial bootstrap B = 2000, seed 20261106); logged in
PREREG_DEVIATIONS (v2.7). usage: v27_pooled_retest.py --out <json>"""
import os  # added by the repo export (paths are env/config driven)
import json, argparse
import numpy as np
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); a = ap.parse_args()
FILES = {'C1': f'{D}/out/main/rC31b_v2.jsonl', 'RSA': f'{D}/out/main/rSA_v27.jsonl', 'RSB': f'{D}/out/main/rSB_v27.jsonl'}
META = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/confirmatory/meta_S1.jsonl')}
ids = [json.loads(l)['context_id'] for l in open(f'{D}/data/confirmatory/pools/S1_A1.jsonl')]
ARMS = [('P0', 0), ('P1', 1), ('P6', 1), ('P8a', 1)]
def load(f):  # verbatim
    R = {}
    for l in open(f):
        try: d = json.loads(l)
        except Exception: continue
        if not d.get('error') and (d['pathway'], d['k']) in ARMS: R[(d['id'], d['pathway'])] = d
    return R
def y(d):  # verbatim
    j = d.get('judge') or {}; e = bool(j.get('is_edit', j.get('name') == 'edit_file')); return int(e and bool(j.get('malformed')))
R = {c: load(f) for c, f in FILES.items()}
Y = {c: {(i, p): y(d) for (i, p), d in R[c].items()} for c in R}
cl = sorted(set(META[i]['task'] for i in ids)); ci_ = {c: j for j, c in enumerate(cl)}
rng = np.random.default_rng(20261106); W = rng.multinomial(len(cl), np.full(len(cl), 1 / len(cl)), size=2000).astype(float)
def pct(x): x = x[np.isfinite(x)]; return [round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4)]
def vec(arm, runs):
    S = np.zeros(len(cl)); N = np.zeros(len(cl))
    for c in runs:
        for i in ids:
            if (i, arm) in Y[c]: S[ci_[META[i]['task']]] += Y[c][(i, arm)]; N[ci_[META[i]['task']]] += 1
    return S, N
runs = ['C1', 'RSA', 'RSB']; out = {'runs': runs, 'B': 2000, 'seed': 20261106, 'pooled': {}}
V = {p: vec(p, runs) for p, _ in ARMS}
for p, _ in ARMS:
    S, N = V[p]; out['pooled'][p] = [round(S.sum() / N.sum(), 4)] + pct((W @ S) / (W @ N)) + [int(N.sum())]
(S1, N1), (S8, _), (S0, _) = V['P1'], V['P8a'], V['P0']
r1, r8, r0 = (W @ S1) / (W @ N1), (W @ S8) / (W @ N1), (W @ S0) / (W @ N1)
den = r1 - r0; rem = np.where(den > 0, (r1 - r8) / np.where(den > 0, den, 1), np.nan)
e1, e8, e0 = S1.sum() / N1.sum(), S8.sum() / N1.sum(), S0.sum() / N1.sum()
out['pooled_removal'] = {'point': round(float((e1 - e8) / (e1 - e0)), 4), 'CI': pct(rem)}
out['pooled_copying_RD'] = [round(float(e1 - e0), 4)] + pct(r1 - r0)
json.dump(out, open(a.out, 'w'), indent=1); print(json.dumps(out, indent=1))
