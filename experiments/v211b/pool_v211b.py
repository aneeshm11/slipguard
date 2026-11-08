"""PREREG_v2.11b (descriptive). P1 counts on the 43 affected / 257 unaffected states across six runs; pooled masked vs
unmasked same-seed. Uses analyze_v211_masked.py's indicator by importing nothing: it reads that script's two outputs and,
for the v2.7 seed sets, their registered analysis JSON if present. usage: pool_v211b.py --out <json>"""
import argparse, json, os
P = '.'; C = P + '/experiments/contagion/out/confirmatory/'
ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); a = ap.parse_args()
r1 = json.load(open(C + 'v211_masked_analysis.json')); r2 = json.load(open(C + 'v211b_masked_analysis.json'))
def p1(r, who, grp): return r[f'descriptive_{grp}_states'][who]['P1']
out = {'prereg': 'PREREG_v2.11b_masked_replicate.md (descriptive; v2.11 verdict unchanged)', 'runs': {}}
for name, r, who in (('masked_1', r1, 'CLI'), ('masked_2', r2, 'CLI'), ('C1', r1, 'QAT'), ('v2.8', r1, 'V28')):
    a43, u257 = p1(r, who, 'affected'), p1(r, who, 'unaffected')
    out['runs'][name] = {'P1_affected': a43, 'P1_unaffected': u257, 'P1_all': [a43[0] + u257[0], 300],
                         'P1_rate': round((a43[0] + u257[0]) / 300, 4)}
out['runs']['masked_2']['copying'] = r2['copying']['CLI']; out['runs']['masked_2']['removal'] = r2['removal_not_gated']['CLI']
out['runs']['masked_2']['replicate_condition_check_not_a_verdict'] = r2['verdict']
pm = sum(out['runs'][k]['P1_all'][0] for k in ('masked_1', 'masked_2')); pu = sum(out['runs'][k]['P1_all'][0] for k in ('C1', 'v2.8'))
out['pooled'] = {'masked_P1': [pm, 600, round(pm / 600, 4)], 'unmasked_same_seed_P1': [pu, 600, round(pu / 600, 4)],
                 'affected_masked': sum(out['runs'][k]['P1_affected'][0] for k in ('masked_1', 'masked_2')),
                 'affected_unmasked': sum(out['runs'][k]['P1_affected'][0] for k in ('C1', 'v2.8')),
                 'unaffected_masked': sum(out['runs'][k]['P1_unaffected'][0] for k in ('masked_1', 'masked_2')),
                 'unaffected_unmasked': sum(out['runs'][k]['P1_unaffected'][0] for k in ('C1', 'v2.8'))}
out['unmasked_P1_range_reference'] = {'C1': 0.1967, 'v2.8': out['runs']['v2.8']['P1_rate'], 'v2.7_seedA': 0.2000, 'v2.7_seedB': 0.2033}
m2 = out['runs']['masked_2']; aff_lo = min(out['runs']['C1']['P1_affected'][0], out['runs']['v2.8']['P1_affected'][0])
if 0.193 <= m2['P1_rate'] <= 0.2033 and m2['P1_affected'][0] >= aff_lo:
    out['reading'] = 'CONSISTENT WITH RUN-TO-RUN NOISE'
elif m2['P1_rate'] <= 0.170:
    out['reading'] = 'DROP REPLICATES'
else:
    out['reading'] = 'INCONCLUSIVE'
json.dump(out, open(a.out, 'w'), indent=1); print(json.dumps(out, indent=1))
