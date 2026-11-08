"""Exact M1/M2/M3 predictions for PREREG_v1.md (workstream D). Pure arithmetic; no data are read.
Anchors: plan anchor (P1k1 = 0.43, P0 = 0.065: A interim 198 contexts) and A's final 31B gate (P1k1 = 0.462, P0 = 0.057;
300 contexts, 11:25 UTC); interim P6(k=1) = 0.286 (70 edits, 11:30 UTC).
M1 recency-1 template copying: dlogit(k) = 0.  M2 exemplar urn: dlogit(k) = beta*log k, beta = 1.05 (observational MR) [and
beta = 1 (pure count urn) as a band].  M3 Bayesian accumulation: dlogit(k) = (k-1)*D1, D1 = logit P(k=1) - logit P0."""
import os  # added by the repo export (paths are env/config driven)
import math, json
lg = lambda p: math.log(p / (1 - p)); sg = lambda x: 1 / (1 + math.exp(-x))
out = {}
for name, p1, p0 in (('plan_anchor', 0.43, 0.065), ('final_gate_31B', 0.462, 0.057), ('P6_interim', 0.286, 0.057)):
    D1 = lg(p1) - lg(p0); row = {'P1(k=1)': p1, 'P0': p0, 'D1=logit p1 - logit p0': round(D1, 4)}
    for k in (2, 4):
        row[f'M1 k={k}'] = round(p1, 4)
        row[f'M2(beta=1.05) k={k}'] = round(sg(lg(p1) + 1.05 * math.log(k)), 4)
        row[f'M2(beta=1.00) k={k}'] = round(sg(lg(p1) + 1.00 * math.log(k)), 4)
        row[f'M3 k={k}'] = round(sg(lg(p1) + (k - 1) * D1), 4)
    row['dlogit M2(1.05) k=2,4'] = [round(1.05 * math.log(2), 4), round(1.05 * math.log(4), 4)]
    row['dlogit M3 k=2,4'] = [round(D1, 4), round(3 * D1, 4)]
    out[name] = row
# decision-region boundaries on dlogit(k=2): midpoints between mechanism predictions (gate anchor)
D1g = out['final_gate_31B']['D1=logit p1 - logit p0']
out['regions_dlogit_k2'] = {'M1|M2 boundary': round(1.05 * math.log(2) / 2, 4), 'M2|M3 boundary': round((1.05 * math.log(2) + D1g) / 2, 4)}
# power: SE of a paired logit difference at p~0.46 with n~260 edits per arm (independent-arm upper bound)
n, p = 260, 0.462
se1 = 1 / math.sqrt(n * p * (1 - p)); out['power'] = {'SE logit per arm': round(se1, 4), 'SE dlogit (unpaired bound)': round(math.sqrt(2) * se1, 4),
                                                       'M1 vs M2 separation in SE': round(0.7278 / (math.sqrt(2) * se1), 2)}
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/predictions_v1.json'), 'w'), indent=1)
