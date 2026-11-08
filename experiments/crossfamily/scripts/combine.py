"""Combine per-model analyses into the pre-registered decisions (prereg.md §5-§7) and results.json.
F2 family (Holm): per Qwen model m, H1_m: RD_uncond(P1L - P0) > 0 and H2_m: RD_uncond(P1L - P5) > 0 (one-sided
attempt-cluster bootstrap p-values from analyze.py).
Success rule per model (UPGRADE_PLAN §P0-X, operationalised in prereg.md):
  S1  RD_uncond(P1L - P0) >= +0.10 and Holm-adjusted p(H1_m) < 0.05
  S2  P0 events >= 5: ratio P1L/P0 >= 3 with bootstrap CI_lo > 1; P0 events < 5: Haldane ratio >= 3 and exact one-sided
      McNemar p < 0.05
  S3  P5 removes >= 50% of the P1L excess (point estimate, unconditional) and Holm-adjusted p(H2_m) < 0.05
  loop is CROSS-FAMILY iff S1 and S2 and S3 hold in >= 1 Qwen model.
usage: combine.py out/results_x.json
"""
import json
import os
import sys

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = ['qwen3-8b', 'qwen3-32b', 'qwen3.5-9b']


def load(p):
    p = os.path.join(X, p)
    return json.load(open(p)) if os.path.exists(p) else None


def holm(pvals):
    """pvals: {key: p} -> {key: adjusted p}"""
    items = sorted(pvals.items(), key=lambda kv: kv[1]); m = len(items); adj = {}; run = 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p)); adj[k] = round(run, 6)
    return adj


def num(x):
    return float('inf') if x == 'inf' else (None if x is None else float(x))


res = {'models': {}, 'F2_holm': {}, 'format': None}
P = {}
for mk in MODELS:
    an = load(f'out/ana_{mk}.json')
    if not an or 'P1L' not in (an.get('paired_vs_P0') or {}):
        continue
    pr = an['paired_vs_P0']['P1L']['uncond']; rm = (an['removal'].get('P5') or {}).get('uncond') or {}
    P[(mk, 'H1')] = pr['p_one_sided_RD_gt_0']
    if rm:
        P[(mk, 'H2')] = rm['p_one_sided_removal_gt_0']
    res['models'][mk] = {'P1L_vs_P0': pr, 'P5_removal': rm, 'n_contexts': an['paired_vs_P0']['P1L']['n_contexts'],
                         'events_P0': an['paired_vs_P0']['P1L']['events_base'], 'arms': {k: v['P_malformed_edit_uncond'] for k, v in an['arms'].items()},
                         'arms_cond': {k: v['P_malformed_given_edit'] for k, v in an['arms'].items()},
                         'P_edit': {k: v['P_edit'] for k, v in an['arms'].items()}}
adj = holm({f'{k[0]}:{k[1]}': v for k, v in P.items()})
res['F2_holm'] = {'raw': {f'{k[0]}:{k[1]}': v for k, v in P.items()}, 'adjusted': adj, 'n_tests': len(P)}
any_pass = False
for mk, r in res['models'].items():
    pr = r['P1L_vs_P0']; rm = r['P5_removal']
    s1 = pr['RD'] >= 0.10 and adj.get(f'{mk}:H1', 1) < 0.05
    if r['events_P0'] >= 5:
        lo = num(pr['ratio_CI'][0]); rat = num(pr['ratio']) if pr['ratio'] is not None else None
        s2 = bool(rat is not None and rat >= 3 and lo is not None and lo > 1); s2_mode = 'bootstrap_ratio'
    else:
        s2 = pr['ratio_haldane'] >= 3 and pr['mcnemar_exact_p_one_sided'] < 0.05; s2_mode = 'haldane+exact_mcnemar (P0 events < 5)'
    fr = rm.get('fraction_removed') if rm else None
    s3 = bool(fr is not None and fr >= 0.5 and adj.get(f'{mk}:H2', 1) < 0.05)
    r['rule'] = {'S1': bool(s1), 'S2': bool(s2), 'S2_mode': s2_mode, 'S3': s3, 'PASS': bool(s1 and s2 and s3)}
    any_pass = any_pass or r['rule']['PASS']
    an = load(f'out/ana_{mk}.json')
    sec = {}
    p6 = (an['paired_vs_P0'].get('P6') or {}).get('uncond')
    if p6:
        sec['P6_induction_RD_ge_5pp_CI_lo_gt_0'] = bool(p6['RD'] >= 0.05 and (num(p6['RD_CI'][0]) or 0) > 0); sec['P6'] = p6
    p8 = (an['removal'].get('P8a') or {}).get('uncond')
    if p8:
        lo = num(p8['CI'][0])
        sec['P8a_removes_ge_70pct_CI_lo_ge_50pct'] = bool(p8['fraction_removed'] is not None and p8['fraction_removed'] >= 0.7 and lo is not None and lo >= 0.5)
        sec['P8a'] = p8
    p1n = (an['paired_vs_P0'].get('P1N') or {}).get('uncond')
    if p1n:
        sec['P1N_vs_P0'] = p1n
    ho = load(f'out/ana_{mk}_heldout.json')
    if ho and 'P1L' in (ho.get('paired_vs_P0') or {}):
        h = ho['paired_vs_P0']['P1L']['uncond']
        sec['heldout_P1L_vs_P0'] = h; sec['heldout_replicates_CI_lo_gt_0'] = bool((num(h['RD_CI'][0]) or 0) > 0)
        if 'P6' in ho['paired_vs_P0']:
            sec['heldout_P6_vs_P0'] = ho['paired_vs_P0']['P6']['uncond']
    sec['copy_check'] = an.get('copy_check')
    sec['census'] = an['arms'].get('C0')
    r['secondary'] = sec
res['cross_family_loop'] = {'PASS_in_at_least_one_Qwen_model': any_pass, 'models_evaluated': list(res['models'])}
fs = load('format/format_summary.json')
if fs:
    V = fs['variants']

    def share(v, pth, keys):
        row = (V.get(v) or {}).get(pth) or {}
        n = row.get('n') or 0
        k = sum(round((row.get(c) or [0, 0, 0, 0])[0] * n) for c in keys)
        return k, n
    fp = {}
    for v in ('J_bt', 'J_real'):
        k, n = share(v, 'hermes.nonstream', ['loud'])
        fp[f'FP1_{v}_hermes_nonstream_loud'] = {'k': k, 'n': n, 'share': round(k / n, 4) if n else None, 'pass(>=0.95)': bool(n and k / n >= 0.95)}
    for v in ('X_bt', 'X_real'):
        k, n = share(v, 'qwen3_coder.nonstream', ['exact', 'silent_local', 'loud'])
        ka, _ = share(v, 'qwen3_coder.nonstream', ['silent_absorbed'])
        fp[f'FP2_{v}_qwen3coder_resync_or_loud'] = {'k': k, 'n': n, 'share': round(k / n, 4) if n else None, 'absorbed': ka,
                                                    'pass(>=0.5)': bool(n and k / n >= 0.5)}
    k, n = share('G', 'gemma4.nonstream', ['silent_absorbed', 'silent_other', 'silent_local'])
    fp['FP3_gemma_silent'] = {'k': k, 'n': n, 'share': round(k / n, 4) if n else None}
    res['format'] = {'predictions': fp, 'summary_file': 'format/format_summary.json'}
json.dump(res, open(sys.argv[1], 'w'), indent=1)
print(json.dumps({'cross_family': res['cross_family_loop'], 'rules': {m: r['rule'] for m, r in res['models'].items()},
                  'holm': res['F2_holm'], 'format': (res['format'] or {}).get('predictions')}, indent=1))
