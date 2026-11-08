"""Markdown results for README (generated; never retyped). Reads results.json, out/decision_rules.json,
out/prereg_analysis.json, out/test_retest.json, out/copy_check.json. Primary = unconditional (ITT) P(next call is a
malformed edit_file); conditional P(malformed | edit) beside it. Risk differences first, ratios second.
usage: report_tables_v2.py > out/tables.md"""
import json, os
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
L = lambda p: json.load(open(p)) if os.path.exists(p) else None
R, DR, PA, TR, CC = L(f'{D}/results.json'), L(f'{D}/out/decision_rules.json'), L(f'{D}/out/prereg_analysis.json'), L(f'{D}/out/test_retest.json'), L(f'{D}/out/copy_check.json')


def w(x):
    if not x or x[0] is None: return 'NA'
    s = f'{100 * x[0]:.1f}% [{100 * x[1]:.1f}, {100 * x[2]:.1f}]'
    return s + (f' (n={x[3]})' if len(x) > 3 else '')


def pp(v, ci): return f'{100 * v:+.1f} pp [{100 * ci[0]:+.1f}, {100 * ci[1]:+.1f}]'


NAME = {'P0k0': 'P0 original history', 'P1k1': 'P1 corrupted re-render + ADK error', 'P7k1': 'P7 = P1 with a double-quote closer',
        'P3k1': 'P3 raw slip text + harness nudge', 'P6k1': 'P6 corrupted re-render + success (no retry motive)', 'P2k1': 'P2 error message only',
        'P9k1': 'P9 = P1 + informative error', 'P4k1': 'P4 canonical old-first re-render + true result', 'P4Pk1': "P4' own-order canonical re-render (= P0 in 297/300)",
        'P8ak1': 'P8a shipped quarantine, recovered (E renderer)', 'P8bk1': 'P8b shipped quarantine, sanitized (E renderer)', 'P5k1': 'P5 removed + note',
        'L2k1': 'lag-2: second most recent edit corrupted'}
print('## Decision rules (UPGRADE_PLAN §P0-A1, verbatim; PREREG_v1)\n')
if DR:
    for k in ('format_induction', 'copying', 'shipped_quarantine', 'july_template'):
        print(f"- **{k}**: {DR[k]['decision']} — rule: {DR[k].get('rule', '')}")
    fi = DR['format_induction']['gate']['uncond']
    if fi: print(f"  - induction, gate half: RD(P6−P0) = {pp(fi['RD'], fi['RD_CI'])} ({fi['n_contexts']} contexts); new-content only: "
                 f"{pp(DR['format_induction']['gate']['newcontent_uncond']['RD'], DR['format_induction']['gate']['newcontent_uncond']['RD_CI'])}")
    if isinstance(DR['format_induction'].get('heldout'), dict) and DR['format_induction']['heldout'].get('uncond'):
        h = DR['format_induction']['heldout']['uncond']; print(f"  - induction, held-out half: RD(P6−P0) = {pp(h['RD'], h['RD_CI'])} ({h['n_contexts']} contexts)")
    c = DR['copying']; print(f"  - copying: verbatim share of P1 malformed {w(c['P1_share_of_malformed_that_are_verbatim_copies'])}; '\"' closer share among malformed: P7 {w(c['P7_quote_closer_share_of_malformed'])} vs P0 {w(c['P0_quote_closer_share_of_malformed'])}")
    nt = DR['july_template']['uncond']
    if nt: print(f"  - July template (150 gate contexts): RD(P1−P0) = {pp(nt['RD'], nt['RD_CI'])}, ratio {nt['ratio']} [{nt['ratio_CI'][0]}, {nt['ratio_CI'][1]}]; "
                 f"P4 removes {DR['july_template']['removal_P4']['fraction_removed']} [{', '.join(map(str, DR['july_template']['removal_P4']['CI']))}], P5 removes {DR['july_template']['removal_P5']['fraction_removed']} [{', '.join(map(str, DR['july_template']['removal_P5']['CI']))}]")
    sq = DR['shipped_quarantine']
    for q in ('P8a', 'P8b', 'P4P', 'P4', 'P5'):
        if isinstance(sq.get(q), dict): print(f"  - removal of the P1 excess by {q} (unconditional): {sq[q]['fraction_removed']} [{sq[q]['CI'][0]}, {sq[q]['CI'][1]}] ({sq[q]['n_contexts']} contexts)")
    print()
    print('## k = 1 pathways, 31B gate set (300 random contexts / 256 attempts; paired attempt-cluster bootstrap)\n')
    print('| arm | RD vs P0 (unconditional) | ratio (unconditional) | P(malformed edit) uncond | P(malformed \\| edit) |')
    print('|---|---|---|---|---|')
    ga = DR['gate_arms_vs_P0']
    p0row = None
    for arm in ('P1k1', 'P7k1', 'P3k1', 'P6k1', 'P2k1', 'P9k1', 'P4k1', 'P4Pk1', 'P8ak1', 'P8bk1', 'P5k1', 'L2k1'):
        x = ga.get(arm)
        if not x or not x.get('uncond'): continue
        u, cnd = x['uncond'], x['cond']; p0row = p0row or (u['base'], cnd['base'])
        print(f"| {NAME.get(arm, arm)} | {pp(u['RD'], u['RD_CI'])} | {u['ratio']} [{u['ratio_CI'][0]}, {u['ratio_CI'][1]}] | {100 * u['arm']:.1f}% | {100 * cnd['arm']:.1f}% |")
    if p0row: print(f"| P0 original history (reference) | — | — | {100 * p0row[0]:.1f}% | {100 * p0row[1]:.1f}% |")
    print()
if PA:
    print('## Pre-registered analyses (PREREG_v1; computed only on complete arm-sets)\n')
    dt = PA.get('dose_tier')
    if isinstance(dt, dict):
        for kind in ('cond', 'uncond'):
            b = dt['P1'][kind]
            print(f"- dose tier ({kind}), {b['n_contexts']} contexts: P1(k=1) {b['P(P1,k=1)']['est']:.3f}, P1(k=2) {b['P(P1,k=2)']['est']:.3f}, P1(k=4) {b['P(P1,k=4)']['est']:.3f}, p0 {b['p0']['est']:.3f}; "
                  f"Δ2 = {b['Delta_2']['est']} {b['Delta_2']['CI']}, Δ4 = {b['Delta_4']['est']} {b['Delta_4']['CI']}, Δ4−2Δ2 = {b['Delta_4_minus_2Delta_2']['est']} {b['Delta_4_minus_2Delta_2']['CI']}")
        print(f"- **rule D-M (primary, conditional): {dt['rule_D-M_primary(cond)']['verdict']}** (regions {dt['rule_D-M_primary(cond)']['regions']}); unconditional: {dt['rule_D-M_uncond']['verdict']}")
        print(f"- P4(k) removal fraction: {dt['P4_removal_fraction']}; old-first share of next edits under P4(k): " + '; '.join(f"{k} {w(v)}" for k, v in dt['P4_order_imitation_old_first_share'].items()))
        print('- edit classes under P1(k): ' + '; '.join(f"{k}: " + ', '.join(f"{c} n={v['n']} mal {w(v['malformed'])}" for c, v in cls.items()) for k, cls in dt['edit_classes_P1'].items()))
    else: print(f'- dose tier: {dt}')
    for key in ('r_dose', 'lag2', 'P6k', 'A2'):
        v = PA.get(key)
        print(f"- {key}: {json.dumps(v) if not isinstance(v, str) else v}"[:1200])
    print(f"- P7 injected-quote share: {json.dumps(PA.get('P7_injected_quote_share'))}")
    print()
AM = L(f'{D}/out/a2_map_h.json')
if AM:
    print("## A2 with B's MAP repairs (:8303; L re-run on the same server; unconditional h = 1 − q(arm)/q(L))\n")
    print('| arm | ITT, all 300 (abstained → Q8b) | repaired 282 |')
    print('|---|---|---|')
    for arm, lab in (('Q8M', "P8a-MAP (E's renderer recovering B's call + MalformedToolCall)"), ('Q4M', "P4′-MAP (repaired call, new-first, + success)")):
        cells = [f"h {AM[sc][arm]['h'][0]:.3f} [{AM[sc][arm]['h'][1][0]:.3f}, {AM[sc][arm]['h'][1][1]:.3f}]; q(arm) {AM[sc][arm]['q(arm)']:.3f}, q(L) {AM[sc][arm]['q(L)']:.3f}" for sc in ('ITT_all_300', 'repaired_282')]
        print(f'| {lab} | ' + ' | '.join(cells) + ' |')
    sc = AM['server_check_L']
    print(f"\n- server check: L on :8300 {w(sc['L_on_8300'])} vs :8303 {w(sc['L_on_8303'])}; Q8b on the 18 abstained: {w(sc['Q8b_on_8300_abstained18'])} / {w(sc['Q8b_on_8303_abstained18'])}")
    print('- retry split (repaired 282): ' + '; '.join(f"{arm}: malformed among retries {w(v['malformed_among_retries'])}, among new {w(v['malformed_among_new'])}, no edit {v['no_edit']}" for arm, v in AM['retry_split_on_repaired'].items()))
    print(f"- rule: {AM['rule']}\n")
if TR:
    print('## Test–retest (100 gate contexts × {P0, P1})\n')
    for tag in ('same_seed', 'new_seed'):
        for arm, v in TR.get(tag, {}).items():
            print(f"- {tag} {arm}: malformed agreement {w(v['malformed_agreement'])}, κ = {v['kappa_malformed']}, next-tool agreement {w(v['next_tool_agreement'])}, "
                  f"byte-identical {w(v['byte_identical_generation'])}; rate original {w(v['rate_original'])} vs retest {w(v['rate_retest'])}")
    print()
if R:
    print('## Replications at k = 1 (12B, E4B; histories are 31B trajectories, i.e. off-policy) and the observational layer\n')
    for g in ('12b_old', 'e4b_old'):
        gk = (R['injection'].get(g) or {}).get('gate_k1_random_sample')
        if not gk: continue
        print(f"- {g} ({gk['n_contexts']} contexts): " + '; '.join(f"{a} uncond {w(v['P_malformed_edit_uncond'])}" for a, v in gk['arms'].items()))
    o = R['observational']; b = o['BASE_plain_31b_qat']
    print(f"- observational (plain base 31B, {b['edits']} edits / {b['attempts']} attempts): malformed {w(b['malformed_rate'])}; first edit {w(b['first_edit'])}; "
          f"later clean history {w(b['later_clean_history'])}; after 1/2/3/≥4 prior malformed " + ' / '.join(w(b['later_by_prior_bad'][k]) for k in ('1', '2', '3', '4')))
