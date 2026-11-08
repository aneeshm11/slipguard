"""PREREG_v2 (paper/protocol_theory/prereg/PREREG_v2.md, sha256 5da75e61...0d73ac) decisions for workstream X on
workstream P's public corpus. Reads the per-model analyses produced by analyze.py --manifest on the pool-A1 battery
(+ pool-B1 census), full sample and halves H1 (pool ranks 1-150) / H2 (151-300).

Rules (PREREG_v2 §3 "Outcome rules", §3.3, §3.4, §5), applied verbatim:
  RD claims (X1 theta_D = 12 / 10 / 10 pp for Qwen3-32B / Qwen3-8B / Qwen3.5-9B; X2 theta_D = 5; X4 theta_D = 5):
    GENERALIZES iff CI_lo > 0 and theta_C >= 0.5 theta_D; PARTIAL iff CI_lo > 0 and theta_C < 0.5 theta_D;
    FAILS iff CI_lo <= 0.   (unconditional RD, episode-cluster bootstrap 95% CI)
  X3 removal (P5 and P8a): GENERALIZES iff removal >= 0.70 with CI_lo >= 0.50; PARTIAL iff removal >= 0.40 with
    CI_lo > 0 (and not the former); FAILS otherwise.
  X5 census malformed edit (B1, base decoding) predicted <= 2%: CONSISTENT iff the observed 95% CI overlaps [0, 2%];
    otherwise HIGHER (descriptive).
  "Generalizes across families" iff X1 GENERALIZES in >= 2 of 3 Qwen models.
  F2c Holm family: X1 per model (H: RD(P1L-P0) > 0) and X3-P5 per model (H: RD(P1L-P5) > 0); adjusted p reported
    beside the labels (the labels themselves are the §3 CI rules).
usage: combine_v2.py out/v2/results_v2.json [ana_dir=out/v2]   (expects <ana_dir>/ana_<mk>[_H1|_H2].json)
"""
import json
import os
import sys

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = {'qwen3-32b': 12.0, 'qwen3-8b': 10.0, 'qwen3.5-9b': 10.0}   # X1 theta_D in pp
THETA = {'X2': 5.0, 'X4': 5.0}
PREREG_V2_SHA256 = '5da75e6170243f838fe0fe1dcb4250a21b8132fc97161e22d149f46fae0d73ac'


def load(p):
    p = os.path.join(X, p)
    return json.load(open(p)) if os.path.exists(p) else None


def num(x):
    return None if x is None else (float('inf') if x == 'inf' else float(x))


def rd_rule(u, theta_pp):
    if not u:
        return None
    lo = num(u['RD_CI'][0]); th = 100 * u['RD']
    lab = 'FAILS' if (lo is None or lo <= 0) else ('GENERALIZES' if th >= 0.5 * theta_pp else 'PARTIAL')
    return {'label': lab, 'RD_pp': round(th, 2), 'CI_pp': [None if v is None else round(100 * num(v), 2) for v in u['RD_CI']],
            'theta_D_pp': theta_pp, 'arm': u['arm'], 'base': u['base'], 'p_one_sided': u['p_one_sided_RD_gt_0']}


def removal_rule(r):
    if not r or r.get('fraction_removed') is None:
        return {'label': 'FAILS', 'note': 'no P1L excess (fraction undefined)', 'detail': r}
    f = r['fraction_removed']; lo = num(r['CI'][0])
    if f >= 0.70 and lo is not None and lo >= 0.50:
        lab = 'GENERALIZES'
    elif f >= 0.40 and lo is not None and lo > 0:
        lab = 'PARTIAL'
    else:
        lab = 'FAILS'
    return {'label': lab, 'fraction_removed': f, 'CI': r['CI'], 'p_removal_gt_0': r.get('p_one_sided_removal_gt_0')}


def holm(pv):
    items = sorted(pv.items(), key=lambda kv: kv[1]); m = len(items); out = {}; run = 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p)); out[k] = round(run, 6)
    return out


ANA = sys.argv[2] if len(sys.argv) > 2 else 'out/v2'
res = {'prereg': 'PREREG_v2', 'prereg_sha256': PREREG_V2_SHA256, 'ana_dir': ANA, 'models': {}}
P = {}
for mk, th1 in MODELS.items():
    an = load(f'{ANA}/ana_{mk}.json')
    if not an:
        continue
    pv = an.get('paired_vs_P0') or {}; rm = an.get('removal') or {}
    m = {'n_contexts': (pv.get('P1L') or {}).get('n_contexts'),
         'X1': rd_rule((pv.get('P1L') or {}).get('uncond'), th1),
         'X2': rd_rule((pv.get('P1N') or {}).get('uncond'), THETA['X2']),
         'X3_P5': removal_rule((rm.get('P5') or {}).get('uncond')),
         'X3_P8a': removal_rule((rm.get('P8a') or {}).get('uncond')),
         'X4': rd_rule((pv.get('P6') or {}).get('uncond'), THETA['X4']),
         'conditional': {k: (v or {}).get('cond') for k, v in pv.items()}}
    c0 = (an.get('arms') or {}).get('C0')
    if c0:
        w = c0['P_malformed_edit_uncond']
        m['X5'] = {'label': 'CONSISTENT' if (w[1] is not None and w[1] <= 0.02) else 'HIGHER', 'census_malformed_edit': w,
                   'P_malformed_given_edit': c0['P_malformed_given_edit']}
    for half in ('H1', 'H2'):
        h = load(f'{ANA}/ana_{mk}_{half}.json')
        if h:
            hp = h.get('paired_vs_P0') or {}
            m[half] = {'X1': rd_rule((hp.get('P1L') or {}).get('uncond'), th1), 'X4': rd_rule((hp.get('P6') or {}).get('uncond'), THETA['X4']),
                       'X3_P5': removal_rule(((h.get('removal') or {}).get('P5') or {}).get('uncond'))}
    if m['X1']:
        P[f'{mk}:X1'] = m['X1']['p_one_sided']
    if (rm.get('P5') or {}).get('uncond'):
        P[f'{mk}:X3_P5'] = rm['P5']['uncond']['p_one_sided_removal_gt_0']
    res['models'][mk] = m
res['F2c_holm'] = {'raw': P, 'adjusted': holm(P), 'n_tests': len(P)}
for mk, m in res['models'].items():
    for k in ('X1', 'X3_P5'):
        if m.get(k):
            m[k]['holm_adjusted_p'] = res['F2c_holm']['adjusted'].get(f'{mk}:{k}')
n_gen = sum(1 for m in res['models'].values() if (m.get('X1') or {}).get('label') == 'GENERALIZES')
res['generalizes_across_families'] = {'X1_GENERALIZES_in': n_gen, 'of': len(res['models']), 'claim': n_gen >= 2 and len(res['models']) == 3}
os.makedirs(os.path.dirname(os.path.join(X, sys.argv[1])), exist_ok=True)
json.dump(res, open(os.path.join(X, sys.argv[1]) if not os.path.isabs(sys.argv[1]) else sys.argv[1], 'w'), indent=1)
print(json.dumps({mk: {k: (v or {}).get('label') for k, v in m.items() if k.startswith('X')} for mk, m in res['models'].items()}, indent=1))
print(json.dumps(res['generalizes_across_families']), json.dumps(res['F2c_holm']))
