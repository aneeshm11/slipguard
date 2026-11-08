"""Fold A's newer outputs into results.json without re-running summarize.py. summarize.py's copy_check subprocess needs
the main-track logs at their old path, which moved on 2026-11-04 at about 18:12 UTC; every other block of results.json is
unchanged. The keys and files are the same as summarize.py's fold-in list.
usage: fold_results.py"""
import json, os, time
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
R = json.load(open(f'{D}/results.json'))
for key, fn in (('thinking_PREREG_v2.1_flag_off', 'v21_analysis.json'), ('thinking_PREREG_v2.2_S_thought_suppressed', 'v22S_analysis.json'),
                ('thinking_PREREG_v2.2_H_reasoning_stripped', 'v22H_analysis.json'), ('template_thinking_off_gap_check', 'template_thinking_off_check.json'),
                ('renderer_v1_v2_equivalence', 'renderer_v1_v2_check.json'), ('moved_data_provenance', 'moved_data_provenance.json'),
                ('moved_data_check', 'moved_data_check.json'), ('prereg_deviation_notes_A', 'prereg_deviations_A.json'),
                ('confirmatory_PREREG_v2_all_models_full', 'confirmatory/confirm_v2_all_full.json'),
                ('confirmatory_PREREG_v2_all_models_verified_only_sensitivity', 'confirmatory/confirm_v2_all_verified_sens.json'),
                ('confirmatory_PREREG_v2_E4B_canonical_first_analysis_full', 'confirmatory/confirm_v2_31b_e4b_full.json'),
                ('confirmatory_PREREG_v2_E4B_canonical_first_analysis_verified_only', 'confirmatory/confirm_v2_31b_e4b_verified_sens.json'),
                ('confirmatory_natural_descriptives_D1_D11', 'confirmatory/natural_descriptives_v2.json'),
                ('onset_transplant_PREREG_v2.3', 'onset_v23_analysis.json'), ('onset_transplant_O1_verification', 'onset_o1_verification.json'),
                ('bf16_precision_row_primary_300', 'confirmatory/bf16_core_all.json'), ('bf16_precision_row_secondary_50', 'confirmatory/bf16_core_le13000.json'),
                ('v25_replay_preconditions', 'confirmatory/v25_replay_preconditions.json'),
                ('audit_behaviour_PREREG_v2.6', 'confirmatory/v26_audit_analysis.json')):
    if os.path.exists(f'{D}/out/{fn}'): R[key] = json.load(open(f'{D}/out/{fn}'))
R['locks']['prereg_v2.1'] = 'paper/protocol_theory/prereg/PREREG_v2.1_thinkingOFF.md sha256=bb3696da3772d0c7ac67eae9f7f76162dbff11ca357161c34e3c5ca53fb44839'
R['locks']['prereg_v2.2'] = 'paper/protocol_theory/prereg/PREREG_v2.2_thoughtSuppressed.md sha256=ec9164ffa833f351618c3eb7ec69aa2e471e096307de7f5fd61e6c72e07f09d3'
R['locks']['v21_v22_script_hashes'] = 'out/v21_v22_script_hashes.txt'
R['locks']['prereg_v2.3'] = 'paper/protocol_theory/prereg/PREREG_v2.3_onsetTransplant.md sha256=7111525f15d76787280b78e6b55494a00edb64c3456a1214f7aebfcdd0ee67cb'
R['locks']['onset_v23_script_hashes'] = 'out/onset_v23_script_hashes.txt'
R['locks']['prereg_v2.6'] = 'paper/protocol_theory/prereg/PREREG_v2.6_auditBehaviour.md sha256=ed19a6d07734afe795f63e7c9c5b6c3d1285d21deff828557ca28b1e333520f6'
pm = f'{D}/data/confirmatory/pools/POOLS_MANIFEST.json'
if os.path.exists(pm):
    m = json.load(open(pm))
    R['confirmatory_pools'] = {s_: {k: m[s_][k] for k in ('counts', 'eligible_before_rule2', 'rule2_excluded_masked_target', 'eligible', 'verified_only')} | {'accepted': {p_: v['accepted'] for p_, v in m[s_]['pools'].items()}}
                               for s_ in ('S1', 'S2') if s_ in m} | {'script_sha256': m['script_sha256'], 'applied_utc': m['applied_utc']}
R['folded_utc'] = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
json.dump(R, open(f'{D}/results.json', 'w'), indent=1)
print('folded', [k for k in R if k.startswith(('thinking', 'template', 'renderer', 'moved'))])
