"""PREREG_v2.10 verdicts (frozen with PREREG_v2.10_audit_breadth.md before any v2.10 audit). Reads the shipped
audit-weights reports; run once after run_audits.sh.  usage: analyze_v210.py --out <json>"""
import argparse, json, os
O = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa/out')
NAMES = ['31b_qatawq_cyankiwi', '31b_nvfp4_nvidia', '31b_bnb4_unsloth', '31b_nvfp4_unsloth', '31b_qatnvfp4_melcheikh']
ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); a = ap.parse_args()
res = {}
for n in NAMES:
    p = f'{O}/audit_v210_{n}.json'
    if not os.path.exists(p):
        res[n] = {'status': 'NOT SERVABLE or not run (see experiments/v210/run_audits.log)'}; continue
    d = json.load(open(p)); s = d['summary']
    res[n] = {'median_deficit_vs_bf16': d['paired_vs_reference']['median_deficit'], 'P_m_lt_ln19': s['P_m_lt_ln19'],
              'E_slip': s['E_slip'], 'censored_frac': s['censored_frac'], 'FLAG': d['FLAG'], 'SEVERE': d['SEVERE']}
q = res['31b_qatawq_cyankiwi'].get('median_deficit_vs_bf16')
hq = 'NOT RUN' if q is None else 'SUPPORTED' if q[0] >= 3 else 'NOT SUPPORTED' if q[2] < 3 else 'INCONCLUSIVE'
out = {'prereg': 'PREREG_v2.10_audit_breadth.md (sha256 in PROGRESS.md at freeze)', 'checkpoints': res, 'H_QAT': hq}
json.dump(out, open(a.out, 'w'), indent=1); print(json.dumps(out, indent=1))
