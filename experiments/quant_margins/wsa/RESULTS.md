# Weight-space audit and repair of the quantization-induced protocol defect: final results (workstream F, 2026-11-05)

**Status: FINAL.**
- **Audit (T1).** The audit-weights tool ships, frozen in `release_audit/`, version `wsa-1.0`.
- **Repair (T3).** Weight repair ENDED. Three closed-form candidates were tried, and none passed the registered gate. Their code and adapters stay here, labelled **"did not pass the registered gate"**. They are not part of the slipguard public API (PI decision, 19:16 UTC).

**Citations.** Every number below is quoted from the JSON named next to it, with the first 8 hex digits of its sha256. All paths are relative to `experiments/quant_margins/wsa/`.

**Data.** Decision points come from the public PNC corpus only (`data/pnc`). No main-track data was used.

## 1. Decision points
- **Source.** `build_points.py` → `data/pnc_points_all.jsonl` (e8364526). It covers 4,207 first-call edit turns.
- **Split.** By sha256(episode_id) parity into calib and held-out.
- **Position types:**
  - **Valid calls.** The closing `<|"|>` of path/new/old.
  - **Slips.** A look-alike closer followed by `,<key>:`. Of the 51 logged slip states, 14 are onsets.
  - **Protected.** Legitimate look-alike content.
- **Item sets:**
  - `data/core_items.jsonl` (23a1377e): 951 items.
  - `data/audit_items_16k.jsonl` (4d1b8dee): 235 held-out items of at most 16.4k tokens. This is the sweep pack, so it fits every server's KV cache.
- **Look-alike set.** The 80 vocabulary tokens matching `▁?[`"'\\]+,?`.
- **Threshold.** τ = ln 19 is the margin below which a look-alike enters the shipped top-p 0.95 nucleus.

## 2. T1, exact (HF): bf16 vs QAT-ct (`out/t1_scores.json`, 78f939c6; held-out string ends)
| | bf16 (n=900) | QAT-ct (n=600) |
|---|---|---|
| margin q10 / q50 / q90 (nats) | 16.34 / 20.42 / 23.14 | 9.89 / 16.18 / 20.95 |
| P(margin < 4) | 0.11% | 0.50% |
| E_slip at valid string ends (shipped sampler) | 8.2e-5 | 9.2e-4 |
| logged slip states (n=8 held-out): mean pLA / top-1 look-alike | 0.021 / 0% | 0.333 / 25% |

- **Paired comparison** (600 positions, `paired_vs_bf16.qatct.heldout`). QAT-ct's margin is smaller at 94.5% of string ends. The median shift is −3.81 nats.
- **Mechanism** (D's analysis, recorded in `../progress.md` at 13:30):
  - QAT-ct's raw logits rise. The `<|"|>` logit goes from 30.7 to 41.9, and the best look-alike from 4.0 to 12.4.
  - The post-softcap loss is softcap saturation plus a risen look-alike logit.
  - The logit lens shows the two arms diverge at the last layer.

## 3. T1 sweep: endpoint audit of 12 checkpoints
**Sources.**
- `out/sweep_report.json` (e1cbe5ff, reference 31B bf16) and `out/sweep_report_e4bref.json` (7063c0ab, reference E4B bf16). Both are frozen and read-only.
- Records are in `out/audit_sweep_<name>.records.jsonl`. The plan is `SWEEP_PLAN.md` (9efc4a02).

**Method.**
- vLLM 0.19.1 serves each checkpoint as published.
- Generation-mode teacher forcing on 454 held-out new/old string ends.
- The shipped sampler (T=1, top-k 64, top-p 0.95) is rebuilt from the top-20.
- The deficit is the paired median margin vs the same-family bf16 model, with a 95% episode-cluster bootstrap CI.

**Flag rule (frozen).**
- FLAG if P(m < ln 19) ≥ 0.5%, or the deficit is ≥ 3 nats.
- SEVERE if P(m < ln 19) ≥ 2%, or E_slip ≥ 1%.

| 31B checkpoint | median margin (lb) | censored | P(m < ln 19) | E_slip | deficit vs bf16 [95% CI] | verdict |
|---|---|---|---|---|---|---|
| bf16 (reference) | 20.01 | 42% | 0.22% | 1.3e-4 | — | — |
| cyankiwi AWQ int4 | 19.99 | 47% | 0 | 0 | **0.02 [−0.18, 0.21]** | none |
| RedHat FP8-dynamic | 19.98 | 43% | 0.22% | 3.6e-4 | 0.03 [−0.24, 0.16] | none |
| Intel AutoRound int4 | 19.38 | 46% | 0.66% | 1.4e-3 | 0.63 [0.31, 0.83] | FLAG (P) |
| RedHat NVFP4 | 19.22 | 37% | 0.44% | 2.6e-4 | 0.79 [0.47, 1.11] | none |
| QuantTrio AWQ int4 | 18.10 | 12% | 0.22% | 6.0e-4 | 1.91 [1.60, 2.19] | none |
| PTQ Q4_0 (fake-quant of bf16) | 17.41 | 24% | 0.66% | 1.1e-3 | 2.60 [2.18, 2.81] | FLAG (P) |
| **Google QAT-ct (W4A16)** | 14.88 | 55% | 0.22% | 1.0e-3 | **5.13 [4.69, 5.56]** | FLAG (deficit) |
| **Google QAT-unquantized** | 14.50 | 41% | 0.66% | 1.2e-3 | **5.51 [5.09, 5.92]** | FLAG |

| other sizes (`sweep_report_e4bref.json`) | median margin | P(m < ln 19) | E_slip | deficit vs E4B bf16 | verdict |
|---|---|---|---|---|---|
| E4B bf16 (reference) | 13.13 | 0.66% | 0 | — | FLAG (P, the reference itself) |
| E4B QAT-ct | 10.00 | 1.32% | 7e-5 | **3.13 [2.94, 3.44]** | FLAG |
| 12B QAT-ct | 12.81 | 0.44% | 1.5e-4 | no same-family bf16 | descriptive only |

- **No SEVERE flags.**
- **Finding: 4-bit is not the same as protocol damage.**
  - A community AWQ int4 31B checkpoint keeps bf16-level margins (deficit 0.02).
  - Google's QAT checkpoints carry the largest deficit of any 31B checkpoint, 5.1–5.5 nats. The deficit is already present in the unquantized QAT weights.
  - The QAT deficit replicates at E4B (3.13).
- **Paper wording (PI):** "audit-weights ranks checkpoints by string-end margin deficit; Google's QAT checkpoints carry the largest deficit (5.1–5.5 nats) while a community AWQ int4 checkpoint of the same size has none (0.02)".
- **Caveats:**
  - **Top-20 censoring.** Where `<|"|>` or every look-alike falls outside the top-20, the margin is a lower bound (lp(`<|"|>`) − lp_20). The censored fraction is 12–55% (column above). Deficits computed from lower bounds may therefore be conservative or distorted. The pairing is per position and the reference is censored too.
  - **Coarse P criterion.** At n=454, one string end is 0.22 pp, so the P(m < ln 19) criterion is coarse: FLAG (P) means ≥ 3 string ends.
  - **Dtype.** cyankiwi AWQ is served in float16 (the checkpoint's native dtype); all other checkpoints are served in bf16.
- **Weights-only proxy (not shipped).** `out/weights_proxy.json` (879ebea9) is an embedding-geometry screen: the separation of `<|"|>` from look-alikes. It does not predict the deficit:
  - it is blind to PTQ, whose embedding is identical to bf16 yet whose deficit is 2.60;
  - at E4B its direction is reversed (QAT 1.29 vs bf16 1.23, while the deficit is 3.13).
  The endpoint audit is therefore the shipped tool.

## 4. Behavioural validation (PREREG_v2.6, run by A)
- **Pointers:**
  - plan: `paper/protocol_theory/prereg/PREREG_v2.6_auditBehaviour.md` (by D);
  - analysis script: `experiments/contagion/scripts/analyze_v26_audit.py` (a8471999, frozen, run once);
  - results: `experiments/contagion/out/confirmatory/v26_audit_analysis.json` (a1d63581).
  - The summary is in PROGRESS.md (18:32 UTC).
- **Design.** 1,200 jobs per checkpoint.
- **H1 (contagion).** The audit pick (cyankiwi AWQ) has contagion P1 of 10.3% vs 19.7% for QAT: RD −9.3 pp [−13.0, −5.9], Holm p < 1e-6.
- **H2 (dose-response).** AutoRound, with deficit 0.63, sits in between at 13.3%: RD −6.3 pp, p 0.0022. The 4-point ordering has Spearman 1.0.
- **H3.** The history quarantine is still needed and works on AWQ: it removes 103% of the contagion.
- **No-harm.** It holds for AWQ. It FAILS for AutoRound, whose clean baseline is 8.3%; this is reported, not a verdict.
- **Interpretation.** The weight audit's ranking predicts behaviour. Audit pick plus slipguard history guard takes contagion from 19.7% to 0/300.

## 5. T3: three closed-form repair candidates. None passed the registered gate.
**The edit.** All three candidates are a closed-form, MEMIT-style edit of layer 59's `down_proj`, shipped as a PEFT LoRA. The method is in `repair_memit.py`, which writes the adapter via `lora_io.py`.
- **Exact offline evaluation.** A last-layer MLP edit changes only that position's x_L, so its effect at every extracted position can be computed exactly offline.
- **Why `down_proj`.** vLLM 0.19.1 cannot place a LoRA on Gemma-4's `lm_head`, because the vocabulary (262,144) exceeds 258,048.

**Plans.**
- `ANALYSIS_PLAN.md` (8f2eb2aa, deviations appended and logged).
- `ANALYSIS_PLAN_addendum.md` (b332186f).
- `CANDIDATE_B.md` (cb293fa0).
- `CANDIDATE_C.md` (78f0bc37).

**Gate:**
- **G1.** E_pop reduction ≥ 50% with the CI lower bound > 0. E_pop is the population-weighted per-call slip probability: 300 held-out valid calls plus 51 slip states, with weights 4,074 and 51.
- **G2/G3.** No NLL, KL or flip regression on PNC text, wikitext (24 never-touched odd test windows), protected content, in-string content and openers.
- **G4.** Greedy byte identity ≥ 95% on held-out valid calls.
- **G5.** vLLM+LoRA reproduces the offline prediction: the median per-position top-10 |Δlogp| must be ≤ 0.1.

| | **A** (`adapters/repairA`, rank 81) | **B** (`adapters/repairB`, rank 81) | **C** (`adapters/repairC`, rank 80) |
|---|---|---|---|
| targets | match bf16 log-odds of `<|"|>` and every look-alike; λ=1e4 | suppress look-alikes only, plus 2,135 line-end hard negatives; λ=1e3 | suppress look-alikes only; output span restricted to look-alike rows (minimum-movement right inverse); plus 723 postopen/nlclose negatives; λ=1e3 |
| margin-deficit closure (offline, calib CV, ratio of sums) | 0.99 (`../progress.md` 13:30 inner CV) | 0.91 (`repairB_selection.json` 6f9403c8) | 0.78 (`repairC_selection.json` dbea7c5b) |
| **G1 E_pop** QAT 0.508% → | 0.261% (bf16 0.281%); **48.5% [8.1, 99.0] FAIL** | not evaluated (stopped at calib gate) | 0.283%; **44.2% [5.8, 96.0] FAIL** |
| gap closure (E_pop) | 1.09 [0.82, 1.25] | — | 0.99 [0.52, 1.16] |
| (a) E_onset reduction | 59% [28, 96] | — | 48% [21, 85] |
| (b) median margin 16.19 → (bf16 20.33); P(m < ln 19) | 20.70; 0.33% → 0 | — | 19.58; 0.33% → 0 |
| G2/G3 PNC KL / ΔNLL | 1.5e-4 / +6e-4 PASS | calib cv1 PASS | 1.6e-5 / +1.2e-4 PASS |
| G2/G3 wikitext KL / ΔNLL / flips | 1.8e-3 / +3.8e-3 / 0.52% PASS | calib cv1 PASS | 2.0e-4 / −5.4e-4 / 0.91% PASS |
| in-string premature close | 0.17% (≤ 0.5%) PASS | 0% | 0% |
| **G4 byte identity** (zero-adapter floor) | **89.0% FAIL** (floor 97.0%), 200 held-out | **94% FAIL** at the calib gate (floor 98%), 100 calib | calib 96% (floor 97%) PASS; **held-out 98.5% PASS** (floor 97.5%), 200 fresh calls |
| **G5** median top-10 \|Δlogp\| (no-adapter floor) | 0.0976 PASS (floor 0.1029) | — | **0.1022 FAIL** (floor 0.1029) |
| verdict | FAIL (G1, G4) | FAIL (calib G4) | FAIL (G1, G5) |

**Sources for the table:**
- A: `out/repair_heldout_final.json` (4a8361ec), `out/byte_identity_repairA.json` (0c97bd87), `out/byte_identity_floor.json` (bec4dec1), `out/lora_validate_repairA.json` (f3d5cc6e).
- B: `out/byte_identity_repairB_calib.json` (7f2ee04f).
- C: `out/repairC_heldout_final.json` (edb3dde7), `out/byte_identity_repairC_calib.json` (4f71c06f), `out/byte_identity_repairC_heldout_fresh.json` (c2f5016c), `out/lora_validate_repairC.json` (a29ec8e2).
- Valid-call rates were unchanged for all three, with 0 valid → invalid.

**Why no candidate passed.**
1. **A's mechanism.** A's match-all targets raise `<|"|>` log-odds at string ends, so A closes some code strings early at line ends. Examples: content truncated from 1,163 to 523 characters, and dropped trailing newlines. The random-position in-string metric missed this.
2. **B's mechanism.** Suppress-only targets removed mid-string premature closes. But the hidden-state edit still nudged the first token of the string and the newline-vs-close choice.
3. **C's mechanism.** C confines the edit to look-alike logit rows. It is behaviour-neutral within vLLM's batch non-invariance floor and bf16-equivalent on E_pop.
4. **G1 cannot be met by a bf16-equivalent repair.** This was noticed post hoc. E_pop is dominated by post-slip contagion states, where bf16 copies too: pLA at the 51 slip states is 0.264 (QAT), 0.208 (bf16), 0.211 (A) and 0.229 (C). bf16 itself sits at 0.281% vs 0.508% for QAT. So a perfect bf16-equivalent edit reaches at most (0.508 − 0.281)/0.508 = 44.6%. The ≥ 50% threshold was frozen before any bf16 E_pop number existed, and it is kept as registered.
5. **G5's threshold is below the floor.** The 0.1 threshold sits under the HF-vs-Marlin numeric floor of 0.1029, i.e. without any adapter. C's G5 is therefore reported as a strict fail at the floor. The paper describes it as "agrees with the offline computation to within vLLM's own numeric floor", with the floor value reported (PI).

## 6. General-text cross-check: wikitext-2 test NLL (descriptive, endpoint-based)
**Method.** 48 BOS-correct windows of 1,023 tokens, scored with vLLM `prompt_logprobs` on a dedicated GPU3 server for each checkpoint (`wiki_nll_endpoint.py`, `wiki_crosscheck.sh`).
- **Raw.** BOS plus the window.
- **Chat-wrapped.** BOS + `<|turn>user\nContinue this Wikipedia article.<turn|>\n<|turn>model\n` + the window.

| 31B checkpoint | raw NLL (nats/token) | chat-wrapped NLL |
|---|---|---|
| bf16 | 9.304 (`wiki_nll_31b_bf16.json` cfc66471) | 6.003 (`wiki_nll_chat_31b_bf16.json` f07c5d23) |
| QAT-ct | 7.368 (6e57945c) | 4.565 (730884b1) |
| cyankiwi AWQ int4 | 9.487 (d3e782c5) | 6.528 (6e4c397b) |
| Intel AutoRound int4 | 9.557 (b2e74612) | 6.795 (dc9fd778) |

**Reading.** These numbers do NOT measure general language-modelling quality, so no ranking claim is made.
- **Degenerate next-token mode.** All four instruction-tuned checkpoints show a degenerate next-token mode on wikitext-2 text (`out/wiki_probe_diag.json` c62d25dc, script `diag_wiki_probe.py`).
  - At most positions the top-1 is a confident filler or copy token: `' own'`, `' same'`, `'//'`, recently seen words. For example, after "One of the" the top-1 is `' same'` (p ≈ 0.998).
  - 47–54% of tokens get a log-probability below −10.
- **Two independent implementations agree.** HF exact gives raw NLL 9.239 (bf16) and 7.343 (QAT-ct) on 1,536 positions in `out/hf_{bf16,qatct}_wiki.pt`; vLLM gives 9.30 and 7.37.
- **Per-window spread.** The bf16 chat-wrapped NLL ranges from 2.87 to 9.38 across windows.
- **Trigger unknown.** We did not establish whether wikitext's tokenised spacing (`' @-@ '`, `' , '`) or the instruction tuning triggers the mode. The detokenised-text control could not run because GPU3 was taken by another user at 19:31:52.
- **Descriptive observations:**
  - QAT-ct has the lowest NLL. On PNC text too, QAT-ct's NLL is lower (0.77 vs 1.05 for bf16), and PNC was generated by QAT-ct.
  - The two community int4 checkpoints sit 0.2–0.8 nats above bf16.
- **Consequence for the repair gates.** The wikitext side-effect gates (G2/G3) were measured in this regime and are relative (KL/ΔNLL vs the unedited model). The in-distribution PNC-text gate is the more meaningful one.

## 7. Library: audit-weights ONLY (frozen; handed to L)
**Package.** `release_audit/` is path-free; every path is an argument.

| file | sha256 |
|---|---|
| `wsaudit/__init__.py` | d73fb8a7968af1bc61364420fac8343834b5d0ac93441fbc211fbea7e3ea6fef |
| `wsaudit/audit.py` | 43df25b33ab9589055a067ee12f0cde2b2a41548e29bf396d1ba19b9a37389c5 |
| `wsaudit/render.py` | 85ce0172fc0e3bac543b79c8a673d66162d8296f3cbb939b377131d20ba8007d |
| `wsaudit/report.py` | b852acbe7929ace74eb2277ea6506b8b8d778e116f7e3224f1c1f4fbcba689a6 |
| `pack/audit_items_16k.jsonl.gz` | fdf85e048f867077427dfe6cc69f80daed2a6e153acbd493f0f089cfad55ee5e |
| `pack/core_items.jsonl.gz` | d4fe1c0e448f4550e977a960ee6f55e164fb36d7d961082d06e8098112f4ea62 |

**API:**
- `audit_endpoint(base_url, served_name, *, pnc_dir, tokenizer_dir, pack, split, kinds, conc, max_total, records_out)`
- `summarize(records)`
- `compare(records, reference)`
- `flag(summary, paired)`
- Also exported: `position_metrics`, `sampler_from_top`, `TAU`, `SCHEMA = 'slipguard.weights.audit/v1'`.

**Flag rule.** As in §3.

**Verification:**
- **Re-scoring the frozen sweep records** with `report.py` reproduces `sweep_report.json` exactly, with two qualifications. L checked this independently in slipguard `dev/check_wsa.py` across 24 rows, and F re-checked the onset fields.
  - **Exact matches:** every summary field except the onset fields, every median-deficit point estimate, and every FLAG/SEVERE. For example:
    - QAT-ct: median 14.875, P 0.0022, deficit 5.133, FLAG;
    - cyankiwi: 19.992, 0, 0.016, no flag;
    - PTQ: 17.406, 0.0066, 2.602, FLAG.
  - **Onset fields (`onset_per_call`, `n_onset_calls`) need a join.** The old sweep records (`out/audit_sweep_*.records.jsonl`) carry no `n_prior_bad` field; `sweep_report.py` joined it from `data/audit_items_16k.jsonl`.
    - Without the join, `summarize` treats every call as clean and counts 227 onset calls instead of 215. For example, AutoRound gives 0.0029 instead of 0.
    - With `n_prior_bad` joined from the shipped pack, all 48 onset fields match.
    - Records written by the shipped `audit_endpoint` carry the field, so new runs need no join.
  - **Bootstrap CIs differ by up to 0.031 nats.** `sweep_report.py` drew every checkpoint from one RNG stream, while `compare()` reseeds for each comparison.
- **Token-id check (CPU only).** `scratch_moved_in/wsa_final/verify_render.py`, output in `verify_render.json`, confirms that the package builds token ids identical to the sweep's: 235/235 and 951/951 pack items, `prompt_tokens` 100% match, identical look-alike set, identical request body. L reproduced the prompt_tokens result on the vendored copy.
- **Not done:** a live end-to-end run of the package against a server (GPU3 was unavailable). The script is `scratch_moved_in/wsa_final/e2e_wsaudit.py`; L will run it if it gets a GPU slot.
- **Where L vendored it.** slipguard `src/slipguard/_frozen/wsa/`. All 6 shas match the table above.
- **Scratch location.** The PI moved F's scratch files from `/scratch/wsa_final` into `scratch_moved_in/` at 19:43; they are logged in DELETIONS.md.

**Not in the package.**
- `repair_memit.py`, `lora_io.py` and `adapters/repair*` are research code that did not pass the registered gate.
- `slipweights.py` (the earlier stub with `repair_adapter`) is superseded and must not be exported.

## 8. Deletions (all logged in `DELETIONS.md` at the time of deletion)
- **Deleted:**
  - RedHat FP8 and NVFP4 (17:45);
  - PTQ Q4_0 and QAT-unquantized 31B (19:25);
  - QuantTrio AWQ and Intel AutoRound (19:34, after the wikitext cross-check).
- **How to recover.** Every entry records an `hf download … --revision <sha>` or a deterministic regeneration command. File lists are in `deleted_manifests/`.
- **Kept:**
  - bf16 31B (`models/gemma-4-31b-it`);
  - QAT-ct 31B;
  - cyankiwi AWQ (`models/community/cyankiwi_gemma-4-31B-it-AWQ-4bit` @a6b1af08).

## 9. Caveats
- **The audit measures the logit margin, not behaviour.** The link to behaviour comes from v2.6 (§4) on two community checkpoints plus QAT and bf16.
- **One family, one task.** All audit items are PNC edit calls from one model family (Gemma-4), at the 31B/12B/E4B sizes.
- **G1 endpoint amended.** The E_pop endpoint replaced a degenerate valid-string-end E_slip before any slip-state or repair number existed (deviation logged at 13:00). The post-hoc ceiling in §5 point 4 follows from that choice.
- **vLLM non-determinism.** vLLM 0.19.1 is not batch-invariant. The byte-identity floor is 97–98%, so every G4 number is reported with its zero-adapter floor.
