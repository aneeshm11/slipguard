"""PREREG_v2.9 verdicts (frozen with PREREG_v2.9_gemma_coverage.md before any v2.9 job). Reads the analysis.json that
`transcriptlab report` wrote with the frozen analyze_bf16_core.py; applies the Table 3 rule; run once.
usage: analyze_v29_coverage.py --runs experiments/transcriptlab_cli/run_e2b experiments/transcriptlab_cli/run_e4b16 --out <json>"""
import argparse, json, os
ap = argparse.ArgumentParser(); ap.add_argument('--runs', nargs='+', required=True); ap.add_argument('--out', required=True)
a = ap.parse_args()
out = {'prereg': 'PREREG_v2.9_gemma_coverage.md (sha256 in PROGRESS.md at freeze)', 'runs': {}}
for d in a.runs:
    p = os.path.join(d, 'analysis.json')
    if not os.path.exists(p):
        out['runs'][d] = {'verdict': 'NOT RUN / no analysis.json'}; continue
    u = json.load(open(p))['uncond']
    cp, ind = u['RD_P1_P0'], u['RD_P6_P0']   # [point, lo, hi]
    need = cp[1] > 0 or ind[1] > 0
    r = {'copying_RD': cp, 'induction_RD': ind, 'rates': {k: u.get(k) for k in ('P0', 'P1', 'P6', 'P8a')},
         'verdict': 'NEEDS A GUARD' if need else 'NO GUARD NEEDED (not detected)'}
    if cp[1] > 0:
        r['quarantine_removal'] = u.get('P8a_removal')
    out['runs'][d] = r
json.dump(out, open(a.out, 'w'), indent=1); print(json.dumps(out, indent=1))
