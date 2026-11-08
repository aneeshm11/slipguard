"""Assemble results.json from the observational analyses and the per-model injection analyses.

For every model group (all result files of that model pooled; the last non-error record per (context, arm) is used):
  gate_k1 : pathways at k=1 vs P0 on the RANDOM phase-1 sample (data/ids_phase1_random600.txt)
  dose    : dose-response k = 0, 1, 2, 4 per pathway on the nested set of contexts with >= 4 clean prior edits
            (data/ids_dose_k4.txt; a non-random subset: longer attempts)
usage: summarize.py [--B 2000]
"""
import json, os, glob, subprocess, sys, time, argparse
ap = argparse.ArgumentParser(); ap.add_argument('--B', default='2000'); a = ap.parse_args()
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_agentpaper/bin/python')
# Interim-safe groups: only result files of COMPLETED runs. Blind (governed) runs in progress are excluded until they
# finish: 31B dose (r31b_old_D), P9/P8/P4' (r31b_old_A1a), lag-2 (r31b_old_L2), P6k (r31b_old_P6k), held-out, r-dose, A2,
# test-retest; 12B P6/A1/r-dose/NT; E4B P6. Add a file here only after its runner has logged 'finished'.
M = f'{D}/out/main'
COMPLETE = {
    '31b_old': [f'{M}/r31b_old_{x}.jsonl' for x in ('a', 'b', 'A', 'B', 'G', 'P6')],
    '12b_old': [f'{M}/r12b_old_t1.jsonl'],
    'e4b_old': [f'{M}/re4b_old_t1.jsonl'],
    '31b_new': [f'{M}/r31b_new_T.jsonl'],
    '12b_new': [f'{M}/r12b_new_T.jsonl'],
}
EXTRA = json.load(open(f'{D}/data/summarize_extra_complete.json')) if os.path.exists(f'{D}/data/summarize_extra_complete.json') else {}
groups = {g: sorted(set(fs + [f'{M}/{x}' for x in EXTRA.get(g, [])])) for g, fs in COMPLETE.items()}
groups = {g: [f for f in fs if os.path.exists(f)] for g, fs in groups.items()}
groups = {g: fs for g, fs in groups.items() if fs}
ids = set()
for fs in groups.values():
    for f in fs:
        for l in open(f):
            try: ids.add(json.loads(l)['id'])
            except Exception: pass
open(f'{D}/data/ids_all_results.txt', 'w').write('\n'.join(sorted(ids)) + '\n')
enr = f'{D}/data/enrich_all.json'
subprocess.run([PY, f'{D}/scripts/enrich_contexts.py', f'{D}/data/contexts_meta.jsonl', f'{D}/data/ids_all_results.txt', enr], check=True)


def pick(o, keys):
    return {k: o[k] for k in keys if k in o}


res = {'generated_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}
obs = json.load(open(f'{D}/out/observational.json'))
K = ['attempts', 'edits', 'malformed_rate', 'first_edit', 'later_clean_history', 'later_by_prior_bad', 'share_bad_following_bad',
     'malformed_per_onset', 'P_bad_given_prev_bad', 'P_bad_given_prev_ok', 'perm_null_P_bad_given_prev_bad', 'after_first_bad_later_clean_edit',
     'attempts_with_ge1_bad', 'retry_vs_new', 'by_emission_order', 'closers_among_malformed', 'resolve_clean_attempts',
     'resolve_attempts_with_bad', 'cluster_bootstrap_95CI']
res['observational'] = {
    'note': 'Rates: [p, Wilson lo, Wilson hi, n] (edits treated as independent); cluster_bootstrap_95CI resamples attempts (B=1000); '
            "perm null: within-attempt shuffles (1000). SYN = synthesis population ('gemma-4-31b' in model name), which includes "
            'Qwen/DeepSeek teacher runs served under that alias; BASE = plain base gemma-4-31b-it-qat-w4a16-ct only.',
    'SYN_replication': pick(obs['SYN']['synthesis_criterion'], K),
    'BASE_plain_31b_qat': pick(obs['BASE']['synthesis_criterion'], K),
    'BASE_refined_criterion': pick(obs['BASE']['refined_criterion'], ['edits', 'malformed_rate', 'first_edit', 'later_clean_history', 'later_by_prior_bad']),
    'BASE_excluding_run-39': pick(obs['BASE']['excluding_run-39'], ['edits', 'malformed_rate', 'first_edit', 'later_clean_history', 'later_by_prior_bad', 'perm_null_P_bad_given_prev_bad']),
    'BASE_by_temperature': obs['BASE']['by_temperature'],
    'BASE_by_run': obs['BASE']['by_run'],
    'FT_adapters': pick(obs['FT']['synthesis_criterion'], ['attempts', 'edits', 'malformed_rate', 'first_edit', 'later_clean_history', 'later_by_prior_bad', 'perm_null_P_bad_given_prev_bad']),
    'teacher_runs_in_SYN': obs['TEACHER_runs_in_SYN'],
}
if os.path.exists(f'{D}/out/hazard_obs.json'):
    res['observational']['hazard_model_BASE'] = json.load(open(f'{D}/out/hazard_obs.json'))
ep = [json.loads(l) for l in open(f'{D}/data/natural_episodes.jsonl')]
L = sum(e['n_after_onset'] for e in ep); Bd = sum(e['n_bad_after_onset'] for e in ep)
rt = {'retry': [0, 0], 'new': [0, 0]}
for e in ep:
    for x in e['edits'][e['onset_index'] + 1:]:
        k = 'retry' if x['retry_of_prev'] else 'new'; rt[k][0] += 1; rt[k][1] += x['bad']
res['observational']['natural_episodes_BASE'] = {
    'file': 'data/natural_episodes.jsonl', 'episodes': len(ep), 'later_edits': L, 'later_malformed': Bd,
    'later_malformed_rate': round(Bd / max(1, L), 4), 'after_onset_retry_same_content': rt['retry'], 'after_onset_new_content': rt['new'],
    'recovered_clean_edit': [sum(e['recovered_clean_edit'] for e in ep), len(ep)]}
if os.path.exists(f'{D}/out/obs_retry_split.json'):
    res['observational']['BASE_next_edit_after_one_malformed_by_retry'] = json.load(open(f'{D}/out/obs_retry_split.json'))
# verbatim-copy mechanism check over all k=1 records of P1/P3/P6/P7 (all models)
# interim-safe: complete k=1 data only (31B gate set incl. final P6/P7; 12B/E4B k=1 runs); governed blind files excluded
cc_files = sorted(set(f for g, fs in groups.items() if g.endswith('_old') for f in fs))  # completed old-template files only
open(f'{D}/data/ids_copycheck_interim.txt', 'w').write(open(f'{D}/data/ids_gate300.txt').read() + open(f'{D}/data/ids_phase1_random600.txt').read())
r = subprocess.run([os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python'), f'{D}/scripts/copy_check.py', f'{D}/out/copy_check.json', f'--ids={D}/data/ids_copycheck_interim.txt',
                    *[f for f in cc_files if os.path.exists(f)]], capture_output=True, text=True)
if r.returncode == 0: res['copy_mechanism_k1'] = json.load(open(f'{D}/out/copy_check.json'))
else: res['copy_mechanism_k1'] = {'error': r.stderr[-800:]}
if os.path.exists(f'{D}/out/xcheck_decision_judge_A2.json'):
    x = json.load(open(f'{D}/out/xcheck_decision_judge_A2.json'))
    res['judge_crosscheck_decision_point_disabled'] = pick(x, ['n_full_judged_edits', 'table', 'decision_point_sensitivity_vs_full'])
res['injection'] = {}
for g, fs in groups.items():
    res['injection'][g] = {'files': [os.path.relpath(f, D) for f in fs]}
    # Interim-safe: only the completed k=1 arms P0..P7; every PREREG_v1-governed arm still being collected (dose tier,
    # P8a/P8b, P9, P4', r-dose, lag-2, P6k, held-out, A2) is analysed only by prereg_analysis.py once complete.
    ARMS_OK = 'P0k0,P1k1,P2k1,P3k1,P4k1,P5k1,P6k1,P7k1,P8ak1,P8bk1,P9k1'
    gate_ids = f'{D}/data/ids_gate300.txt' if (g.startswith('31b') or g.endswith('_new')) else f'{D}/data/ids_phase1_random600.txt'
    for part, idsf in (('gate_k1_random_sample', gate_ids),):
        outp = f'{D}/out/ana_{g}_{part}.json'
        r = subprocess.run([PY, f'{D}/scripts/analyze_injection.py', '--res', *fs, '--out', outp, '--enrich', enr, '--label', f'{g}:{part}',
                            '--B', a.B, '--ids', idsf, '--arms', ARMS_OK], capture_output=True, text=True)
        if r.returncode != 0:
            res['injection'][g][part] = {'error': r.stderr[-1500:]}; continue
        res['injection'][g][part] = json.load(open(outp))
# single source of truth: fold in the pre-registered / decision-rule / replication / reliability outputs
for key, fn in (('prereg_analysis_PREREG_v1', 'prereg_analysis.json'), ('decision_rules_upgrade_plan', 'decision_rules.json'),
                ('replication_12b_rdose_lag2', 'rep_12b_rdose_lag2.json'), ('test_retest', 'test_retest.json'),
                ('prereg_deviation_notes_A', 'prereg_deviations_A.json'), ('p4prime_identity', 'p4prime_identity.json'),
                ('sensitivity_excl9_flagged_contexts', 'ana_31b_sensitivity_excl9.json'), ('a2_map_B_repairs_8303', 'a2_map_h.json'),
                ('a2_retry_split_8300', 'a2_retry_split.json'), ('F_pairing_coverage', 'F_pairing_coverage.json'),
                ('thinking_PREREG_v2.1_flag_off', 'v21_analysis.json'), ('thinking_PREREG_v2.2_S_thought_suppressed', 'v22S_analysis.json'),
                ('thinking_PREREG_v2.2_H_reasoning_stripped', 'v22H_analysis.json'), ('template_thinking_off_gap_check', 'template_thinking_off_check.json')):
    if os.path.exists(f'{D}/out/{fn}'): res[key] = json.load(open(f'{D}/out/{fn}'))
res['locks'] = {'heldout': json.load(open(f'{D}/data/heldout_lock.json')),
                'prereg': 'paper/protocol_theory/prereg/PREREG_v1.md sha256=53e34f1fc0c061e8d67bb559b2458419154159608f9e63cadae8eb9bcbecee38',
                'prereg_v2': 'paper/protocol_theory/prereg/PREREG_v2.md sha256=5da75e6170243f838fe0fe1dcb4250a21b8132fc97161e22d149f46fae0d73ac',
                'confirmatory_script_hashes': 'out/confirmatory_script_hashes_v1.txt (v1 15:12:43Z, v1.1 15:51:30Z, natural descriptives 15:56:57Z)'}
smoke = f'{D}/data/smoke_descriptives/out_smoke.json'
if os.path.exists(smoke):
    sm = json.load(open(smoke))
    res['confirmatory_prep'] = {'natural_descriptives_v2_smoke_on_DISCOVERY_logs': {k: v for k, v in sm['verdicts_primary_full_corpus'].items()},
                                'note': 'smoke test only (run-39, 400 attempts, task key = episode); the governed run is on P corpus after it lands',
                                'framing_summary': 'out/FRAMING_SUMMARY.md (scripts/framing_summary.py)'}
json.dump(res, open(f'{D}/results.json', 'w'), indent=1)
print('wrote results.json; groups', {g: len(fs) for g, fs in groups.items()})
for g, v in res['injection'].items():
    gk = v.get('gate_k1_random_sample', {})
    print(g, 'n_contexts', gk.get('n_contexts'), json.dumps(gk.get('gate'))[:900])
