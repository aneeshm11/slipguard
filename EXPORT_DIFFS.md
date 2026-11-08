# Export diffs -- what changed between each frozen source and its copy in this tree

Built by `release/repo_build/build_tree.py` from `release/repo_build/manifest.json` (sha256 6d01f5c43ee4e275). 1208 files copied; 432 changed (paths -> env/config lookups, privacy redaction); all other files are byte-identical to their frozen source.

Path rules (the data holder's literal paths are in the private manifest only): project_root -> `$TRANSCRIPTLAB_ROOT` (default `<repo dir>`); models -> `$TRANSCRIPTLAB_MODELS` (default `models/`); envs -> `$TRANSCRIPTLAB_ENVS` (default `envs/`); discovery_logs -> `$TRANSCRIPTLAB_DISCOVERY_ROOT` (default `(data holder only)`)

## `release/build_numbers.py`

source `release/build_numbers.py` (group R_release_tools, owner R): pseudonymized: run_or_adapter_name 10

```diff

```

## `release/DEFINITIONS.md`

source `release/DEFINITIONS.md` (group R_release_tools, owner R): pseudonymized: run_or_adapter_name 2

```diff

```

## `croissant.json`

source `release/hosting/croissant_DRAFT.json` (group R_release_tools, owner R): M8 croissant: path MANIFEST.json -> data/pnc/MANIFEST.json; path grading.jsonl -> data/pnc/grading.jsonl; path tasks.json -> data/pnc/tasks.json; path chat_template.jinja -> data/pnc/chat_template.jinja; FileSet episodes/*.jsonl -> data/pnc/episodes/*.jsonl (ships in the Kaggle PNC dataset); FileSet episode_meta/*.json -> data/pnc/episode_meta/*.json (ships in the Kaggle PNC dataset) (+4 more)

```diff
--- a/release/hosting/croissant_DRAFT.json
+++ b/croissant.json
@@ -50 +50 @@
- "description": "Natural, unedited agent trajectories of google/gemma-4-31b-it-qat-w4a16-ct (thinking on, the checkpoint's own sampling) solving SWE-bench tasks with a small generic tool-calling harness: 1,181 episodes, 41,290 model turns, 1,167 graded with the official SWE-bench evaluation scripts, 499 resolved. Every turn records the exact request, the raw generated text including the native tool-call protocol, the calls exactly as vLLM 0.19.1's gemma4 parser delivered them, and the tool results. Splits: verified (400 SWE-bench Verified tasks with schema S1, 100 of them also with schema S2) and swebench_test_ext (681 non-Verified SWE-bench test tasks, schema S1).",
+ "description": "Natural, unedited agent trajectories of google/gemma-4-31b-it-qat-w4a16-ct (thinking on, the checkpoint's own sampling) solving SWE-bench tasks with a small generic tool-calling harness: 1,181 episodes, 41,290 model turns, 1,167 graded with the official SWE-bench evaluation scripts, 499 resolved. Every turn records the exact request, the raw generated text including the native tool-call protocol, the calls exactly as vLLM 0.19.1's gemma4 parser delivered them, and the tool results. Splits: verified (400 SWE-bench Verified tasks with schema S1, 100 of them also with schema S2) and swebench_test_ext (681 non-Verified SWE-bench test tasks, schema S1). In the GitHub repository this file sits at the root and its paths are relative to the repository root: the PNC metadata files are in data/pnc/; the episodes/, episode_meta/ and contexts/ FileSets ship only in the Kaggle PNC dataset (https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc), to be unpacked into data/pnc/. Licences: the corpus data and annotations are CC BY 4.0; the companion code is Apache-2.0; third-party repository text in tool outputs keeps its upstream SPDX licence, listed per repository in data/pnc/MANIFEST.json#licenses.",
@@ -73 +73 @@
-   "contentUrl": "MANIFEST.json",
+   "contentUrl": "data/pnc/MANIFEST.json",
@@ -82 +82 @@
-   "contentUrl": "grading.jsonl",
+   "contentUrl": "data/pnc/grading.jsonl",
@@ -90 +90 @@
-   "contentUrl": "tasks.json",
+   "contentUrl": "data/pnc/tasks.json",
@@ -98 +98 @@
-   "contentUrl": "chat_template.jinja",
+   "contentUrl": "data/pnc/chat_template.jinja",
@@ -107 +107 @@
-   "includes": "episodes/*.jsonl",
+   "includes": "data/pnc/episodes/*.jsonl",
@@ -115 +115 @@
-   "includes": "episode_meta/*.json"
+   "includes": "data/pnc/episode_meta/*.json"
@@ -122 +122 @@
-   "includes": "contexts/*/contexts.jsonl",
+   "includes": "data/pnc/contexts/*/contexts.jsonl",
@@ -508,2 +508,2 @@
- "rai:dataSocialImpact": "supports more reliable tool-using agents; no personal data by design",
- "rai:personalSensitiveInformation": "none expected: public repositories and issues; host identifiers redacted from tool outputs",
+ "rai:dataSocialImpact": "supports more reliable tool-using agents; developer e-mail addresses that appear in upstream repository files inside tool outputs are masked as <email> in the released corpus; no other personal data was found (0 local usernames, hostnames, host IPs or secret/key patterns)",
+ "rai:personalSensitiveInformation": "public repositories and issues; developer e-mail addresses that appear in upstream repository files inside tool outputs are masked as <email> in the released corpus; no other personal data was found (0 local usernames, hostnames, host IPs or secret/key patterns)",

```

## `experiments/conformance/history/results_history.json`

source `experiments/conformance/history/results_history.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 3; pseudonymized: log_name 1, run_or_adapter_name 54; B2 F2 str_token_inside input redacted (verdict kept); B2 F2 protocol_tokens_inside input redacted (verdict kept); M9 F1 harness render windows masked (96)

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/conformance/results.json`

source `experiments/conformance/results.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_harness 1, host_path_repo 4; pseudonymized: log_name 1, run_or_adapter_name 54; B1 T6 payloads -> counts (july); B1 T6 payloads -> counts (june); B3 vllm019_infinite_loop_probe -> {hang: true}; B2 F2 str_token_inside input redacted (verdict kept); B2 F2 protocol_tokens_inside input redacted (verdict kept); M9 F1 harness render windows masked (96)

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/conformance/slips/release/corpus_stats.json`

source `experiments/conformance/slips/release/corpus_stats.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_harness 1

```diff

```

## `experiments/contagion/out/confirmatory/v215_audit_panel.json`

source `experiments/contagion/out/confirmatory/v215_audit_panel.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 7

```diff

```

## `experiments/contagion/out/confirmatory/v216_qat_weights.json`

source `experiments/contagion/out/confirmatory/v216_qat_weights.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 11

```diff

```

## `experiments/contagion/out/observational.json`

source `experiments/contagion/out/observational.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): pseudonymized: run_or_adapter_name 13

```diff

```

## `experiments/contagion/results.json`

source `experiments/contagion/results.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_harness 2, host_path_other 5, host_path_repo 6; pseudonymized: context_id 399, moved_tree_path 5, run_or_adapter_name 14

```diff

```

## `experiments/crossfamily/out/v2/results_v2.json`

source `experiments/crossfamily/out/v2/results_v2.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/results.json`

source `experiments/crossfamily/results.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 12

```diff

```

## `experiments/endtoend/acceptance/p1_quotestorm_freeze_candidate.json`

source `experiments/endtoend/acceptance/p1_quotestorm_freeze_candidate.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 1

```diff

```

## `experiments/format_census/census.json`

source `experiments/format_census/census.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_other 1; 1 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `experiments/intent_decoding/out/proxy_equivalence.json`

source `experiments/intent_decoding/out/proxy_equivalence.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 8; pseudonymized: context_id 18

```diff

```

## `experiments/intent_decoding/results.json`

source `experiments/intent_decoding/results.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 7; pseudonymized: context_id 18

```diff

```

## `experiments/quant_margins/wsa/out/repairC_heldout_final.json`

source `experiments/quant_margins/wsa/out/repairC_heldout_final.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/repair_heldout_final.json`

source `experiments/quant_margins/wsa/out/repair_heldout_final.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): privacy redaction: host_path_repo 3

```diff

```

## `paper/protocol_theory/sim/out/t2_logs_by_run.json`

source `paper/protocol_theory/sim/out/t2_logs_by_run.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): pseudonymized: log_name 8, run_or_adapter_name 139

```diff

```

## `release/provenance/provenance_summary.json`

source `release/provenance/provenance_summary.json` (group results_json_for_the_ledger, owner A,B,C,D,E,F,X,L,P,R): pseudonymized: teammate_handle 2

```diff

```

## `experiments/contagion/README.md`

source `experiments/contagion/README.md` (group A_contagion, owner A): privacy redaction: host_path_harness 2, host_path_other 1, host_path_repo 2; pseudonymized: moved_tree_path 1

```diff

```

## `experiments/contagion/out/F_pairing_coverage.json`

source `experiments/contagion/out/F_pairing_coverage.json` (group A_contagion, owner A): pseudonymized: context_id 396

```diff

```

## `experiments/contagion/out/confirmatory/bf16_server_v1_models.json`

source `experiments/contagion/out/confirmatory/bf16_server_v1_models.json` (group A_contagion, owner A): privacy redaction: host_path_repo 1

```diff

```

## `experiments/contagion/out/confirmatory/natural_descriptives_v2.json`

source `experiments/contagion/out/confirmatory/natural_descriptives_v2.json` (group A_contagion, owner A): privacy redaction: host_path_repo 4

```diff

```

## `experiments/contagion/out/confirmatory/v25_replay_preconditions.md`

source `experiments/contagion/out/confirmatory/v25_replay_preconditions.md` (group A_contagion, owner A): privacy redaction: host_path_repo 1

```diff

```

## `experiments/contagion/out/enrich_gate31b_T1.json`

source `experiments/contagion/out/enrich_gate31b_T1.json` (group A_contagion, owner A): pseudonymized: context_id 300

```diff

```

## `experiments/contagion/out/enrich_gate31b_final.json`

source `experiments/contagion/out/enrich_gate31b_final.json` (group A_contagion, owner A): pseudonymized: context_id 300

```diff

```

## `experiments/contagion/out/enrich_gate31b_interim.json`

source `experiments/contagion/out/enrich_gate31b_interim.json` (group A_contagion, owner A): pseudonymized: context_id 300

```diff

```

## `experiments/contagion/out/examples_31b.json`

source `experiments/contagion/out/examples_31b.json` (group A_contagion, owner A): pseudonymized: context_id 15

```diff

```

## `experiments/contagion/out/interim_enrich_A2.json`

source `experiments/contagion/out/interim_enrich_A2.json` (group A_contagion, owner A): pseudonymized: context_id 115

```diff

```

## `experiments/contagion/out/moved_data_check.json`

source `experiments/contagion/out/moved_data_check.json` (group A_contagion, owner A): privacy redaction: host_path_other 1; pseudonymized: moved_tree_path 1

```diff

```

## `experiments/contagion/out/p4prime_identity.json`

source `experiments/contagion/out/p4prime_identity.json` (group A_contagion, owner A): pseudonymized: context_id 3

```diff

```

## `experiments/contagion/out/p8_extra_quarantined_calls.json`

source `experiments/contagion/out/p8_extra_quarantined_calls.json` (group A_contagion, owner A): pseudonymized: context_id 11

```diff

```

## `experiments/contagion/out/prereg_deviations_A.json`

source `experiments/contagion/out/prereg_deviations_A.json` (group A_contagion, owner A): privacy redaction: host_path_harness 1, host_path_other 2; pseudonymized: moved_tree_path 2

```diff

```

## `experiments/contagion/out/renderer_v1_v2_check.json`

source `experiments/contagion/out/renderer_v1_v2_check.json` (group A_contagion, owner A): privacy redaction: host_path_repo 2

```diff

```

## `experiments/contagion/out/xcheck_decision_judge_A2.json`

source `experiments/contagion/out/xcheck_decision_judge_A2.json` (group A_contagion, owner A): pseudonymized: context_id 4

```diff

```

## `experiments/contagion/scripts/a2_map_analysis.py`

source `experiments/contagion/scripts/a2_map_analysis.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/a2_map_analysis.py
+++ b/experiments/contagion/scripts/a2_map_analysis.py
@@ -6,0 +7 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -9 +10 @@
-D = 'experiments/contagion'; B = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); B = int(sys.argv[2]) if len(sys.argv) > 2 else 2000

```

## `experiments/contagion/scripts/a2_split.py`

source `experiments/contagion/scripts/a2_split.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/a2_split.py
+++ b/experiments/contagion/scripts/a2_split.py
@@ -3,0 +4 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -5 +6 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/analyze_bf16_core.py`

source `experiments/contagion/scripts/analyze_bf16_core.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/analyze_bf16_core.py
+++ b/experiments/contagion/scripts/analyze_bf16_core.py
@@ -20 +20 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/analyze_injection.py`

source `experiments/contagion/scripts/analyze_injection.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/analyze_injection.py
+++ b/experiments/contagion/scripts/analyze_injection.py
@@ -5,0 +6 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -10 +11 @@
-ap.add_argument('--meta', default='experiments/contagion/data/contexts_meta.jsonl')
+ap.add_argument('--meta', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl'))

```

## `experiments/contagion/scripts/analyze_obs.py`

source `experiments/contagion/scripts/analyze_obs.py` (group A_contagion, owner A): pseudonymized: run_or_adapter_name 3

```diff

```

## `experiments/contagion/scripts/analyze_onset_v23.py`

source `experiments/contagion/scripts/analyze_onset_v23.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/analyze_onset_v23.py
+++ b/experiments/contagion/scripts/analyze_onset_v23.py
@@ -32 +32 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
@@ -40 +40 @@
-MAN = json.load(open('data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json'))
+MAN = json.load(open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json')))

```

## `experiments/contagion/scripts/analyze_v211_masked.py`

source `experiments/contagion/scripts/analyze_v211_masked.py` (group A_contagion, owner A): 3 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/analyze_v211_masked.py
+++ b/experiments/contagion/scripts/analyze_v211_masked.py
@@ -7 +7 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
@@ -10,2 +10,2 @@
-ap.add_argument('--affected', default='tmp/wp_pnc/affected_states.json')
-ap.add_argument('--v28_gen', default='experiments/transcriptlab_cli/run_v28/gen.jsonl')
+ap.add_argument('--affected', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'tmp/wp_pnc/affected_states.json'))
+ap.add_argument('--v28_gen', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/transcriptlab_cli/run_v28/gen.jsonl'))

```

## `experiments/contagion/scripts/analyze_v21_v22.py`

source `experiments/contagion/scripts/analyze_v21_v22.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/analyze_v21_v22.py
+++ b/experiments/contagion/scripts/analyze_v21_v22.py
@@ -43 +43 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
@@ -225 +225 @@
-    tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+    tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/analyze_v26_audit.py`

source `experiments/contagion/scripts/analyze_v26_audit.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/analyze_v26_audit.py
+++ b/experiments/contagion/scripts/analyze_v26_audit.py
@@ -27 +27 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/analyze_v27_robustness.py`

source `experiments/contagion/scripts/analyze_v27_robustness.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/analyze_v27_robustness.py
+++ b/experiments/contagion/scripts/analyze_v27_robustness.py
@@ -18 +18 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/analyze_v28_cli.py`

source `experiments/contagion/scripts/analyze_v28_cli.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/analyze_v28_cli.py
+++ b/experiments/contagion/scripts/analyze_v28_cli.py
@@ -7 +7 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/attach_map_repairs.py`

source `experiments/contagion/scripts/attach_map_repairs.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/attach_map_repairs.py
+++ b/experiments/contagion/scripts/attach_map_repairs.py
@@ -4,0 +5 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -6,2 +7,2 @@
-D = 'experiments/contagion'
-src = sys.argv[1] if len(sys.argv) > 1 else 'experiments/intent_decoding/out/a2_map_repairs.jsonl'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/out/a2_map_repairs.jsonl')

```

## `experiments/contagion/scripts/build_a2_states.py`

source `experiments/contagion/scripts/build_a2_states.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/build_a2_states.py
+++ b/experiments/contagion/scripts/build_a2_states.py
@@ -12 +12 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')

```

## `experiments/contagion/scripts/build_contexts.py`

source `experiments/contagion/scripts/build_contexts.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/build_contexts.py
+++ b/experiments/contagion/scripts/build_contexts.py
@@ -14 +14 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')

```

## `experiments/contagion/scripts/chain_C31b_then_O23.sh`

source `experiments/contagion/scripts/chain_C31b_then_O23.sh` (group A_contagion, owner A): 5 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/contagion/scripts/chain_C31b_then_O23.sh
+++ b/experiments/contagion/scripts/chain_C31b_then_O23.sh
@@ -4,2 +4,2 @@
-cd experiments/contagion
-C=data/pnc/contexts/P-swebench-31b-S1-v1; PY=/opt/envs/env_gemma/bin/python; LIM=tools/limited.sh
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion
+C=${TRANSCRIPTLAB_ROOT:-.}/data/pnc/contexts/P-swebench-31b-S1-v1; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LIM=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh
@@ -11 +11 @@
-echo "== O23 start $(date -u +%H:%M:%S) | renderer $(sha256sum experiments/endtoend/export/quarantine_renderer.py | cut -c1-16) | run_onset $(sha256sum scripts/run_onset.py | cut -c1-16)" >> logs/ctg-O23.log
+echo "== O23 start $(date -u +%H:%M:%S) | renderer $(sha256sum ${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend/export/quarantine_renderer.py | cut -c1-16) | run_onset $(sha256sum scripts/run_onset.py | cut -c1-16)" >> logs/ctg-O23.log

```

## `experiments/contagion/scripts/check_bos.py`

source `experiments/contagion/scripts/check_bos.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/check_bos.py
+++ b/experiments/contagion/scripts/check_bos.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -3 +4 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/check_bos2.py`

source `experiments/contagion/scripts/check_bos2.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/check_bos2.py
+++ b/experiments/contagion/scripts/check_bos2.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -3 +4 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/check_renderer_v1_v2.py`

source `experiments/contagion/scripts/check_renderer_v1_v2.py` (group A_contagion, owner A): 6 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/check_renderer_v1_v2.py
+++ b/experiments/contagion/scripts/check_renderer_v1_v2.py
@@ -19,4 +19,4 @@
-D = 'experiments/contagion'
-V1 = 'experiments/endtoend/archive/candidate_0c2a5278/export/quarantine_renderer.py'
-SHIPPED = 'experiments/endtoend/export/quarantine_renderer.py'
-V2_6B08 = 'experiments/intent_decoding/proxy_vendor_fix/export/quarantine_renderer.py'  # copy of the version the PI announced
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+V1 = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/archive/candidate_0c2a5278/export/quarantine_renderer.py')
+SHIPPED = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/export/quarantine_renderer.py')
+V2_6B08 = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/proxy_vendor_fix/export/quarantine_renderer.py')  # copy of the version the PI announced
@@ -40 +40 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
@@ -84 +84 @@
-    pdir = 'experiments/pnc/runs/smoke1/data/contexts/P-swebench-31b-S1-v1'
+    pdir = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/pnc/runs/smoke1/data/contexts/P-swebench-31b-S1-v1')

```

## `experiments/contagion/scripts/check_template.py`

source `experiments/contagion/scripts/check_template.py` (group A_contagion, owner A): 4 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/check_template.py
+++ b/experiments/contagion/scripts/check_template.py
@@ -2,0 +3 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -5,3 +6,3 @@
-OLD = '/harness/work/models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja'
-NEW = 'models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja'
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+OLD = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')
+NEW = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
@@ -13 +14 @@
-root = '/harness/work/runs'
+root = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')

```

## `experiments/contagion/scripts/check_template_thinking_off.py`

source `experiments/contagion/scripts/check_template_thinking_off.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/check_template_thinking_off.py
+++ b/experiments/contagion/scripts/check_template_thinking_off.py
@@ -9,2 +9,2 @@
-D = 'experiments/contagion'
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/check_thought_forms.py`

source `experiments/contagion/scripts/check_thought_forms.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/check_thought_forms.py
+++ b/experiments/contagion/scripts/check_thought_forms.py
@@ -8,2 +8,2 @@
-D = 'experiments/contagion'
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/copy_check.py`

source `experiments/contagion/scripts/copy_check.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/copy_check.py
+++ b/experiments/contagion/scripts/copy_check.py
@@ -21 +21 @@
-META = {json.loads(l)['id']: json.loads(l) for l in open('experiments/contagion/data/contexts_meta.jsonl')}
+META = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl'))}

```

## `experiments/contagion/scripts/decision_rules.py`

source `experiments/contagion/scripts/decision_rules.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/decision_rules.py
+++ b/experiments/contagion/scripts/decision_rules.py
@@ -17,2 +17,2 @@
-D = 'experiments/contagion'
-PREREG = 'paper/protocol_theory/prereg/PREREG_v1.md'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+PREREG = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/PREREG_v1.md')

```

## `experiments/contagion/scripts/enrich_contexts.py`

source `experiments/contagion/scripts/enrich_contexts.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/enrich_contexts.py
+++ b/experiments/contagion/scripts/enrich_contexts.py
@@ -5,0 +6 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -7 +8 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')

```

## `experiments/contagion/scripts/figures.py`

source `experiments/contagion/scripts/figures.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/figures.py
+++ b/experiments/contagion/scripts/figures.py
@@ -14 +14 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/figures_v1_interim.py`

source `experiments/contagion/scripts/figures_v1_interim.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/figures_v1_interim.py
+++ b/experiments/contagion/scripts/figures_v1_interim.py
@@ -10 +10 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/fold_results.py`

source `experiments/contagion/scripts/fold_results.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/fold_results.py
+++ b/experiments/contagion/scripts/fold_results.py
@@ -6 +6 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/framing_summary.py`

source `experiments/contagion/scripts/framing_summary.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/framing_summary.py
+++ b/experiments/contagion/scripts/framing_summary.py
@@ -9 +9 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/gate_report.py`

source `experiments/contagion/scripts/gate_report.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/gate_report.py
+++ b/experiments/contagion/scripts/gate_report.py
@@ -6 +6 @@
-D = 'experiments/contagion'; PY = '/opt/envs/env_agentpaper/bin/python'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_agentpaper/bin/python')

```

## `experiments/contagion/scripts/gemma_protocol.py`

source `experiments/contagion/scripts/gemma_protocol.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups; privacy redaction: host_path_harness 1; M9 competition-harness retry nudge withheld

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/contagion/scripts/gemma_protocol_v1_backup.py`

source `experiments/contagion/scripts/gemma_protocol_v1_backup.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups; privacy redaction: host_path_harness 1

```diff
--- a/experiments/contagion/scripts/gemma_protocol_v1_backup.py
+++ b/experiments/contagion/scripts/gemma_protocol_v1_backup.py
@@ -7,0 +8 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -17,2 +18,2 @@
-OLD_TEMPLATE = '/harness/work/models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja'   # produced the logs
-NEW_TEMPLATE = 'models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja'  # current HF template
+OLD_TEMPLATE = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')   # produced the logs
+NEW_TEMPLATE = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')  # current HF template

```

## `experiments/contagion/scripts/launch_31b_chain.sh`

source `experiments/contagion/scripts/launch_31b_chain.sh` (group A_contagion, owner A): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/contagion/scripts/launch_31b_chain.sh
+++ b/experiments/contagion/scripts/launch_31b_chain.sh
@@ -4,2 +4,2 @@
-D=experiments/contagion; O=$D/out/main; PYX=/opt/envs/env_gemma/bin/python; R=$D/scripts/run_injection.py
-LIM=tools/limited.sh; CH=$D/scripts/chain_after.sh; U=http://127.0.0.1:8300/v1
+D=${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion; O=$D/out/main; PYX=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; R=$D/scripts/run_injection.py
+LIM=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh; CH=$D/scripts/chain_after.sh; U=http://127.0.0.1:8300/v1

```

## `experiments/contagion/scripts/launch_8302_all.sh`

source `experiments/contagion/scripts/launch_8302_all.sh` (group A_contagion, owner A): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/contagion/scripts/launch_8302_all.sh
+++ b/experiments/contagion/scripts/launch_8302_all.sh
@@ -4,2 +4,2 @@
-cd experiments/contagion
-PORT=${1:-8302}; GPU=${2:-2}; PY=/opt/envs/env_gemma/bin/python; LIM=tools/limited.sh
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion
+PORT=${1:-8302}; GPU=${2:-2}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LIM=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh

```

## `experiments/contagion/scripts/launch_v22.sh`

source `experiments/contagion/scripts/launch_v22.sh` (group A_contagion, owner A): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/contagion/scripts/launch_v22.sh
+++ b/experiments/contagion/scripts/launch_v22.sh
@@ -5,2 +5,2 @@
-cd experiments/contagion
-PORT=${1:-8302}; GPU=${2:-2}; PY=/opt/envs/env_gemma/bin/python; LIM=tools/limited.sh
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion
+PORT=${1:-8302}; GPU=${2:-2}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LIM=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh

```

## `experiments/contagion/scripts/natural_descriptives_v2.py`

source `experiments/contagion/scripts/natural_descriptives_v2.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/natural_descriptives_v2.py
+++ b/experiments/contagion/scripts/natural_descriptives_v2.py
@@ -42 +42 @@
-sys.path.insert(0, 'experiments/conformance')   # C's reference serializer + parser (read-only)
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance'))   # C's reference serializer + parser (read-only)
@@ -56 +56 @@
-PREREG = 'paper/protocol_theory/prereg/PREREG_v2.md'
+PREREG = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/PREREG_v2.md')

```

## `experiments/contagion/scripts/prereg_analysis.py`

source `experiments/contagion/scripts/prereg_analysis.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/prereg_analysis.py
+++ b/experiments/contagion/scripts/prereg_analysis.py
@@ -25 +25 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/regress_profiles.py`

source `experiments/contagion/scripts/regress_profiles.py` (group A_contagion, owner A): 3 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/regress_profiles.py
+++ b/experiments/contagion/scripts/regress_profiles.py
@@ -3,0 +4 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -5 +6 @@
-sys.path.insert(0, 'experiments/contagion/scripts')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/scripts'))
@@ -9 +10 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
@@ -26 +27 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/rep_12b.py`

source `experiments/contagion/scripts/rep_12b.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/rep_12b.py
+++ b/experiments/contagion/scripts/rep_12b.py
@@ -3,0 +4 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -6 +7 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/report_tables.py`

source `experiments/contagion/scripts/report_tables.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/report_tables.py
+++ b/experiments/contagion/scripts/report_tables.py
@@ -2,0 +3 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -4 +5 @@
-R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'experiments/contagion/results.json'))
+R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/results.json')))

```

## `experiments/contagion/scripts/report_tables_v2.py`

source `experiments/contagion/scripts/report_tables_v2.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/report_tables_v2.py
+++ b/experiments/contagion/scripts/report_tables_v2.py
@@ -6 +6 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/run_injection.py`

source `experiments/contagion/scripts/run_injection.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/run_injection.py
+++ b/experiments/contagion/scripts/run_injection.py
@@ -24 +24 @@
-ap.add_argument('--meta', default='experiments/contagion/data/contexts_meta.jsonl')
+ap.add_argument('--meta', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl'))
@@ -26 +26 @@
-ap.add_argument('--tok', default='models/gemma-4-31b-it-qat-w4a16-ct')
+ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/run_injection_v1_backup.py`

source `experiments/contagion/scripts/run_injection_v1_backup.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/run_injection_v1_backup.py
+++ b/experiments/contagion/scripts/run_injection_v1_backup.py
@@ -24 +24 @@
-ap.add_argument('--meta', default='experiments/contagion/data/contexts_meta.jsonl')
+ap.add_argument('--meta', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl'))
@@ -26 +26 @@
-ap.add_argument('--tok', default='models/gemma-4-31b-it-qat-w4a16-ct')
+ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/sample_pools_v2.py`

source `experiments/contagion/scripts/sample_pools_v2.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/sample_pools_v2.py
+++ b/experiments/contagion/scripts/sample_pools_v2.py
@@ -40 +40 @@
-PREREG = 'paper/protocol_theory/prereg/PREREG_v2.md'
+PREREG = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/PREREG_v2.md')

```

## `experiments/contagion/scripts/smoke_build_discovery_requests.py`

source `experiments/contagion/scripts/smoke_build_discovery_requests.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups; pseudonymized: run_or_adapter_name 2

```diff
--- a/experiments/contagion/scripts/smoke_build_discovery_requests.py
+++ b/experiments/contagion/scripts/smoke_build_discovery_requests.py
@@ -10 +10 @@
-D = 'experiments/contagion'; ROOT = '/harness/work/runs'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')

```

## `experiments/contagion/scripts/summarize.py`

source `experiments/contagion/scripts/summarize.py` (group A_contagion, owner A): 3 path literal(s) -> env/config lookups; pseudonymized: run_or_adapter_name 3

```diff
--- a/experiments/contagion/scripts/summarize.py
+++ b/experiments/contagion/scripts/summarize.py
@@ -11,2 +11,2 @@
-D = 'experiments/contagion'
-PY = '/opt/envs/env_agentpaper/bin/python'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_agentpaper/bin/python')
@@ -80 +80 @@
-r = subprocess.run(['/opt/envs/env_gemma/bin/python', f'{D}/scripts/copy_check.py', f'{D}/out/copy_check.json', f'--ids={D}/data/ids_copycheck_interim.txt',
+r = subprocess.run([os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python'), f'{D}/scripts/copy_check.py', f'{D}/out/copy_check.json', f'--ids={D}/data/ids_copycheck_interim.txt',

```

## `experiments/contagion/scripts/test_P_smoke.py`

source `experiments/contagion/scripts/test_P_smoke.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/test_P_smoke.py
+++ b/experiments/contagion/scripts/test_P_smoke.py
@@ -12 +12 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/test_P_v11.py`

source `experiments/contagion/scripts/test_P_v11.py` (group A_contagion, owner A): 4 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/test_P_v11.py
+++ b/experiments/contagion/scripts/test_P_v11.py
@@ -10,3 +10,3 @@
-sys.path.insert(0, 'experiments/contagion/scripts')
-D = 'experiments/contagion'; S = f'{D}/data/test_S1'; T = f'{D}/data/test_P_v11'
-PY = '/opt/envs/env_gemma/bin/python'
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/scripts'))
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); S = f'{D}/data/test_S1'; T = f'{D}/data/test_P_v11'
+PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python')
@@ -21 +21 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/test_S1_synthetic.py`

source `experiments/contagion/scripts/test_S1_synthetic.py` (group A_contagion, owner A): 4 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/test_S1_synthetic.py
+++ b/experiments/contagion/scripts/test_S1_synthetic.py
@@ -4,2 +4,2 @@
-sys.path.insert(0, 'experiments/contagion/scripts')
-D = 'experiments/contagion'; T = f'{D}/data/test_S1'
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/scripts'))
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); T = f'{D}/data/test_S1'
@@ -8 +8 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
@@ -46 +46 @@
-PY = '/opt/envs/env_gemma/bin/python'
+PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python')

```

## `experiments/contagion/scripts/test_retest.py`

source `experiments/contagion/scripts/test_retest.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/test_retest.py
+++ b/experiments/contagion/scripts/test_retest.py
@@ -4,0 +5 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -6 +7 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/test_run_cond.py`

source `experiments/contagion/scripts/test_run_cond.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/test_run_cond.py
+++ b/experiments/contagion/scripts/test_run_cond.py
@@ -10,2 +10,2 @@
-D = 'experiments/contagion'
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/test_variants.py`

source `experiments/contagion/scripts/test_variants.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/test_variants.py
+++ b/experiments/contagion/scripts/test_variants.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -5 +6 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/update_readme.py`

source `experiments/contagion/scripts/update_readme.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/update_readme.py
+++ b/experiments/contagion/scripts/update_readme.py
@@ -2,0 +3 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -4 +5 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/v25_replay_preconditions.py`

source `experiments/contagion/scripts/v25_replay_preconditions.py` (group A_contagion, owner A): 3 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/v25_replay_preconditions.py
+++ b/experiments/contagion/scripts/v25_replay_preconditions.py
@@ -13,2 +13,2 @@
-D = 'experiments/contagion'
-CDIR = 'data/pnc/contexts/P-swebench-31b-S1-v1'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+CDIR = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
@@ -18 +18 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/v27_pooled_retest.py`

source `experiments/contagion/scripts/v27_pooled_retest.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/v27_pooled_retest.py
+++ b/experiments/contagion/scripts/v27_pooled_retest.py
@@ -4,0 +5 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -7 +8 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/contagion/scripts/validate_contexts.py`

source `experiments/contagion/scripts/validate_contexts.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/validate_contexts.py
+++ b/experiments/contagion/scripts/validate_contexts.py
@@ -11 +11 @@
-tokdir = sys.argv[sys.argv.index('--tok') + 1] if '--tok' in sys.argv else 'models/gemma-4-31b-it-qat-w4a16-ct'
+tokdir = sys.argv[sys.argv.index('--tok') + 1] if '--tok' in sys.argv else os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')

```

## `experiments/contagion/scripts/variants.py`

source `experiments/contagion/scripts/variants.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups; editorial override (1x): public tree: the released state metadata gives contexts_file repo-relative; resolve it against TRANSCRIPTLAB_ROOT (an absolute path is unchanged by os.path.join)

```diff
--- a/experiments/contagion/scripts/variants.py
+++ b/experiments/contagion/scripts/variants.py
@@ -34 +34 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
@@ -39 +39 @@
-        with open(meta['contexts_file'], 'rb') as f:
+        with open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), meta['contexts_file']), 'rb') as f:
@@ -157 +157 @@
-QR_PATH = 'experiments/endtoend/export/quarantine_renderer.py'  # workstream E, FROZEN (read-only)
+QR_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/export/quarantine_renderer.py')  # workstream E, FROZEN (read-only)

```

## `experiments/contagion/scripts/variants_v1_backup.py`

source `experiments/contagion/scripts/variants_v1_backup.py` (group A_contagion, owner A): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/variants_v1_backup.py
+++ b/experiments/contagion/scripts/variants_v1_backup.py
@@ -30 +30 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')

```

## `experiments/contagion/scripts/variants_v2_backup.py`

source `experiments/contagion/scripts/variants_v2_backup.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/variants_v2_backup.py
+++ b/experiments/contagion/scripts/variants_v2_backup.py
@@ -30 +30 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
@@ -148 +148 @@
-QR_PATH = 'experiments/endtoend/export/quarantine_renderer.py'  # workstream E, FROZEN (read-only)
+QR_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/export/quarantine_renderer.py')  # workstream E, FROZEN (read-only)

```

## `experiments/contagion/scripts/verify_moved_data.py`

source `experiments/contagion/scripts/verify_moved_data.py` (group A_contagion, owner A): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/verify_moved_data.py
+++ b/experiments/contagion/scripts/verify_moved_data.py
@@ -9,2 +9,2 @@
-D = 'experiments/contagion'
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/verify_onset_o1.py`

source `experiments/contagion/scripts/verify_onset_o1.py` (group A_contagion, owner A): 4 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/verify_onset_o1.py
+++ b/experiments/contagion/scripts/verify_onset_o1.py
@@ -11 +11 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
@@ -15 +15 @@
-sys.path.insert(0, 'experiments/conformance/history')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/history'))
@@ -22 +22 @@
-man = json.load(open('data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json'))
+man = json.load(open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json')))
@@ -24 +24 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/contagion/scripts/with_paths.py`

source `experiments/contagion/scripts/with_paths.py` (group A_contagion, owner A): privacy redaction: host_path_harness 2, host_path_other 2; pseudonymized: moved_tree_path 2

```diff

```

## `experiments/crossfamily/README.md`

source `experiments/crossfamily/README.md` (group X_crossfamily, owner X): privacy redaction: host_path_envs 2, host_path_repo 2

```diff

```

## `experiments/crossfamily/out/ana_qwen3-32b.json`

source `experiments/crossfamily/out/ana_qwen3-32b.json` (group X_crossfamily, owner X): pseudonymized: context_id 6

```diff

```

## `experiments/crossfamily/out/ana_qwen3-32b_heldout.json`

source `experiments/crossfamily/out/ana_qwen3-32b_heldout.json` (group X_crossfamily, owner X): pseudonymized: context_id 2

```diff

```

## `experiments/crossfamily/out/ana_qwen3-32b_lenient.json`

source `experiments/crossfamily/out/ana_qwen3-32b_lenient.json` (group X_crossfamily, owner X): pseudonymized: context_id 6

```diff

```

## `experiments/crossfamily/out/ana_qwen3-8b.json`

source `experiments/crossfamily/out/ana_qwen3-8b.json` (group X_crossfamily, owner X): pseudonymized: context_id 8

```diff

```

## `experiments/crossfamily/out/ana_qwen3-8b_heldout.json`

source `experiments/crossfamily/out/ana_qwen3-8b_heldout.json` (group X_crossfamily, owner X): pseudonymized: context_id 3

```diff

```

## `experiments/crossfamily/out/ana_qwen3-8b_lenient.json`

source `experiments/crossfamily/out/ana_qwen3-8b_lenient.json` (group X_crossfamily, owner X): pseudonymized: context_id 11

```diff

```

## `experiments/crossfamily/out/ext/ext_prepare_manifest.json`

source `experiments/crossfamily/out/ext/ext_prepare_manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 2

```diff

```

## `experiments/crossfamily/out/ext/pf_qwen3.8-27b.json`

source `experiments/crossfamily/out/ext/pf_qwen3.8-27b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/ext/prompts_devstral-24b_extA1.manifest.json`

source `experiments/crossfamily/out/ext/prompts_devstral-24b_extA1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/ext/prompts_devstral-24b_extB1.manifest.json`

source `experiments/crossfamily/out/ext/prompts_devstral-24b_extB1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/ext/prompts_gpt-oss-20b_extA1.manifest.json`

source `experiments/crossfamily/out/ext/prompts_gpt-oss-20b_extA1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/ext/prompts_gpt-oss-20b_extB1.manifest.json`

source `experiments/crossfamily/out/ext/prompts_gpt-oss-20b_extB1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/ext/prompts_qwen3-coder-30b_extA1.manifest.json`

source `experiments/crossfamily/out/ext/prompts_qwen3-coder-30b_extA1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/ext/prompts_qwen3-coder-30b_extB1.manifest.json`

source `experiments/crossfamily/out/ext/prompts_qwen3-coder-30b_extB1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/ext/prompts_qwen3.8-27b_extA1.manifest.json`

source `experiments/crossfamily/out/ext/prompts_qwen3.8-27b_extA1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/ext/prompts_qwen3.8-27b_extB1.manifest.json`

source `experiments/crossfamily/out/ext/prompts_qwen3.8-27b_extB1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/ext/run_manifest_devstral-24b.json`

source `experiments/crossfamily/out/ext/run_manifest_devstral-24b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 6

```diff

```

## `experiments/crossfamily/out/ext/run_manifest_gpt-oss-20b.json`

source `experiments/crossfamily/out/ext/run_manifest_gpt-oss-20b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 5

```diff

```

## `experiments/crossfamily/out/ext/run_manifest_qwen3-coder-30b.json`

source `experiments/crossfamily/out/ext/run_manifest_qwen3-coder-30b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 5

```diff

```

## `experiments/crossfamily/out/ext/run_manifest_qwen3.8-27b.json`

source `experiments/crossfamily/out/ext/run_manifest_qwen3.8-27b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 5

```diff

```

## `experiments/crossfamily/out/sensitivity_reasoning_summary.json`

source `experiments/crossfamily/out/sensitivity_reasoning_summary.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 3

```diff

```

## `experiments/crossfamily/out/smoke_ext_testS1.json`

source `experiments/crossfamily/out/smoke_ext_testS1.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/smoke_ext_testS1_devstral.json`

source `experiments/crossfamily/out/smoke_ext_testS1_devstral.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/pf_qwen3-32b.json`

source `experiments/crossfamily/out/v2/pf_qwen3-32b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/pf_qwen3-8b.json`

source `experiments/crossfamily/out/v2/pf_qwen3-8b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/pf_qwen3.5-9b.json`

source `experiments/crossfamily/out/v2/pf_qwen3.5-9b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/prompts_qwen3-32b_v2A1.manifest.json`

source `experiments/crossfamily/out/v2/prompts_qwen3-32b_v2A1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/prompts_qwen3-32b_v2B1.manifest.json`

source `experiments/crossfamily/out/v2/prompts_qwen3-32b_v2B1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/prompts_qwen3-8b_v2A1.manifest.json`

source `experiments/crossfamily/out/v2/prompts_qwen3-8b_v2A1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/prompts_qwen3-8b_v2B1.manifest.json`

source `experiments/crossfamily/out/v2/prompts_qwen3-8b_v2B1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/prompts_qwen3.5-9b_v2A1.manifest.json`

source `experiments/crossfamily/out/v2/prompts_qwen3.5-9b_v2A1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/prompts_qwen3.5-9b_v2B1.manifest.json`

source `experiments/crossfamily/out/v2/prompts_qwen3.5-9b_v2B1.manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 1

```diff

```

## `experiments/crossfamily/out/v2/run_manifest_qwen3-32b.json`

source `experiments/crossfamily/out/v2/run_manifest_qwen3-32b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 5

```diff

```

## `experiments/crossfamily/out/v2/v2_prepare_manifest.json`

source `experiments/crossfamily/out/v2/v2_prepare_manifest.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 2

```diff

```

## `experiments/crossfamily/out/v2/v2_prepare_manifest_32b.json`

source `experiments/crossfamily/out/v2/v2_prepare_manifest_32b.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 2

```diff

```

## `experiments/crossfamily/out/v2/v2_prepare_manifest_gpu1.json`

source `experiments/crossfamily/out/v2/v2_prepare_manifest_gpu1.json` (group X_crossfamily, owner X): privacy redaction: host_path_repo 2

```diff

```

## `experiments/crossfamily/scripts/arms.py`

source `experiments/crossfamily/scripts/arms.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/arms.py
+++ b/experiments/crossfamily/scripts/arms.py
@@ -38 +38 @@
-META_PATH = 'experiments/contagion/data/contexts_meta.jsonl'
+META_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')

```

## `experiments/crossfamily/scripts/discovery/arms.py`

source `experiments/crossfamily/scripts/discovery/arms.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/discovery/arms.py
+++ b/experiments/crossfamily/scripts/discovery/arms.py
@@ -38 +38 @@
-META_PATH = 'experiments/contagion/data/contexts_meta.jsonl'
+META_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')

```

## `experiments/crossfamily/scripts/discovery/frozen/a_variants.py`

source `experiments/crossfamily/scripts/discovery/frozen/a_variants.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/discovery/frozen/a_variants.py
+++ b/experiments/crossfamily/scripts/discovery/frozen/a_variants.py
@@ -30 +30 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
@@ -148 +148 @@
-QR_PATH = 'experiments/endtoend/export/quarantine_renderer.py'  # workstream E, FROZEN (read-only)
+QR_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/export/quarantine_renderer.py')  # workstream E, FROZEN (read-only)

```

## `experiments/crossfamily/scripts/discovery/frozen/gemma_protocol.py`

source `experiments/crossfamily/scripts/discovery/frozen/gemma_protocol.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups; privacy redaction: host_path_harness 1; M9 competition-harness retry nudge withheld

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/crossfamily/scripts/discovery/prep_prompts.py`

source `experiments/crossfamily/scripts/discovery/prep_prompts.py` (group X_crossfamily, owner X): 3 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/discovery/prep_prompts.py
+++ b/experiments/crossfamily/scripts/discovery/prep_prompts.py
@@ -24,3 +24,3 @@
-GATE = 'experiments/contagion/data/ids_gate300.txt'
-BSET = 'experiments/intent_decoding/data/replay_gemma_first_edit.jsonl'
-PHASE1 = 'experiments/contagion/data/ids_phase1_random600.txt'
+GATE = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')
+BSET = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/data/replay_gemma_first_edit.jsonl')
+PHASE1 = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_phase1_random600.txt')

```

## `experiments/crossfamily/scripts/discovery/qwenproto.py`

source `experiments/crossfamily/scripts/discovery/qwenproto.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/discovery/qwenproto.py
+++ b/experiments/crossfamily/scripts/discovery/qwenproto.py
@@ -30 +30 @@
-os.environ.setdefault("HF_HOME", "cache/hf")
+os.environ.setdefault("HF_HOME", os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "cache/hf"))
@@ -36 +36 @@
-MD = 'models/'
+MD = os.environ.get('TRANSCRIPTLAB_MODELS', 'models/')

```

## `experiments/crossfamily/scripts/discovery/run_chain.sh`

source `experiments/crossfamily/scripts/discovery/run_chain.sh` (group X_crossfamily, owner X): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/discovery/run_chain.sh
+++ b/experiments/crossfamily/scripts/discovery/run_chain.sh
@@ -5,2 +5,2 @@
-cd experiments/crossfamily
-PY=/opt/envs/env_gemma/bin/python
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily
+PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python

```

## `experiments/crossfamily/scripts/dl_ext.sh`

source `experiments/crossfamily/scripts/dl_ext.sh` (group X_crossfamily, owner X): 4 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/dl_ext.sh
+++ b/experiments/crossfamily/scripts/dl_ext.sh
@@ -2 +2 @@
-# Workstream X benchmark extension: weight downloads into models (user-approved location).
+# Workstream X benchmark extension: weight downloads into ${TRANSCRIPTLAB_MODELS:-models} (user-approved location).
@@ -4 +4 @@
-export HF_HOME=hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_TOKEN_PATH=$HOME/.cache/huggingface/token
+export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_TOKEN_PATH=$HOME/.cache/huggingface/token
@@ -6 +6 @@
-M=models; HF=/opt/envs/env_gemma/bin/hf
+M=${TRANSCRIPTLAB_MODELS:-models}; HF=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf

```

## `experiments/crossfamily/scripts/dl_ext2.sh`

source `experiments/crossfamily/scripts/dl_ext2.sh` (group X_crossfamily, owner X): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/dl_ext2.sh
+++ b/experiments/crossfamily/scripts/dl_ext2.sh
@@ -3 +3 @@
-export HF_HOME=hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_TOKEN_PATH=$HOME/.cache/huggingface/token
+export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_TOKEN_PATH=$HOME/.cache/huggingface/token
@@ -5 +5 @@
-M=models; HF=/opt/envs/env_gemma/bin/hf
+M=${TRANSCRIPTLAB_MODELS:-models}; HF=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf

```

## `experiments/crossfamily/scripts/dl_ext3.sh`

source `experiments/crossfamily/scripts/dl_ext3.sh` (group X_crossfamily, owner X): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/dl_ext3.sh
+++ b/experiments/crossfamily/scripts/dl_ext3.sh
@@ -4 +4 @@
-export HF_HOME=hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_TOKEN_PATH=$HOME/.cache/huggingface/token
+export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_TOKEN_PATH=$HOME/.cache/huggingface/token
@@ -6 +6 @@
-M=models; HF=/opt/envs/env_gemma/bin/hf
+M=${TRANSCRIPTLAB_MODELS:-models}; HF=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf

```

## `experiments/crossfamily/scripts/explore/check_arms_v2.py`

source `experiments/crossfamily/scripts/explore/check_arms_v2.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/check_arms_v2.py
+++ b/experiments/crossfamily/scripts/explore/check_arms_v2.py
@@ -22 +22 @@
-ids = [x.strip() for x in open('experiments/contagion/data/ids_gate300.txt') if x.strip()][:N]
+ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()][:N]

```

## `experiments/crossfamily/scripts/explore/check_b_set.py`

source `experiments/crossfamily/scripts/explore/check_b_set.py` (group X_crossfamily, owner X): 3 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/check_b_set.py
+++ b/experiments/crossfamily/scripts/explore/check_b_set.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -3 +4 @@
-for l in open('experiments/contagion/data/contexts_meta.jsonl'):
+for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')):
@@ -5,2 +6,2 @@
-ROOT = '/harness/work/runs'
-P = 'experiments/intent_decoding/data/replay_gemma_first_edit.jsonl'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
+P = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/data/replay_gemma_first_edit.jsonl')

```

## `experiments/crossfamily/scripts/explore/dbg_diff.py`

source `experiments/crossfamily/scripts/explore/dbg_diff.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/dbg_diff.py
+++ b/experiments/crossfamily/scripts/explore/dbg_diff.py
@@ -2 +2 @@
-sys.path.insert(0, 'experiments/crossfamily/scripts')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
@@ -5 +5 @@
-ids = [x.strip() for x in open('experiments/contagion/data/ids_gate300.txt') if x.strip()][:6]
+ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()][:6]

```

## `experiments/crossfamily/scripts/explore/dbg_diff2.py`

source `experiments/crossfamily/scripts/explore/dbg_diff2.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/dbg_diff2.py
+++ b/experiments/crossfamily/scripts/explore/dbg_diff2.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -2 +3 @@
-sys.path.insert(0, 'experiments/crossfamily/scripts')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
@@ -5 +6 @@
-ids = [x.strip() for x in open('experiments/contagion/data/ids_gate300.txt') if x.strip()]
+ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()]

```

## `experiments/crossfamily/scripts/explore/fmt_dbg.py`

source `experiments/crossfamily/scripts/explore/fmt_dbg.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/fmt_dbg.py
+++ b/experiments/crossfamily/scripts/explore/fmt_dbg.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -12 +13 @@
-for l in open('experiments/conformance/fuzz/cases.jsonl'):
+for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/fuzz/cases.jsonl')):

```

## `experiments/crossfamily/scripts/explore/hub_check2.py`

source `experiments/crossfamily/scripts/explore/hub_check2.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/hub_check2.py
+++ b/experiments/crossfamily/scripts/explore/hub_check2.py
@@ -14 +14 @@
-        p = api.hf_hub_download(r, 'config.json', cache_dir='experiments/crossfamily/data/hubprobe')
+        p = api.hf_hub_download(r, 'config.json', cache_dir=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/data/hubprobe'))

```

## `experiments/crossfamily/scripts/explore/hub_check3.py`

source `experiments/crossfamily/scripts/explore/hub_check3.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/hub_check3.py
+++ b/experiments/crossfamily/scripts/explore/hub_check3.py
@@ -4 +4 @@
-api = HfApi(); cd = 'experiments/crossfamily/data/hubprobe'
+api = HfApi(); cd = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/data/hubprobe')

```

## `experiments/crossfamily/scripts/explore/make_s1_test_contexts.py`

source `experiments/crossfamily/scripts/explore/make_s1_test_contexts.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/make_s1_test_contexts.py
+++ b/experiments/crossfamily/scripts/explore/make_s1_test_contexts.py
@@ -1,0 +2 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -7 +8 @@
-ids = [x.strip() for x in open('experiments/contagion/data/ids_gate300.txt') if x.strip()][:N]
+ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()][:N]

```

## `experiments/crossfamily/scripts/explore/peek_ctx.py`

source `experiments/crossfamily/scripts/explore/peek_ctx.py` (group X_crossfamily, owner X): 4 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/peek_ctx.py
+++ b/experiments/crossfamily/scripts/explore/peek_ctx.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -2 +3 @@
-sys.path.insert(0, 'experiments/contagion/scripts')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/scripts'))
@@ -4 +5 @@
-for l in open('experiments/contagion/data/contexts_meta.jsonl'):
+for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')):
@@ -6,2 +7,2 @@
-ids = [x.strip() for x in open('experiments/contagion/data/ids_gate300.txt')]
-ROOT = '/harness/work/runs'
+ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt'))]
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')

```

## `experiments/crossfamily/scripts/explore/probe_ext.py`

source `experiments/crossfamily/scripts/explore/probe_ext.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/probe_ext.py
+++ b/experiments/crossfamily/scripts/explore/probe_ext.py
@@ -2 +2 @@
-sys.path.insert(0, 'experiments/crossfamily/scripts')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
@@ -8 +8 @@
-recs, H = A2.load_p_corpus('experiments/contagion/data/test_S1/manifest.json')
+recs, H = A2.load_p_corpus(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/test_S1/manifest.json'))

```

## `experiments/crossfamily/scripts/explore/probe_ext2.py`

source `experiments/crossfamily/scripts/explore/probe_ext2.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/probe_ext2.py
+++ b/experiments/crossfamily/scripts/explore/probe_ext2.py
@@ -2 +2 @@
-sys.path.insert(0, 'experiments/crossfamily/scripts')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
@@ -8 +8 @@
-recs, H = A2.load_p_corpus('experiments/contagion/data/test_S1/manifest.json')
+recs, H = A2.load_p_corpus(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/test_S1/manifest.json'))

```

## `experiments/crossfamily/scripts/explore/probe_ext3.py`

source `experiments/crossfamily/scripts/explore/probe_ext3.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/probe_ext3.py
+++ b/experiments/crossfamily/scripts/explore/probe_ext3.py
@@ -2 +2 @@
-sys.path.insert(0, 'experiments/crossfamily/scripts')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
@@ -7 +7 @@
-recs, H = A2.load_p_corpus('experiments/contagion/data/test_S1/manifest.json')
+recs, H = A2.load_p_corpus(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/test_S1/manifest.json'))

```

## `experiments/crossfamily/scripts/explore/render_probe.py`

source `experiments/crossfamily/scripts/explore/render_probe.py` (group X_crossfamily, owner X): 5 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/render_probe.py
+++ b/experiments/crossfamily/scripts/explore/render_probe.py
@@ -2 +2 @@
-os.environ.setdefault("HF_HOME", "cache/hf"); os.environ.setdefault("HF_HUB_OFFLINE", "1")
+os.environ.setdefault("HF_HOME", os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "cache/hf")); os.environ.setdefault("HF_HUB_OFFLINE", "1")
@@ -10 +10 @@
-for l in open('experiments/contagion/data/contexts_meta.jsonl'):
+for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')):
@@ -12,2 +12,2 @@
-ids = [x.strip() for x in open('experiments/contagion/data/ids_gate300.txt')]
-ROOT = '/harness/work/runs'
+ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt'))]
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
@@ -34 +34 @@
-    tok = AutoTokenizer.from_pretrained(f'models/{mk}')
+    tok = AutoTokenizer.from_pretrained(fos.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), '{mk}'))

```

## `experiments/crossfamily/scripts/explore/tokids.py`

source `experiments/crossfamily/scripts/explore/tokids.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/explore/tokids.py
+++ b/experiments/crossfamily/scripts/explore/tokids.py
@@ -5 +5 @@
-    tok = AutoTokenizer.from_pretrained(f'models/{mk}')
+    tok = AutoTokenizer.from_pretrained(fos.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), '{mk}'))

```

## `experiments/crossfamily/scripts/ext_frozen/arms.py`

source `experiments/crossfamily/scripts/ext_frozen/arms.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/ext_frozen/arms.py
+++ b/experiments/crossfamily/scripts/ext_frozen/arms.py
@@ -38 +38 @@
-META_PATH = 'experiments/contagion/data/contexts_meta.jsonl'
+META_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')

```

## `experiments/crossfamily/scripts/ext_frozen/ext_prepare.py`

source `experiments/crossfamily/scripts/ext_frozen/ext_prepare.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/ext_frozen/ext_prepare.py
+++ b/experiments/crossfamily/scripts/ext_frozen/ext_prepare.py
@@ -16,2 +16,2 @@
-CONTAGION = 'experiments/contagion'
-PY = '/opt/envs/env_gemma/bin/python'
+CONTAGION = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python')

```

## `experiments/crossfamily/scripts/ext_frozen/fmt_ext.py`

source `experiments/crossfamily/scripts/ext_frozen/fmt_ext.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/ext_frozen/fmt_ext.py
+++ b/experiments/crossfamily/scripts/ext_frozen/fmt_ext.py
@@ -19 +19 @@
-os.environ.setdefault('TIKTOKEN_RS_CACHE_DIR', 'experiments/crossfamily/data/tiktoken_cache')
+os.environ.setdefault('TIKTOKEN_RS_CACHE_DIR', os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/data/tiktoken_cache'))

```

## `experiments/crossfamily/scripts/ext_frozen/format_cpu.py`

source `experiments/crossfamily/scripts/ext_frozen/format_cpu.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/ext_frozen/format_cpu.py
+++ b/experiments/crossfamily/scripts/ext_frozen/format_cpu.py
@@ -42 +42 @@
-CASES = 'experiments/conformance/fuzz/cases.jsonl'
+CASES = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/fuzz/cases.jsonl')
@@ -116 +116 @@
-        _W['g4tok'] = get_tokenizer('models/gemma-4-31b-it-qat-w4a16-ct')
+        _W['g4tok'] = get_tokenizer(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/crossfamily/scripts/ext_frozen/frozen/a_variants.py`

source `experiments/crossfamily/scripts/ext_frozen/frozen/a_variants.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/ext_frozen/frozen/a_variants.py
+++ b/experiments/crossfamily/scripts/ext_frozen/frozen/a_variants.py
@@ -30 +30 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
@@ -148 +148 @@
-QR_PATH = 'experiments/endtoend/export/quarantine_renderer.py'  # workstream E, FROZEN (read-only)
+QR_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/export/quarantine_renderer.py')  # workstream E, FROZEN (read-only)

```

## `experiments/crossfamily/scripts/ext_frozen/frozen/gemma_protocol.py`

source `experiments/crossfamily/scripts/ext_frozen/frozen/gemma_protocol.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups; privacy redaction: host_path_harness 1; M9 competition-harness retry nudge withheld

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/crossfamily/scripts/ext_frozen/qwenproto.py`

source `experiments/crossfamily/scripts/ext_frozen/qwenproto.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/ext_frozen/qwenproto.py
+++ b/experiments/crossfamily/scripts/ext_frozen/qwenproto.py
@@ -30 +30 @@
-os.environ.setdefault("HF_HOME", "cache/hf")
+os.environ.setdefault("HF_HOME", os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "cache/hf"))
@@ -36 +36 @@
-MD = 'models/'
+MD = os.environ.get('TRANSCRIPTLAB_MODELS', 'models/')

```

## `experiments/crossfamily/scripts/ext_prepare.py`

source `experiments/crossfamily/scripts/ext_prepare.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/ext_prepare.py
+++ b/experiments/crossfamily/scripts/ext_prepare.py
@@ -16,2 +16,2 @@
-CONTAGION = 'experiments/contagion'
-PY = '/opt/envs/env_gemma/bin/python'
+CONTAGION = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python')

```

## `experiments/crossfamily/scripts/figure_forest.py`

source `experiments/crossfamily/scripts/figure_forest.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups; privacy redaction: host_path_envs 1

```diff
--- a/experiments/crossfamily/scripts/figure_forest.py
+++ b/experiments/crossfamily/scripts/figure_forest.py
@@ -15 +15 @@
-A_REF = 'experiments/contagion/out/ana_31b_old_gate_k1_random_sample.json'
+A_REF = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/out/ana_31b_old_gate_k1_random_sample.json')

```

## `experiments/crossfamily/scripts/finalize.py`

source `experiments/crossfamily/scripts/finalize.py` (group X_crossfamily, owner X): 4 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/finalize.py
+++ b/experiments/crossfamily/scripts/finalize.py
@@ -12 +12 @@
-A_REF = 'experiments/contagion/out/ana_31b_old_gate_k1_random_sample.json'
+A_REF = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/out/ana_31b_old_gate_k1_random_sample.json')
@@ -58 +58 @@
-PREREG_V2 = 'paper/protocol_theory/prereg/PREREG_v2.md'
+PREREG_V2 = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/PREREG_v2.md')
@@ -61,2 +61,2 @@
-    'corpus_manifest': 'data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json',
-    'pools': 'experiments/contagion/data/confirmatory/pools (S1_A1 first 300, H1 = ranks 1-150, H2 = 151-300; S1_B1 first 600)',
+    'corpus_manifest': os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json'),
+    'pools': os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/confirmatory/pools (S1_A1 first 300, H1 = ranks 1-150, H2 = 151-300; S1_B1 first 600)'),

```

## `experiments/crossfamily/scripts/fmt_ext.py`

source `experiments/crossfamily/scripts/fmt_ext.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/fmt_ext.py
+++ b/experiments/crossfamily/scripts/fmt_ext.py
@@ -19 +19 @@
-os.environ.setdefault('TIKTOKEN_RS_CACHE_DIR', 'experiments/crossfamily/data/tiktoken_cache')
+os.environ.setdefault('TIKTOKEN_RS_CACHE_DIR', os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/data/tiktoken_cache'))

```

## `experiments/crossfamily/scripts/format_cpu.py`

source `experiments/crossfamily/scripts/format_cpu.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/format_cpu.py
+++ b/experiments/crossfamily/scripts/format_cpu.py
@@ -42 +42 @@
-CASES = 'experiments/conformance/fuzz/cases.jsonl'
+CASES = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/fuzz/cases.jsonl')
@@ -116 +116 @@
-        _W['g4tok'] = get_tokenizer('models/gemma-4-31b-it-qat-w4a16-ct')
+        _W['g4tok'] = get_tokenizer(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/crossfamily/scripts/format_v31.py`

source `experiments/crossfamily/scripts/format_v31.py` (group X_crossfamily, owner X): privacy redaction: host_path_envs 1

```diff

```

## `experiments/crossfamily/scripts/frozen/a_variants.py`

source `experiments/crossfamily/scripts/frozen/a_variants.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/frozen/a_variants.py
+++ b/experiments/crossfamily/scripts/frozen/a_variants.py
@@ -30 +30 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
@@ -148 +148 @@
-QR_PATH = 'experiments/endtoend/export/quarantine_renderer.py'  # workstream E, FROZEN (read-only)
+QR_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/export/quarantine_renderer.py')  # workstream E, FROZEN (read-only)

```

## `experiments/crossfamily/scripts/frozen/gemma_protocol.py`

source `experiments/crossfamily/scripts/frozen/gemma_protocol.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups; privacy redaction: host_path_harness 1; M9 competition-harness retry nudge withheld

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/crossfamily/scripts/post_ext.sh`

source `experiments/crossfamily/scripts/post_ext.sh` (group X_crossfamily, owner X): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/post_ext.sh
+++ b/experiments/crossfamily/scripts/post_ext.sh
@@ -4,2 +4,2 @@
-X=experiments/crossfamily; PY=/opt/envs/env_gemma/bin/python
-MAN=data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json; MK=$1
+X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
+MAN=${TRANSCRIPTLAB_ROOT:-.}/data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json; MK=$1

```

## `experiments/crossfamily/scripts/post_v2.sh`

source `experiments/crossfamily/scripts/post_v2.sh` (group X_crossfamily, owner X): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/post_v2.sh
+++ b/experiments/crossfamily/scripts/post_v2.sh
@@ -4,2 +4,2 @@
-X=experiments/crossfamily; PY=/opt/envs/env_gemma/bin/python
-MAN=data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json; MK=$1
+X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
+MAN=${TRANSCRIPTLAB_ROOT:-.}/data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json; MK=$1

```

## `experiments/crossfamily/scripts/prep_all.sh`

source `experiments/crossfamily/scripts/prep_all.sh` (group X_crossfamily, owner X): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/prep_all.sh
+++ b/experiments/crossfamily/scripts/prep_all.sh
@@ -3,2 +3,2 @@
-cd experiments/crossfamily
-PY=/opt/envs/env_gemma/bin/python
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily
+PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python

```

## `experiments/crossfamily/scripts/prep_heldout.sh`

source `experiments/crossfamily/scripts/prep_heldout.sh` (group X_crossfamily, owner X): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/prep_heldout.sh
+++ b/experiments/crossfamily/scripts/prep_heldout.sh
@@ -2,2 +2,2 @@
-cd experiments/crossfamily
-PY=/opt/envs/env_gemma/bin/python
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily
+PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python

```

## `experiments/crossfamily/scripts/prep_prompts.py`

source `experiments/crossfamily/scripts/prep_prompts.py` (group X_crossfamily, owner X): 3 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/prep_prompts.py
+++ b/experiments/crossfamily/scripts/prep_prompts.py
@@ -24,3 +24,3 @@
-GATE = 'experiments/contagion/data/ids_gate300.txt'
-BSET = 'experiments/intent_decoding/data/replay_gemma_first_edit.jsonl'
-PHASE1 = 'experiments/contagion/data/ids_phase1_random600.txt'
+GATE = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')
+BSET = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/data/replay_gemma_first_edit.jsonl')
+PHASE1 = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_phase1_random600.txt')

```

## `experiments/crossfamily/scripts/prep_rest.sh`

source `experiments/crossfamily/scripts/prep_rest.sh` (group X_crossfamily, owner X): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/prep_rest.sh
+++ b/experiments/crossfamily/scripts/prep_rest.sh
@@ -2,2 +2,2 @@
-X=experiments/crossfamily; PY=/opt/envs/env_gemma/bin/python
-POOLS=experiments/contagion/data/confirmatory/pools
+X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
+POOLS=${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion/data/confirmatory/pools

```

## `experiments/crossfamily/scripts/qwenproto.py`

source `experiments/crossfamily/scripts/qwenproto.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/qwenproto.py
+++ b/experiments/crossfamily/scripts/qwenproto.py
@@ -30 +30 @@
-os.environ.setdefault("HF_HOME", "cache/hf")
+os.environ.setdefault("HF_HOME", os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "cache/hf"))
@@ -36 +36 @@
-MD = 'models/'
+MD = os.environ.get('TRANSCRIPTLAB_MODELS', 'models/')

```

## `experiments/crossfamily/scripts/report.py`

source `experiments/crossfamily/scripts/report.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/report.py
+++ b/experiments/crossfamily/scripts/report.py
@@ -104 +104 @@
-ref = load('experiments/contagion/out/ana_31b_old_gate_k1_random_sample.json')
+ref = load(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/out/ana_31b_old_gate_k1_random_sample.json'))

```

## `experiments/crossfamily/scripts/run_chain.sh`

source `experiments/crossfamily/scripts/run_chain.sh` (group X_crossfamily, owner X): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/run_chain.sh
+++ b/experiments/crossfamily/scripts/run_chain.sh
@@ -5,2 +5,2 @@
-cd experiments/crossfamily
-PY=/opt/envs/env_gemma/bin/python
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily
+PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python

```

## `experiments/crossfamily/scripts/run_ext_chain.sh`

source `experiments/crossfamily/scripts/run_ext_chain.sh` (group X_crossfamily, owner X): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/run_ext_chain.sh
+++ b/experiments/crossfamily/scripts/run_ext_chain.sh
@@ -5 +5 @@
-X=experiments/crossfamily; PY=/opt/envs/env_gemma/bin/python
+X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python

```

## `experiments/crossfamily/scripts/run_v2_32b.sh`

source `experiments/crossfamily/scripts/run_v2_32b.sh` (group X_crossfamily, owner X): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/run_v2_32b.sh
+++ b/experiments/crossfamily/scripts/run_v2_32b.sh
@@ -4 +4 @@
-X=experiments/crossfamily; PY=/opt/envs/env_gemma/bin/python
+X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python

```

## `experiments/crossfamily/scripts/run_v2_chain.sh`

source `experiments/crossfamily/scripts/run_v2_chain.sh` (group X_crossfamily, owner X): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/crossfamily/scripts/run_v2_chain.sh
+++ b/experiments/crossfamily/scripts/run_v2_chain.sh
@@ -4 +4 @@
-X=experiments/crossfamily; PY=/opt/envs/env_gemma/bin/python
+X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python

```

## `experiments/crossfamily/scripts/smoke.py`

source `experiments/crossfamily/scripts/smoke.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/smoke.py
+++ b/experiments/crossfamily/scripts/smoke.py
@@ -27 +27 @@
-ids = [x.strip() for x in open('experiments/contagion/data/ids_gate300.txt') if x.strip()][:N]
+ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()][:N]

```

## `experiments/crossfamily/scripts/teacher_xml_slips.py`

source `experiments/crossfamily/scripts/teacher_xml_slips.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/teacher_xml_slips.py
+++ b/experiments/crossfamily/scripts/teacher_xml_slips.py
@@ -14 +14 @@
-    for fn in sorted(glob.glob(f'/harness/work/runs/{run}/llm_calls_*.jsonl')):
+    for fn in sorted(glob.glob(fos.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs/{run}/llm_calls_*.jsonl'))):

```

## `experiments/crossfamily/scripts/v2_frozen/arms.py`

source `experiments/crossfamily/scripts/v2_frozen/arms.py` (group X_crossfamily, owner X): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/v2_frozen/arms.py
+++ b/experiments/crossfamily/scripts/v2_frozen/arms.py
@@ -38 +38 @@
-META_PATH = 'experiments/contagion/data/contexts_meta.jsonl'
+META_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')

```

## `experiments/crossfamily/scripts/v2_frozen/frozen/a_variants.py`

source `experiments/crossfamily/scripts/v2_frozen/frozen/a_variants.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/v2_frozen/frozen/a_variants.py
+++ b/experiments/crossfamily/scripts/v2_frozen/frozen/a_variants.py
@@ -30 +30 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
@@ -148 +148 @@
-QR_PATH = 'experiments/endtoend/export/quarantine_renderer.py'  # workstream E, FROZEN (read-only)
+QR_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/export/quarantine_renderer.py')  # workstream E, FROZEN (read-only)

```

## `experiments/crossfamily/scripts/v2_frozen/frozen/gemma_protocol.py`

source `experiments/crossfamily/scripts/v2_frozen/frozen/gemma_protocol.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups; privacy redaction: host_path_harness 1; M9 competition-harness retry nudge withheld

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/crossfamily/scripts/v2_frozen/qwenproto.py`

source `experiments/crossfamily/scripts/v2_frozen/qwenproto.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/v2_frozen/qwenproto.py
+++ b/experiments/crossfamily/scripts/v2_frozen/qwenproto.py
@@ -30 +30 @@
-os.environ.setdefault("HF_HOME", "cache/hf")
+os.environ.setdefault("HF_HOME", os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "cache/hf"))
@@ -36 +36 @@
-MD = 'models/'
+MD = os.environ.get('TRANSCRIPTLAB_MODELS', 'models/')

```

## `experiments/crossfamily/scripts/v2_frozen/v2_prepare.py`

source `experiments/crossfamily/scripts/v2_frozen/v2_prepare.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/v2_frozen/v2_prepare.py
+++ b/experiments/crossfamily/scripts/v2_frozen/v2_prepare.py
@@ -16,2 +16,2 @@
-CONTAGION = 'experiments/contagion'
-PY = '/opt/envs/env_gemma/bin/python'
+CONTAGION = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python')

```

## `experiments/crossfamily/scripts/v2_prepare.py`

source `experiments/crossfamily/scripts/v2_prepare.py` (group X_crossfamily, owner X): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/crossfamily/scripts/v2_prepare.py
+++ b/experiments/crossfamily/scripts/v2_prepare.py
@@ -16,2 +16,2 @@
-CONTAGION = 'experiments/contagion'
-PY = '/opt/envs/env_gemma/bin/python'
+CONTAGION = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python')

```

## `experiments/intent_decoding/README.md`

source `experiments/intent_decoding/README.md` (group B_intent_decoding, owner B): privacy redaction: host_path_envs 1, host_path_other 1, host_path_repo 2; pseudonymized: moved_tree_path 1

```diff

```

## `experiments/intent_decoding/README_files_section.md`

source `experiments/intent_decoding/README_files_section.md` (group B_intent_decoding, owner B): privacy redaction: host_path_envs 1, host_path_other 1, host_path_repo 1; pseudonymized: moved_tree_path 1

```diff

```

## `experiments/intent_decoding/README_head.md`

source `experiments/intent_decoding/README_head.md` (group B_intent_decoding, owner B): privacy redaction: host_path_repo 1

```diff

```

## `experiments/intent_decoding/analyze_g1r.py`

source `experiments/intent_decoding/analyze_g1r.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/analyze_g1r.py
+++ b/experiments/intent_decoding/analyze_g1r.py
@@ -21 +21 @@
-        CORPUS = 'experiments/conformance/slips/release/gemma4_slips.jsonl'
+        CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')

```

## `experiments/intent_decoding/analyze_replay.py`

source `experiments/intent_decoding/analyze_replay.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/analyze_replay.py
+++ b/experiments/intent_decoding/analyze_replay.py
@@ -235 +235 @@
-            _TK = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+            _TK = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/build_gold_copy.py`

source `experiments/intent_decoding/build_gold_copy.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/build_gold_copy.py
+++ b/experiments/intent_decoding/build_gold_copy.py
@@ -15 +15 @@
-COMP = 'data/comp'
+COMP = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/comp')

```

## `experiments/intent_decoding/confirm/confirm_gold.py`

source `experiments/intent_decoding/confirm/confirm_gold.py` (group B_intent_decoding, owner B): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/confirm/confirm_gold.py
+++ b/experiments/intent_decoding/confirm/confirm_gold.py
@@ -17 +17 @@
-CONTAGION = 'experiments/contagion'
+CONTAGION = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
@@ -23 +23 @@
-ap.add_argument('--tok', default='models/gemma-4-31b-it-qat-w4a16-ct')
+ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/confirm/confirm_runner.py`

source `experiments/intent_decoding/confirm/confirm_runner.py` (group B_intent_decoding, owner B): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/confirm/confirm_runner.py
+++ b/experiments/intent_decoding/confirm/confirm_runner.py
@@ -27 +27 @@
-CONTAGION = 'experiments/contagion'
+CONTAGION = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
@@ -34 +34 @@
-ap.add_argument('--tok', default='models/gemma-4-31b-it-qat-w4a16-ct')
+ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/explore_tok.py`

source `experiments/intent_decoding/explore_tok.py` (group B_intent_decoding, owner B): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/explore_tok.py
+++ b/experiments/intent_decoding/explore_tok.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -3 +4 @@
-tok = AutoTokenizer.from_pretrained('models/gemma-4-31b-it-qat-w4a16-ct')
+tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
@@ -7 +8 @@
-rows=[json.loads(l) for l in open('data/protocol/contexts.jsonl')][:3]
+rows=[json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/protocol/contexts.jsonl'))][:3]

```

## `experiments/intent_decoding/g1r.py`

source `experiments/intent_decoding/g1r.py` (group B_intent_decoding, owner B): 3 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/g1r.py
+++ b/experiments/intent_decoding/g1r.py
@@ -19,2 +19,2 @@
-CORPUS = 'experiments/conformance/slips/release/gemma4_slips.jsonl'
-CTX = 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz'
+CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')
+CTX = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz')
@@ -44 +44 @@
-ap.add_argument('--tok', default='models/gemma-4-31b-it-qat-w4a16-ct')
+ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/map_repair.py`

source `experiments/intent_decoding/map_repair.py` (group B_intent_decoding, owner B): 3 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/map_repair.py
+++ b/experiments/intent_decoding/map_repair.py
@@ -19,2 +19,2 @@
-CORPUS = 'experiments/conformance/slips/release/gemma4_slips.jsonl'
-CTX = 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz'
+CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')
+CTX = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz')
@@ -26 +26 @@
-ap.add_argument('--tok', default='models/gemma-4-31b-it-qat-w4a16-ct')
+ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/mine_logs.py`

source `experiments/intent_decoding/mine_logs.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups; privacy redaction: host_path_harness 1

```diff
--- a/experiments/intent_decoding/mine_logs.py
+++ b/experiments/intent_decoding/mine_logs.py
@@ -14 +14 @@
-ROOT = '/harness/work/runs'
+ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')

```

## `experiments/intent_decoding/mine_payloads.py`

source `experiments/intent_decoding/mine_payloads.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/mine_payloads.py
+++ b/experiments/intent_decoding/mine_payloads.py
@@ -15 +15 @@
-HF = 'hf_cache/hub'
+HF = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'hf_cache/hub')

```

## `experiments/intent_decoding/out/confirm_selftest_manifest.json`

source `experiments/intent_decoding/out/confirm_selftest_manifest.json` (group B_intent_decoding, owner B): M9 competition-harness tool descriptions stripped (6)

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/intent_decoding/out/proxy_eq/_cases.py`

source `experiments/intent_decoding/out/proxy_eq/_cases.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups; pseudonymized: context_id 4

```diff
--- a/experiments/intent_decoding/out/proxy_eq/_cases.py
+++ b/experiments/intent_decoding/out/proxy_eq/_cases.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -3 +4 @@
-sys.argv = ["x", "offline"]; sys.path.insert(0, "experiments/intent_decoding")
+sys.argv = ["x", "offline"]; sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "experiments/intent_decoding"))

```

## `experiments/intent_decoding/out/proxy_eq/_g1check.py`

source `experiments/intent_decoding/out/proxy_eq/_g1check.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/out/proxy_eq/_g1check.py
+++ b/experiments/intent_decoding/out/proxy_eq/_g1check.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -3 +4 @@
-sys.argv = ["x"]; sys.path.insert(0, "experiments/intent_decoding")
+sys.argv = ["x"]; sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "experiments/intent_decoding"))

```

## `experiments/intent_decoding/out/proxy_eq/_render_cmp.py`

source `experiments/intent_decoding/out/proxy_eq/_render_cmp.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/out/proxy_eq/_render_cmp.py
+++ b/experiments/intent_decoding/out/proxy_eq/_render_cmp.py
@@ -3 +3 @@
-sys.argv = ["x", "offline"]; sys.path.insert(0, "experiments/intent_decoding")
+sys.argv = ["x", "offline"]; sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "experiments/intent_decoding"))

```

## `experiments/intent_decoding/out/proxy_eq/_rt.py`

source `experiments/intent_decoding/out/proxy_eq/_rt.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/out/proxy_eq/_rt.py
+++ b/experiments/intent_decoding/out/proxy_eq/_rt.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -3 +4 @@
-sys.argv = ["x"]; sys.path.insert(0, "experiments/intent_decoding")
+sys.argv = ["x"]; sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "experiments/intent_decoding"))

```

## `experiments/intent_decoding/out/proxy_eq/offline_gate_efix_summary.json`

source `experiments/intent_decoding/out/proxy_eq/offline_gate_efix_summary.json` (group B_intent_decoding, owner B): privacy redaction: host_path_repo 1

```diff

```

## `experiments/intent_decoding/out/proxy_eq/offline_render.json`

source `experiments/intent_decoding/out/proxy_eq/offline_render.json` (group B_intent_decoding, owner B): pseudonymized: context_id 10; M9/m11 discovery render windows masked (20)

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/intent_decoding/out/proxy_eq/p1_quotestorm_prefix.json`

source `experiments/intent_decoding/out/proxy_eq/p1_quotestorm_prefix.json` (group B_intent_decoding, owner B): privacy redaction: host_path_repo 1

```diff

```

## `experiments/intent_decoding/out/proxy_eq/p1e_quotestorm_efix.json`

source `experiments/intent_decoding/out/proxy_eq/p1e_quotestorm_efix.json` (group B_intent_decoding, owner B): privacy redaction: host_path_repo 1

```diff

```

## `experiments/intent_decoding/out/proxy_eq/p1e_quotestorm_efix_renderer6b08.json`

source `experiments/intent_decoding/out/proxy_eq/p1e_quotestorm_efix_renderer6b08.json` (group B_intent_decoding, owner B): privacy redaction: host_path_repo 1

```diff

```

## `experiments/intent_decoding/out/proxy_eq/p1e_quotestorm_prefix.json`

source `experiments/intent_decoding/out/proxy_eq/p1e_quotestorm_prefix.json` (group B_intent_decoding, owner B): privacy redaction: host_path_repo 1

```diff

```

## `experiments/intent_decoding/paths_override.py`

source `experiments/intent_decoding/paths_override.py` (group B_intent_decoding, owner B): privacy redaction: host_path_harness 2, host_path_other 2; pseudonymized: moved_tree_path 2

```diff

```

## `experiments/intent_decoding/proxy_equivalence.py`

source `experiments/intent_decoding/proxy_equivalence.py` (group B_intent_decoding, owner B): 2 path literal(s) -> env/config lookups; privacy redaction: host_path_other 1; pseudonymized: context_id 1, moved_tree_path 1

```diff
--- a/experiments/intent_decoding/proxy_equivalence.py
+++ b/experiments/intent_decoding/proxy_equivalence.py
@@ -466,2 +466,2 @@
-    CORPUS = 'experiments/conformance/slips/release/gemma4_slips.jsonl'
-    CTXX = 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz'
+    CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')
+    CTXX = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz')

```

## `experiments/intent_decoding/proxy_vendor/proxy/e2e_proxy.py`

source `experiments/intent_decoding/proxy_vendor/proxy/e2e_proxy.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/proxy_vendor/proxy/e2e_proxy.py
+++ b/experiments/intent_decoding/proxy_vendor/proxy/e2e_proxy.py
@@ -730 +730 @@
-    ap.add_argument('--model-dir', default='models/gemma-4-31b-it-qat-w4a16-ct')
+    ap.add_argument('--model-dir', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/proxy_vendor_fix/proxy/e2e_proxy.py`

source `experiments/intent_decoding/proxy_vendor_fix/proxy/e2e_proxy.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/proxy_vendor_fix/proxy/e2e_proxy.py
+++ b/experiments/intent_decoding/proxy_vendor_fix/proxy/e2e_proxy.py
@@ -726 +726 @@
-    ap.add_argument('--model-dir', default='models/gemma-4-31b-it-qat-w4a16-ct')
+    ap.add_argument('--model-dir', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/quotestorm_model.py`

source `experiments/intent_decoding/quotestorm_model.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/quotestorm_model.py
+++ b/experiments/intent_decoding/quotestorm_model.py
@@ -21 +21 @@
-ap.add_argument('--tok', default='models/gemma-4-e4b-it-qat-w4a16-ct')
+ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-e4b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/replay.py`

source `experiments/intent_decoding/replay.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/replay.py
+++ b/experiments/intent_decoding/replay.py
@@ -21 +21 @@
-ap.add_argument('--tok', default='models/gemma-4-31b-it-qat-w4a16-ct')
+ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/replay_utils.py`

source `experiments/intent_decoding/replay_utils.py` (group B_intent_decoding, owner B): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/replay_utils.py
+++ b/experiments/intent_decoding/replay_utils.py
@@ -1,0 +2 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -29,2 +30,2 @@
-TEMPLATES = {'june': '/harness/work/models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja',
-             'july': 'models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja'}
+TEMPLATES = {'june': os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja'),
+             'july': os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')}

```

## `experiments/intent_decoding/rs279.py`

source `experiments/intent_decoding/rs279.py` (group B_intent_decoding, owner B): 3 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/rs279.py
+++ b/experiments/intent_decoding/rs279.py
@@ -23,2 +23,2 @@
-CORPUS = 'experiments/conformance/slips/release/gemma4_slips.jsonl'
-CTX = 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz'
+CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')
+CTX = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz')
@@ -28 +28 @@
-ap.add_argument('--tok', default='models/gemma-4-31b-it-qat-w4a16-ct')
+ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/intent_decoding/v24/analyze_battery.py`

source `experiments/intent_decoding/v24/analyze_battery.py` (group B_intent_decoding, owner B): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/v24/analyze_battery.py
+++ b/experiments/intent_decoding/v24/analyze_battery.py
@@ -40 +40 @@
-CORPUS = 'data/pnc/contexts/P-swebench-31b-S1-v1'
+CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')

```

## `experiments/intent_decoding/v24/battery_manifest.json`

source `experiments/intent_decoding/v24/battery_manifest.json` (group B_intent_decoding, owner B): privacy redaction: host_path_repo 1

```diff

```

## `experiments/intent_decoding/v24/build_battery.py`

source `experiments/intent_decoding/v24/build_battery.py` (group B_intent_decoding, owner B): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/v24/build_battery.py
+++ b/experiments/intent_decoding/v24/build_battery.py
@@ -26,2 +26,2 @@
-CORPUS = 'data/pnc/contexts/P-swebench-31b-S1-v1'
-TOK = 'models/gemma-4-31b-it-qat-w4a16-ct'
+CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
+TOK = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')

```

## `experiments/intent_decoding/v24/run_battery.py`

source `experiments/intent_decoding/v24/run_battery.py` (group B_intent_decoding, owner B): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/intent_decoding/v24/run_battery.py
+++ b/experiments/intent_decoding/v24/run_battery.py
@@ -28,2 +28,2 @@
-CORPUS = 'data/pnc/contexts/P-swebench-31b-S1-v1'
-TOKP = 'models/gemma-4-31b-it-qat-w4a16-ct'
+CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
+TOKP = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')

```

## `experiments/intent_decoding/v24/run_manifest.json`

source `experiments/intent_decoding/v24/run_manifest.json` (group B_intent_decoding, owner B): privacy redaction: host_path_envs 1, host_path_repo 2

```diff

```

## `experiments/intent_decoding/v25/stack_runner.py`

source `experiments/intent_decoding/v25/stack_runner.py` (group B_intent_decoding, owner B): 4 path literal(s) -> env/config lookups; editorial override (1x): the library lives at slipguard/ in the public tree (sys.path entry for slipguard/src)

```diff
--- a/experiments/intent_decoding/v25/stack_runner.py
+++ b/experiments/intent_decoding/v25/stack_runner.py
@@ -19,4 +19,4 @@
-A_DIR = 'experiments/contagion'
-CORPUS = 'data/pnc/contexts/P-swebench-31b-S1-v1'
-TOKP = 'models/gemma-4-31b-it-qat-w4a16-ct'
-SG_SRC = 'release/lib/src'
+A_DIR = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
+TOKP = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')
+SG_SRC = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'slipguard/src')

```

## `experiments/intent_decoding/v25b/out/preconditions_e4b.json`

source `experiments/intent_decoding/v25b/out/preconditions_e4b.json` (group B_intent_decoding, owner B): privacy redaction: host_path_repo 3

```diff

```

## `experiments/intent_decoding/v25b/stack_runner_e4b.py`

source `experiments/intent_decoding/v25b/stack_runner_e4b.py` (group B_intent_decoding, owner B): 4 path literal(s) -> env/config lookups; editorial override (1x): the library lives at slipguard/ in the public tree (sys.path entry for slipguard/src)

```diff
--- a/experiments/intent_decoding/v25b/stack_runner_e4b.py
+++ b/experiments/intent_decoding/v25b/stack_runner_e4b.py
@@ -23,4 +23,4 @@
-A_DIR = 'experiments/contagion'
-CORPUS = 'data/pnc/contexts/P-swebench-31b-S1-v1'
-TOKP = 'models/gemma-4-31b-it-qat-w4a16-ct'
-SG_SRC = 'release/lib/src'
+A_DIR = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
+CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
+TOKP = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')
+SG_SRC = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'slipguard/src')

```

## `experiments/quant_margins/README.md`

source `experiments/quant_margins/README.md` (group F_quant_margins, owner F): privacy redaction: host_path_harness 1, host_path_repo 1; pseudonymized: run_or_adapter_name 1

```diff

```

## `experiments/quant_margins/wsa/ANALYSIS_PLAN.md`

source `experiments/quant_margins/wsa/ANALYSIS_PLAN.md` (group F_quant_margins, owner F): privacy redaction: host_path_repo 1

```diff

```

## `experiments/quant_margins/wsa/RESULTS.md`

source `experiments/quant_margins/wsa/RESULTS.md` (group F_quant_margins, owner F): privacy redaction: host_path_repo 1, host_path_scratch 1

```diff

```

## `experiments/quant_margins/wsa/candidate_a.py`

source `experiments/quant_margins/wsa/candidate_a.py` (group F_quant_margins, owner F): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/quant_margins/wsa/candidate_a.py
+++ b/experiments/quant_margins/wsa/candidate_a.py
@@ -25 +25 @@
-EQ = emb('models/gemma-4-31b-it-qat-w4a16-ct')[S]; EB = emb('models/gemma-4-31b-it')[S]
+EQ = emb(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))[S]; EB = emb(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it'))[S]

```

## `experiments/quant_margins/wsa/diag_wiki_probe.py`

source `experiments/quant_margins/wsa/diag_wiki_probe.py` (group F_quant_margins, owner F): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/quant_margins/wsa/diag_wiki_probe.py
+++ b/experiments/quant_margins/wsa/diag_wiki_probe.py
@@ -4 +4 @@
-H='experiments/quant_margins/wsa'; sys.path.insert(0,H)
+H=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa'); sys.path.insert(0,H)

```

## `experiments/quant_margins/wsa/dl_community.sh`

source `experiments/quant_margins/wsa/dl_community.sh` (group F_quant_margins, owner F): 4 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/dl_community.sh
+++ b/experiments/quant_margins/wsa/dl_community.sh
@@ -3,2 +3,2 @@
-export HF_HOME=hf_cache HF_HUB_DISABLE_TELEMETRY=1
-cd .
+export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1
+cd ${TRANSCRIPTLAB_ROOT:-.}
@@ -7,2 +7,2 @@
-  rev=$(/opt/envs/env_gemma/bin/python -c "from huggingface_hub import HfApi; print(HfApi().model_info('$r').sha)" 2>/dev/null)
-  if /opt/envs/env_gemma/bin/hf download $r --revision $rev --local-dir $d --max-workers 4 > /dev/null 2>&1; then
+  rev=$(${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python -c "from huggingface_hub import HfApi; print(HfApi().model_info('$r').sha)" 2>/dev/null)
+  if ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf download $r --revision $rev --local-dir $d --max-workers 4 > /dev/null 2>&1; then

```

## `experiments/quant_margins/wsa/dl_qatunq.sh`

source `experiments/quant_margins/wsa/dl_qatunq.sh` (group F_quant_margins, owner F): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/dl_qatunq.sh
+++ b/experiments/quant_margins/wsa/dl_qatunq.sh
@@ -3,3 +3,3 @@
-export HF_HOME=hf_cache HF_HUB_DISABLE_TELEMETRY=1
-cd .
-/opt/envs/env_gemma/bin/hf download google/gemma-4-31b-it-qat-q4_0-unquantized --revision 1e4d8beecacb8b7590c1d8bedd7335f687bf311f \
+export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1
+cd ${TRANSCRIPTLAB_ROOT:-.}
+${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf download google/gemma-4-31b-it-qat-q4_0-unquantized --revision 1e4d8beecacb8b7590c1d8bedd7335f687bf311f \

```

## `experiments/quant_margins/wsa/gate_eval.sh`

source `experiments/quant_margins/wsa/gate_eval.sh` (group F_quant_margins, owner F): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/gate_eval.sh
+++ b/experiments/quant_margins/wsa/gate_eval.sh
@@ -4,2 +4,2 @@
-cd experiments/quant_margins/wsa
-P=.; PY=/opt/envs/env_gemma/bin/python; LOGV=$P/logs/vllm/g3_8304.log; B=http://127.0.0.1:8304/v1
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
+P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LOGV=$P/logs/vllm/g3_8304.log; B=http://127.0.0.1:8304/v1

```

## `experiments/quant_margins/wsa/gpu2_lineend.sh`

source `experiments/quant_margins/wsa/gpu2_lineend.sh` (group F_quant_margins, owner F): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/gpu2_lineend.sh
+++ b/experiments/quant_margins/wsa/gpu2_lineend.sh
@@ -3 +3 @@
-cd experiments/quant_margins/wsa
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
@@ -7 +7 @@
-CUDA_VISIBLE_DEVICES=2 timeout $(( END - $(date -u +%s) )) /opt/envs/env_gemma/bin/python hf_extract.py --arm qatct --lineend_only --no_resid \
+CUDA_VISIBLE_DEVICES=2 timeout $(( END - $(date -u +%s) )) ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python hf_extract.py --arm qatct --lineend_only --no_resid \

```

## `experiments/quant_margins/wsa/gpu3_B_then_sweep.sh`

source `experiments/quant_margins/wsa/gpu3_B_then_sweep.sh` (group F_quant_margins, owner F): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/gpu3_B_then_sweep.sh
+++ b/experiments/quant_margins/wsa/gpu3_B_then_sweep.sh
@@ -4,2 +4,2 @@
-cd experiments/quant_margins/wsa
-P=.; PY=/opt/envs/env_gemma/bin/python; B=http://127.0.0.1:8304/v1; LOGV=$P/logs/vllm/g3_8304.log
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
+P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; B=http://127.0.0.1:8304/v1; LOGV=$P/logs/vllm/g3_8304.log

```

## `experiments/quant_margins/wsa/gpu3_C_gate.sh`

source `experiments/quant_margins/wsa/gpu3_C_gate.sh` (group F_quant_margins, owner F): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/gpu3_C_gate.sh
+++ b/experiments/quant_margins/wsa/gpu3_C_gate.sh
@@ -4,2 +4,2 @@
-cd experiments/quant_margins/wsa
-P=.; PY=/opt/envs/env_gemma/bin/python; B=http://127.0.0.1:8304/v1
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
+P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; B=http://127.0.0.1:8304/v1

```

## `experiments/quant_margins/wsa/gpu3_chain.sh`

source `experiments/quant_margins/wsa/gpu3_chain.sh` (group F_quant_margins, owner F): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/gpu3_chain.sh
+++ b/experiments/quant_margins/wsa/gpu3_chain.sh
@@ -3,2 +3,2 @@
-cd experiments/quant_margins/wsa
-P=.; PY=/opt/envs/env_gemma/bin/python; LOGV=$P/logs/vllm/g3_8304.log
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
+P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LOGV=$P/logs/vllm/g3_8304.log

```

## `experiments/quant_margins/wsa/gpu3_chain2.sh`

source `experiments/quant_margins/wsa/gpu3_chain2.sh` (group F_quant_margins, owner F): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/gpu3_chain2.sh
+++ b/experiments/quant_margins/wsa/gpu3_chain2.sh
@@ -4,2 +4,2 @@
-cd experiments/quant_margins/wsa
-PY=/opt/envs/env_gemma/bin/python; ts() { date -u +%H:%M:%S; }
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
+PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; ts() { date -u +%H:%M:%S; }

```

## `experiments/quant_margins/wsa/gpu3_sweep_after_floor.sh`

source `experiments/quant_margins/wsa/gpu3_sweep_after_floor.sh` (group F_quant_margins, owner F): 1 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/gpu3_sweep_after_floor.sh
+++ b/experiments/quant_margins/wsa/gpu3_sweep_after_floor.sh
@@ -3 +3 @@
-cd experiments/quant_margins/wsa
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa

```

## `experiments/quant_margins/wsa/gpu3_wikival.sh`

source `experiments/quant_margins/wsa/gpu3_wikival.sh` (group F_quant_margins, owner F): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/gpu3_wikival.sh
+++ b/experiments/quant_margins/wsa/gpu3_wikival.sh
@@ -3,2 +3,2 @@
-cd experiments/quant_margins/wsa
-PY=/opt/envs/env_gemma/bin/python; ts() { date -u +%H:%M:%S; }
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
+PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; ts() { date -u +%H:%M:%S; }

```

## `experiments/quant_margins/wsa/gpuX_cneg.sh`

source `experiments/quant_margins/wsa/gpuX_cneg.sh` (group F_quant_margins, owner F): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/gpuX_cneg.sh
+++ b/experiments/quant_margins/wsa/gpuX_cneg.sh
@@ -3 +3 @@
-cd experiments/quant_margins/wsa
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
@@ -6 +6 @@
-CUDA_VISIBLE_DEVICES=$G /opt/envs/env_gemma/bin/python hf_extract.py --arm qatct --cneg_only --no_resid \
+CUDA_VISIBLE_DEVICES=$G ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python hf_extract.py --arm qatct --cneg_only --no_resid \

```

## `experiments/quant_margins/wsa/hf_extract.py`

source `experiments/quant_margins/wsa/hf_extract.py` (group F_quant_margins, owner F): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/quant_margins/wsa/hf_extract.py
+++ b/experiments/quant_margins/wsa/hf_extract.py
@@ -20 +20 @@
-M = 'models'
+M = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'models')

```

## `experiments/quant_margins/wsa/lora_smoke.py`

source `experiments/quant_margins/wsa/lora_smoke.py` (group F_quant_margins, owner F): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/quant_margins/wsa/lora_smoke.py
+++ b/experiments/quant_margins/wsa/lora_smoke.py
@@ -1,0 +2 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -3 +4 @@
-sys.path.insert(0, 'experiments/quant_margins/wsa')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa'))
@@ -6 +7 @@
-its = [json.loads(l) for l in open('experiments/quant_margins/wsa/data/core_items.jsonl')]; its = [i for i in its if i['kind'] == 'valid'][:3]
+its = [json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa/data/core_items.jsonl'))]; its = [i for i in its if i['kind'] == 'valid'][:3]

```

## `experiments/quant_margins/wsa/make_smoke_adapters.py`

source `experiments/quant_margins/wsa/make_smoke_adapters.py` (group F_quant_margins, owner F): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/quant_margins/wsa/make_smoke_adapters.py
+++ b/experiments/quant_margins/wsa/make_smoke_adapters.py
@@ -0,0 +1 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -2 +3 @@
-sys.path.insert(0, 'experiments/quant_margins/wsa')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa'))
@@ -8 +9 @@
-    write_peft_adapter(f'experiments/quant_margins/wsa/adapters/smoke_{variant}',
+    write_peft_adapter(fos.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa/adapters/smoke_{variant}'),

```

## `experiments/quant_margins/wsa/out/byte_identity_floor.json`

source `experiments/quant_margins/wsa/out/byte_identity_floor.json` (group F_quant_margins, owner F): privacy redaction: secret_assignment 6

```diff

```

## `experiments/quant_margins/wsa/out/byte_identity_repairA.json`

source `experiments/quant_margins/wsa/out/byte_identity_repairA.json` (group F_quant_margins, owner F): privacy redaction: secret_assignment 4

```diff

```

## `experiments/quant_margins/wsa/out/repairB_fit.json`

source `experiments/quant_margins/wsa/out/repairB_fit.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/repairB_selection.json`

source `experiments/quant_margins/wsa/out/repairB_selection.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/repairB_selection_lineend150_superseded.json`

source `experiments/quant_margins/wsa/out/repairB_selection_lineend150_superseded.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/repairC_fit.json`

source `experiments/quant_margins/wsa/out/repairC_fit.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/repairC_selection.json`

source `experiments/quant_margins/wsa/out/repairC_selection.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/repair_innercv_300_stageA.json`

source `experiments/quant_margins/wsa/out/repair_innercv_300_stageA.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 2, host_path_scratch 1

```diff

```

## `experiments/quant_margins/wsa/out/repair_innercv_300_stageB.json`

source `experiments/quant_margins/wsa/out/repair_innercv_300_stageB.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 2, host_path_scratch 1

```diff

```

## `experiments/quant_margins/wsa/out/repair_innercv_full.json`

source `experiments/quant_margins/wsa/out/repair_innercv_full.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/repair_innercv_full_wiki.json`

source `experiments/quant_margins/wsa/out/repair_innercv_full_wiki.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/repair_selection_final.json`

source `experiments/quant_margins/wsa/out/repair_selection_final.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/t1_scores.json`

source `experiments/quant_margins/wsa/out/t1_scores.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 3

```diff

```

## `experiments/quant_margins/wsa/out/t1_scores_bf16.json`

source `experiments/quant_margins/wsa/out/t1_scores_bf16.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 1

```diff

```

## `experiments/quant_margins/wsa/out/t1_scores_partial.json`

source `experiments/quant_margins/wsa/out/t1_scores_partial.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 1

```diff

```

## `experiments/quant_margins/wsa/out/weights_proxy.json`

source `experiments/quant_margins/wsa/out/weights_proxy.json` (group F_quant_margins, owner F): privacy redaction: host_path_repo 8

```diff

```

## `experiments/quant_margins/wsa/pnc_render.py`

source `experiments/quant_margins/wsa/pnc_render.py` (group F_quant_margins, owner F): 2 path literal(s) -> env/config lookups

```diff
--- a/experiments/quant_margins/wsa/pnc_render.py
+++ b/experiments/quant_margins/wsa/pnc_render.py
@@ -7,2 +7,2 @@
-PNC = 'data/pnc'
-TOK_DIR = 'models/gemma-4-31b-it-qat-w4a16-ct'
+PNC = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc')
+TOK_DIR = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')

```

## `experiments/quant_margins/wsa/repair_memit.py`

source `experiments/quant_margins/wsa/repair_memit.py` (group F_quant_margins, owner F): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/quant_margins/wsa/repair_memit.py
+++ b/experiments/quant_margins/wsa/repair_memit.py
@@ -29 +29 @@
-ap.add_argument('--embed', default='models/gemma-4-31b-it-qat-w4a16-ct/model.safetensors')
+ap.add_argument('--embed', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct/model.safetensors'))

```

## `experiments/quant_margins/wsa/stack_d.py`

source `experiments/quant_margins/wsa/stack_d.py` (group F_quant_margins, owner F): 1 path literal(s) -> env/config lookups; editorial override (1x): the library lives at slipguard/ in the public tree (sys.path entry for slipguard/src)

```diff
--- a/experiments/quant_margins/wsa/stack_d.py
+++ b/experiments/quant_margins/wsa/stack_d.py
@@ -10 +10 @@
-sys.path.insert(0, H); sys.path.insert(0, 'release/lib/src')
+sys.path.insert(0, H); sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'slipguard/src'))

```

## `experiments/quant_margins/wsa/t1_sweep.sh`

source `experiments/quant_margins/wsa/t1_sweep.sh` (group F_quant_margins, owner F): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/t1_sweep.sh
+++ b/experiments/quant_margins/wsa/t1_sweep.sh
@@ -4,2 +4,2 @@
-cd experiments/quant_margins/wsa
-P=.; M=$P/models; PY=/opt/envs/env_gemma/bin/python
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
+P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python

```

## `experiments/quant_margins/wsa/temperature_baseline.py`

source `experiments/quant_margins/wsa/temperature_baseline.py` (group F_quant_margins, owner F): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/quant_margins/wsa/temperature_baseline.py
+++ b/experiments/quant_margins/wsa/temperature_baseline.py
@@ -11 +11 @@
-ap.add_argument('--embed', default='models/gemma-4-31b-it-qat-w4a16-ct')
+ap.add_argument('--embed', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/quant_margins/wsa/weights_proxy.py`

source `experiments/quant_margins/wsa/weights_proxy.py` (group F_quant_margins, owner F): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/quant_margins/wsa/weights_proxy.py
+++ b/experiments/quant_margins/wsa/weights_proxy.py
@@ -12 +12 @@
-M = 'models'
+M = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'models')

```

## `experiments/quant_margins/wsa/wiki_crosscheck.sh`

source `experiments/quant_margins/wsa/wiki_crosscheck.sh` (group F_quant_margins, owner F): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/quant_margins/wsa/wiki_crosscheck.sh
+++ b/experiments/quant_margins/wsa/wiki_crosscheck.sh
@@ -3,2 +3,2 @@
-cd experiments/quant_margins/wsa
-P=.; M=$P/models; PY=/opt/envs/env_gemma/bin/python; LOGV=$P/logs/vllm/g3_8304.log; B=http://127.0.0.1:8304/v1
+cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
+P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LOGV=$P/logs/vllm/g3_8304.log; B=http://127.0.0.1:8304/v1

```

## `experiments/endtoend/RUNBOOK.md`

source `experiments/endtoend/RUNBOOK.md` (group E_endtoend, owner E): privacy redaction: host_path_envs 1, host_path_other 1, host_path_repo 8; 1 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `experiments/endtoend/acceptance/FREEZE_CANDIDATE.txt`

source `experiments/endtoend/acceptance/FREEZE_CANDIDATE.txt` (group E_endtoend, owner E): privacy redaction: host_path_repo 1; pseudonymized: context_id 1

```diff

```

## `experiments/endtoend/acceptance/p1_quotestorm_efix.json`

source `experiments/endtoend/acceptance/p1_quotestorm_efix.json` (group E_endtoend, owner E): privacy redaction: host_path_repo 1

```diff

```

## `experiments/endtoend/analysis/branch_fidelity_corrected.py`

source `experiments/endtoend/analysis/branch_fidelity_corrected.py` (group E_endtoend, owner E): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/analysis/branch_fidelity_corrected.py
+++ b/experiments/endtoend/analysis/branch_fidelity_corrected.py
@@ -10,0 +11 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -16 +17 @@
-E = Path('experiments/endtoend')
+E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))

```

## `experiments/endtoend/analysis/build_branch_plan.py`

source `experiments/endtoend/analysis/build_branch_plan.py` (group E_endtoend, owner E): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/analysis/build_branch_plan.py
+++ b/experiments/endtoend/analysis/build_branch_plan.py
@@ -9,0 +10 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -17 +18 @@
-E = Path('experiments/endtoend')
+E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))

```

## `experiments/endtoend/analysis/failure_log.py`

source `experiments/endtoend/analysis/failure_log.py` (group E_endtoend, owner E): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/analysis/failure_log.py
+++ b/experiments/endtoend/analysis/failure_log.py
@@ -18,0 +19 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -29 +30 @@
-E = Path('experiments/endtoend')
+E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))

```

## `experiments/endtoend/analysis/make_results.py`

source `experiments/endtoend/analysis/make_results.py` (group E_endtoend, owner E): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/analysis/make_results.py
+++ b/experiments/endtoend/analysis/make_results.py
@@ -2,0 +3 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -12 +13 @@
-E = Path('experiments/endtoend')
+E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))

```

## `experiments/endtoend/analysis/pilot_metrics.py`

source `experiments/endtoend/analysis/pilot_metrics.py` (group E_endtoend, owner E): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/analysis/pilot_metrics.py
+++ b/experiments/endtoend/analysis/pilot_metrics.py
@@ -17,0 +18 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -27 +28 @@
-E = Path('experiments/endtoend')
+E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))

```

## `experiments/endtoend/analysis/prereg_analysis.py`

source `experiments/endtoend/analysis/prereg_analysis.py` (group E_endtoend, owner E): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/analysis/prereg_analysis.py
+++ b/experiments/endtoend/analysis/prereg_analysis.py
@@ -10,0 +11 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -309 +310 @@
-    p.add_argument('--tasks', default='experiments/endtoend/configs/eligible_113.txt')
+    p.add_argument('--tasks', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/configs/eligible_113.txt'))

```

## `experiments/endtoend/harness/common.py`

source `experiments/endtoend/harness/common.py` (group E_endtoend, owner E): 3 path literal(s) -> env/config lookups; privacy redaction: host_path_other 1; 1 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff
--- a/experiments/endtoend/harness/common.py
+++ b/experiments/endtoend/harness/common.py
@@ -14,2 +14,2 @@
-E2E = Path('experiments/endtoend')
-COMP = Path('data/comp')
+E2E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))
+COMP = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/comp'))
@@ -18 +18 @@
-os.environ.setdefault('DOCKER_CONFIG', 'docker/cli')
+os.environ.setdefault('DOCKER_CONFIG', os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'docker/cli'))

```

## `experiments/endtoend/harness/wheelsel.py`

source `experiments/endtoend/harness/wheelsel.py` (group E_endtoend, owner E): 2 path literal(s) -> env/config lookups; privacy redaction: host_path_harness 1

```diff
--- a/experiments/endtoend/harness/wheelsel.py
+++ b/experiments/endtoend/harness/wheelsel.py
@@ -18,0 +19 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -32,2 +33,2 @@
-E2E = Path('experiments/endtoend')
-COMP = Path('data/comp')
+E2E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))
+COMP = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/comp'))

```

## `experiments/endtoend/proxy/e2e_proxy.py`

source `experiments/endtoend/proxy/e2e_proxy.py` (group E_endtoend, owner E): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/proxy/e2e_proxy.py
+++ b/experiments/endtoend/proxy/e2e_proxy.py
@@ -726 +726 @@
-    ap.add_argument('--model-dir', default='models/gemma-4-31b-it-qat-w4a16-ct')
+    ap.add_argument('--model-dir', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))

```

## `experiments/endtoend/run_population.sh`

source `experiments/endtoend/run_population.sh` (group E_endtoend, owner E): 5 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/run_population.sh
+++ b/experiments/endtoend/run_population.sh
@@ -5 +5 @@
-#   bash run_population.sh http://127.0.0.1:8300/v1 gemma-4-31b models/gemma-4-31b-it-qat-w4a16-ct \
+#   bash run_population.sh http://127.0.0.1:8300/v1 gemma-4-31b ${TRANSCRIPTLAB_MODELS:-models}/gemma-4-31b-it-qat-w4a16-ct \
@@ -10 +10 @@
-E=experiments/endtoend; L=tools/limited.sh; PY=/opt/envs/env_gemma/bin/python
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; L=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
@@ -14 +14 @@
-export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=cache/hf HF_HUB_OFFLINE=1
+export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf HF_HUB_OFFLINE=1

```

## `experiments/endtoend/run_population_qi.sh`

source `experiments/endtoend/run_population_qi.sh` (group E_endtoend, owner E): 5 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/run_population_qi.sh
+++ b/experiments/endtoend/run_population_qi.sh
@@ -6 +6 @@
-#   bash run_population.sh http://127.0.0.1:8300/v1 gemma-4-31b models/gemma-4-31b-it-qat-w4a16-ct \
+#   bash run_population.sh http://127.0.0.1:8300/v1 gemma-4-31b ${TRANSCRIPTLAB_MODELS:-models}/gemma-4-31b-it-qat-w4a16-ct \
@@ -11 +11 @@
-E=experiments/endtoend; L=tools/limited.sh; PY=/opt/envs/env_gemma/bin/python
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; L=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
@@ -15 +15 @@
-export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=cache/hf HF_HUB_OFFLINE=1
+export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf HF_HUB_OFFLINE=1

```

## `experiments/endtoend/ext/dispatch_ext.sh`

source `experiments/endtoend/ext/dispatch_ext.sh` (group E_endtoend, owner E): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/ext/dispatch_ext.sh
+++ b/experiments/endtoend/ext/dispatch_ext.sh
@@ -11 +11 @@
-E=experiments/endtoend; P=.; LOG=$E/ext/dispatch_ext.log
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; P=${TRANSCRIPTLAB_ROOT:-.}; LOG=$E/ext/dispatch_ext.log

```

## `experiments/endtoend/ext/run_awq.sh`

source `experiments/endtoend/ext/run_awq.sh` (group E_endtoend, owner E): 1 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/ext/run_awq.sh
+++ b/experiments/endtoend/ext/run_awq.sh
@@ -5 +5 @@
-G=6; P=.; E=$P/experiments/endtoend; LOG=$E/ext/run_awq.log
+G=6; P=${TRANSCRIPTLAB_ROOT:-.}; E=$P/experiments/endtoend; LOG=$E/ext/run_awq.log

```

## `experiments/endtoend/ext/dispatch_awq2.sh`

source `experiments/endtoend/ext/dispatch_awq2.sh` (group E_endtoend, owner E): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/ext/dispatch_awq2.sh
+++ b/experiments/endtoend/ext/dispatch_awq2.sh
@@ -11 +11 @@
-E=experiments/endtoend; P=.; LOG=$E/ext/dispatch_awq2.log
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; P=${TRANSCRIPTLAB_ROOT:-.}; LOG=$E/ext/dispatch_awq2.log

```

## `experiments/endtoend/ext/dispatch_q.sh`

source `experiments/endtoend/ext/dispatch_q.sh` (group E_endtoend, owner E): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/ext/dispatch_q.sh
+++ b/experiments/endtoend/ext/dispatch_q.sh
@@ -16 +16 @@
-E=experiments/endtoend; P=.
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; P=${TRANSCRIPTLAB_ROOT:-.}

```

## `tools/dl_eaudit.sh`

source `tools/dl_eaudit.sh` (group E_endtoend, owner E): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/tools/dl_eaudit.sh
+++ b/tools/dl_eaudit.sh
@@ -3 +3 @@
-cd .; LOG=logs/dl/eaudit.log
+cd ${TRANSCRIPTLAB_ROOT:-.}; LOG=logs/dl/eaudit.log
@@ -8 +8 @@
-  HF_HOME=cache/hf /opt/envs/env_gemma/bin/hf download $r --revision $rev --local-dir $d --max-workers 4 >> $LOG.raw 2>&1 \
+  HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf download $r --revision $rev --local-dir $d --max-workers 4 >> $LOG.raw 2>&1 \

```

## `experiments/endtoend/ext/run_final_analyses.sh`

source `experiments/endtoend/ext/run_final_analyses.sh` (group E_endtoend, owner E): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/ext/run_final_analyses.sh
+++ b/experiments/endtoend/ext/run_final_analyses.sh
@@ -5 +5 @@
-E=experiments/endtoend; P=.; PY=/opt/envs/env_agentpaper/bin/python
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `paper/protocol_theory/prereg/E_PREDICTIONS_v1.md`

source `paper/protocol_theory/prereg/E_PREDICTIONS_v1.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/PREREG_DEVIATIONS.md`

source `paper/protocol_theory/prereg/PREREG_DEVIATIONS.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_envs 1, host_path_harness 1, host_path_other 2, host_path_repo 1; pseudonymized: moved_tree_path 2

```diff

```

## `paper/protocol_theory/prereg/PREREG_v1.md`

source `paper/protocol_theory/prereg/PREREG_v1.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.1_thinkingOFF.md`

source `paper/protocol_theory/prereg/PREREG_v2.1_thinkingOFF.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.2_thoughtSuppressed.md`

source `paper/protocol_theory/prereg/PREREG_v2.2_thoughtSuppressed.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.3_onsetTransplant.md`

source `paper/protocol_theory/prereg/PREREG_v2.3_onsetTransplant.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_harness 1, host_path_other 1, host_path_repo 1; 1 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.4_injectedSlipRepair.md`

source `paper/protocol_theory/prereg/PREREG_v2.4_injectedSlipRepair.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_harness 1, host_path_other 1, host_path_repo 1; 1 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.5_stackGain.md`

source `paper/protocol_theory/prereg/PREREG_v2.5_stackGain.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.5b_stackGainE4B.md`

source `paper/protocol_theory/prereg/PREREG_v2.5b_stackGainE4B.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.6_auditBehaviour.md`

source `paper/protocol_theory/prereg/PREREG_v2.6_auditBehaviour.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.7_robustness.md`

source `paper/protocol_theory/prereg/PREREG_v2.7_robustness.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.8_cli.md`

source `paper/protocol_theory/prereg/PREREG_v2.8_cli.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_envs 1, host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/PREREG_v2.md`

source `paper/protocol_theory/prereg/PREREG_v2.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 1

```diff

```

## `paper/protocol_theory/prereg/compute_predictions.py`

source `paper/protocol_theory/prereg/compute_predictions.py` (group PREREG_all, owner D, A, X, E): 1 path literal(s) -> env/config lookups

```diff
--- a/paper/protocol_theory/prereg/compute_predictions.py
+++ b/paper/protocol_theory/prereg/compute_predictions.py
@@ -5,0 +6 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -27 +28 @@
-json.dump(out, open('paper/protocol_theory/prereg/predictions_v1.json', 'w'), indent=1)
+json.dump(out, open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/predictions_v1.json'), 'w'), indent=1)

```

## `paper/protocol_theory/sim/out/t2_trigger_scan.json`

source `paper/protocol_theory/sim/out/t2_trigger_scan.json` (group PREREG_all, owner D, A, X, E): pseudonymized: log_name 8

```diff

```

## `paper/protocol_theory/sim/out/t3_results.json`

source `paper/protocol_theory/sim/out/t3_results.json` (group PREREG_all, owner D, A, X, E): pseudonymized: run_or_adapter_name 84

```diff

```

## `paper/protocol_theory/sim/out/t3_results_v1_TEACHER_CONTAMINATED_B300.json`

source `paper/protocol_theory/sim/out/t3_results_v1_TEACHER_CONTAMINATED_B300.json` (group PREREG_all, owner D, A, X, E): pseudonymized: run_or_adapter_name 87

```diff

```

## `paper/protocol_theory/sim/out/t3_results_v2_test_B2.json`

source `paper/protocol_theory/sim/out/t3_results_v2_test_B2.json` (group PREREG_all, owner D, A, X, E): pseudonymized: run_or_adapter_name 84

```diff

```

## `experiments/pnc/README.md`

source `experiments/pnc/README.md` (group PREREG_all, owner D, A, X, E): privacy redaction: host_path_repo 2

```diff

```

## `transcriptlab/README.md`

source `release/transcriptlab/README.md` (group T_transcriptlab_cli, owner C (packaging task of 2026-11-06); R integrates): editorial override (1x): re-export item 9

```diff
--- a/release/transcriptlab/README.md
+++ b/transcriptlab/README.md
@@ -119 +119 @@
-- **Golden tests:** the job list equals the registered plan; `report` reproduces the paper's bf16 row and X's
+- **Golden tests:** the job list equals the registered plan except the `tier` label (seeds depend only on the state id); `report` reproduces the paper's bf16 row and X's

```

## `notebooks/quickstart.ipynb`

source `release/quickstart/quickstart.ipynb` (group Q_quickstart, owner C (packaging task of 2026-11-06); R integrates): editorial override (1x): reviewer: works from the Kaggle dataset layout

```diff
--- a/release/quickstart/quickstart.ipynb
+++ b/notebooks/quickstart.ipynb
@@ -37 +37 @@
-    "    for c in [os.environ.get(\"TRANSCRIPTLAB_ROOT\"), *map(str, [Path.cwd(), *Path.cwd().parents])]:\n",
+    "    for c in [os.environ.get(\"TRANSCRIPTLAB_ROOT\"), *map(str, [Path.cwd(), *Path.cwd().parents]), *glob.glob(\"/kaggle/input/*\"), *glob.glob(\"/kaggle/input/*/*\")]:\n",

```

## `notebooks/quickstart.py`

source `release/quickstart/quickstart.py` (group Q_quickstart, owner C (packaging task of 2026-11-06); R integrates): editorial override (1x): reviewer: works from the Kaggle dataset layout (repository attached as a dataset) without TRANSCRIPTLAB_ROOT

```diff
--- a/release/quickstart/quickstart.py
+++ b/notebooks/quickstart.py
@@ -24 +24 @@
-    for c in [os.environ.get("TRANSCRIPTLAB_ROOT"), *map(str, [Path.cwd(), *Path.cwd().parents])]:
+    for c in [os.environ.get("TRANSCRIPTLAB_ROOT"), *map(str, [Path.cwd(), *Path.cwd().parents]), *glob.glob("/kaggle/input/*"), *glob.glob("/kaggle/input/*/*")]:

```

## `RESOURCE_CARD.md`

source `release/RESOURCE_CARD.md` (group C_docs_figures, owner C, W): editorial override (1x): m10: the public tree ships the Writeup's Figure 1 (v3) at figures/; paper/protocol/draft/ is not shipped

```diff
--- a/release/RESOURCE_CARD.md
+++ b/RESOURCE_CARD.md
@@ -31 +31 @@
-| Every Figure 1 number, from the result JSONs | `python paper/protocol/draft/figures/fig1_gains.py`. It writes `figure_data.json` (value, `path#key`, file sha256). |
+| Every Figure 1 number, from the result JSONs | `python figures/fig1_gains_v3.py`. It writes `figures/figure_data_v3.json` (value, `path#key`, file sha256). |

```

## `figures/fig1_gains_v3.py`

source `paper/protocol/draft/figures/fig1_gains_v3.py` (group C_docs_figures, owner C, W): privacy redaction: host_path_envs 1

```diff

```

## `experiments/contagion/data/confirmatory/pools/POOLS_MANIFEST.json`

source `experiments/contagion/data/confirmatory/pools/POOLS_MANIFEST.json` (group T_cli_runtime_inputs, owner A, X, E (inputs of the transcriptlab CLI)): privacy redaction: host_path_repo 2

```diff

```

## `experiments/contagion/data/confirmatory/meta_S1.jsonl`

source `experiments/contagion/data/confirmatory/meta_S1.jsonl` (group T_cli_runtime_inputs, owner A, X, E (inputs of the transcriptlab CLI)): privacy redaction: host_path_repo 7882

```diff

```

## `experiments/contagion/out/main/rC31b_v2.jsonl`

source `experiments/contagion/out/main/rC31b_v2.jsonl` (group T_cli_runtime_inputs, owner A, X, E (inputs of the transcriptlab CLI)): 7 developer e-mail address(es) masked as <email>; privacy redaction: host_path_repo 2690

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/contagion/out/main/rCbf16_v2.jsonl`

source `experiments/contagion/out/main/rCbf16_v2.jsonl` (group T_cli_test_fixtures, owner A, X (registered PNC runs used by transcriptlab/tests)): 1 developer e-mail address(es) masked as <email>; privacy redaction: host_path_repo 1200

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/crossfamily/out/ext/gen_qwen3-coder-30b.jsonl`

source `experiments/crossfamily/out/ext/gen_qwen3-coder-30b.jsonl` (group T_cli_test_fixtures, owner A, X (registered PNC runs used by transcriptlab/tests)): 2 developer e-mail address(es) masked as <email>

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `RESULTS.md`

source `release/docs_pack/RESULTS.md` (group DOCS_pack, owner PI (docs_pack: read and copy only)): editorial override (10x): paths: the library lives at slipguard/ (files byte-identical, hashes unchanged)

```diff
--- a/release/docs_pack/RESULTS.md
+++ b/RESULTS.md
@@ -88,2 +88,2 @@
-| Wrong call delivered on ill-formed turns of known intent | known-intent turns 218; vLLM 0.19.1 built-in 188; vLLM 0.33 built-in 216; slipguard plugin 0.33 0 | frozen suite | `release/lib/results/conformance_pnc/RESULTS.json#populations/ill_intent_known`<br>`release/lib/results/conformance_pnc/RESULTS.json#targets/vllm019.server/intent_known/wrong`<br>`release/lib/results/conformance_pnc/RESULTS.json#targets/vllm033.server/intent_known/wrong`<br>`release/lib/results/conformance_pnc/RESULTS.json#targets/gg.vllm033.server/intent_known/wrong` |
-| Opt-in text repair on the same turns (after the post-hoc fix; before: prefix_fix/) | exact 152; loud 66; pre-fix exact 152; pre-fix wrong 1 | descriptive (post-hoc fix disclosed) | `release/lib/results/conformance_pnc/RESULTS.json#targets/gg.repair/intent_known/exact`<br>`release/lib/results/conformance_pnc/RESULTS.json#targets/gg.repair/intent_known/surfaced`<br>`release/lib/results/conformance_pnc/prefix_fix/RESULTS.json#targets/gg.repair/intent_known/exact`<br>`release/lib/results/conformance_pnc/prefix_fix/RESULTS.json#targets/gg.repair/intent_known/wrong` |
+| Wrong call delivered on ill-formed turns of known intent | known-intent turns 218; vLLM 0.19.1 built-in 188; vLLM 0.33 built-in 216; slipguard plugin 0.33 0 | frozen suite | `slipguard/results/conformance_pnc/RESULTS.json#populations/ill_intent_known`<br>`slipguard/results/conformance_pnc/RESULTS.json#targets/vllm019.server/intent_known/wrong`<br>`slipguard/results/conformance_pnc/RESULTS.json#targets/vllm033.server/intent_known/wrong`<br>`slipguard/results/conformance_pnc/RESULTS.json#targets/gg.vllm033.server/intent_known/wrong` |
+| Opt-in text repair on the same turns (after the post-hoc fix; before: prefix_fix/) | exact 152; loud 66; pre-fix exact 152; pre-fix wrong 1 | descriptive (post-hoc fix disclosed) | `slipguard/results/conformance_pnc/RESULTS.json#targets/gg.repair/intent_known/exact`<br>`slipguard/results/conformance_pnc/RESULTS.json#targets/gg.repair/intent_known/surfaced`<br>`slipguard/results/conformance_pnc/prefix_fix/RESULTS.json#targets/gg.repair/intent_known/exact`<br>`slipguard/results/conformance_pnc/prefix_fix/RESULTS.json#targets/gg.repair/intent_known/wrong` |
@@ -149,2 +149,2 @@
-| `release/lib/results/conformance_pnc/RESULTS.json` | 408147e6a86abe72 |
-| `release/lib/results/conformance_pnc/prefix_fix/RESULTS.json` | 3f6af9593acaf5ff |
+| `slipguard/results/conformance_pnc/RESULTS.json` | 408147e6a86abe72 |
+| `slipguard/results/conformance_pnc/prefix_fix/RESULTS.json` | 3f6af9593acaf5ff |

```

## `REPRODUCE.md`

source `release/docs_pack/REPRODUCE.md` (group DOCS_pack, owner PI (docs_pack: read and copy only)): editorial override (1x): public tree ships the clean Writeup without source comments, so the shipped gate checks READMEs only (WP-release); editorial override (1x): final public export: 83 manifest entries match through export edits (one more than the stand-in: the security / M9 redactions)

```diff
--- a/release/docs_pack/REPRODUCE.md
+++ b/REPRODUCE.md
@@ -26 +26 @@
-| `python tools/verify_preregs.py --root .` | each registration document and frozen code file against the hash recorded at its freeze | `PASS: 0 unexplained problem(s)`, exit 0. The last lines tally it: 25/25 documents (13 of them through their recorded export edits); 173 manifest entries match (82 through export edits: host paths and privacy redactions), 47 are withheld with their hashes listed, 8 differ for logged reasons (`PREREGISTRATIONS.md`); 26/26 files frozen with PREREG_v2.7 and later | 25/25 documents (23 byte-identical, 2 by frozen prefix); 220 manifest entries and 26/26 later frozen files match; the same 8 differ for logged reasons; exit 0 |
+| `python tools/verify_preregs.py --root .` | each registration document and frozen code file against the hash recorded at its freeze | `PASS: 0 unexplained problem(s)`, exit 0. The last lines tally it: 25/25 documents (13 of them through their recorded export edits); 173 manifest entries match (83 through export edits: host paths, privacy redactions and the withheld-material / competition-text redactions), 47 are withheld with their hashes listed, 8 differ for logged reasons (`PREREGISTRATIONS.md`); 26/26 files frozen with PREREG_v2.7 and later | 25/25 documents (23 byte-identical, 2 by frozen prefix); 220 manifest entries and 26/26 later frozen files match; the same 8 differ for logged reasons; exit 0 |
@@ -28 +28 @@
-| `python release/build_numbers.py --strict` | every number in the paper against its source file#key | paper gate PASS, 0 blocking (paper v2.2 of 2026-11-07: 163 OK, 26 qualitative/derived, 31 text, 3 node; refreshed at the final export). On this tree it checks the paper and READMEs only | same counts |
+| `python release/build_numbers.py --strict` | every number in the paper against its source file#key | paper gate PASS, 0 blocking (paper v2.2 of 2026-11-07: 163 OK, 26 qualitative/derived, 31 text, 3 node; refreshed at the final export). On this public tree, which ships the clean Writeup (`paper/WRITEUP.md`, no source comments), the shipped gate checks the READMEs only (`strict gate: PASS -- paper (none)`); the paper master's source comments were gated against this tree at export (0 blocking: 169 OK, 32 qualitative/derived, 41 text, 4 node; `VERIFY_LOG.md`) | same counts |

```

## `tools/LEVEL1_RESULTS.md`

source `release/docs_pack/tools/LEVEL1_RESULTS.md` (group DOCS_pack, owner PI (docs_pack: read and copy only)): editorial override (2x): the library lives at slipguard/ in the public tree; editorial override (3x): the library lives at slipguard/ in the public tree

```diff
--- a/release/docs_pack/tools/LEVEL1_RESULTS.md
+++ b/tools/LEVEL1_RESULTS.md
@@ -98 +98 @@
-| sweep_ship | 13 F SWEEP_PLAN re-scored by shipped code | `(cd . && python release/lib/dev/check_wsa.py experiments/quant_margins/wsa/out > $OUT/sweep_ship/check_wsa.json)` | **POINTS-IDENTICAL** | 4.4 |
+| sweep_ship | 13 F SWEEP_PLAN re-scored by shipped code | `(cd . && python slipguard/dev/check_wsa.py experiments/quant_margins/wsa/out > $OUT/sweep_ship/check_wsa.json)` | **POINTS-IDENTICAL** | 4.4 |
@@ -108 +108 @@
-| v210_rescore | 20 PREREG_v2.10 audits re-scored from records | `(cd release/lib && env PYTHONPATH=src python -m slipguard audit-weights --from-records $ROOT/experiments/quant_margins/wsa/out/audit_v210_31b_nvfp4_nvidia.records.jsonl --reference $ROOT/experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out $OUT/v210_rescore/audit_v210_31b_nvfp4_nvidia.json)`<br>`(cd release/lib && env PYTHONPATH=src python -m slipguard audit-weights --from-records $ROOT/experiments/quant_margins/wsa/out/audit_v210_31b_qatawq_cyankiwi.records.jsonl --reference $ROOT/experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out $OUT/v210_rescore/audit_v210_31b_qatawq_cyankiwi.json)`<br>`(cd release/lib && env PYTHONPATH=src python -m slipguard audit-weights --from-records $ROOT/experiments/quant_margins/wsa/out/audit_v210_31b_qatnvfp4_melcheikh.records.jsonl --reference $ROOT/experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out $OUT/v210_rescore/audit_v210_31b_qatnvfp4_melcheikh.json)` | **IDENTICAL** | 1.3 |
+| v210_rescore | 20 PREREG_v2.10 audits re-scored from records | `(cd slipguard && env PYTHONPATH=src python -m slipguard audit-weights --from-records $ROOT/experiments/quant_margins/wsa/out/audit_v210_31b_nvfp4_nvidia.records.jsonl --reference $ROOT/experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out $OUT/v210_rescore/audit_v210_31b_nvfp4_nvidia.json)`<br>`(cd slipguard && env PYTHONPATH=src python -m slipguard audit-weights --from-records $ROOT/experiments/quant_margins/wsa/out/audit_v210_31b_qatawq_cyankiwi.records.jsonl --reference $ROOT/experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out $OUT/v210_rescore/audit_v210_31b_qatawq_cyankiwi.json)`<br>`(cd slipguard && env PYTHONPATH=src python -m slipguard audit-weights --from-records $ROOT/experiments/quant_margins/wsa/out/audit_v210_31b_qatnvfp4_melcheikh.records.jsonl --reference $ROOT/experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out $OUT/v210_rescore/audit_v210_31b_qatnvfp4_melcheikh.json)` | **IDENTICAL** | 1.3 |
@@ -136 +136 @@
-- `release/lib/dev/check_wsa.py` re-scores F's frozen sweep records with the shipped `slipguard.weights` and compares
+- `slipguard/dev/check_wsa.py` re-scores F's frozen sweep records with the shipped `slipguard.weights` and compares

```

## `tools/compare_json.py`

source `release/docs_pack/tools/compare_json.py` (group DOCS_pack, owner PI (docs_pack: read and copy only)): editorial override (1x): the library lives at slipguard/ in the public tree

```diff
--- a/release/docs_pack/tools/compare_json.py
+++ b/tools/compare_json.py
@@ -17 +17 @@
-``--wsa-check`` classifies the JSON summary printed by release/lib/dev/check_wsa.py (it compares the shipped audit
+``--wsa-check`` classifies the JSON summary printed by slipguard/dev/check_wsa.py (it compares the shipped audit

```

## `tools/make_results_md.py`

source `release/docs_pack/tools/make_results_md.py` (group DOCS_pack, owner PI (docs_pack: read and copy only)): editorial override (2x): the library lives at slipguard/ in the public tree

```diff
--- a/release/docs_pack/tools/make_results_md.py
+++ b/tools/make_results_md.py
@@ -30,2 +30,2 @@
-PNC = 'release/lib/results/conformance_pnc/RESULTS.json'
-PNCF = 'release/lib/results/conformance_pnc/prefix_fix/RESULTS.json'
+PNC = 'slipguard/results/conformance_pnc/RESULTS.json'
+PNCF = 'slipguard/results/conformance_pnc/prefix_fix/RESULTS.json'

```

## `tools/reproduce_level1.sh`

source `release/docs_pack/tools/reproduce_level1.sh` (group DOCS_pack, owner PI (docs_pack: read and copy only)): editorial override (1x): the library lives at slipguard/ in the public tree; editorial override (1x): the library lives at slipguard/ in the public tree

```diff
--- a/release/docs_pack/tools/reproduce_level1.sh
+++ b/tools/reproduce_level1.sh
@@ -241 +241 @@
-  PYRUN_STDOUT="$D/check_wsa.json" ALLOW_RC=1 pyrun . "$PY_A" release/lib/dev/check_wsa.py $W/out
+  PYRUN_STDOUT="$D/check_wsa.json" ALLOW_RC=1 pyrun . "$PY_A" slipguard/dev/check_wsa.py $W/out
@@ -256 +256 @@
-    pyrun release/lib env PYTHONPATH=src "$PY_A" -m slipguard audit-weights --from-records "$f" \
+    pyrun slipguard env PYTHONPATH=src "$PY_A" -m slipguard audit-weights --from-records "$f" \

```

## `experiments/contagion/out/v21_v22_script_hashes.txt`

source `experiments/contagion/out/v21_v22_script_hashes.txt` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): privacy redaction: host_path_harness 1, host_path_other 1; pseudonymized: moved_tree_path 1

```diff

```

## `experiments/contagion/scripts/archive/sample_pools_v2.v1.py`

source `experiments/contagion/scripts/archive/sample_pools_v2.v1.py` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/contagion/scripts/archive/sample_pools_v2.v1.py
+++ b/experiments/contagion/scripts/archive/sample_pools_v2.v1.py
@@ -28 +28 @@
-PREREG = 'paper/protocol_theory/prereg/PREREG_v2.md'
+PREREG = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/PREREG_v2.md')

```

## `experiments/endtoend/configs/channel_prior.json`

source `experiments/endtoend/configs/channel_prior.json` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): privacy redaction: host_path_repo 1

```diff

```

## `experiments/endtoend/configs/client_tools.json`

source `experiments/endtoend/configs/client_tools.json` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): M9 competition-harness tool descriptions stripped (9)

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/endtoend/proxy/VENDOR_B.txt`

source `experiments/endtoend/proxy/VENDOR_B.txt` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): privacy redaction: host_path_repo 1

```diff

```

## `experiments/endtoend/run_branches.sh`

source `experiments/endtoend/run_branches.sh` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 4 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/run_branches.sh
+++ b/experiments/endtoend/run_branches.sh
@@ -9 +9 @@
-E=experiments/endtoend; L=tools/limited.sh; PY=/opt/envs/env_gemma/bin/python
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; L=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
@@ -13 +13 @@
-export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=cache/hf HF_HUB_OFFLINE=1
+export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf HF_HUB_OFFLINE=1

```

## `experiments/endtoend/run_chain.sh`

source `experiments/endtoend/run_chain.sh` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 1 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/run_chain.sh
+++ b/experiments/endtoend/run_chain.sh
@@ -9 +9 @@
-E=experiments/endtoend; cd $E
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; cd $E

```

## `experiments/endtoend/run_pilot.sh`

source `experiments/endtoend/run_pilot.sh` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 5 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/run_pilot.sh
+++ b/experiments/endtoend/run_pilot.sh
@@ -16,2 +16,2 @@
-E=experiments/endtoend; L=tools/limited.sh
-PY=/opt/envs/env_gemma/bin/python
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; L=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh
+PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
@@ -19 +19 @@
-MODEL_DIR=${MODEL_DIR:-models/gemma-4-31b-it-qat-w4a16-ct}
+MODEL_DIR=${MODEL_DIR:-${TRANSCRIPTLAB_MODELS:-models}/gemma-4-31b-it-qat-w4a16-ct}
@@ -25 +25 @@
-export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=cache/hf HF_HUB_OFFLINE=1
+export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf HF_HUB_OFFLINE=1

```

## `experiments/endtoend/tests/run_branch_test.sh`

source `experiments/endtoend/tests/run_branch_test.sh` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 4 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/tests/run_branch_test.sh
+++ b/experiments/endtoend/tests/run_branch_test.sh
@@ -6 +6 @@
-E=experiments/endtoend; L=tools/limited.sh; PY=/opt/envs/env_gemma/bin/python
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; L=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
@@ -9 +9 @@
-export TMPDIR=$E/tmp HF_HOME=cache/hf HF_HUB_OFFLINE=1
+export TMPDIR=$E/tmp HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf HF_HUB_OFFLINE=1

```

## `experiments/endtoend/tests/smoke31.sh`

source `experiments/endtoend/tests/smoke31.sh` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/tests/smoke31.sh
+++ b/experiments/endtoend/tests/smoke31.sh
@@ -4 +4 @@
-E=experiments/endtoend
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend
@@ -6 +6 @@
-bash $E/run_population.sh ${1:-http://127.0.0.1:8300/v1} gemma-4-31b models/gemma-4-31b-it-qat-w4a16-ct \
+bash $E/run_population.sh ${1:-http://127.0.0.1:8300/v1} gemma-4-31b ${TRANSCRIPTLAB_MODELS:-models}/gemma-4-31b-it-qat-w4a16-ct \

```

## `experiments/endtoend/tests/test_generate.py`

source `experiments/endtoend/tests/test_generate.py` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 1 path literal(s) -> env/config lookups; pseudonymized: context_id 1

```diff
--- a/experiments/endtoend/tests/test_generate.py
+++ b/experiments/endtoend/tests/test_generate.py
@@ -3,0 +4 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -13 +14 @@
-MD = 'models/gemma-4-31b-it-qat-w4a16-ct'
+MD = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')

```

## `experiments/endtoend/tests/test_ipd_real.py`

source `experiments/endtoend/tests/test_ipd_real.py` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/tests/test_ipd_real.py
+++ b/experiments/endtoend/tests/test_ipd_real.py
@@ -17 +17 @@
-ctxs = [json.loads(l) for l in open('data/protocol/contexts.jsonl')]
+ctxs = [json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/protocol/contexts.jsonl'))]

```

## `experiments/endtoend/tests/test_parity.py`

source `experiments/endtoend/tests/test_parity.py` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/tests/test_parity.py
+++ b/experiments/endtoend/tests/test_parity.py
@@ -17 +17 @@
-ctxs = [json.loads(l) for l in open('data/protocol/contexts.jsonl')]
+ctxs = [json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/protocol/contexts.jsonl'))]

```

## `experiments/endtoend/tests/test_protocol.py`

source `experiments/endtoend/tests/test_protocol.py` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 3 path literal(s) -> env/config lookups; pseudonymized: context_id 1; B4 stray-']' hang-input checks dropped from the public copy

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/endtoend/tests/test_proxy_e2e.py`

source `experiments/endtoend/tests/test_proxy_e2e.py` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/tests/test_proxy_e2e.py
+++ b/experiments/endtoend/tests/test_proxy_e2e.py
@@ -3,0 +4 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -17 +18 @@
-MD = 'models/gemma-4-12b-it-qat-w4a16-ct'
+MD = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-12b-it-qat-w4a16-ct')

```

## `experiments/endtoend/tests/test_renderer_compat.py`

source `experiments/endtoend/tests/test_renderer_compat.py` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/endtoend/tests/test_renderer_compat.py
+++ b/experiments/endtoend/tests/test_renderer_compat.py
@@ -8,0 +9 @@
+import os  # added by the repo export (paths are env/config driven)
@@ -61 +62 @@
-pay = [json.loads(l) for l in open('experiments/intent_decoding/data/quotestorm.jsonl')]
+pay = [json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/data/quotestorm.jsonl'))]

```

## `experiments/endtoend/tools_freeze.sh`

source `experiments/endtoend/tools_freeze.sh` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): 1 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/endtoend/tools_freeze.sh
+++ b/experiments/endtoend/tools_freeze.sh
@@ -4 +4 @@
-E=experiments/endtoend; cd $E
+E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; cd $E

```

## `experiments/intent_decoding/v24/battery_inputs.jsonl`

source `experiments/intent_decoding/v24/battery_inputs.jsonl` (group FROZEN_listed, owner A, B, C, E, X (files named in freeze manifests)): privacy redaction: home_dir_user 3, secret_assignment 1; 3 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `experiments/soak/out/aborted_K1_165752/run_K1.json`

source `experiments/soak/out/aborted_K1_165752/run_K1.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 2

```diff

```

## `experiments/soak/out/run_K1.done.json`

source `experiments/soak/out/run_K1.done.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 2

```diff

```

## `experiments/soak/out/run_K1.json`

source `experiments/soak/out/run_K1.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 2

```diff

```

## `experiments/soak/out/run_K2.done.json`

source `experiments/soak/out/run_K2.done.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 2

```diff

```

## `experiments/soak/out/run_K2.json`

source `experiments/soak/out/run_K2.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 2

```diff

```

## `experiments/soak/soak_analyze.py`

source `experiments/soak/soak_analyze.py` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 2 path literal(s) -> env/config lookups; editorial override (1x): the library lives at slipguard/ in the public tree (sys.path entry for slipguard/src)

```diff
--- a/experiments/soak/soak_analyze.py
+++ b/experiments/soak/soak_analyze.py
@@ -16 +16 @@
-sys.path.insert(0, 'release/lib/src')
+sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'slipguard/src'))
@@ -22 +22 @@
-ap.add_argument('--pnc', default='data/pnc')
+ap.add_argument('--pnc', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc'))

```

## `experiments/soak/soak_drive.py`

source `experiments/soak/soak_drive.py` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/soak/soak_drive.py
+++ b/experiments/soak/soak_drive.py
@@ -22 +22 @@
-ap.add_argument('--pnc', default='data/pnc'); ap.add_argument('--max_tokens', type=int, default=2048)
+ap.add_argument('--pnc', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc')); ap.add_argument('--max_tokens', type=int, default=2048)

```

## `experiments/v28/run_cli.sh`

source `experiments/v28/run_cli.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v28/run_cli.sh
+++ b/experiments/v28/run_cli.sh
@@ -5 +5 @@
-G=6; PORT=8376; P=.; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct
+G=6; PORT=8376; P=${TRANSCRIPTLAB_ROOT:-.}; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct
@@ -7 +7 @@
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/v29/run_cov.sh`

source `experiments/v29/run_cov.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v29/run_cov.sh
+++ b/experiments/v29/run_cov.sh
@@ -5,2 +5,2 @@
-G=$1; VC=$2; CC=$3; PORT=$((8380 + G)); P=.; LOG=$P/experiments/v29/run_cov.log; LIM=$P/tools/limited.sh
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+G=$1; VC=$2; CC=$3; PORT=$((8380 + G)); P=${TRANSCRIPTLAB_ROOT:-.}; LOG=$P/experiments/v29/run_cov.log; LIM=$P/tools/limited.sh
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/v210/analyze_v210.py`

source `experiments/v210/analyze_v210.py` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/v210/analyze_v210.py
+++ b/experiments/v210/analyze_v210.py
@@ -4 +4 @@
-O = 'experiments/quant_margins/wsa/out'
+O = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa/out')

```

## `experiments/v210/chain_gpu6.sh`

source `experiments/v210/chain_gpu6.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 1 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v210/chain_gpu6.sh
+++ b/experiments/v210/chain_gpu6.sh
@@ -3 +3 @@
-P=.
+P=${TRANSCRIPTLAB_ROOT:-.}

```

## `experiments/v210/run_audits.sh`

source `experiments/v210/run_audits.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v210/run_audits.sh
+++ b/experiments/v210/run_audits.sh
@@ -5,2 +5,2 @@
-G=$1; VC=$2; CC=$3; PORT=$((8390 + G)); P=.; LOG=$P/experiments/v210/run_audits.log; LIM=$P/tools/limited.sh
-PYA=/opt/envs/env_agentpaper/bin/python; O=$P/experiments/quant_margins/wsa/out; REF=$O/audit_sweep_31b_bf16.records.jsonl
+G=$1; VC=$2; CC=$3; PORT=$((8390 + G)); P=${TRANSCRIPTLAB_ROOT:-.}; LOG=$P/experiments/v210/run_audits.log; LIM=$P/tools/limited.sh
+PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python; O=$P/experiments/quant_margins/wsa/out; REF=$O/audit_sweep_31b_bf16.records.jsonl

```

## `experiments/v211/run_masked.sh`

source `experiments/v211/run_masked.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v211/run_masked.sh
+++ b/experiments/v211/run_masked.sh
@@ -5 +5 @@
-G=4; PORT=8384; P=.; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct; LIM=$P/tools/limited.sh
+G=4; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct; LIM=$P/tools/limited.sh
@@ -8 +8 @@
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/v211/run_masked_r2.sh`

source `experiments/v211/run_masked_r2.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v211/run_masked_r2.sh
+++ b/experiments/v211/run_masked_r2.sh
@@ -5 +5 @@
-G=4; PORT=8384; P=.; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct; LIM=$P/tools/limited.sh
+G=4; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct; LIM=$P/tools/limited.sh
@@ -8 +8 @@
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/v211b/pool_v211b.py`

source `experiments/v211b/pool_v211b.py` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 1

```diff

```

## `experiments/v211b/run_masked2.sh`

source `experiments/v211b/run_masked2.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v211b/run_masked2.sh
+++ b/experiments/v211b/run_masked2.sh
@@ -5 +5 @@
-G=4; PORT=8384; P=.; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct; LIM=$P/tools/limited.sh
+G=4; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct; LIM=$P/tools/limited.sh
@@ -8 +8 @@
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/v212/run_llama.sh`

source `experiments/v212/run_llama.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v212/run_llama.sh
+++ b/experiments/v212/run_llama.sh
@@ -4 +4 @@
-G=4; PORT=8384; P=.; M=$P/models/community/NousResearch_Hermes-3-Llama-3.1-8B; LIM=$P/tools/limited.sh
+G=4; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models/community/NousResearch_Hermes-3-Llama-3.1-8B; LIM=$P/tools/limited.sh
@@ -6 +6 @@
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/v212/run_llama_r2.sh`

source `experiments/v212/run_llama_r2.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v212/run_llama_r2.sh
+++ b/experiments/v212/run_llama_r2.sh
@@ -4 +4 @@
-G=4; PORT=8384; P=.; M=$P/models/community/NousResearch_Hermes-3-Llama-3.1-8B; LIM=$P/tools/limited.sh
+G=4; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models/community/NousResearch_Hermes-3-Llama-3.1-8B; LIM=$P/tools/limited.sh
@@ -6 +6 @@
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/v213/run_h2p.sh`

source `experiments/v213/run_h2p.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v213/run_h2p.sh
+++ b/experiments/v213/run_h2p.sh
@@ -4 +4 @@
-G=4; PORT=8384; P=.; M=$P/models/community/NousResearch_Hermes-2-Pro-Llama-3-8B; LIM=$P/tools/limited.sh
+G=4; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models/community/NousResearch_Hermes-2-Pro-Llama-3-8B; LIM=$P/tools/limited.sh
@@ -6 +6 @@
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/v214/analyze_v214_bf16.py`

source `experiments/v214/analyze_v214_bf16.py` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 1 path literal(s) -> env/config lookups

```diff
--- a/experiments/v214/analyze_v214_bf16.py
+++ b/experiments/v214/analyze_v214_bf16.py
@@ -8 +8 @@
-D = 'experiments/contagion'
+D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')

```

## `experiments/v214/run_bf16.sh`

source `experiments/v214/run_bf16.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v214/run_bf16.sh
+++ b/experiments/v214/run_bf16.sh
@@ -4 +4 @@
-GA=4; GB=5; PORT=8384; P=.; M=$P/models/gemma-4-31b-it; LIM=$P/tools/limited.sh
+GA=4; GB=5; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models/gemma-4-31b-it; LIM=$P/tools/limited.sh
@@ -6 +6 @@
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/v215/analyze_v215.py`

source `experiments/v215/analyze_v215.py` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 1

```diff

```

## `experiments/v215/driver.sh`

source `experiments/v215/driver.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 2 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v215/driver.sh
+++ b/experiments/v215/driver.sh
@@ -5 +5 @@
-P=.; V=$P/experiments/v215; LOG=$V/driver.log
+P=${TRANSCRIPTLAB_ROOT:-.}; V=$P/experiments/v215; LOG=$V/driver.log
@@ -18 +18 @@
-( cd $P && TMPDIR=$P/tmp taskset -c 120-123 /opt/envs/env_gemma/bin/python $V/analyze_v215.py --out $P/experiments/contagion/out/confirmatory/v215_audit_panel.json >> $LOG 2>&1 )
+( cd $P && TMPDIR=$P/tmp taskset -c 120-123 ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python $V/analyze_v215.py --out $P/experiments/contagion/out/confirmatory/v215_audit_panel.json >> $LOG 2>&1 )

```

## `experiments/v215/run_one.sh`

source `experiments/v215/run_one.sh` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): 3 path literal(s) -> ${ENV:-default}

```diff
--- a/experiments/v215/run_one.sh
+++ b/experiments/v215/run_one.sh
@@ -4 +4 @@
-C=$1; G=$2; PORT=$3; P=.; LIM=$P/tools/limited.sh; CM=$P/models/community; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct
+C=$1; G=$2; PORT=$3; P=${TRANSCRIPTLAB_ROOT:-.}; LIM=$P/tools/limited.sh; CM=$P/models/community; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct
@@ -7 +7 @@
-PYG=/opt/envs/env_gemma/bin/python; PYA=/opt/envs/env_agentpaper/bin/python
+PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python

```

## `experiments/transcriptlab_cli/run_e2b/gen.jsonl`

source `experiments/transcriptlab_cli/run_e2b/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 8, home_dir_user 1, host_path_repo 1200; 1 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `experiments/transcriptlab_cli/run_e2b/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_e2b/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_e4b16/gen.jsonl`

source `experiments/transcriptlab_cli/run_e4b16/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_e4b16/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_e4b16/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v211_masked/gen.jsonl`

source `experiments/transcriptlab_cli/run_v211_masked/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v211_masked/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v211_masked/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v211b_masked/gen.jsonl`

source `experiments/transcriptlab_cli/run_v211b_masked/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v211b_masked/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v211b_masked/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v212_hermes3/gen.jsonl`

source `experiments/transcriptlab_cli/run_v212_hermes3/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 2

```diff

```

## `experiments/transcriptlab_cli/run_v212_hermes3/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v212_hermes3/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 2, host_path_repo 14

```diff

```

## `experiments/transcriptlab_cli/run_v214_bf16/gen.jsonl`

source `experiments/transcriptlab_cli/run_v214_bf16/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 2, host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v214_bf16/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v214_bf16/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v215_nvnvfp4/gen.jsonl`

source `experiments/transcriptlab_cli/run_v215_nvnvfp4/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 3, host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v215_nvnvfp4/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v215_nvnvfp4/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v215_qatawq/gen.jsonl`

source `experiments/transcriptlab_cli/run_v215_qatawq/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 2, host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v215_qatawq/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v215_qatawq/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v215_qatnvfp4/gen.jsonl`

source `experiments/transcriptlab_cli/run_v215_qatnvfp4/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 3, host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v215_qatnvfp4/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v215_qatnvfp4/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v216_awq_quanttrio/gen.jsonl`

source `experiments/transcriptlab_cli/run_v216_awq_quanttrio/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 4, host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v216_awq_quanttrio/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v216_awq_quanttrio/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v216_fp8_redhat/gen.jsonl`

source `experiments/transcriptlab_cli/run_v216_fp8_redhat/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 3, host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v216_fp8_redhat/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v216_fp8_redhat/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v216_nvfp4_redhat/gen.jsonl`

source `experiments/transcriptlab_cli/run_v216_nvfp4_redhat/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 4, host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v216_nvfp4_redhat/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v216_nvfp4_redhat/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v216_qatunq/gen.jsonl`

source `experiments/transcriptlab_cli/run_v216_qatunq/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 2, host_path_repo 1200, secret_assignment 1

```diff

```

## `experiments/transcriptlab_cli/run_v216_qatunq/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v216_qatunq/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v28/gen.jsonl`

source `experiments/transcriptlab_cli/run_v28/gen.jsonl` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: email 4, host_path_repo 1200

```diff

```

## `experiments/transcriptlab_cli/run_v28/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v28/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_envs 1, host_path_repo 11

```diff

```

## `experiments/transcriptlab_cli/run_v28_failed_1733/transcriptlab_run.json`

source `experiments/transcriptlab_cli/run_v28_failed_1733/transcriptlab_run.json` (group NEW_experiments, owner A, E, F, C (v2.7-v2.10, soak, E ext/awq, CLI runs, weight-audit records)): privacy redaction: host_path_repo 11

```diff

```

## `experiments/contagion/logs/ctg-Cbf16.log`

source `experiments/contagion/logs/ctg-Cbf16.log` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: host_path_repo 1

```diff

```

## `experiments/contagion/out/main/rAWQbf16_v27.jsonl`

source `experiments/contagion/out/main/rAWQbf16_v27.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 3 developer e-mail address(es) masked as <email>; privacy redaction: host_path_repo 1200

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/contagion/out/main/rC12b_v2.jsonl`

source `experiments/contagion/out/main/rC12b_v2.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 2 developer e-mail address(es) masked as <email>; privacy redaction: host_path_repo 1500, secret_assignment 4

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/contagion/out/main/rCautoround_v26.jsonl`

source `experiments/contagion/out/main/rCautoround_v26.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 3 developer e-mail address(es) masked as <email>; privacy redaction: host_path_repo 1200

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/contagion/out/main/rCawq_v26.jsonl`

source `experiments/contagion/out/main/rCawq_v26.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 4 developer e-mail address(es) masked as <email>; privacy redaction: host_path_repo 1200

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/contagion/out/main/rCe4b_v2.jsonl`

source `experiments/contagion/out/main/rCe4b_v2.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: host_path_repo 1500

```diff

```

## `experiments/contagion/out/main/rO_v23.jsonl`

source `experiments/contagion/out/main/rO_v23.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: host_path_repo 1200, secret_assignment 3

```diff

```

## `experiments/contagion/out/main/rSA_v27.jsonl`

source `experiments/contagion/out/main/rSA_v27.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 1 developer e-mail address(es) masked as <email>; privacy redaction: host_path_repo 1200, secret_assignment 1

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/contagion/out/main/rSB_v27.jsonl`

source `experiments/contagion/out/main/rSB_v27.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 4 developer e-mail address(es) masked as <email>; privacy redaction: host_path_repo 1200

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/contagion/out/main/rT00_v27.jsonl`

source `experiments/contagion/out/main/rT00_v27.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 3 developer e-mail address(es) masked as <email>; privacy redaction: host_path_repo 1200

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/contagion/out/main/rT06_v27.jsonl`

source `experiments/contagion/out/main/rT06_v27.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 2 developer e-mail address(es) masked as <email>; privacy redaction: home_dir_user 1, host_path_repo 1200; 1 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/crossfamily/out/ext/gen_devstral-24b.jsonl`

source `experiments/crossfamily/out/ext/gen_devstral-24b.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 5 developer e-mail address(es) masked as <email>

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/crossfamily/out/ext/gen_gpt-oss-20b.jsonl`

source `experiments/crossfamily/out/ext/gen_gpt-oss-20b.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 3 developer e-mail address(es) masked as <email>

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/crossfamily/out/ext/gen_qwen3.8-27b.jsonl`

source `experiments/crossfamily/out/ext/gen_qwen3.8-27b.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): 7 developer e-mail address(es) masked as <email>

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `experiments/crossfamily/out/v2/gen_qwen3-32b.jsonl`

source `experiments/crossfamily/out/v2/gen_qwen3-32b.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: email 3, home_dir_user 2, secret_assignment 3; 2 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `experiments/crossfamily/out/v2/gen_qwen3-32b_lenient.jsonl`

source `experiments/crossfamily/out/v2/gen_qwen3-32b_lenient.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: email 4, home_dir_user 2, secret_assignment 4; 2 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `experiments/crossfamily/out/v2/gen_qwen3-8b.jsonl`

source `experiments/crossfamily/out/v2/gen_qwen3-8b.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: secret_assignment 2

```diff

```

## `experiments/crossfamily/out/v2/gen_qwen3-8b_lenient.jsonl`

source `experiments/crossfamily/out/v2/gen_qwen3-8b_lenient.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: secret_assignment 2

```diff

```

## `experiments/crossfamily/out/v2/gen_qwen3.5-9b.jsonl`

source `experiments/crossfamily/out/v2/gen_qwen3.5-9b.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: email 6, git_author_name 4, secret_assignment 6; 1 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `experiments/crossfamily/out/v2/gen_qwen3.5-9b_lenient.jsonl`

source `experiments/crossfamily/out/v2/gen_qwen3.5-9b_lenient.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: email 8, git_author_name 6, secret_assignment 6; 1 host-root pseudonym(s) neutralized (data / home root pseudonyms -> <host-path>, <home>)

```diff

```

## `experiments/intent_decoding/v24/battery_run.jsonl`

source `experiments/intent_decoding/v24/battery_run.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: secret_assignment 6

```diff

```

## `experiments/intent_decoding/v25/out/live_f2.jsonl`

source `experiments/intent_decoding/v25/out/live_f2.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: secret_assignment 2

```diff

```

## `experiments/intent_decoding/v25/out/live_l1.jsonl`

source `experiments/intent_decoding/v25/out/live_l1.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: email 2

```diff

```

## `experiments/intent_decoding/v25/out/replay.jsonl`

source `experiments/intent_decoding/v25/out/replay.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: email 2

```diff

```

## `experiments/soak/out/proxy_logs/proxy_fullp.jsonl`

source `experiments/soak/out/proxy_logs/proxy_fullp.jsonl` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: email 10, git_author_name 1

```diff

```

## `experiments/transcriptlab_cli/run_e2b/run.log`

source `experiments/transcriptlab_cli/run_e2b/run.log` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: host_path_envs 2, host_path_repo 14

```diff

```

## `experiments/transcriptlab_cli/run_e4b16/run.log`

source `experiments/transcriptlab_cli/run_e4b16/run.log` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: host_path_envs 2, host_path_repo 14

```diff

```

## `experiments/transcriptlab_cli/run_v28/run.log`

source `experiments/transcriptlab_cli/run_v28/run.log` (group L1_reanalysis_inputs, owner A, B, F, X, C (run records read by tools/reproduce_level1.sh)): privacy redaction: host_path_envs 2, host_path_repo 14

```diff

```

## `slipguard/src/slipguard/_frozen/MANIFEST.json`

source `release/lib/src/slipguard/_frozen/MANIFEST.json` (group L_library, owner L): frozen MANIFEST: _vendor/gemmaproto/gen.py recorded as exported (M2 neutralization)

```diff
--- a/release/lib/src/slipguard/_frozen/MANIFEST.json
+++ b/slipguard/src/slipguard/_frozen/MANIFEST.json
@@ -158,3 +158,5 @@
-   "shipped_sha256": "7113088fc8f2b194bd56cef42b3486431f63fb4cd9ff9ac1e5f519e77c447b0d",
-   "changed": false,
-   "changes": []
+   "shipped_sha256": "9538a2f4dc2ec026651e8a3e7d9f48737b3e62a4a019d8d180381297f94a29fa",
+   "changed": true,
+   "changes": [
+    "injection fragments in TRICKY_FRAGMENTS neutralised by the public-repo export (release_hygiene M2; see EXPORT_DIFFS.md / FROZEN_EXPORT_PINS.json)"
+   ]

```

## `slipguard/src/slipguard/_vendor/gemmaproto/gen.py`

source `release/lib/src/slipguard/_vendor/gemmaproto/gen.py` (group L_library, owner L): injection fragments neutralized (release_hygiene M2): 3 literal(s) replaced

```diff
(diff suppressed: the changed lines carry withheld injection fragments or developer e-mail addresses; see WITHHELD.json security_withheld, SECURITY.md and the counts above)
```

## `slipguard/tests/test_frozen.py`

source `release/lib/tests/test_frozen.py` (group L_library, owner L): editorial override (1x): M2: gen.py is neutralized by the public export, so it joins the changed-by-export set this test asserts

```diff
--- a/release/lib/tests/test_frozen.py
+++ b/slipguard/tests/test_frozen.py
@@ -19 +19 @@
-        "_frozen/endtoend/configs/channel_prior.json"])
+        "_frozen/endtoend/configs/channel_prior.json", "_vendor/gemmaproto/gen.py"])

```

