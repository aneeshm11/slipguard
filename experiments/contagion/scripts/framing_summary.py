"""Write out/FRAMING_SUMMARY.md: every workstream-A result in one table (estimand, n, estimate + 95% CI, prereg status,
data source, rule outcome), generated from A's result files only, so numbers match the JSONs exactly.
Prereg status: registered = a numeric prediction or rule in PREREG_v1 (§3, §4.2) or PREREG_v2 (§3.1, §4);
plan rule = UPGRADE_PLAN decision rules (copied verbatim into PREREG_v1 §4.1/§4.3) or the assignment's gate;
exploratory = everything else. Data source: discovery (main-track logs, June template unless noted) or
confirmatory (workstream P's public SWE-bench corpus, PREREG_v2; runs on 2026-11-05).
usage: framing_summary.py  (reads results.json, out/*.json; writes out/FRAMING_SUMMARY.md)"""
import json, os, time
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
J = lambda p: json.load(open(os.path.join(D, p)))
R = J('results.json'); DR = J('out/decision_rules.json'); PA = J('out/prereg_analysis.json')
G = R['injection']['31b_old']['gate_k1_random_sample']
pp = lambda x: f'{100 * x:+.1f} pp' if x is not None else '—'
pc = lambda x: f'{100 * x:.1f}%'


def ci(lo, hi, scale=100, d=1, unit=''):
    f = lambda v: ('inf' if v in ('inf', float('inf')) else f'{scale * v:.{d}f}')
    return f'[{f(lo)}, {f(hi)}]{unit}'


def rd(x):  # decision_rules / gate_arms format
    return f"{pp(x['RD'])} {ci(*x['RD_CI'])}"


def rm(x):
    return f"{100 * x['fraction_removed']:.0f}% {ci(*x['CI'], d=0)}"


def wil(v):  # [p, lo, hi, n]
    return f'{pc(v[0])} {ci(v[1], v[2])}'


rows = []


def add(sec, result, estimand, n, est, status, source, outcome=''):
    rows.append((sec, result, estimand, n, est, status, source, outcome))


DISC = 'discovery (main-track)'
# ---------------------------------------------------------------- observational
B = R['observational']['BASE_plain_31b_qat']; cb = B['cluster_bootstrap_95CI']
SY = R['observational']['SYN_replication']
add('Observational (base 31B, teacher-free; attempt-cluster bootstrap CIs)', 'synthesis numbers replicated (population incl. teacher runs)',
    'first edit; later clean; after 1; after >= 4 prior malformed', f"{SY['attempts']} attempts",
    f"{pc(SY['first_edit'][0])} / {pc(SY['later_clean_history'][0])} / {pc(SY['later_by_prior_bad']['1'][0])} / {pc(SY['later_by_prior_bad']['4'][0])}",
    'exploratory (original task 1)', DISC, 'replicated; population contaminated by teacher runs served under the 31B alias, so the corrected base numbers follow')
add('', 'first-edit onset', 'P(first edit malformed)', f"{B['attempts']} attempts",
    f"{pc(B['first_edit'][0])} {ci(*cb['first_edit'])}", 'exploratory', DISC)
add('', 'later edit, clean history', 'P(malformed | 0 prior malformed edits)', B['later_clean_history'][3],
    f"{pc(B['later_clean_history'][0])} {ci(*cb['later_clean_history'])}", 'exploratory', DISC)
add('', 'after 1 malformed edit', 'P(malformed | 1 prior)', B['later_by_prior_bad']['1'][3],
    f"{pc(B['later_by_prior_bad']['1'][0])} {ci(*cb['after_1_bad'])}", 'exploratory', DISC)
add('', 'after >= 4 malformed edits', 'P(malformed | >= 4 prior)', B['later_by_prior_bad']['4'][3],
    f"{pc(B['later_by_prior_bad']['4'][0])} {ci(*cb['after_ge4_bad'])}", 'exploratory', DISC)
pn = B['perm_null_P_bad_given_prev_bad']
add('', 'serial dependence vs permutation null', 'P(bad | prev bad) vs within-attempt shuffle', f"{B['edits']} edits",
    f"{pc(pn['observed'])} vs null {pc(pn['mean'])} (q97.5 {pc(pn['q975'])}), p = {pn['p_value']:.3f}", 'exploratory', DISC)
hz = R['observational']['hazard_model_BASE']['hazard']['prev_bad']
add('', 'hazard model', 'odds ratio of previous edit malformed', f"{B['edits']} edits", f"OR {hz['odds_ratio']:.1f} {ci(*hz['OR_CI95'], scale=1)}",
    'exploratory', DISC)
# ---------------------------------------------------------------- gate (k = 1), 31B
P1 = G['paired_vs_P0']['P1k1']
add('Causal injection, 31B, k = 1 (gate half: 300 contexts / 256 attempts; P0 = 5.0%)', 'P1 laundered corrupted re-render + error',
    'RD(P1 − P0), unconditional (ITT)', 300, f"{pp(P1['uncond']['diff'])} {ci(*P1['uncond']['diff_CI'])}; ratio {P1['uncond']['ratio']:.1f} {ci(*P1['uncond']['ratio_CI'], scale=1)}",
    'plan rule (assignment gate: ratio ≥ 3×)', DISC, 'gate PASSED')
add('', 'P1 (conditional)', 'P(malformed | edit): P1 vs P0', P1['cond']['n_contexts'],
    f"{pc(P1['cond']['arm'])} vs {pc(P1['cond']['base'])}; ratio {P1['cond']['ratio']:.1f} {ci(*P1['cond']['ratio_CI'], scale=1)}", 'plan rule (secondary estimand)', DISC)
GA = DR['gate_arms_vs_P0']
add('', 'P2 error message only', 'RD(P2 − P0)', 300, rd(GA['P2k1']['uncond']), 'exploratory', DISC, 'error alone does not raise slips')
add('', 'P3 raw slip text in content', 'RD(P3 − P0)', 300, rd(GA['P3k1']['uncond']), 'exploratory', DISC)
add('', 'P6 valid content, corrupted format (induction)', 'RD(P6 − P0)', 300, rd(GA['P6k1']['uncond']),
    'registered (PREREG_v1 §3.3: RD ≥ +5 pp, CI_lo > 0)', DISC, 'holds')
add('', 'P7 = P1 with a " closer', 'RD(P7 − P0); share of slips using the injected "', 300,
    f"{rd(GA['P7k1']['uncond'])}; quote share {wil(PA['P7_injected_quote_share']['share_with_quote_closer'])}",
    'registered (PREREG_v1 §3.3: share 0.55, 80% PI 0.40–0.70)', DISC, 'inside the PI')
q9 = G['quarantine_removal']['P9k1']['uncond']
add('', 'P9 = P1 + informative error', 'RD(P9 − P0); retained share of the P1 excess', 300,
    f"{rd(GA['P9k1']['uncond'])}; retains {100 * (1 - q9['fraction_removed']):.0f}% {ci(1 - q9['CI'][1], 1 - q9['CI'][0], d=0)}",
    'registered (PREREG_v1 §3.3: retains ≥ 50%)', DISC, 'holds')
SQ = DR['shipped_quarantine']
add('', 'P8a shipped quarantine (recovered call + MalformedToolCall)', 'removal of the P1 excess (P1 − Q)/(P1 − P0)', 300, rm(SQ['P8a']),
    'registered (PREREG_v1 §3.3: ≥ 70%) + plan rule', DISC, 'holds; plan rule "shipped quarantine works"')
add('', 'P8b sanitized quarantine', 'removal', 300, rm(SQ['P8b']), 'registered (≥ 50% and < P8a)', DISC, '≥ 50% holds; "< P8a" not met (equal)')
add('', "P4' canonical re-render, own order", 'removal', 300, rm(SQ['P4P']), 'registered (≥ 80%) + plan rule', DISC,
    'byte-identical to P0 in 297/300, so 100% by construction (deviation 7)')
add('', 'P4 canonical re-render (new-first)', 'removal', 300, rm(SQ['P4']), 'plan rule (assignment gate: ≥ 50%)', DISC, 'gate PASSED')
add('', 'P5 call removed + note', 'removal', 300, rm(SQ['P5']), 'plan rule (assignment gate: ≥ 50%)', DISC, 'gate PASSED')
RF = G['replay_fidelity_P0']
add('', 'replay fidelity (P0 = unmodified context re-sampled)', 'logged next call malformed vs P0 replay (uncond)', RF['n_contexts'],
    f"logged {wil(RF['logged_next_call_malformed'])} vs replay {pc(G['arms']['P0k0']['P_malformed_edit_uncond'][0])}", 'exploratory', DISC, 'replay reproduces the natural rate')
cp = DR['copying']
add('', 'copying', 'share of P1 malformed edits that are verbatim copies', cp['P1_share_of_malformed_that_are_verbatim_copies'][3],
    wil(cp['P1_share_of_malformed_that_are_verbatim_copies']), 'plan rule (≥ 80% and the P7 quote test)', DISC, f"copying {cp['decision']}")
SE = J('out/ana_31b_sensitivity_excl9.json')
add('', 'sensitivity: 9 flagged histories excluded', 'RD(P1 − P0); P8a removal', SE['n_contexts'],
    f"{pp(SE['paired_vs_P0']['P1k1']['uncond']['diff'])} {ci(*SE['paired_vs_P0']['P1k1']['uncond']['diff_CI'])}; P8a {rm(SE['quarantine_removal']['P8ak1']['uncond'])}",
    'registered sensitivity (deviation 10)', DISC, 'unchanged')
# ---------------------------------------------------------------- held-out
H = DR['heldout_replication']
add('Held-out half (294 contexts / 244 attempts; frozen before the outcomes; analysed once)', 'P1', 'RD(P1 − P0)', H['n_contexts_frozen'],
    rd(H['P1_vs_P0']['uncond']), 'plan rule (P0-A1 held-out arm)', DISC, 'replicates the gate')
add('', 'P6 (induction)', 'RD(P6 − P0); new-content only', H['n_contexts_frozen'],
    f"{rd(H['P6_vs_P0']['uncond'])}; new-content {rd(H['P6_vs_P0']['newcontent_uncond'])}", 'plan rule (format induction: both halves)', DISC,
    f"format induction {DR['format_induction']['decision'].upper()}")
add('', 'P8a', 'removal', H['n_contexts_frozen'], rm(H['P8a_removal_of_P1_excess']['uncond']), 'registered (≥ 70%)', DISC, 'holds')
# ---------------------------------------------------------------- July template
JT = DR['july_template']['uncond']
add('July (HF) template, 31B (NT; 150 contexts)', 'P1 vs P0 under the July template', 'RD; ratio', JT['n_contexts'],
    f"{rd(JT)}; ratio {JT['ratio']:.1f} {ci(*JT['ratio_CI'], scale=1)}", 'registered (PREREG_v1 §3.3: ≥ 3×, CI_lo > 1) + plan rule', 'discovery (main-track contexts, July template)',
    'July template does NOT fix the loop')
# ---------------------------------------------------------------- dose tier
P1c = PA['dose_tier']['P1']['cond']; P1u = PA['dose_tier']['P1']['uncond']
e = lambda x, s=1, d=2: f"{s * x['est']:.{d}f} {ci(*x['CI'], scale=s, d=d)}"
add('Dose and mechanism (PREREG_v1; 305 contexts with k_usable ≥ 4 / 137 attempts)', 'P1(k) at k = 1/2/4',
    'P(malformed | edit); unconditional beside', 305,
    f"cond {pc(P1c['P(P1,k=1)']['est'])} / {pc(P1c['P(P1,k=2)']['est'])} / {pc(P1c['P(P1,k=4)']['est'])}; uncond {pc(P1u['P(P1,k=1)']['est'])} / {pc(P1u['P(P1,k=2)']['est'])} / {pc(P1u['P(P1,k=4)']['est'])}",
    'registered (PREREG_v1 §3.1, §3.4)', DISC)
add('', 'rule D-M (primary, conditional)', 'Δ₂, Δ₄, Δ₄ − 2Δ₂ (logit vs k = 1)', 305,
    f"Δ₂ {e(P1c['Delta_2'])}; Δ₄ {e(P1c['Delta_4'])}; Δ₄ − 2Δ₂ {e(P1c['Delta_4_minus_2Delta_2'])}", 'registered (rule D-M, §4.2)', DISC,
    'not discriminated M1/M2; shapes contradict M1–M3, so the free curve is fitted')
fc = P1c['free_curve_logit_linear_in_k']
add('', 'free curve', 'first-exemplar step; slope per extra exemplar (logit)', 305,
    f"step {fc['first_exemplar_step D1']:.2f}; slope {e(fc['slope_per_extra_exemplar (Delta4/3)'])}", 'registered (D-M fallback)', DISC)
add('', 'P1 dose, unconditional', 'Δ₂; Δ₄', 305, f"Δ₂ {e(P1u['Delta_2'])}; Δ₄ {e(P1u['Delta_4'])}", 'registered (secondary estimand)', DISC)
P4r = PA['dose_tier']['P4_removal_fraction']
add('', 'P4(k) quarantine', 'removal at k = 1/2/4 (uncond)', 305,
    f"{100 * P4r['k=1:uncond']:.0f}% / {100 * P4r['k=2:uncond']:.0f}% / {100 * P4r['k=4:uncond']:.0f}%; P4(k) ≤ p0 at all k", 'registered (≥ 90% at all k)', DISC, 'holds')
oi = PA['dose_tier']['P4_order_imitation_old_first_share']
add('', 'order imitation under P4(k)', 'share of next edits old-first, k = 1/2/4', '267/272/279 edits',
    f"{pc(oi['k=1'][0])} / {pc(oi['k=2'][0])} / {pc(oi['k=4'][0])}", 'registered (M1 flat; M2 0.73/0.85; M3 → 1)', DISC, 'rises toward 1')
ec = PA['dose_tier']['edit_classes_P1']
add('', 'new-content edits under P1(k)', 'P(malformed | new-content edit), k = 1/2/4',
    f"{ec['k=1']['new_content']['n']}/{ec['k=2']['new_content']['n']}/{ec['k=4']['new_content']['n']} edits",
    ' / '.join(wil(ec[f'k={k}']['new_content']['malformed']) for k in (1, 2, 4)), 'registered (M1 flat; M2/M3 rise)', DISC, 'rises')
rdz = PA['r_dose']['cond']
add('', 'r-dose (same corrupted call shown r times)', 'Δ_r2; Δ_r4 (logit, cond)', rdz['n_contexts'],
    f"{rdz['Delta_r2'][0]:+.2f} {ci(*rdz['Delta_r2'][1], scale=1, d=2)}; {rdz['Delta_r4'][0]:+.2f} {ci(*rdz['Delta_r4'][1], scale=1, d=2)}",
    'registered (M1: 0; M2: +0.73/+1.46)', DISC, 'null: repetition of the same exemplar does not add')
lg = PA['lag2']['uncond']
add('', 'lag-2 (corruption one edit back)', '(P_lag2 − p0)/(p1 − p0)', lg['n_contexts'], f"{lg['lag2_excess_share'][0]:.2f} {ci(*lg['lag2_excess_share'][1], scale=1, d=2)}",
    'registered (M1 < 0.25; M2/M3 ≥ 0.5)', DISC, 'between the regions (CI spans 0.29–0.64)')
pk = PA['P6k']['cond']
add('', 'P6k (distinct valid-content exemplars)', 'P(malformed | edit), k = 1/2/4; Δ₂; Δ₄ − 2Δ₂', 305,
    f"{pc(pk['P(P6,k=1)']['est'])} / {pc(pk['P(P6,k=2)']['est'])} / {pc(pk['P(P6,k=4)']['est'])}; Δ₂ {e(pk['Delta_2'])}; Δ₄ − 2Δ₂ {e(pk['Delta_4_minus_2Delta_2'])}",
    'registered (§3.2 point predictions)', DISC, "k = 2 at M2's 0.45; k = 4 (0.84) between M2's 0.63 and M3's 0.99; logit ∝ log k (β ≈ 2.6)")
A2 = PA['A2']['h_by_arm (unconditional, h = 1 - q(arm)/q(L))']
add('A2: natural slips, quarantine replay (300 natural onset states; :8300)', 'history-borne share', 'h = 1 − q(arm)/q(L); q(L) = 77.7%', 300,
    f"P5 {A2['P5']['h'][0]:.2f} {ci(*A2['P5']['h'][1], scale=1, d=2)}; Q8b (E's renderer, sanitized) {A2['Q8b']['h'][0]:.2f} {ci(*A2['Q8b']['h'][1], scale=1, d=2)}",
    'registered (h ≈ 0.6, 80% PI 0.4–0.8) + plan rule (h ≥ 0.7 / ≤ 0.4)', DISC, 'P5 inside the PI; Q8b ≥ 0.7, so quarantine is the dominant lever')
AS = J('out/a2_retry_split.json')
add('', 'A2 retry split', 'P(malformed | next edit retries the slipped content): L / P5 / Q8b', '262/159/259 retries',
    f"{wil(AS['L']['malformed_among_retries'])} / {wil(AS['P5']['malformed_among_retries'])} / {wil(AS['Q8b']['malformed_among_retries'])}",
    'exploratory', DISC, 'quarantine removes copy-on-retry; P5 leaves half the retries malformed')
if os.path.exists(os.path.join(D, 'out/a2_map_h.json')):
    M = J('out/a2_map_h.json')
    for scope, lab in (('ITT_all_300', 'ITT, 300 (abstained as Q8b)'), ('repaired_282', 'repaired 282')):
        x = M[scope]
        add('', f"A2-MAP with B's repairs ({lab}; :8303, L re-run on the same server)", 'h; q(L)', x['Q4M']['n'],
            f"P4'-MAP {x['Q4M']['h'][0]:.2f} {ci(*x['Q4M']['h'][1], scale=1, d=2)}; P8a-MAP {x['Q8M']['h'][0]:.2f} {ci(*x['Q8M']['h'][1], scale=1, d=2)}; q(L) {pc(x['Q4M']['q(L)'])}",
            'plan rule (P0-A2 with MAP repair)', DISC,
            ('h ≥ 0.7 in both arms: quarantine is the dominant lever' if min(x['Q4M']['h'][0], x['Q8M']['h'][0]) >= 0.7 else 'see h')
            + ('' if scope == 'ITT_all_300' else f"; P8a-MAP is the clean test (P4'-MAP: {M['retry_split_on_repaired']['Q4M']['no_edit']}/282 next calls are not edits after the synthesized success)"))
# ---------------------------------------------------------------- small models
for grp, name in (('12b_old', '12B'), ('e4b_old', 'E4B')):
    g = R['injection'][grp]['gate_k1_random_sample']
    p1 = g['paired_vs_P0']['P1k1']['uncond']; p6 = g['paired_vs_P0']['P6k1']['uncond']
    extra = ''
    if 'P8ak1' in g['arms']: extra = f"; P8a {pc(g['arms']['P8ak1']['P_malformed_edit_uncond'][0])} (n {g['arms']['P8ak1']['n']})"
    add('Small models (same discovery contexts, k = 1)' if name == '12B' else '', f'{name}: P1 and P6',
        'RD(P1 − P0); RD(P6 − P0)', p1['n_contexts'],
        f"P0 {pc(g['arms']['P0k0']['P_malformed_edit_uncond'][0])}; P1 {pp(p1['diff'])} {ci(*p1['diff_CI'])}; P6 {pp(p6['diff'])} {ci(*p6['diff_CI'])}{extra}",
        'exploratory (plan power-up)', DISC)
RB = J('out/rep_12b_rdose_lag2.json')
add('', '12B: r-dose and lag-2', 'Δ_r2 (cond); lag-2 excess share', 300,
    f"{RB['r_dose_cond']['Delta_r2'][0]:+.2f} {ci(*RB['r_dose_cond']['Delta_r2'][1], scale=1, d=2)}; lag-2 {RB['lag2_cond']['excess_share'][0]:.2f} {ci(*RB['lag2_cond']['excess_share'][1], scale=1, d=2)}",
    'exploratory', DISC, 'null / underpowered')
g = R['injection']['12b_new']['gate_k1_random_sample']['paired_vs_P0']['P1k1']['uncond']
add('', '12B under the July template', 'RD(P1 − P0)', g['n_contexts'], f"{pp(g['diff'])} {ci(*g['diff_CI'])}", 'exploratory', 'discovery (July template)')
# ---------------------------------------------------------------- reliability
TR = J('out/test_retest.json')
add('Reliability', 'test–retest, 100 gate contexts', 'malformed agreement; κ (P1)', 100,
    f"same seed {pc(TR['same_seed']['P1k1']['malformed_agreement'][0])}, κ {TR['same_seed']['P1k1']['kappa_malformed']:.2f}; new seed {wil(TR['new_seed']['P1k1']['malformed_agreement'])}, κ {TR['new_seed']['P1k1']['kappa_malformed']:.2f}",
    'exploratory', DISC, 'the slip is a stable property of the context')
# ---------------------------------------------------------------- thinking batteries (PREREG_v2.1 / v2.2) + template finding
TC = J('out/template_thinking_off_check.json') if os.path.exists(os.path.join(D, 'out/template_thinking_off_check.json')) else None
if TC:
    add('Thinking: the flag, a suppressed thought, a stripped history (300 gate contexts)', 'template gap: thinking-off is not honoured after a tool response',
        'share of flag-off prompts after a tool response that end with no closed thought (June / July)', '300 contexts x 2 templates',
        f"{TC['endings']['june:OFF'].get('<tool_response|> (nothing appended)', 0)}/300 / {TC['endings']['july:OFF'].get('<tool_response|> (nothing appended)', 0)}/300; a fresh model turn gets the closed thought (ids 100 45518 107 101)",
        'exploratory (template finding)', 'discovery contexts (render); behaviour: B 583/587 June-OFF still think', 'switch not honoured in multi-turn tool use (out/template_thinking_off_gap.md)')
for fn, tag, src, mkey in (('out/v21_analysis.json', 'PREREG_v2.1 (flag off)', 'discovery (gate contexts, June template, enable_thinking=false)', 'manipulation_check_M_v2.1'),
                           ('out/v22S_analysis.json', 'PREREG_v2.2 S (thought suppressed)', 'discovery (gate contexts, June template, flag off + closed thought)', 'manipulation_check_M_S'),
                           ('out/v22H_analysis.json', 'PREREG_v2.2 H (reasoning stripped)', 'discovery (gate contexts, June template, no prior reasoning)', 'manipulation_check_H')):
    if not os.path.exists(os.path.join(D, fn)): continue
    A = J(fn); lab = A.get('condition_labels', {}); n = A['complete_case_contexts']
    for name, r in A['claims_complete_case'].items():
        if not isinstance(r, dict) or 'verdict' not in r: continue
        if 'removal_uncond' in r:
            e = r['removal_uncond']; est = f"{100 * e['removal']:.0f}% {ci(*e['CI'], d=0)}" if e.get('removal') is not None and e.get('CI') else 'undefined'
            estd = 'removal of the P1 excess'
        else:
            est = f"{pp(r['uncond']['RD'])} {ci(*r['uncond']['RD_CI'])} ({pc(r['uncond']['arm'])} vs {pc(r['uncond']['base'])})"; estd = r['contrast'] + ', unconditional'
        add('', f"{tag}: {name}", estd, n, est + f"; Holm p {r.get('holm_p')}", f"registered ({A['prereg'].split(' sha256')[0]}; 80% PI {r.get('prediction_80PI')})", src,
            r['verdict'] + (f" ({lab.get(name)})" if lab.get(name) else ''))
    M = A.get(mkey) or {}
    if M.get('pooled'):
        add('', f"{tag}: manipulation check", 'thought opened (pooled over arms); median thought chars vs ON', len(A['levels']) * n if False else n,
            f"{wil(M['pooled']['opened'])}; median {M['pooled'].get('median_chars')} vs ON {M['pooled'].get('ON_median_chars')}", 'registered check', src, '')
# ---------------------------------------------------------------- confirmatory (PREREG_v2, P's public corpus)
CONF = 'confirmatory public (P corpus, PREREG_v2)'
CF = f'{D}/out/confirmatory/confirm_v2_all_full.json'
if os.path.exists(CF):
    CA = J('out/confirmatory/confirm_v2_all_full.json'); E4 = J('out/confirmatory/confirm_v2_31b_e4b_full.json')['E4B']
    b31 = CA['31B']; f = b31['full']; hp = b31['holm_F1c_adjusted_p']
    sec = 'Confirmatory replication (PREREG_v2; P\'s public SWE-bench corpus, S1; analysed once)'
    rdr = lambda x: f"{pp(x['RD'])} {ci(*x['RD_CI'])} ({pc(x['arm'])} vs {pc(x['base'])})"
    rmr = lambda x: f"{100 * x['removal']:.0f}% {ci(*x['CI'], d=0)}" if x.get('removal') is not None and x.get('CI') and x['CI'][0] is not None else 'undefined'
    holm = lambda c: f"; Holm F1c p < 1/2000" if hp.get(c) == 0 else (f"; Holm p {hp.get(c)}" if c in hp else '')
    add(sec, 'C1 31B: laundered exemplar raises slips', 'RD(P1 − P0), unconditional', '300 states / 231 episodes', rdr(f['C1']['uncond']) + holm('C1'),
        'registered (PREREG_v2 §3.1; 80% PI +27 pp [+11, +45])', CONF, f['C1']['verdict'])
    add('', 'C2 31B: induction without retry', 'RD(P6 − P0)', 300, rdr(f['C2']['uncond']) + holm('C2'), 'registered (80% PI +15 [+5, +30])', CONF,
        f['C2']['verdict'] + ('; plan induction threshold met' if f['C2'].get('plan_induction_threshold(>=+5pp, CI_lo>0)') else ''))
    c3 = b31['C3']['uncond']
    add('', 'C3 31B: P6k accumulation (pool A2)', 'P6 at k = 1/2/4; Δ₂; Δ₄ (logit)', c3['n_contexts'],
        f"{' / '.join(pc(v) for v in c3['rates'].values())}; Δ₂ {c3['Delta_2'][0]:+.2f} {ci(*c3['Delta_2'][1], scale=1, d=2)}; Δ₄ {c3['Delta_4'][0]:+.2f} {ci(*c3['Delta_4'][1], scale=1, d=2)}",
        'registered (Δ₂ +1.6, Δ₄ +3.2)', CONF, b31['C3_verdict'])
    for c, lab in (('C4', 'P5 removal'), ('C5', 'P8a removal (shipped renderer 5ca5c62c)'), ('C6', 'P8b removal')):
        add('', f'{c} 31B: {lab}', 'removal of the P1 excess', 300, rmr(f[c]['uncond']) + holm(c), 'registered (removal rule)', CONF, f[c]['verdict'])
    add('', 'C7 31B: informative error keeps the effect', 'retention RD(P9 − P0)/RD(P1 − P0)', 300,
        f"{f['C7']['retention_point']:.2f} {ci(*f['C7']['retention_CI_from_removal'], scale=1, d=2)}", 'registered (0.85 [0.55, 1.10])', CONF, f['C7']['verdict'])
    x12 = CA['12B']
    add('', 'C8 12B: RD(P1 − P0)', 'RD unconditional', 300, rdr(x12['C8']['uncond']), 'registered (+4 pp [+1, +9])', CONF, x12['C8']['verdict'])
    add('', 'C9 E4B: RD(P1 − P0)', 'RD unconditional', 300, rdr(E4['C9']['uncond']), 'registered (+3 pp [0, +8])', CONF, E4['C9']['verdict'])
    add('', 'C10 small models: induction ≥ copy', 'RD(P6 − P1); RD(P6 − P0)', 300,
        f"12B {pp(x12['C10']['RD_P6_P1']['RD'])}, {pp(x12['C10']['RD_P6_P0']['RD'])}; E4B {pp(E4['C10']['RD_P6_P1']['RD'])}, {pp(E4['C10']['RD_P6_P0']['RD'])}",
        'registered (descriptive rule)', CONF, f"12B {x12['C10']['verdict']}; E4B {E4['C10']['verdict']}")
    add('', 'C11 small models: P5 / P8a removal', 'removal', 300,
        f"E4B P5 {rmr(E4['C11']['P5'])}, P8a {rmr(E4['C11']['P8a'])}; 12B no excess to remove", 'registered (removal rule)', CONF,
        f"E4B P5 {E4['C11']['P5']['verdict']}, P8a {E4['C11']['P8a']['verdict']}; 12B FAILS (no excess; not evaluable)")
    add('', '§3.4 global statement', 'C1, C2, C5', '—', str(CA['global']['claims']), 'registered (§3.4)', CONF, 'the laundering loop ' + CA['global']['laundering_loop'])
    VSx = J('out/confirmatory/confirm_v2_all_verified_sens.json')['31B']['full']
    add('', 'Verified-only sensitivity (31B, 99 states)', 'C1; C2; C5', 99,
        f"C1 {pp(VSx['C1']['uncond']['RD'])}; C2 {pp(VSx['C2']['uncond']['RD'])}; C5 {rmr(VSx['C5']['uncond'])}", 'registered sensitivity (PI 15:27 entry)', CONF,
        f"{VSx['C1']['verdict']} / {VSx['C2']['verdict']} / {VSx['C5']['verdict']}")
NDf = f'{D}/out/confirmatory/natural_descriptives_v2.json'
if os.path.exists(NDf):
    ND = J('out/confirmatory/natural_descriptives_v2.json'); v = ND['verdicts_primary_full_corpus']
    lab = {'D1': 'first-edit onset', 'D2': 'later edit, K = 0', 'D3': 'K >= 1 contagion', 'D4': 'immediate retry', 'D5': 'D3/D2', 'D6a': 'closer share of malformed edits',
           'D6b': 'backtick share of closers', 'D7': 'old_string lost', 'D8': 'malformed calls / episode', 'D9': 'stuck episodes', 'D10': 'S2 onset', 'D11': 'laundered re-entry'}
    for k, x in v.items():
        e = (f"{x['est']:.2f} {ci(*x['ci95'], scale=1, d=2)}" if k in ('D5', 'D8') else f"{pc(x['est'])} {ci(*x['ci95'])}") if x['ci95'] else 'NA'
        add('Natural descriptives of P\'s corpus (PREREG_v2 §4; 1,080 S1 episodes)' if k == 'D1' else '', f'{k} {lab.get(k, "")}', 'episode-cluster bootstrap 95% CI', 'all S1 episodes',
            e, f'registered (80% PI {x["pi80"]})', CONF, x['verdict'])
OT = f'{D}/out/onset_v23_analysis.json'
if os.path.exists(OT):
    O = J('out/onset_v23_analysis.json'); pr = O['primary_closer_slip']; dr = O['secondary']['string_mode_drift_share_among_edits']
    add('Onset transplant (PREREG_v2.3; 600 P first-edit states)', 'O1 = ADK + LiteLLM tool-result serialization vs O0 native', 'first-edit closer slip, unconditional (RD; G = share of the 17% vs 1% gap)', 600,
        f"{pc(pr['O0'][0])} → {pc(pr['O1'][0])}; RD {pp(pr['RD'])} {ci(*pr['RD_CI'])}; McNemar {pr['mcnemar_discordant_O1only_O0only'][0]}:{pr['mcnemar_discordant_O1only_O0only'][1]}, p {pr['mcnemar_exact_one_sided_p']:.3f}; G {pr['gap_fraction_G']:.2f}",
        'registered (PREREG_v2.3 §4)', 'confirmatory public (P corpus, intervention)', pr['verdict'])
    add('', 'string-mode drift under O1', 'edits with literal \\n / \\" absent from native tool results', '342 edits per arm',
        f"{pc(dr['O0'][0])} → {pc(dr['O1'][0])}; diff {pp(dr['O1_minus_O0'][0])} {ci(*dr['O1_minus_O0'][1:])}", 'registered secondary (5% [1, 15])', 'confirmatory public (P corpus, intervention)',
        'mechanism corroborated (drift)')

BF = f'{D}/out/confirmatory/bf16_core_all.json'
if os.path.exists(BF):
    B = J('out/confirmatory/bf16_core_all.json'); u = B['uncond']; dq = u['bf16_minus_QAT_same_states']
    add('Precision reference (EXPLORATORY; 31B bf16 vs QAT-ct, same 300 S1_A1 states)', 'bf16: P0 / P1 / P6 / P8a', 'unconditional malformed-edit rate', '300 states / 231 episodes',
        f"{pc(u['P0'][0])} / {pc(u['P1'][0])} {ci(*u['P1'][1:])} / {pc(u['P6'][0])} / {pc(u['P8a'][0])}; RD(P1 − P0) {pp(u['RD_P1_P0'][0])} {ci(*u['RD_P1_P0'][1:])}; P8a removal {100 * u['P8a_removal'][0]:.0f}%",
        'exploratory (PI request; pre-declared)', 'confirmatory public (P corpus)', 'contagion present at bf16; quarantine removes it')
    add('', 'bf16 − QAT, same states', 'paired difference, unconditional', 300,
        f"P0 {pp(dq['P0'][0])} {ci(*dq['P0'][1:])}; P1 {pp(dq['P1'][0])} {ci(*dq['P1'][1:])}; P6 {pp(dq['P6'][0])} {ci(*dq['P6'][1:])}",
        'exploratory', 'confirmatory public (P corpus)', 'QAT about doubles the injected-exemplar effect')

V26 = f'{D}/out/confirmatory/v26_audit_analysis.json'
if os.path.exists(V26):
    A6 = J('out/confirmatory/v26_audit_analysis.json'); rt = A6['rates']
    sec6 = 'Audit behaviour (PREREG_v2.6; 4-bit checkpoints on the 300 S1_A1 states)'
    for h, lab in (('H1', 'AWQ (audit pick, 0.02 nats) vs QAT-ct (5.13)'), ('H2', 'AutoRound (0.63) vs QAT-ct'), ('H3', 'quarantine on AWQ: P8a vs P1')):
        x = A6[h]
        add(sec6 if h == 'H1' else '', f'{h}: {lab}', 'RD unconditional; exact one-sided McNemar; Holm', 300,
            f"{pc(x['A'])} vs {pc(x['B'])}; RD {pp(x['RD'])} {ci(*x['RD_CI'])}; discordant {x['discordant_B_only_A_only'][0]}:{x['discordant_B_only_A_only'][1]}; Holm p {x['holm_p']}"
            + (f"; removal {100 * x['removal']['point']:.0f}% {ci(*x['removal']['CI'], d=0)}" if h == 'H3' else ''),
            'registered (PREREG_v2.6)', 'confirmatory public (P corpus)', x['verdict'])
    nh = A6['no_harm_P0_vs_QAT']; do = A6['descriptive_ordering']
    add('', 'no-harm: P0 vs QAT-ct', 'P0 difference', 300, f"AWQ {pp(nh['AWQ']['RD'])} {ci(*nh['AWQ']['RD_CI'])}; AutoRound {pp(nh['AR']['RD'])} {ci(*nh['AR']['RD_CI'])}",
        'registered (non-inferiority, +2 pp)', 'confirmatory public (P corpus)', f"AWQ {nh['AWQ']['verdict']}; AutoRound {nh['AR']['verdict']}")
    add('', '4-point ordering (descriptive)', 'P1 vs audit deficit (bf16, AWQ, AutoRound, QAT)', 4,
        ' / '.join(pc(do['P1_by_condition'][c]) for c in ('BF16', 'AWQ', 'AR', 'QAT')) + f"; Spearman {do['spearman_rho']:.2f}, exact p {do['exact_one_sided_p']:.3f}",
        'registered descriptive', 'confirmatory public (P corpus)', 'Ordered' if do['ordered'] else 'not ordered')

L = ['# Workstream A: framing summary (all results in one table)', '',
     f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} by `scripts/framing_summary.py` from `results.json` and `out/*.json`. "
     'Unconditional (ITT) estimand = P(next call is a malformed edit) per context; conditional = P(malformed | next call is an edit). '
     'Risk differences use paired attempt-cluster bootstraps (B = 2000); removal = (P1 − Q)/(P1 − P0), where > 100% means the arm '
     'goes below P0. Prereg status: **registered** = a numeric prediction or rule in PREREG_v1 (sha256 53e34f1f…, 11:47 UTC) or '
     'PREREG_v2 (5da75e61…, 14:46 UTC); **plan rule** = UPGRADE_PLAN decision rules (verbatim in PREREG_v1 §4) or the assignment gate; '
     '**exploratory** = everything else.', '',
     'CIs of the same contrast computed by different scripts (independent bootstrap draws) can differ by up to about 0.5 pp. ', '',
     '**Status of the evidence.** Rows whose data source is "discovery" come from the main-track logs and contexts. Rows marked '
     '"confirmatory public" come from workstream P\'s public SWE-bench corpus, analysed once under PREREG_v2 / v2.3 with frozen scripts.', '',
     '| section | result | estimand | n | estimate [95% CI] | prereg status | data source | rule outcome |', '|---|---|---|---|---|---|---|---|']
for r in rows:
    L.append('| ' + ' | '.join(str(x).replace('|', '\\|') for x in r) + ' |')
open(os.path.join(D, 'out/FRAMING_SUMMARY.md'), 'w').write('\n'.join(L) + '\n')
print(len(rows), 'rows')
