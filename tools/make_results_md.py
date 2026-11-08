#!/usr/bin/env python3
"""Generate RESULTS.md: every headline result, its value read from the result file at generation time (never typed by
hand), its registration status and its source (file#json/path).

    python tools/make_results_md.py --root ROOT --out RESULTS.md          # (re)generate
    python tools/make_results_md.py --root ROOT --out RESULTS.md --check  # verify; never writes

--check compares the would-be content with the existing file (ignoring the timestamp line) and exits 1 if it differs
or any reference does not resolve. Without --check the file is written; exit 1 if any reference is unresolved.

Both tree layouts work (--layout auto, the default, picks one from ROOT):
  * project layout: the library lives at release/lib/;
  * public layout (the released repository): the library lives at slipguard/, and the tree carries
    FROZEN_EXPORT_PINS.json (files whose public copy differs from the frozen file) and WITHHELD.json (files a freeze
    manifest lists that the release does not contain).
Paths below are written in the project layout and are rewritten to the chosen layout when resolved and printed. A
missing file that WITHHELD.json lists is reported as "withheld (listed)", not as unresolved; --withheld '' disables
that. A file listed in FROZEN_EXPORT_PINS.json gets its frozen hash next to its current one in the hash table.
Standard library only."""
import argparse, datetime, hashlib, json, os, sys

E = 'experiments/endtoend/analysis/'
C = 'experiments/contagion/out/confirmatory/'
B4 = 'experiments/intent_decoding/v24/battery_run_analysis.json'
B5 = 'experiments/intent_decoding/v25/out/analysis_v25.json'
B5b = 'experiments/intent_decoding/v25b/out/analysis_v25b.json'
ID = 'experiments/intent_decoding/results.json'
W = 'experiments/quant_margins/wsa/out/sweep_report.json'
V26 = C + 'v26_audit_analysis.json'
PNC = 'slipguard/results/conformance_pnc/RESULTS.json'
PNCF = 'slipguard/results/conformance_pnc/prefix_fix/RESULTS.json'
XD = E + 'EXPLORATORY_distributions.json'
BS = E + 'EXPLORATORY_bootseed.json'
CEN = 'experiments/quant_margins/wsa/out/EXPLORATORY_censoring.json'
XV2 = 'experiments/crossfamily/out/v2/results_v2.json'
XEXT = 'experiments/crossfamily/out/ext/results_ext.json'
EXT = E + 'prereg_E_ext.json'
AWQ = E + 'prereg_E_awq.json'
AWQ2 = E + 'prereg_E_awq2.json'
EAUD = E + 'prereg_E_audit.json'
ECOMP = E + 'prereg_E_comp.json'
LAYOUT_PREFIX = {'project': 'release/lib/', 'public': 'slipguard/'}   # where the library lives

REG, EXP, DESC = 'registered', 'exploratory', 'descriptive'
# (section, claim, status + registration, [(label, file, json/path)])
ROWS = [
    ('End to end: the challenge harness (ADK, vLLM 0.19.1, Gemma-4-31B 4-bit QAT; 113 public tasks x 2 replicates)', None, None, None),
    ('', 'Malformed calls per episode, stock vs proxy (co-primary Y1)', REG + ' (PREREG_E)', [
        ('base', E + 'prereg_pop31.json', 'co_primary/Y1/base_mean'), ('proxy', E + 'prereg_pop31.json', 'co_primary/Y1/fullp_mean'),
        ('ratio', E + 'prereg_pop31.json', 'co_primary/Y1/ratio_fullp_over_base'),
        ('diff', E + 'prereg_pop31.json', 'co_primary/Y1/diff_fullp_minus_base/mean_diff'), ('diff CI', E + 'prereg_pop31.json', 'co_primary/Y1/diff_fullp_minus_base/ci95')]),
    ('', 'Wasted calls per episode (co-primary Y2)', REG + ' (PREREG_E)', [
        ('base', E + 'prereg_pop31.json', 'co_primary/Y2/base_mean'), ('proxy', E + 'prereg_pop31.json', 'co_primary/Y2/fullp_mean'),
        ('success rule', E + 'prereg_pop31.json', 'co_primary/success_Y1_reduction_ge_70pct_ci_excludes_0')]),
    ('', 'Stuck episodes (>=5 consecutive malformed calls), per replicate', REG + ' (PREREG_E secondary)', [
        ('rep1 base', E + 'prereg_pop31.json', 'secondary/stuck/replicate1/base'), ('rep1 proxy', E + 'prereg_pop31.json', 'secondary/stuck/replicate1/fullp'),
        ('rep1 p', E + 'prereg_pop31.json', 'secondary/stuck/replicate1/mcnemar_p'),
        ('rep2 base', E + 'prereg_pop31.json', 'secondary/stuck/replicate2/base'), ('rep2 proxy', E + 'prereg_pop31.json', 'secondary/stuck/replicate2/fullp'),
        ('rep2 p', E + 'prereg_pop31.json', 'secondary/stuck/replicate2/mcnemar_p')]),
    ('', 'Resolved tasks and the non-inferiority test at -3 pp, per replicate (not met in either; met with 8 fresh replicates, PREREG_E_ext below)', REG + ' (PREREG_E secondary)', [
        ('rep1 base', E + 'prereg_pop31.json', 'secondary/resolved/replicate1/base'), ('rep1 proxy', E + 'prereg_pop31.json', 'secondary/resolved/replicate1/fullp'),
        ('rep1 NI', E + 'prereg_pop31.json', 'secondary/resolved/replicate1/non_inferior_at_-3pp'),
        ('rep2 base', E + 'prereg_pop31.json', 'secondary/resolved/replicate2/base'), ('rep2 proxy', E + 'prereg_pop31.json', 'secondary/resolved/replicate2/fullp'),
        ('rep2 NI', E + 'prereg_pop31.json', 'secondary/resolved/replicate2/non_inferior_at_-3pp')]),
    ('', 'Other sizes (one replicate each): Y1 ratio proxy/stock', REG + ' (PREREG_E)', [
        ('E4B', E + 'prereg_popE4B.json', 'co_primary/Y1/ratio_fullp_over_base/ratio'),
        ('12B (section 6 conforming)', E + 'prereg_pop12B_sec6conforming.json', 'co_primary/Y1/ratio_fullp_over_base/ratio')]),
    ('', 'Branch at onset (31B): post-onset malformed calls per branch, by component', REG + ' (PREREG_E 3(b); >=50% rule)', [
        ('n', E + 'prereg_br31.json', 'n_branch_points'), ('base', E + 'prereg_br31.json', 'post_onset/base/post_onset_malformed_mean'),
        ('quarantine', E + 'prereg_br31.json', 'post_onset/quar/post_onset_malformed_mean'), ('IPD', E + 'prereg_br31.json', 'post_onset/ipd/post_onset_malformed_mean')]),
    ('', 'Distribution: share of episodes with >=1 malformed call (31B)', EXP + ' (review B3)', [
        ('base [k, n, share]', XD, 'population/31B/Y1_base/share_ge1'), ('proxy', XD, 'population/31B/Y1_fullp/share_ge1'),
        ('diff', XD, 'population/31B/share_ge1_diff_fullp_minus_base_taskcluster/mean_diff'),
        ('CI', XD, 'population/31B/share_ge1_diff_fullp_minus_base_taskcluster/ci95')]),
    ('', 'Loops: the 14 stuck base pairs; Y1 without them', EXP + ' (review B3/B10)', [
        ('stuck pairs', XD, 'population/31B/base_stuck_pairs/n_pairs'), ('their Y1 base', XD, 'population/31B/base_stuck_pairs/Y1_base_mean'),
        ('their resolve base/proxy', XD, 'population/31B/base_stuck_pairs/resolved_base'), ('', XD, 'population/31B/base_stuck_pairs/resolved_fullp'),
        ('tokens base', XD, 'population/31B/base_stuck_pairs/gen_tokens_base_mean'), ('tokens proxy', XD, 'population/31B/base_stuck_pairs/gen_tokens_fullp_mean'),
        ('Y1 excl. stuck base', XD, 'population/31B/Y1_excluding_base_stuck_pairs/base_mean'),
        ('proxy', XD, 'population/31B/Y1_excluding_base_stuck_pairs/fullp_mean'), ('ratio', XD, 'population/31B/Y1_excluding_base_stuck_pairs/ratio')]),
    ('', 'Branches: share with >=1 post-onset malformed call', EXP + ' (review B3)', [
        ('base', XD, 'branches_31B/post_malformed_base/share_ge1'), ('quarantine', XD, 'branches_31B/post_malformed_quar/share_ge1'),
        ('IPD', XD, 'branches_31B/post_malformed_ipd/share_ge1')]),
    ('', 'Bootstrap-seed sensitivity of the frozen E2E analysis (all 1,000 seeds)', EXP + ' (reproducibility audit)', [
        ('Y1 CI hi range', BS, 'population_31B/Y1/ci_hi_range'), ('seeds reproducing released', BS, 'population_31B/Y1/seeds_reproducing_released'),
        ('success rule at all seeds', BS, 'population_31B/success_rule_holds_for_all_seeds'),
        ('branch >=50% rule at all seeds (quar)', BS, 'branches_31B/quar/success_reduction_ge_50pct_holds_for_all_seeds'),
        ('ipd', BS, 'branches_31B/ipd/success_reduction_ge_50pct_holds_for_all_seeds')]),
    ('', 'Branches with natural onsets only', EXP + ' (review B9)', [
        ('n', XD, 'branches_31B/onset_natural/n'), ('base', XD, 'branches_31B/onset_natural/base/mean'),
        ('quarantine', XD, 'branches_31B/onset_natural/quar/mean'), ('IPD', XD, 'branches_31B/onset_natural/ipd/mean')]),

    ('End to end: 8 fresh replicates (PREREG_E_ext) and the audit pick served end to end (PREREG_E_awq, PREREG_E_awq2)', None, None, None),
    ('', 'Resolved tasks, 8 fresh replicates: non-inferiority at -3 pp (primary)', REG + ' (PREREG_E_ext)', [
        ('verdict', EXT, 'primary_verdict'), ('resolved [base, proxy, of]', EXT, 'primary_resolve/resolved_base_fullp_of'),
        ('diff', EXT, 'primary_resolve/mean_diff'), ('CI', EXT, 'primary_resolve/ci95'),
        ('episode pairs', EXT, 'n_episode_pairs'), ('excluded', EXT, 'excluded_pairs')]),
    ('', 'Malformed calls per episode, 8 fresh replicates (S1: replication of co-primary Y1; S2: Y2)', REG + ' (PREREG_E_ext S1/S2)', [
        ('base', EXT, 'secondary/Y1/base_mean'), ('proxy', EXT, 'secondary/Y1/fullp_mean'),
        ('ratio', EXT, 'secondary/Y1/ratio_fullp_over_base'), ('diff', EXT, 'secondary/Y1/diff_fullp_minus_base/mean_diff'),
        ('diff CI', EXT, 'secondary/Y1/diff_fullp_minus_base/ci95'), ('verdict', EXT, 'secondary/Y1/verdict'),
        ('Y2 base', EXT, 'secondary/Y2/base_mean'), ('Y2 proxy', EXT, 'secondary/Y2/fullp_mean'),
        ('Y2 ratio', EXT, 'secondary/Y2/ratio_fullp_over_base')]),
    ('', 'Stuck episodes, 8 fresh replicates pooled [stuck, of]', REG + ' (PREREG_E_ext S3)', [
        ('base', EXT, 'secondary/stuck/base'), ('proxy', EXT, 'secondary/stuck/fullp'), ('McNemar p', EXT, 'secondary/stuck/mcnemar_p')]),
    ('', 'Resolved tasks over all 10 replicates (r1-r10)', DESC + ' (PREREG_E_ext, sequential)', [
        ('resolved [base, proxy, of]', EXT, 'descriptive_all_replicates/resolve/resolved_base_fullp_of'),
        ('diff', EXT, 'descriptive_all_replicates/resolve/mean_diff'), ('CI', EXT, 'descriptive_all_replicates/resolve/ci95')]),
    ('', 'Audit pick (cyankiwi AWQ, bf16) vs Google QAT under stock vLLM: malformed calls per episode (primary)', REG + ' (PREREG_E_awq; 2 AWQ vs 10 QAT replicates, task-paired across runs, not CRN-paired)', [
        ('AWQ base', AWQ, 'primary_awq_base_vs_qat_base/A_mean'), ('QAT base', AWQ, 'primary_awq_base_vs_qat_base/B_mean'),
        ('ratio', AWQ, 'primary_awq_base_vs_qat_base/ratio_A_over_B'), ('diff', AWQ, 'primary_awq_base_vs_qat_base/diff_A_minus_B/mean_diff'),
        ('diff CI', AWQ, 'primary_awq_base_vs_qat_base/diff_A_minus_B/ci95'), ('verdict', AWQ, 'primary_awq_base_vs_qat_base/verdict')]),
    ('', 'Proxy on top of the audit pick, first 2 AWQ replicates: AWQ-fullp vs AWQ-base (S-a; predicted ratio <= 0.3: failed; 6 fresh replicates: PREREG_E_awq2 below)', REG + ' (PREREG_E_awq secondary)', [
        ('AWQ fullp', AWQ, 'S_a_awq_fullp_vs_awq_base/A_mean'), ('AWQ base', AWQ, 'S_a_awq_fullp_vs_awq_base/B_mean'),
        ('ratio', AWQ, 'S_a_awq_fullp_vs_awq_base/ratio_A_over_B'), ('diff', AWQ, 'S_a_awq_fullp_vs_awq_base/diff_A_minus_B/mean_diff'),
        ('diff CI', AWQ, 'S_a_awq_fullp_vs_awq_base/diff_A_minus_B/ci95'), ('p', AWQ, 'S_a_awq_fullp_vs_awq_base/diff_A_minus_B/p_boot')]),
    ('', 'AWQ-fullp vs QAT-fullp (S-b)', DESC + ' (PREREG_E_awq S-b)', [
        ('AWQ fullp', AWQ, 'S_b_awq_fullp_vs_qat_fullp/A_mean'), ('QAT fullp', AWQ, 'S_b_awq_fullp_vs_qat_fullp/B_mean'),
        ('ratio', AWQ, 'S_b_awq_fullp_vs_qat_fullp/ratio_A_over_B')]),
    ('', 'Stuck and resolved episodes per arm [count, of] (S-c, S-d)', DESC + ' (PREREG_E_awq S-c/S-d)', [
        ('stuck AWQ base', AWQ, 'S_c_stuck/awq_base'), ('AWQ fullp', AWQ, 'S_c_stuck/awq_fullp'),
        ('QAT base', AWQ, 'S_c_stuck/qat_base'), ('QAT fullp', AWQ, 'S_c_stuck/qat_fullp'),
        ('resolved AWQ base', AWQ, 'S_d_resolved/awq_base'), ('AWQ fullp', AWQ, 'S_d_resolved/awq_fullp'),
        ('QAT base', AWQ, 'S_d_resolved/qat_base'), ('QAT fullp', AWQ, 'S_d_resolved/qat_fullp')]),
    ('', 'Proxy on top of the audit pick, 6 fresh AWQ replicates (r3-r8): AWQ-fullp vs AWQ-base, malformed calls per episode (primary P2)', REG + ' (PREREG_E_awq2)', [
        ('verdict', AWQ2, 'primary_P2_awq_fullp_vs_awq_base/verdict'), ('AWQ fullp', AWQ2, 'primary_P2_awq_fullp_vs_awq_base/A_mean'), ('AWQ base', AWQ2, 'primary_P2_awq_fullp_vs_awq_base/B_mean'),
        ('ratio', AWQ2, 'primary_P2_awq_fullp_vs_awq_base/ratio_A_over_B'), ('diff', AWQ2, 'primary_P2_awq_fullp_vs_awq_base/diff_A_minus_B/mean_diff'),
        ('diff CI', AWQ2, 'primary_P2_awq_fullp_vs_awq_base/diff_A_minus_B/ci95'), ('p', AWQ2, 'primary_P2_awq_fullp_vs_awq_base/diff_A_minus_B/p_boot'),
        ('episode pairs', AWQ2, 'n_episode_pairs'), ('excluded', AWQ2, 'excluded_pairs')]),
    ('', 'Fresh AWQ replicates: wasted calls per episode (S1, Y2) and stuck episodes (S2) [stuck, of]', REG + ' (PREREG_E_awq2 secondary)', [
        ('Y2 fullp', AWQ2, 'secondary/S1_Y2/A_mean'), ('Y2 base', AWQ2, 'secondary/S1_Y2/B_mean'),
        ('Y2 ratio', AWQ2, 'secondary/S1_Y2/ratio_A_over_B'), ('stuck base', AWQ2, 'secondary/S2_stuck/base'),
        ('stuck fullp', AWQ2, 'secondary/S2_stuck/fullp'), ('McNemar p', AWQ2, 'secondary/S2_stuck/mcnemar_p')]),
    ('', 'Audit pick vs Google QAT under stock vLLM, fresh AWQ episodes only (S4: replication of the PREREG_E_awq primary)', REG + ' (PREREG_E_awq2 S4; 6 AWQ vs 10 QAT replicates, task-paired across runs, not CRN-paired)', [
        ('AWQ base', AWQ2, 'secondary/S4_awq_base_vs_qat_base_fresh/A_mean'), ('QAT base', AWQ2, 'secondary/S4_awq_base_vs_qat_base_fresh/B_mean'), ('ratio', AWQ2, 'secondary/S4_awq_base_vs_qat_base_fresh/ratio_A_over_B'),
        ('diff', AWQ2, 'secondary/S4_awq_base_vs_qat_base_fresh/diff_A_minus_B/mean_diff'), ('diff CI', AWQ2, 'secondary/S4_awq_base_vs_qat_base_fresh/diff_A_minus_B/ci95'), ('verdict', AWQ2, 'secondary/S4_awq_base_vs_qat_base_fresh/verdict')]),
    ('', 'Fresh AWQ replicates: resolved tasks (S3; not claimed: 6 replicates, no power analysis)', DESC + ' (PREREG_E_awq2 S3)', [
        ('resolved [base, fullp, of]', AWQ2, 'secondary/S3_resolve/resolved_base_fullp_of'),
        ('diff', AWQ2, 'secondary/S3_resolve/mean_diff'), ('CI', AWQ2, 'secondary/S3_resolve/ci95')]),
    ('', 'Proxy on top of the audit pick over all 8 AWQ replicates (r1-r8): AWQ-fullp vs AWQ-base', DESC + ' (PREREG_E_awq2, sequential)', [
        ('AWQ fullp', AWQ2, 'descriptive_all_awq_replicates/P2/A_mean'), ('AWQ base', AWQ2, 'descriptive_all_awq_replicates/P2/B_mean'),
        ('ratio', AWQ2, 'descriptive_all_awq_replicates/P2/ratio_A_over_B')]),
    ('', 'Audit flags vs end-to-end malformed calls across checkpoints: T1 bf16 < QAT, T2 nvidia NVFP4 < QAT, T3 QAT-AWQ > AWQ, T4 QAT-NVFP4 > AWQ (Holm)', REG + ' (PREREG_E_audit; analysed once Nov 8 15:09 UTC)', [
        ('verdict', EAUD, 'primary/verdict'), ('T1', EAUD, 'primary/tests/T1_bf16_below_qat'), ('T2', EAUD, 'primary/tests/T2_nvnvfp4_below_qat'),
        ('T3', EAUD, 'primary/tests/T3_qatawq_above_awq'), ('T4', EAUD, 'primary/tests/T4_qatnvfp4_above_awq'), ('analysis sets', EAUD, 'analysis_sets')]),
    ('', 'Base malformed calls per episode by checkpoint [checkpoint, deficit nats, base Y1]; Spearman', DESC + ' (PREREG_E_audit)', [
        ('rows', EAUD, 'descriptive_rank/rows_checkpoint_deficit_baseY1'), ('Spearman', EAUD, 'descriptive_rank/spearman')]),
    ('', 'Is the proxy needed on this checkpoint? fullp vs base per new checkpoint (ratio)', REG + ' (PREREG_E_audit secondary)', [
        ('bf16', EAUD, 'checkpoints/bf16/fullp_vs_base/ratio_A_over_B'), ('nvidia NVFP4', EAUD, 'checkpoints/nvnvfp4/fullp_vs_base/ratio_A_over_B'),
        ('QAT-AWQ', EAUD, 'checkpoints/qatawq/fullp_vs_base/ratio_A_over_B'), ('QAT-NVFP4', EAUD, 'checkpoints/qatnvfp4/fullp_vs_base/ratio_A_over_B'),
        ('bf16 p', EAUD, 'checkpoints/bf16/fullp_vs_base/diff_A_minus_B/p_boot')]),
    ('', 'Which component carries the end-to-end gain: quarantine-only and IPD-only vs stock (Holm over 2), r3-r6', REG + ' (PREREG_E_comp; analysed once Nov 8 15:09 UTC)', [
        ('Q1 verdict', ECOMP, 'primary/Q1_quarantine_alone/verdict'), ('quar', ECOMP, 'primary/Q1_quarantine_alone/A_mean'), ('stock', ECOMP, 'primary/Q1_quarantine_alone/B_mean'),
        ('quar ratio', ECOMP, 'primary/Q1_quarantine_alone/ratio_A_over_B'), ('Q2 verdict', ECOMP, 'primary/Q2_ipd_alone/verdict'), ('ipd', ECOMP, 'primary/Q2_ipd_alone/A_mean'),
        ('ipd ratio', ECOMP, 'primary/Q2_ipd_alone/ratio_A_over_B'), ('analysis set', ECOMP, 'analysis_set')]),
    ('', 'Component secondaries: full vs quarantine, full vs IPD, quarantine vs IPD; stuck; resolve (NI descriptive)', REG + ' (PREREG_E_comp secondary)', [
        ('full vs quar', ECOMP, 'secondary/fullp_vs_quar/ratio_A_over_B'), ('full vs ipd', ECOMP, 'secondary/fullp_vs_ipd/ratio_A_over_B'),
        ('quar vs ipd', ECOMP, 'secondary/quar_vs_ipd/ratio_A_over_B'), ('stuck stock', ECOMP, 'secondary/counts/base/stuck'), ('stuck quar', ECOMP, 'secondary/counts/quar/stuck'), ('stuck ipd', ECOMP, 'secondary/counts/ipd/stuck'), ('stuck full', ECOMP, 'secondary/counts/fullp/stuck'),
        ('resolve quar - base', ECOMP, 'secondary/resolve_quar_minus_base'), ('resolve ipd - base', ECOMP, 'secondary/resolve_ipd_minus_base')]),

    ('TranscriptLab: one corrupted past call in 300 public PNC states', None, None, None),
    ('', '31B 4-bit: copying (laundered call + error), RD P1 - P0', REG + ' (PREREG_v2 C1: replicates)', [
        ('P0', C + 'confirm_v2_all_full.json', '31B/full/C1/uncond/base'), ('P1', C + 'confirm_v2_all_full.json', '31B/full/C1/uncond/arm'),
        ('RD', C + 'confirm_v2_all_full.json', '31B/full/C1/uncond/RD'), ('CI', C + 'confirm_v2_all_full.json', '31B/full/C1/uncond/RD_CI')]),
    ('', '31B: induction (laundered call + success), RD P6 - P0; dose k=4', REG + ' (PREREG_v2 C2/C3: attenuated)', [
        ('RD', C + 'confirm_v2_all_full.json', '31B/full/C2/uncond/RD'), ('k=4 rate', C + 'confirm_v2_all_full.json', '31B/C3/uncond/rates/k=4')]),
    ('', '31B: quarantine removal with the recovered call (P8a, the proxy\'s form) and sanitized (P8b, the ADK/LiteLLM hooks\' form); informative-error retention', REG + ' (PREREG_v2 C5/C6/C7)', [
        ('P8a removal', C + 'confirm_v2_all_full.json', '31B/full/C5/uncond/removal'), ('CI', C + 'confirm_v2_all_full.json', '31B/full/C5/uncond/CI'),
        ('P8b removal', C + 'confirm_v2_all_full.json', '31B/full/C6/uncond/removal'), ('CI', C + 'confirm_v2_all_full.json', '31B/full/C6/uncond/CI'),
        ('retention', C + 'confirm_v2_all_full.json', '31B/full/C7/retention_point')]),
    ('', '31B bf16: copying and induction', EXP + ' (benchmark row; plan frozen before data)', [
        ('copying', C + 'bf16_core_all.json', 'uncond/RD_P1_P0'), ('induction', C + 'bf16_core_all.json', 'uncond/RD_P6_P0')]),
    ('', 'E4B and 12B', REG + ' (PREREG_v2 C8-C10)', [
        ('E4B copying', C + 'confirm_v2_31b_e4b_full.json', 'E4B/C9/uncond'), ('12B copying', C + 'confirm_v2_all_full.json', '12B/C8/uncond')]),
    ('', 'Qwen models (copy-on-retry X1, induction X4), RD in pp', REG + ' (X PREREG_v2)', [
        ('Qwen3-8B X1', XV2, 'models/qwen3-8b/X1/RD_pp'), ('X4', XV2, 'models/qwen3-8b/X4/RD_pp'),
        ('Qwen3-32B X1', XV2, 'models/qwen3-32b/X1/RD_pp'), ('X4', XV2, 'models/qwen3-32b/X4/RD_pp'),
        ('Qwen3.5-9B X1', XV2, 'models/qwen3.5-9b/X1/RD_pp'), ('X4', XV2, 'models/qwen3.5-9b/X4/RD_pp')]),
    ('', 'Four more families: copying (P1L vs P0) and induction (P6)', REG + ' (X prereg_ext)', [
        ('gpt-oss-20b', XEXT, 'models/gpt-oss-20b/P1L_vs_P0'), ('', XEXT, 'models/gpt-oss-20b/secondary/P6'),
        ('Qwen3-Coder-30B', XEXT, 'models/qwen3-coder-30b/P1L_vs_P0'), ('', XEXT, 'models/qwen3-coder-30b/secondary/P6'),
        ('Devstral-Small-2', XEXT, 'models/devstral-24b/P1L_vs_P0'), ('', XEXT, 'models/devstral-24b/secondary/P6'),
        ('Qwen3.8-27B', XEXT, 'models/qwen3.8-27b/P1L_vs_P0'), ('', XEXT, 'models/qwen3.8-27b/secondary/P6')]),

    ('Repair: injected slips (393 detectable) and valid calls', None, None, None),
    ('', 'Exact intent recovered (reweighted to natural closer shares)', REG + ' (PREREG_v2.4)', [
        ('n', B4, 'n_detectable'), ('IPD', B4, 'outcomes_detectable/IPD/exact/reweighted/rate'),
        ('lenient (stock)', B4, 'outcomes_detectable/lenient/exact/reweighted/rate'), ('greedy', B4, 'outcomes_detectable/greedy/exact/reweighted/rate'),
        ('grammar-CD', B4, 'outcomes_detectable/grammar_CD/exact/reweighted/rate')]),
    ('', 'IPD vs text-only repair (T1); IPD silent corruption; failed rules', REG + ' (PREREG_v2.4)', [
        ('contrast', B4, 'IPD_vs_T1_exact/contrast_reweighted'), ('CI', B4, 'IPD_vs_T1_exact/ci95'),
        ('IPD silent', B4, 'outcomes_detectable/IPD/silent/reweighted/rate'), ('R3', B4, 'rules/R3_IPD_no_silent_on_detectable'),
        ('R4', B4, 'rules/R4_grammarCD_corrupts_silently'), ('R7', B4, 'rules/R7_retry_rarely_recovers'), ('R8', B4, 'rules/R8_greedy_rarely_recovers')]),
    ('', 'Silent corruption (a delivered call with the wrong intent) on the 393 detectable injected slips', REG + ' (PREREG_v2.4; rule R3 failed)', [
        ('n', B4, 'n_detectable'), ('IPD', B4, 'outcomes_detectable/IPD/silent/reweighted/rate'), ('stock lenient', B4, 'outcomes_detectable/lenient/silent/reweighted/rate'),
        ('fail-loud', B4, 'outcomes_detectable/fail_loud/silent/reweighted/rate'), ('text-only repair (T1)', B4, 'outcomes_detectable/T1/silent/reweighted/rate'),
        ('greedy', B4, 'outcomes_detectable/greedy/silent/reweighted/rate')]),
    ('', 'Silent corruption and exact intent over all 600 injected slips (ITT; undetectable slips included)', 'registered population (PREREG_v2.4 ITT; descriptive, no rule)', [
        ('n', B4, 'n_states'), ('IPD silent', B4, 'outcomes_ITT/IPD/silent/reweighted/rate'), ('stock lenient', B4, 'outcomes_ITT/lenient/silent/reweighted/rate'),
        ('fail-loud', B4, 'outcomes_ITT/fail_loud/silent/reweighted/rate'), ('text-only repair (T1)', B4, 'outcomes_ITT/T1/silent/reweighted/rate'),
        ('greedy', B4, 'outcomes_ITT/greedy/silent/reweighted/rate'), ('IPD exact', B4, 'outcomes_ITT/IPD/exact/reweighted/rate')]),
    ('', 'IPD on valid first-edit calls (byte identity)', REG + ' (PREREG_v2 C14)', [
        ('valid calls', ID, 'confirmatory_PREREG_v2/S1_B1_full/C14_byte_identity/valid_calls'), ('changed', ID, 'confirmatory_PREREG_v2/S1_B1_full/C14_byte_identity/changed')]),

    ('Full stack on contaminated histories', None, None, None),
    ('', '31B: harmful rate stock vs slipguard; verdict; no-harm N2', REG + ' (PREREG_v2.5)', [
        ('stock', B5, 'F1_R1/STOCK/rate'), ('slipguard', B5, 'F1_R1/SLIPGUARD'), ('verdict', B5, 'verdicts/F1'),
        ('N2 violations', B5, 'no_harm/N2/violations'), ('of', B5, 'no_harm/N2/samples_checked')]),
    ('', 'E4B: same', REG + ' (PREREG_v2.5b)', [
        ('stock', B5b, 'F1_R1/STOCK/rate'), ('slipguard', B5b, 'F1_R1/SLIPGUARD'), ('verdict', B5b, 'verdicts/F1_E4B'),
        ('N2 violations', B5b, 'no_harm/N2/violations'), ('of', B5b, 'no_harm/N2/samples_checked')]),
    ('', 'Thought opened with thinking off after a tool response (patched template)', REG + ' (PREREG_v2.5 F3)', [
        ('stock', B5, 'F3/STOCK/rate'), ('guarded', B5, 'F3/GUARDED/rate'), ('n', B5, 'F3/n_states')]),

    ('Weight audit and its behavioural test', None, None, None),
    ('', 'Closer-margin deficit vs bf16 (nats, median paired) and censored fraction', REG + ' (F SWEEP_PLAN)', [
        ('QAT 31B', W, 'checkpoints/31b_qatct/paired_vs_ref/median_deficit'), ('censored', W, 'checkpoints/31b_qatct/censored_frac'),
        ('cyankiwi AWQ', W, 'checkpoints/31b_awq_cyankiwi/paired_vs_ref/median_deficit'), ('censored', W, 'checkpoints/31b_awq_cyankiwi/censored_frac'),
        ('QAT 31B unquantized weights', W, 'checkpoints/31b_qatunq/paired_vs_ref/median_deficit')]),
    ('', 'Uncensored-only deficits (sensitivity)', EXP + ' (review B13)', [
        ('QAT 31B [point, lo, hi]', CEN, 'vs_reference/31b_qatct/median_deficit_uncensored'), ('n both uncensored', CEN, 'vs_reference/31b_qatct/n_both_uncensored'),
        ('cyankiwi AWQ', CEN, 'vs_reference/31b_awq_cyankiwi/median_deficit_uncensored'), ('n', CEN, 'vs_reference/31b_awq_cyankiwi/n_both_uncensored')]),
    ('', 'Serving the audit pick: P1 rate QAT vs AWQ vs AutoRound; H1; quarantine on AWQ', REG + ' (PREREG_v2.6)', [
        ('QAT P1', V26, 'rates/QAT/P1'), ('AWQ P1', V26, 'rates/AWQ/P1'), ('AutoRound P1', V26, 'rates/AR/P1'), ('AutoRound P0', V26, 'rates/AR/P0'),
        ('H1', V26, 'H1/verdict'), ('AWQ P8a', V26, 'rates/AWQ/P8a'), ('H3 removal', V26, 'H3/removal/point')]),

    ('Conformance on public real inputs (all 41,290 PNC turns)', None, None, None),
    ('', 'Wrong call delivered on ill-formed turns of known intent', REG.replace('registered', 'frozen suite') , [
        ('known-intent turns', PNC, 'populations/ill_intent_known'),
        ('vLLM 0.19.1 built-in', PNC, 'targets/vllm019.server/intent_known/wrong'), ('vLLM 0.33 built-in', PNC, 'targets/vllm033.server/intent_known/wrong'),
        ('slipguard plugin 0.33', PNC, 'targets/gg.vllm033.server/intent_known/wrong')]),
    ('', 'Opt-in text repair on the same turns (after the post-hoc fix; before: prefix_fix/)', DESC + ' (post-hoc fix disclosed)', [
        ('exact', PNC, 'targets/gg.repair/intent_known/exact'), ('loud', PNC, 'targets/gg.repair/intent_known/surfaced'),
        ('pre-fix exact', PNCF, 'targets/gg.repair/intent_known/exact'), ('pre-fix wrong', PNCF, 'targets/gg.repair/intent_known/wrong')]),

    ('Robustness (PREREG_v2.7) and the released CLI (PREREG_v2.8)', None, None, None),
    ('', 'Copying and quarantine at temperature 0.6 and greedy', REG + ' (PREREG_v2.7 T1-T4)', [
        ('T0.6 copying', C + 'v27_robustness_analysis.json', 'copying/RT06/RD_P1_minus_P0'), ('CI', C + 'v27_robustness_analysis.json', 'copying/RT06/CI'), ('removal', C + 'v27_robustness_analysis.json', 'removal/RT06/point'),
        ('greedy copying', C + 'v27_robustness_analysis.json', 'copying/RT00/RD_P1_minus_P0'), ('CI', C + 'v27_robustness_analysis.json', 'copying/RT00/CI'), ('removal', C + 'v27_robustness_analysis.json', 'removal/RT00/point'),
        ('verdicts T0.6', C + 'v27_robustness_analysis.json', 'verdicts/RT06_copying'), ('', C + 'v27_robustness_analysis.json', 'verdicts/RT06_quarantine'),
        ('greedy', C + 'v27_robustness_analysis.json', 'verdicts/RT00_copying'), ('', C + 'v27_robustness_analysis.json', 'verdicts/RT00_quarantine')]),
    ('', 'Audit pick at matched dtype: AWQ served bf16 vs QAT, P1', REG + ' (PREREG_v2.7 D1)', [
        ('AWQ-bf16 P1', C + 'v27_robustness_analysis.json', 'rates/RD16/P1'), ('contrast', C + 'v27_robustness_analysis.json', 'contrasts/D1'), ('verdict', C + 'v27_robustness_analysis.json', 'verdicts/D1')]),
    ('', 'Test-retest with two new seed sets (copying RD; quarantine removal)', REG + ' (PREREG_v2.7 S1/S2)', [
        ('seed A copying', C + 'v27_robustness_analysis.json', 'copying/RSA/RD_P1_minus_P0'), ('removal', C + 'v27_robustness_analysis.json', 'removal/RSA/point'),
        ('seed B copying', C + 'v27_robustness_analysis.json', 'copying/RSB/RD_P1_minus_P0'), ('removal', C + 'v27_robustness_analysis.json', 'removal/RSB/point'),
        ('P1 spread (C1, A, B)', C + 'v27_robustness_analysis.json', 'test_retest_spread/P1'), ('verdict', C + 'v27_robustness_analysis.json', 'verdicts/test_retest')]),
    ('', 'Pooled test-retest of the proxy\'s quarantine form P8a (C1 + two new seed sets: 300 states x 3 runs = 900 samples per arm)', 'pre-specified descriptive (PREREG_v2.7 §4), computed afterwards (deviation v2.7 item 6)', [
        ('P0', C + 'v27_pooled_retest.json', 'pooled/P0'), ('P1', C + 'v27_pooled_retest.json', 'pooled/P1'), ('P8a', C + 'v27_pooled_retest.json', 'pooled/P8a'),
        ('copying RD', C + 'v27_pooled_retest.json', 'pooled_copying_RD'), ('quarantine removal', C + 'v27_pooled_retest.json', 'pooled_removal')]),
    ('', 'Released TranscriptLab CLI vs the registered run (same seeds)', REG + ' (PREREG_v2.8)', [
        ('copying', C + 'v28_cli_analysis.json', 'copying/CLI'), ('removal', C + 'v28_cli_analysis.json', 'removal/CLI/point'),
        ('P1 vs C1', C + 'v28_cli_analysis.json', 'P1_CLI_vs_C1/mcnemar_two_sided_p'), ('job agreement', C + 'v28_cli_analysis.json', 'job_agreement'),
        ('verdict', C + 'v28_cli_analysis.json', 'verdict')]),
    ('', 'Soak: stock vLLM + proxy (K1) and the plugin server (K2), 60 min each', REG + ' (PREREG_v2.7 §5)', [
        ('verdict', 'experiments/soak/out/soak_analysis.json', 'verdict'), ('criteria', 'experiments/soak/out/soak_analysis.json', 'criteria')]),
    ('', 'Gemma coverage via the CLI: E2B 4-bit, E4B bf16', REG + ' (PREREG_v2.9)', [
        ('E2B', C + 'v29_coverage.json', 'runs/experiments/transcriptlab_cli/run_e2b/verdict'),
        ('E4B bf16', C + 'v29_coverage.json', 'runs/experiments/transcriptlab_cli/run_e4b16/verdict')]),
    ('', 'Audit of the most-downloaded unaudited 31B checkpoints; H-QAT', REG + ' (PREREG_v2.10)', [
        ('H-QAT', 'experiments/quant_margins/wsa/out/v210_audit_breadth.json', 'H_QAT')]),
    ('', 'Released masked corpus (e-mails as `<email>`) vs the registered run, via the CLI', REG + ' (PREREG_v2.11)', [
        ('copying', C + 'v211_masked_analysis.json', 'copying/CLI'), ('P1 masked vs C1', C + 'v211_masked_analysis.json', 'P1_masked_vs_C1'), ('P1 McNemar p', C + 'v211_masked_analysis.json', 'P1_masked_vs_C1/mcnemar_two_sided_p'),
        ('removal (not gated)', C + 'v211_masked_analysis.json', 'removal_not_gated/CLI'), ('verdict', C + 'v211_masked_analysis.json', 'verdict')]),
    ('', 'Second masked-corpus run (descriptive): P1, copying, pooled masked vs unmasked; reading', REG + ' (PREREG_v2.11b, descriptive)', [
        ('masked run 2 P1', C + 'v211b_pooled.json', 'runs/masked_2/P1_all'), ('copying', C + 'v211b_pooled.json', 'runs/masked_2/copying'),
        ('pooled', C + 'v211b_pooled.json', 'pooled'), ('reading', C + 'v211b_pooled.json', 'reading')]),
    ('', '31B bf16 via the CLI (registered): copying without quantization; bf16 P1 vs QAT P1', REG + ' (PREREG_v2.14)', [
        ('copying', C + 'v214_bf16_analysis.json', 'copying/CLI'), ('bf16 vs QAT P1', C + 'v214_bf16_analysis.json', 'B_bf16_P1_vs_QAT_P1'),
        ('verdict A', C + 'v214_bf16_analysis.json', 'verdict_A'), ('verdict B', C + 'v214_bf16_analysis.json', 'verdict_B')]),
    ('', 'Weight audit predicts TranscriptLab copying across seven 31B checkpoints (three new, out of sample)', REG + ' (PREREG_v2.15)', [
        ('panel', C + 'v215_audit_panel.json', 'primary'), ('S1 QAT-AWQ > bf16, RD', C + 'v215_audit_panel.json', 'secondary_out_of_sample/S1_qatawq_above_bf16/RD'), ('S1 met', C + 'v215_audit_panel.json', 'secondary_out_of_sample/S1_qatawq_above_bf16/met'), ('S2 QAT-NVFP4 > bf16, RD', C + 'v215_audit_panel.json', 'secondary_out_of_sample/S2_qatnvfp4_above_bf16/RD'), ('S2 met', C + 'v215_audit_panel.json', 'secondary_out_of_sample/S2_qatnvfp4_above_bf16/met'), ('S3 nvidia NVFP4 < QAT, RD', C + 'v215_audit_panel.json', 'secondary_out_of_sample/S3_nvnvfp4_below_qat/RD'), ('S3 met', C + 'v215_audit_panel.json', 'secondary_out_of_sample/S3_nvnvfp4_below_qat/met')]),
    ('', 'Copying follows the QAT weights, not the 4-bit format: unquantized QAT weights vs bf16 and vs 4-bit QAT; 11-checkpoint panel', REG + ' (PREREG_v2.16)', [
        ('H1', C + 'v216_qat_weights.json', 'H1_qatunq_above_bf16'), ('verdict H1', C + 'v216_qat_weights.json', 'verdict_H1'),
        ('H2', C + 'v216_qat_weights.json', 'H2_qatunq_minus_qat'), ('panel (descriptive)', C + 'v216_qat_weights.json', 'descriptive_extended_panel')]),
    ('', 'Llama family via the CLI 0.1.3: Hermes-3-Llama-3.1-8B (copying, imitation, removal; verdict)', REG + ' (PREREG_v2.12)', [
        ('copying', C + 'v212_llama.json', 'copying_RD'), ('imitation', C + 'v212_llama.json', 'imitation_RD'),
        ('removal', C + 'v212_llama.json', 'removal_P8a/uncond/fraction_removed'), ('verdict', C + 'v212_llama.json', 'verdict')]),
]


def to_layout(f, layout):
    """Rewrite a project-layout path to the chosen layout (the library moves between release/lib/ and slipguard/)."""
    for lay, pre in LAYOUT_PREFIX.items():
        if lay != layout and f.startswith(pre):
            return LAYOUT_PREFIX[layout] + f[len(pre):]
    return f


def detect_layout(root):
    if os.path.isdir(os.path.join(root, LAYOUT_PREFIX['project'])):
        return 'project'
    if os.path.isdir(os.path.join(root, LAYOUT_PREFIX['public'])) or os.path.exists(os.path.join(root, 'FROZEN_EXPORT_PINS.json')):
        return 'public'
    return 'project'


def load_list(path):
    """{relative path: record} from FROZEN_EXPORT_PINS.json / WITHHELD.json; {} if the file is absent or unreadable."""
    if not path or not os.path.exists(path):
        return {}
    try:
        return json.load(open(path)).get('files', {})
    except (OSError, ValueError, AttributeError):
        return {}


def get(root, f, key, withheld=None):
    p = os.path.join(root, f)
    if not os.path.exists(p):
        return None, ('WITHHELD' if withheld and f in withheld else 'MISSING FILE')
    if not key: return None, 'file'
    x = json.load(open(p))
    parts = key.split('/'); i = 0
    while i < len(parts):
        if isinstance(x, list):
            try: x = x[int(parts[i])]; i += 1; continue
            except Exception: return None, 'BAD PATH'  # noqa: BLE001
        if not isinstance(x, dict): return None, 'BAD PATH'
        for j in range(len(parts), i, -1):   # longest key first: some keys contain '/' (run directories)
            k = '/'.join(parts[i:j])
            if k in x: x = x[k]; i = j; break
        else:
            return None, 'BAD PATH'
    return x, 'ok'


def fmt(v):
    if isinstance(v, bool): return str(v)
    if isinstance(v, float): return f'{v:.4g}'
    if isinstance(v, list): return '[' + ', '.join(fmt(x) for x in v[:6]) + (', ...' if len(v) > 6 else '') + ']'
    if isinstance(v, dict):
        if 'RD' in v and 'RD_CI' in v: return f"RD {fmt(v['RD'])} {fmt(v['RD_CI'])}"
        if 'ratio' in v and 'ci95' in v: return f"{fmt(v['ratio'])} {fmt(v['ci95'])}"
        if 'rate' in v and 'k' in v and 'n' in v: return f"{v['k']}/{v['n']} = {fmt(v['rate'])}"
        items = [(k, x) for k, x in v.items() if not isinstance(x, (dict, list)) or (isinstance(x, list) and len(x) <= 3)]
        return '{' + ', '.join(f'{k}: {fmt(x)}' for k, x in items[:6]) + '}'
    s = str(v)
    return s if len(s) <= 90 else s[:87] + '...'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default='.'); ap.add_argument('--out', default='RESULTS.md'); ap.add_argument('--check', action='store_true')
    ap.add_argument('--layout', choices=('auto', 'project', 'public'), default='auto',
                    help='tree layout (default: auto; the library is at release/lib/ in the project, slipguard/ in the public tree)')
    ap.add_argument('--withheld', default=None, help='WITHHELD.json to consult (default: ROOT/WITHHELD.json if present; "" = none)')
    ap.add_argument('--verbose', action='store_true', help='list every unresolved reference, not one line per file')
    ap.add_argument('--pins', default=None, help='FROZEN_EXPORT_PINS.json to consult (default: ROOT/FROZEN_EXPORT_PINS.json if present; "" = none)')
    a = ap.parse_args()
    layout = detect_layout(a.root) if a.layout == 'auto' else a.layout
    withheld = load_list(os.path.join(a.root, 'WITHHELD.json') if a.withheld is None else a.withheld)
    pins = load_list(os.path.join(a.root, 'FROZEN_EXPORT_PINS.json') if a.pins is None else a.pins)
    lines, bad, n_withheld = [], [], 0
    files = set()
    for sec, claim, status, refs in ROWS:
        if claim is None:
            lines += ['', f'## {sec}', '', '| result | values (read from the file) | status | source |', '|---|---|---|---|']; continue
        vals, srcs = [], []
        for lab, f0, key in refs:
            f = to_layout(f0, layout)
            v, st = get(a.root, f, key, withheld)
            files.add(f)
            if st == 'ok': vals.append((f'{lab} ' if lab else '') + fmt(v))
            elif st == 'file': vals.append('see file')
            elif st == 'WITHHELD':
                vals.append(f'{lab} *withheld (listed in WITHHELD.json)*'); n_withheld += 1
            else:
                pend = any(x in f for x in ('soak', 'v29', 'v210'))
                vals.append(f'{lab} *{"pending" if pend else st}*')
                if not pend: bad.append((claim, f, key, st))
            srcs.append(f'`{f}#{key}`' if key else f'`{f}`')
        lines.append(f'| {claim} | {"; ".join(vals)} | {status} | {"<br>".join(dict.fromkeys(srcs))} |')
    head = ['# Results', '',
            'Every value below is read from its result file by `tools/make_results_md.py` when this page is generated; '
            'none is typed by hand. *Registered* = decided by a frozen analysis (`PREREGISTRATIONS.md`); *exploratory* = '
            'computed afterwards with the frozen code reused unchanged; *descriptive* = reported, never used as a verdict '
            '(*pre-specified descriptive* = named in a registration, but not a test). '
            'Rates are proportions (0.197 = 19.7%); CIs are 95% (cluster bootstrap or exact, as registered). '
            'Limitations: `LIMITATIONS.md`.', '',
            f'Generated {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC from {len(files)} files.']
    tail = ['', '## Source file hashes', '', '| file | sha256 (16) |', '|---|---|']
    for f in sorted(files):
        p = os.path.join(a.root, f)
        if os.path.exists(p):
            cell = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
            rec = pins.get(f)
            if rec and rec.get('frozen_sha256'):
                cell += f" (exported with edits; frozen {rec['frozen_sha256'][:16]})"
        else:
            cell = 'withheld (listed in WITHHELD.json)' if f in withheld else 'pending'
        tail.append(f'| `{f}` | {cell} |')
    text = '\n'.join(head + lines + tail) + '\n'
    if a.verbose:
        for b in bad: print('UNRESOLVED', b)
    else:   # one line per file (--verbose lists every reference)
        by = {}
        for _, f, _, st in bad: by.setdefault((f, st), 0); by[(f, st)] += 1
        for (f, st), k in sorted(by.items()): print(f'UNRESOLVED {f}: {k} reference(s), {st}')
    n = sum(1 for r in ROWS if r[1])
    extra = f', {n_withheld} withheld (listed)' if n_withheld else ''
    if a.check:   # compare with the existing file; never write. Ignore the 'Generated ...' timestamp line.
        strip = lambda t: '\n'.join(l for l in t.split('\n') if not l.startswith('Generated '))
        old = open(a.out).read() if os.path.exists(a.out) else ''
        same = strip(old) == strip(text)
        print(f'check {a.out} ({layout} layout): {n} results, {len(bad)} unresolved{extra}, {"UP TO DATE" if same else "DIFFERS from the result files"}')
        return 0 if (same and not bad) else 1
    open(a.out, 'w').write(text)
    print(f'wrote {a.out} ({layout} layout): {n} results, {len(bad)} unresolved{extra}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
