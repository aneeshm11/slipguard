"""Assemble results.json for workstream X's DISCOVERY replication: the registered decisions (combine.py output),
per-model registered analyses (primary + held-out), the secondary lenient-reasoning sensitivity, the EXPLORATORY
"any protocol failure" metrics, the CPU format analysis, the teacher-run descriptive, and the Gemma-4-31B reference
on the same 300 gate contexts (workstream A, read-only).
usage: finalize.py   (writes results.json and out/results_x.json must exist)"""
import hashlib
import json
import os

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = ['qwen3-8b', 'qwen3-32b', 'qwen3.5-9b']
A_REF = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/out/ana_31b_old_gate_k1_random_sample.json')


def load(p):
    p = p if os.path.isabs(p) else os.path.join(X, p)
    return json.load(open(p)) if os.path.exists(p) else None


def sha(p):
    p = p if os.path.isabs(p) else os.path.join(X, p)
    return hashlib.sha256(open(p, 'rb').read()).hexdigest() if os.path.exists(p) else None


def compact(an):
    if not an:
        return None
    return {'arms': {k: {kk: v[kk] for kk in ('n', 'P_edit', 'P_malformed_edit_uncond', 'P_malformed_given_edit',
                                             'P_malformed_edit_uncond_gemma_definition', 'P_loud_edit_uncond', 'malformed_edit_flags',
                                             'budget_forced', 'thought_tokens_median')} for k, v in an['arms'].items()},
            'paired_vs_P0': an.get('paired_vs_P0'), 'removal': an.get('removal'), 'copy_check': an.get('copy_check'),
            'natural_calls': an.get('natural_calls'), 'logged_gemma31b_next_call_malformed': an.get('logged_gemma31b_next_call_malformed'),
            'errors': an.get('errors'), 'n_records': an.get('n_records')}


res = {'workstream': 'X (cross-family / cross-format replication)', 'scope': 'DISCOVERY replication on workstream A\'s main-track contexts',
       'preregistration': {'file': 'prereg.md', 'registered_utc': '2026-11-04T12:15Z', 'md5': open(os.path.join(X, 'data/prereg.md5')).read().split()[0],
                           'deviations': 'PREREG_DEVIATIONS.md'},
       'registered_decisions': load('out/results_x.json'), 'models': {}}
for mk in MODELS:
    res['models'][mk] = {
        'primary': compact(load(f'out/ana_{mk}.json')),
        'heldout': compact(load(f'out/ana_{mk}_heldout.json')),
        'sensitivity_lenient_reasoning_primary': compact(load(f'out/ana_{mk}_lenient.json')),
        'exploratory_protocol_failure': {'primary': load(f'out/pf_{mk}.json'), 'heldout': load(f'out/pf_{mk}_heldout.json')}}
sens = load('out/sensitivity_reasoning_summary.json')
res['sensitivity_call_in_unclosed_reasoning'] = sens
ref = load(A_REF)
if ref:
    res['gemma31b_reference_same_gate_contexts'] = {
        'source': A_REF, 'sha256': sha(A_REF), 'note': 'workstream A, read-only; Gemma template (June-5), logged T/top_p; P1 = X\'s P1L analogue, P3 = X\'s hermes-P1N analogue',
        'arms': {k: {kk: v.get(kk) for kk in ('n', 'P_edit', 'P_malformed_edit_uncond', 'P_malformed_given_edit')} for k, v in ref['arms'].items()}}
res['format_cpu'] = {'vllm_0.19.1': load('format/format_summary.json'), 'vllm_0.31.0': load('format/format_summary_v31.json')}
res['teacher_runs_xml_descriptive'] = (load('out/teacher/teacher_xml_slips.json') or {}).get('counts')
res['smoke_cpu'] = load('out/smoke_cpu_300.json')

# ---- PREREG_v2 confirmatory rerun (workstream P's public corpus; pool A1 battery + B1 census; scripts/v2_frozen)
PREREG_V2 = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/PREREG_v2.md')
res['confirmatory_v2'] = {
    'preregistration': {'file': PREREG_V2, 'sha256': sha(PREREG_V2), 'frozen_utc': '2026-11-04T14:46:45Z'},
    'corpus_manifest': os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json'),
    'pools': os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/confirmatory/pools (S1_A1 first 300, H1 = ranks 1-150, H2 = 151-300; S1_B1 first 600)'),
    'code_sha256': 'scripts/v2_frozen/SHA256SUMS',
    'decisions': load('out/v2/results_v2.json'), 'models': {}}
for mk in MODELS:
    res['confirmatory_v2']['models'][mk] = {
        'full': compact(load(f'out/v2/ana_{mk}.json')), 'H1': compact(load(f'out/v2/ana_{mk}_H1.json')),
        'H2': compact(load(f'out/v2/ana_{mk}_H2.json')),
        'exploratory_protocol_failure': load(f'out/v2/pf_{mk}.json')}
# ---- benchmark extension (prereg_ext.md; same public pool A1 + B1 census; scripts/ext_frozen)
EXT = ['gpt-oss-20b', 'qwen3-coder-30b', 'devstral-24b', 'qwen3.8-27b']
res['extension'] = {
    'preregistration': {'file': 'prereg_ext.md', 'registered_utc': '2026-11-04T18:51Z',
                        'sha256': (open(os.path.join(X, 'data/prereg_ext.sha256')).read().split() or [None])[0]},
    'code_sha256': 'scripts/ext_frozen/SHA256SUMS',
    'decisions': load('out/ext/results_ext.json'), 'models': {}}
for mk in EXT:
    res['extension']['models'][mk] = {
        'full': compact(load(f'out/ext/ana_{mk}.json')), 'H1': compact(load(f'out/ext/ana_{mk}_H1.json')),
        'H2': compact(load(f'out/ext/ana_{mk}_H2.json')),
        'exploratory_protocol_failure': load(f'out/ext/pf_{mk}.json')}
res['format_cpu']['extension_formats'] = load('format/format_ext_summary.json')
json.dump(res, open(os.path.join(X, 'results.json'), 'w'), indent=1)
print('wrote results.json;', {mk: bool(v['primary']) for mk, v in res['models'].items()},
      {'v2': {mk: bool(v['full']) for mk, v in res['confirmatory_v2']['models'].items()}},
      {'ext': {mk: bool(v['full']) for mk, v in res['extension']['models'].items()}})
