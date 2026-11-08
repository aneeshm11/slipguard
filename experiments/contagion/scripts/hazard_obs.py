"""Observational discrete-time hazard model of edit_file malformation (plain base 31B), read-only over the index.

logit P(bad_t) = b0 + b1*prev_bad + b2*log1p(n_prior_bad) + b3*retry_of_prev + b4*prev_bad*retry + b5*first_edit
                 + b6*log1p(position) + b7*temp_hi + run fixed effects
Unpenalised logistic regression; 95% CIs from an attempt-cluster bootstrap. A second fit adds the attempt's
*eventual* number of malformed edits among its FUTURE edits as a crude proxy for latent attempt difficulty (sensitivity
check: the self-exciting terms should survive if contagion is not just attempt heterogeneity).
usage: hazard_obs.py index.jsonl out.json
"""
import json, sys, collections, random, math
import numpy as np
from sklearn.linear_model import LogisticRegression
random.seed(0); np.random.seed(0)
idx, outp = sys.argv[1], sys.argv[2]
att = collections.defaultdict(list)
for l in open(idx):
    r = json.loads(l)
    if r.get('bad_line') or r['teacher'] or r['model'] != 'openai/gemma-4-31b-it-qat-w4a16-ct': continue
    for c in r['calls']:
        if c['name'] == 'edit_file':
            att[r['task']].append((r['ln'], c['bad_syn'], c.get('fp'), c.get('nh'), r['run'], r['temp']))
runs = sorted(set(e[4] for v in att.values() for e in v))
rows = []; groups = []
for a, v in att.items():
    v.sort()
    nb = 0
    for i, e in enumerate(v):
        prev_bad = v[i - 1][1] if i > 0 else 0
        retry = int(i > 0 and e[2] == v[i - 1][2] and e[3] == v[i - 1][3])
        future_bad = sum(x[1] for x in v[i + 1:])
        x = [prev_bad, math.log1p(nb), retry, prev_bad * retry, int(i == 0), math.log1p(i), int((e[5] or 0) > 0.5)]
        x += [int(e[4] == r) for r in runs[1:]]
        rows.append((x, e[1], math.log1p(future_bad))); groups.append(a)
        nb += e[1]
names = ['prev_bad', 'log1p_n_prior_bad', 'retry_of_prev', 'prev_bad_x_retry', 'first_edit', 'log1p_position', 'temp_0.7plus'] + ['run=' + r for r in runs[1:]]
X = np.array([r[0] for r in rows], float); y = np.array([r[1] for r in rows]); F = np.array([r[2] for r in rows])[:, None]
G = np.array(groups)


def fit(Xm, ym):
    m = LogisticRegression(penalty=None, max_iter=5000)
    m.fit(Xm, ym); return np.concatenate([m.intercept_, m.coef_[0]])


out = {'n_edits': int(len(y)), 'n_attempts': int(len(att)), 'malformed_rate': float(y.mean())}
uniq = np.array(sorted(set(groups))); gi = {g: np.where(G == g)[0] for g in uniq}
for label, Xm, nm in (('hazard', X, names), ('hazard_plus_future_bad_proxy', np.hstack([X, F]), names + ['log1p_future_bad'])):
    b = fit(Xm, y)
    bs = []
    for _ in range(200):
        samp = np.random.choice(uniq, len(uniq), replace=True)
        ii = np.concatenate([gi[s] for s in samp])
        try: bs.append(fit(Xm[ii], y[ii]))
        except Exception: pass
    bs = np.array(bs)
    out[label] = {n: {'coef': round(float(b[j + 1]), 3), 'odds_ratio': round(float(np.exp(b[j + 1])), 3),
                      'OR_CI95': [round(float(np.exp(np.percentile(bs[:, j + 1], 2.5))), 3), round(float(np.exp(np.percentile(bs[:, j + 1], 97.5))), 3)]}
                  for j, n in enumerate(nm) if not n.startswith('run=')}
    out[label]['intercept'] = round(float(b[0]), 3); out[label]['n_boot'] = int(len(bs))
json.dump(out, open(outp, 'w'), indent=1)
print(json.dumps(out, indent=1))
