# Pre-registrations

Every confirmatory claim in the paper is decided by an analysis frozen before its data were analysed, and, with one
logged exception, before they existed: PREREG_v1's final P6/P7 runs finished at 11:42 UTC, before its 11:47 freeze, and
were not analysed or shown until after it (deviation ledger, A item 2). A registration is **frozen** when its sha256 and UTC
time are written to the project log (`PROGRESS.md`). Its analysis code is frozen with it, in a hash manifest. Verdicts
are reported as the frozen rules return them, including failures. Three other labels are used:
- *pre-specified descriptive*: a quantity a registration names but does not test (e.g. PREREG_v2.7's pooled
  quarantine removal, computed afterwards because the frozen script omitted it; a logged deviation);
- *frozen suite*: a deterministic test (the conformance suite), not a statistical registration;
- *EXPLORATORY*: analyses done afterwards, reusing the frozen code unchanged and labelled so in their file names.

## Check it yourself

```bash
python tools/verify_preregs.py --root .              # standard library only; a few seconds
```

It re-hashes:
- each registration document against the hash recorded at its freeze;
- every file in each code manifest written at freeze time.

It prints any mismatch together with its documented explanation. A mismatch is never hidden.

On the public tree the same command also reads `FROZEN_EXPORT_PINS.json` (files whose public copy had to be edited:
host paths, privacy redactions; frozen and exported hashes) and `WITHHELD.json` (files that cannot be public, with the
hash each manifest recorded). A file matched through its recorded export edits is "OK (exported with edits)"; a missing
file listed there with the registered hash is "WITHHELD", an explained entry. A file that is absent and not listed is
MISSING. The last line before the verdict tallies everything.

**Current output (2026-11-07 20:51 UTC, project tree; exit 0, "PASS: 0 unexplained problem(s)"):**
- **25 of 25 registration documents match.**
  - 23 match byte for byte.
  - 2 match on their frozen prefix: F's ANALYSIS_PLAN and SWEEP_PLAN. After the freeze, each received a dated
    "Deviations"/"Amendment" section appended at the end. Every entry states whether it was decided before or after
    seeing the governed data. The registered hash is the hash of the first 6,443 and 4,108 bytes respectively.
- **220 manifest entries match, and so do all 26 files frozen with v2.7–v2.10, E_ext, E_awq, E_awq2, E_audit and
  E_comp** (hashes from their freeze entries in `PROGRESS.md`; 2 of them, PREREG_E's `prereg_analysis.py` and
  `run_population.sh`, are re-listed with E_awq2 and are also in PREREG_E's manifest). **8 manifest entries differ,
  each for a logged reason:**

  | file(s) | why it differs | where it is logged |
  |---|---|---|
  | the end-to-end study's `PREREG_DEVIATIONS.md` and `RUNBOOK.md` | append-only logs listed in the manifest; verified before unblinding | |
  | the quarantine renderer used by v2.1/v2.2 | re-frozen by the end-to-end study at 18:48 and 19:05 UTC on Nov 4, with 0 render differences on 1,480 renders | the confirmatory manifest |
  | the v2.5 glue script | an operational fix before any v2.5 outcome was opened | `PREREG_DEVIATIONS.md`, B v2.5 item 6 |
  | four cross-family scripts | development copies; the registered runs executed from frozen snapshots, which all match | |

  The discovery snapshot equals the registered hashes except for three logged changes, each made before any GPU job
  or affecting descriptive output only.

**On the public tree** (checked 2026-11-07 on the public export with the Nov 7 registration files added): 25 of 25
documents match, 13 of them through their recorded export edits; 173 manifest entries match (82 through export edits),
47 are withheld and listed with their hashes, and the same 8 differ for the logged reasons above; all 26 later frozen
files match (13 through export edits). Exit 0.

## The registrations

Times are UTC. "Doc" is the first 16 hex digits of the document's sha256.

| # | registration | frozen | doc | question | verdict (as registered) | result file |
|---|---|---|---|---|---|---|
| 1 | PREREG_v1 | Nov 4 11:47:06 | 53e34f1f | Dose and lag shape of contagion (development set) | none of the predicted dose models M1–M3 fit; r-dose null | `experiments/contagion/out/prereg_analysis.json` |
| 2 | E_PREDICTIONS_v1 | Nov 4 11:56:08 | 182365c9 | Numeric predictions for the end-to-end endpoints | P-b holds; P-a holds at 31B, fails at 12B/E4B; P-c consistent | `experiments/endtoend/analysis/E_predictions_eval.md` |
| 3 | X prereg (cross-family) | Nov 4 12:15 | md5 6435db48 | Copy-on-retry in Qwen models | fails (Qwen3-8B, 3.5-9B) | `experiments/crossfamily/results.json` |
| 4 | PREREG_v2 | Nov 4 14:46:45 | 5da75e61 | Public confirmatory replication on PNC | 31B: *replicates with attenuation* (copying +18.3 pp [13.6, 23.2]; quarantine removes 98%); E4B replicates; 12B fails; Qwen null replicates | `experiments/contagion/out/confirmatory/confirm_v2_all_full.json` |
| 5 | PREREG_v2.1 | Nov 4 16:14:17 | bb3696da | Contagion with the shipped thinking-off flag | T1–T4 replicate | `experiments/contagion/out/v21_analysis.json` |
| 6 | PREREG_v2.2 | Nov 4 17:37:23 | ec9164ff | Contagion with thought suppressed / reasoning stripped | S1–S3 replicate; H +26.0 pp | `experiments/contagion/out/v22S_analysis.json`, `v22H_analysis.json` |
| 7 | X prereg_ext | Nov 4 18:51 | 0843ebd7 | Copying and induction in 4 more model families | copying 0/4; induction passes for Devstral-Small-2 only | `experiments/crossfamily/out/ext/results_ext.json` |
| 8 | PREREG_v2.3 | Nov 5 07:07:28 | 7111525f | Does JSON tool-result serialization induce slip onsets? | *serialization induces onset, partial* (+0.83 pp [0.17, 1.67]; ~5% of the gap) | `experiments/contagion/out/onset_v23_analysis.json` |
| 9 | PREREG_E | Nov 5 07:14 | 20fa3860 | End-to-end: proxy vs stock vLLM in the challenge harness | co-primary success (malformed calls/episode 2.47 → 0.27); resolve non-inferiority not met in either of its 2 replicates (later met with 8 fresh replicates, row 18); branch ≥50% rule met | `experiments/endtoend/analysis/prereg_pop31.json`, `prereg_br31.json` |
| 10 | PREREG_v2.4 | Nov 5 11:07:17 | e7af894b | Exact-intent repair on injected slips | IPD 90.6% exact, beats text repair +7.0 pp; R3/R4/R7/R8 fail (6.9% silent vs 2% bound; baselines stronger than predicted) | `experiments/intent_decoding/v24/battery_run_analysis.json` |
| 11 | F ANALYSIS_PLAN (+ addendum 13:50) | Nov 5 12:41 | c67d049a (prefix) | Weight-space repair of the QAT checkpoint | three candidates fail their gates; no repair shipped | `experiments/quant_margins/wsa/out/repair_heldout_final.json`, `repairC_heldout_final.json` |
| 12 | PREREG_v2.5 | Nov 5 14:00:57 | 50f8a395 | Full stack on contaminated histories (31B) | *gain with harm* (19.7% → 0/300; N2 1/1,500) | `experiments/intent_decoding/v25/out/analysis_v25.json` |
| 13 | F SWEEP_PLAN | Nov 5 14:16 | 7faf0172 (prefix) | Audit 12 checkpoints' closer margins | Google's QAT 31B release 5.13 nats; its unquantized QAT weights 5.51, and its exports audited in row 20 lose more; cyankiwi AWQ 0.02. The 12B and E4B checkpoints, scored against the 31B bf16 reference (cross-size), show larger deficits (E4B QAT 10.01, 12B QAT 7.20, E4B bf16 6.88). Amended to audit-only before any sweep number | `experiments/quant_margins/wsa/out/sweep_report.json` |
| 14 | PREREG_v2.6 | Nov 5 17:37:48 | ed19a6d0 | Does serving the audit's pick reduce contagion? | confirmed (19.7% → 10.3% [7.0, 13.9]); quarantine still removes 103% | `experiments/contagion/out/confirmatory/v26_audit_analysis.json` |
| 15 | PREREG_v2.5b | Nov 5 21:09:59 | c78e7512 | Full stack at E4B | *gain with harm* (7.0% → 0/300; N2 3/600) | `experiments/intent_decoding/v25b/out/analysis_v25b.json` |
| 16 | PREREG_v2.7 | Nov 6 13:32:39 | 3bc5b4a8 | Robustness: T 0.6 / greedy; AWQ at bf16; test-retest; 2 h soak | copying persists at T 0.6 and greedy (+18.7, +20.7 pp); quarantine works under greedy (92%), attenuated at T 0.6 (88%); **audit pick replicates at matched dtype** (12.0% vs 19.7%); test-retest **partly stable** (removal 86% in one seed set); **soak FAIL** (K-a, K-b: timeouts on every route; see LIMITATIONS §11) | `experiments/contagion/out/confirmatory/v27_robustness_analysis.json`, `experiments/soak/out/soak_analysis.json` |
| 17 | PREREG_v2.8 | Nov 6 17:30:46 | c69d54a5 | Does the released TranscriptLab CLI reproduce C1? | **does not reproduce** on removal only (85% < 90%); copying exact (+18.33 pp), P1 19.3% vs 19.7% | `experiments/contagion/out/confirmatory/v28_cli_analysis.json` |
| 18 | PREREG_E_ext | Nov 6 17:54:21 | cc4cc803 | 8 fresh end-to-end replicates: resolve NI at −3 pp; co-primary replication | analysed once, Nov 7 06:50:58 (r3–r10 all complete; 904 episode pairs, 0 excluded). **RESOLVE NON-INFERIOR** (393 vs 394 of 904 resolved; +0.11 pp [−2.21, +2.43]); S1 Y1 **REPLICATES** (1.76 → 0.37, 0.21× [0.13, 0.35]; a smaller cut than PREREG_E's 0.11×, outside the predicted [0.07, 0.18]); stuck 49 → 3 of 904 | `experiments/endtoend/analysis/prereg_E_ext.json` (stdout: `prereg_E_ext.stdout.txt`) |
| 19 | PREREG_v2.9 | Nov 6 17:56:22 | 565f3017 | TranscriptLab via the CLI on Gemma-4-E2B 4-bit and E4B bf16 | both **need a guard** (E2B induction +10.3 pp, above prediction) | `experiments/contagion/out/confirmatory/v29_coverage.json` |
| 20 | PREREG_v2.10 | Nov 6 17:59:10 | 06b3ee6c | Audit of the 5 most-downloaded unaudited 31B 4-bit checkpoints; H-QAT | **H-QAT supported** (QAT-derived AWQ 6.00, NVFP4 7.41 nats, flagged; nvidia NVFP4 1.36, not flagged; 2 not servable in our stack) | `experiments/quant_margins/wsa/out/v210_audit_breadth.json` |
| 21 | PREREG_E_awq | Nov 6 19:56:34 | 33d430ea | Does serving the audit's pick (AWQ) reduce malformed calls end to end? 2 replicates, base vs fullp | analysed once, Nov 7 06:51:34 (QAT comparator r1–r10). **AUDIT PICK REDUCES MALFORMED CALLS END TO END** (base Y1: QAT 1.91, 10 replicates → AWQ 0.41, 2 replicates; 0.22× [0.11, 0.39]; task-paired across runs, not CRN-paired); S-a, proxy on AWQ, 0.41 → 0.32 (0.77× [0.44, 1.47], p 0.54): predicted ratio ≤ 0.3 **failed**; AWQ-base predicted 1.2–1.8, observed 0.41 | `experiments/endtoend/analysis/prereg_E_awq.json` (stdout: `prereg_E_awq.stdout.txt`) |
| 22 | PREREG_E_awq2 | Nov 7 06:57:35 | 7e7cc12d | 6 fresh AWQ replicates (r3–r8): is slipguard's proxy still useful on the audit's pick? Also replicates row 21's primary | analysed once, Nov 7 13:06:15 (r3–r8 all complete; 678 episode pairs, 0 excluded). **SLIPGUARD STILL REDUCES MALFORMED CALLS ON THE AUDIT'S PICK** (AWQ base 0.50 → fullp 0.29 per episode, 0.59× [0.36, 0.99]; difference −0.20 [−0.46, −0.003], p 0.045, so the CI's upper bound is only just below 0); S4 **REPLICATES** row 21's primary on fresh episodes (AWQ base 0.50 vs QAT base 1.91, 0.26× [0.15, 0.44]); stuck 5 → 1 of 678. Predicted: ratio ≈ 0.75, a significant cut with probability ≈ 0.4. Written after row 21's analysis, whose r1–r2 numbers it disclosed and excluded from its primary | `experiments/endtoend/analysis/prereg_E_awq2.json` (stdout: `prereg_E_awq2.stdout.txt`) |
| 23 | PREREG_E_audit | Nov 7 07:12:07 | 90005d2f | Do the audit's flags predict malformed calls end to end? 4 more checkpoints (bf16, nvidia NVFP4, QAT-AWQ, QAT-NVFP4) | **AUDIT PREDICTS END-TO-END MALFORMED CALLS** (T1–T4 all pass, Holm): base Y1 flagged QAT 1.91 / QAT-AWQ 3.81 / QAT-NVFP4 4.85 vs unflagged nvidia NVFP4 0.34 / bf16 0.42 / AWQ 0.47; sets bf16 r3–4, others r3–5; analysed once Nov 8 15:09 UTC (late start, deviation logged) | `experiments/endtoend/analysis/prereg_E_audit.json` (a9ff64d2) |
| 24 | PREREG_E_comp | Nov 7 07:12:07 | 4d1acb42 | Which component carries the end-to-end gain? Quarantine-only and IPD-only arms, salt-paired with row 18's episodes | **QUARANTINE ALONE REDUCES** (1.56 → 0.66, 0.42× [0.25, 0.73]) and **IPD ALONE REDUCES** (→ 0.37, 0.24× [0.15, 0.37]) malformed calls end to end; full proxy 0.29; set r3–r6; analysed once Nov 8 15:09 UTC (late start, deviation logged) | `experiments/endtoend/analysis/prereg_E_comp.json` (6e4be7f0) |
| 25 | PREREG_v2.11 | Nov 7 21:55:01 | 50c2f0a3 | Does masking e-mail addresses in the released PNC change TranscriptLab's result? (released CLI, registered seeds) | **masking changes the result** (P1 16.7% vs 19.7%, McNemar p = 0.022); copying +15.0 pp [10.9, 19.5], inside the registered CI; deviation 1: a failed start (corpus argument), no data lost | `experiments/contagion/out/confirmatory/v211_masked_analysis.json` |
| 26 | PREREG_v2.12 | Nov 8 00:14:11 | 06caf31d | TranscriptLab via the released CLI on a Llama-family model (Hermes-3-Llama-3.1-8B) | **history-sensitive** (copying +6.0 pp [2.6, 9.6], imitation +5.3 [2.3, 8.7]; prediction of no copying failed; 0 of 28 malformed edits copy the laundered call); deviation 1: CLI 0.1.2 failed on this tokenizer, run with 0.1.3 | `experiments/contagion/out/confirmatory/v212_llama.json` |
| 27 | PREREG_v2.11b | Nov 8 05:38 | f5f97848 | A second masked-corpus run (descriptive): is row 25's P1 drop masking or run-to-run noise? | **inconclusive** (pre-specified reading): P1 18.0%, copying +16.7 pp [12.2, 21.3]; on the 43 masked states P1 13/43 in both masked runs vs 17 and 16 unmasked; row 25's verdict unchanged | `experiments/contagion/out/confirmatory/v211b_pooled.json` |
| 28 | PREREG_v2.13 | Nov 8 06:36 | 9714ee69 | A second Llama-tokenizer model via the CLI 0.1.3 (Hermes-2-Pro-Llama-3-8B): does row 26's retry-not-copy pattern hold? | **not run**: the model's context window (8,192 tokens) is shorter than the states (to ~18k tokens); no data | `experiments/contagion/out/confirmatory/v213_hermes2pro.json` |
| 29 | PREREG_v2.14 | Nov 8 09:40 | 8ed7bccb | Gemma-4-31B bf16 via the CLI: copying without quantization? Less than 4-bit QAT on the same states? | **both met**: copying +8.7 pp [5.7, 12.0]; bf16 P1 8.7% vs QAT 19.7%, −11.0 pp [−15.1, −6.9], McNemar p = 5e-8; replaces the exploratory bf16 row (P1 8.7% vs 9.0%) | `experiments/contagion/out/confirmatory/v214_bf16_analysis.json` |
| 30 | PREREG_v2.15 | Nov 8 09:45 | efd6399b | Does the weight audit's deficit predict TranscriptLab copying out of sample? Seven 31B checkpoints (three new) | **audit predicts copying**: ρ = 0.89, exact p = 0.006; out of sample, flagged QAT-AWQ 22.3% and QAT-NVFP4 24.3% vs bf16 8.7%, unflagged nvidia NVFP4 10.0% vs QAT 19.7% (all three McNemars met) | `experiments/contagion/out/confirmatory/v215_audit_panel.json` |
| 31 | PREREG_v2.16 | Nov 8 11:20 | 080b6ecf | Does copying follow the QAT weights, not the 4-bit format? Unquantized QAT weights + three bf16-derived exports on TranscriptLab | **copying follows the QAT weights**: unquantized QAT weights P1 18.0% vs bf16 8.7% (p = 2e-6) and vs 4-bit QAT 19.7% (−1.7 pp [−5.2, +2.0]: the format adds little); bf16-derived FP8, NVFP4, AWQ 7.3–10.3%; NVFP4-RedHat prediction missed (7.3% < 9–13%); deviation 1: placement | `experiments/contagion/out/confirmatory/v216_qat_weights.json` |

Rows 2 and 9 are one registration family: E_PREDICTIONS_v1 holds the numeric predictions for PREREG_E's endpoints.
Rows 18 and 21–24 extend row 9 with PREREG_E's frozen proxy and analysis functions unchanged, and its frozen launcher
unchanged except for row 24's arm list (`run_population_qi.sh`: quar, ipd instead of base, fullp).

**Frozen code of rows 22–24** (sha256 prefixes; full hashes in `PROGRESS.md` and in `tools/verify_preregs.py`, which
checks them):
- Row 22, with the document: `analysis/prereg_E_awq2_analysis.py` (dbc7e8b2), `ext/dispatch_awq2.sh` (faa381ee), and
  PREREG_E's `analysis/prereg_analysis.py` (1f8fca3a) and `run_population.sh` (ef09af67), unchanged.
- Rows 23 and 24, frozen together: `analysis/prereg_E_audit_analysis.py` (13a27cc3), `analysis/prereg_E_comp_analysis.py`
  (9175d262), `analysis/prereg_cov_common.py` (e4f7affa), `ext/dispatch_q.sh` (199456d5), `ext/queue_single.txt`
  (425ba584), `ext/queue_tp.txt` (fbebb550), `run_population_qi.sh` (33459c10), and the project's `tools/dl_eaudit.sh`
  (cd7f6041).
- Paths are relative to `experiments/endtoend/` except `tools/dl_eaudit.sh` (project root).

## Deviations

All deviations are logged with a UTC time and whether they were decided before or after seeing the governed data:
- `paper/protocol_theory/prereg/PREREG_DEVIATIONS.md` (contagion, repair, stack, robustness);
- `experiments/endtoend/PREREG_DEVIATIONS.md` (end to end);
- `experiments/crossfamily/PREREG_DEVIATIONS.md` (cross-family);
- the appended sections of F's ANALYSIS_PLAN and SWEEP_PLAN (weights).

**Deviations that touch a reported claim:**
- **End to end.** The branch analysis uses a corrected fidelity normaliser, logged before outcomes were opened; 15 of
  the 150 planned branch points were excluded by its fidelity or infrastructure rule (135 analysed).
- **Outcome-adjacent observations** (none changed a decision; each is logged with its time):
  - PREREG_E, 2026-11-05 10:52 UTC: a log tail showed the resolve counts of half of one replicate (a secondary
    endpoint); no co-primary data was seen.
  - PREREG_E, 2026-11-06 02:17 UTC: while diagnosing a slow tail, per-arm completion counts and the timing of in-flight
    stock-arm branch sessions (some running about 100 turns) were seen before branch completion; no malformed-call or
    resolve values.
  - PREREG_v1, 2026-11-04 11:47–11:50 UTC: per-arm malformed counts of a runner started before the freeze were printed
    after it (deviation ledger, A item 1).
  - PREREG_E, 2026-11-04 12:02 UTC: a progress monitor printed per-arm resolve counts of the exploratory pilots once,
    before the freeze (their values are in PREREG_E.md §8).
- **Weights.** The registered endpoint turned out degenerate: the sampler slip rate on valid string ends was 0 for
  both bf16 and QAT-ct. The primary endpoint was therefore changed to the population-weighted E_pop after seeing that
  number and before any repair number. No repair is claimed.
- **Weights.** The sweep was amended to audit-only before any sweep number.
- **Opt-in text repair.** A post-hoc fix was made after seeing the PNC turns. PNC is therefore not held out for that
  rule (see `LIMITATIONS.md` §3).
