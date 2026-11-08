
## 5. Files
- **Library**
  - `gemma_protocol.py`: grammar, guard, slip/opener/kwarg/qkey sites, bounded repair candidates, grammar-state
    emulation, `runtime_view` (delivered / silent corruption), census judge.
  - `intent_decode.py`: `Server` (prompt_logprobs guard), `Pin` (prefix pinning), exact forced-token scoring, WCTF,
    `ChannelPrior`, `rollback_resume` (i), `lik_repair` (ii), `generate_call`.
  - `arms.py`: retry, greedy, forbid-trigger (both variants), grammar-CD.
  - `replay_utils.py`: message fixing, June/July templates, exemplar.
- **Tests**
  - `tests/test_protocol.py`: unit, property and pathological-run tests.
  - `tests/test_decode_pure.py`: prior, cut rules, continuations, prompt_logprobs guard, opt-in rules.
  - `tests/smoke_server.py`: live smoke test.
- **Data**
  - `mine_logs.py` builds `data/first_edit_contexts.jsonl` and `data/log_slips.jsonl`.
  - `data/replay_gemma_first_edit.jsonl`: Gemma-only E1 contexts.
  - `build_gold_copy.py` builds `data/gold_copy_*`, `data/gold_copy_files/` and `data/gold_all_ctx*.jsonl`.
  - `mine_payloads.py` builds `data/quotestorm.jsonl`.
  - `data/tools_official.json`
- **Experiments**: `replay.py` (E1, inline arms, G2), `head2head_gen.py`, `rs279.py` (G1), `quotestorm_free*.py`
  (E2), `quotestorm_model.py` (E3), `selfslip.py`, `retry_baseline.py`, `bench_latency.py`, `extend_residual.py`,
  `map_repair.py` (A2 service), lane scripts `lane_*.sh`.
- **Analysis**: `analyze_replay.py` (gate metrics, natural-next-call), `analyze_h2h.py` (head-to-head, gold
  metrics), `analyze_rs279.py`, `analyze_quotestorm.py`, `gate_summary.py`, `make_results.py` (writes
  `results.json`), `render_results_md.py` (writes the §4 tables), `stats.py`.
- **Outputs**: `out/v3_*_june.jsonl` (primary), `out/v2_*` (July arm 12, E4B, E3), `out/v4_*_exm.jsonl` (arm 11),
  `out/h2h_*.jsonl`, `out/rs279_31b.jsonl`, `out/gc_*.jsonl`, `out/quotestorm_free*.json`, `results.json`.
  `out/old_v1/` holds superseded or contaminated outputs and is not used.
- **Run everything** via `tools/limited.sh` with QN=VLLM:Worker_D<gpu>, using
  `/opt/envs/env_gemma/bin/python`.
- **Proxy equivalence (§8)**: `proxy_equivalence.py` (offline / quotestorm / p1 / p1e / tf / live / analyze),
  `proxy_vendor/` (read-only, hash-verified copy of E's frozen-candidate proxy), `data/proxy_modeldir_june/`
  (tokenizer links + the June-5 template, md5 d6c5bd0d…), `out/proxy_eq/`, `out/proxy_equivalence.json`.
- **Path shim**: `paths_override.py` (main-track tree moved to <competition-logs> template md5 verified).
