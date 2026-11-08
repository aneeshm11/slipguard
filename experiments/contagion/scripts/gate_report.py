"""Gate report for the 31B gate set (random 300 contexts): runs analyze_injection.py restricted to the gate ids and
prints a compact summary (rates with Wilson CIs, paired ratio/differences with attempt-cluster bootstrap CIs, quarantine
removal fractions, retry/other decomposition, emitted order).
usage: gate_report.py <model_prefix e.g. r31b_old> <ids file> <label> [B]"""
import json, sys, glob, subprocess, os
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_agentpaper/bin/python')
pref, idsf, label = sys.argv[1], sys.argv[2], sys.argv[3]; B = sys.argv[4] if len(sys.argv) > 4 else '2000'
files = sorted(glob.glob(f'{D}/out/main/{pref}_*.jsonl'))
enr = f'{D}/out/enrich_{label}.json'
subprocess.run([PY, f'{D}/scripts/enrich_contexts.py', f'{D}/data/contexts_meta.jsonl', idsf, enr], check=True, capture_output=True)
outp = f'{D}/out/gate_{label}.json'
r = subprocess.run([PY, f'{D}/scripts/analyze_injection.py', '--res', *files, '--out', outp, '--enrich', enr, '--ids', idsf,
                    '--arms', 'P0k0,P1k1,P2k1,P3k1,P4k1,P5k1', '--B', B, '--label', label], capture_output=True, text=True)
if r.returncode: print(r.stderr[-2000:]); sys.exit(1)
d = json.load(open(outp))
f = lambda w: 'NA' if w[0] is None else '%.1f%% [%.1f, %.1f] (n=%d)' % (100 * w[0], 100 * w[1], 100 * w[2], w[3])
print(f'{label}: files={len(files)} contexts={d["n_contexts"]} records={d["n_records"]}')
def kn(w):
    return (0, 0) if not w or w[0] is None else (round(w[0] * w[3]), w[3])
for arm, v in d['arms'].items():
    mc = v['malformed_by_edit_class']
    rk, rn = kn(mc.get('retry_most_recent')); ok_, on = kn(mc.get('other')); tk, tn = kn(mc.get('target')); ok2, on2 = kn(mc.get('retry_older'))
    print(f'  {arm}: P(edit) {f(v["P_edit"])} | P(malformed|edit) {f(v["P_malformed_given_edit"])} | P(malformed edit) {f(v["P_malformed_edit_uncond"])}'
          f' | malformed among: retry-of-replaced {rk}/{rn}, older-retry {ok2}/{on2}, logged-target {tk}/{tn}, other {ok_}/{on} | order {v["edit_order"]}')
for arm, v in d['paired_vs_P0'].items():
    c = v['cond']; u = v['uncond']
    print(f'  paired {arm} vs P0 (cond on edit): {c["arm"]:.4f} vs {c["base"]:.4f} diff {c["diff"]:+.4f} CI {c["diff_CI"]} ratio {c["ratio"]} CI {c["ratio_CI"]} [boot inf {c["ratio_boot_inf_frac"]}, undef {c["ratio_boot_undefined_frac"]}] (n_ctx {c["n_contexts"]}, attempts {c["n_attempts"]}) | uncond diff {u["diff"]:+.4f} CI {u["diff_CI"]} ratio {u["ratio"]} CI {u["ratio_CI"]}')
for q, v in d['quarantine_removal'].items():
    c = v['cond']; print(f'  removal {q}: P1 {c["P1"]:.4f} Q {c["Q"]:.4f} P0 {c["P0"]:.4f} -> fraction removed {c["fraction_removed"]} CI {c["CI"]} (n {c["n_contexts"]})')
print('  GATE', json.dumps(d['gate']))
print('  replay fidelity', json.dumps(d.get('replay_fidelity_P0')))
