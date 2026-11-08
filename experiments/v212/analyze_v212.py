"""PREREG_v2.12 verdict (frozen with PREREG_v2.12_llama_family.md before any v2.12 job). Reads the analysis.json that
`transcriptlab report` wrote with X's frozen analyze.py; applies the Table 3 rule; run once.
usage: analyze_v212.py --run experiments/transcriptlab_cli/run_v212_hermes3 --out <json>"""
import argparse, json, os
ap = argparse.ArgumentParser(); ap.add_argument('--run', required=True); ap.add_argument('--out', required=True); a = ap.parse_args()
p = os.path.join(a.run, 'analysis.json')
if not os.path.exists(p):
    out = {'verdict': 'NOT RUN / no analysis.json'}
else:
    ana = json.load(open(p)); pv = ana.get('paired_vs_P0') or {}
    cp, im = pv.get('P1L', {}).get('uncond', {}), pv.get('P6', {}).get('uncond', {})
    lo = lambda d: (d.get('RD_CI') or [None])[0]
    need = (lo(cp) is not None and lo(cp) > 0) or (lo(im) is not None and lo(im) > 0)
    out = {'prereg': 'PREREG_v2.12_llama_family.md (sha256 in PROGRESS.md at freeze)', 'copying_RD': [cp.get('RD'), cp.get('RD_CI')],
           'imitation_RD': [im.get('RD'), im.get('RD_CI')], 'removal_P8a': (ana.get('removal') or {}).get('P8a'),
           'n_records': ana.get('n_records'), 'errors': ana.get('errors'),
           'verdict': 'HISTORY-SENSITIVE' if need else 'NOT HISTORY-SENSITIVE (not detected)'}
json.dump(out, open(a.out, 'w'), indent=1); print(json.dumps(out, indent=1))
