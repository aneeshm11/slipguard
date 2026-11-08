"""Markdown report for the PREREG_v2.1 (thinking-OFF flag) and PREREG_v2.2 (S: thought suppressed; H: reasoning-stripped
history) batteries, generated from the analysis JSONs (never retyped). Risk differences first; ON (discovery) and each
condition side by side on the same 300 gate contexts.
usage: report_v21_v22.py <v21.json|-> <S.json|-> <H.json|-> > out/v21_v22_tables.md"""
import json, sys, os


def L(p): return json.load(open(p)) if p != '-' and os.path.exists(p) else None


V21, S, H = (L(x) for x in sys.argv[1:4])
pp = lambda x: f'{100 * x:+.1f} pp' if x is not None else 'NA'
pc = lambda x: f'{100 * x:.1f}%' if x is not None else 'NA'


def ci(c, s=100, d=1): return f'[{s * c[0]:.{d}f}, {s * c[1]:.{d}f}]' if c else '[NA]'


def w(x): return f'{pc(x[0])} {ci(x[1:3])}' if x else 'NA'


def claim_rows(A, on_key='side_by_side_ON_vs_condition'):
    out = []; cc = A['claims_complete_case']; side = A.get(on_key, {}); lab = A.get('condition_labels', {})
    for name, r in cc.items():
        if not isinstance(r, dict) or 'verdict' not in r: continue
        on = (side.get(name) or {}).get('ON') or {}
        if 'removal_uncond' in r:
            rem = r['removal_uncond']
            est = f"removal {100 * rem['removal']:.0f}% {ci(rem['CI'], d=0)}" if rem.get('removal') is not None else 'removal undefined'
            est += f"; RD(P1 − {r['contrast'].split('by ')[1].split(';')[0]}) {pp(r['uncond']['RD'])} {ci(r['uncond']['RD_CI'])}"
            ons = f"{100 * on['removal']:.0f}% {ci(on.get('CI'), d=0)}" if on.get('removal') is not None else 'NA'
        else:
            est = f"{pp(r['uncond']['RD'])} {ci(r['uncond']['RD_CI'])} (arm {pc(r['uncond']['arm'])} vs P0 {pc(r['uncond']['base'])})"
            ons = f"{pp(on.get('RD'))} {ci(on.get('RD_CI'))}" if on else 'NA'
        v = r['verdict'] + (f" ({lab.get(name)})" if lab.get(name) else '')
        out.append(f"| {name} | {r['contrast']} | {ons} | {est} | {r.get('holm_p')} | {r.get('prediction_80PI')} | **{v}** |")
    return out


def section(A, title, mkey):
    if not A: return [f'### {title}\n', 'not run / not yet analysed\n']
    o = [f'### {title}\n', f"{A['prereg']}. Contexts: {A['complete_case_contexts']} complete-case (300 gate contexts); missing jobs per arm {A['missing_jobs']}; "
         f"server(s) {list(A['servers'])}; ON comparison runs on {list(A['on_servers'])}. Unconditional ITT primary; attempt-cluster bootstrap B = {A['B']}.\n",
         '| claim | contrast | ON (discovery, same contexts) | condition estimate [95% CI] | Holm p (one-sided) | D 80% PI | verdict |', '|---|---|---|---|---|---|---|']
    o += claim_rows(A); o.append('')
    lv = A['levels']; pon = A['paired_vs_thinking_ON']
    o += ['| arm | condition: P(malformed edit), uncond [95% CI] | conditional | P(edit) | D 80% PI (level) | condition − ON, uncond RD [95% CI] | condition − ON, P(edit) |', '|---|---|---|---|---|---|---|']
    for arm, x in lv.items():
        if not isinstance(x, dict) or 'uncond' not in x: continue
        pr = pon.get(arm, {})
        r = pr.get('RD_malformed_uncond') or {}
        pe = pr.get('P_edit_cond_minus_ON')
        o.append(f"| {arm} | {pc(x['uncond'][0])} {ci(x['uncond'][1:])} | {pc(x['cond'][0])} {ci(x['cond'][1:])} | {w(x['P_edit'])} | "
                 f"{ci(x['D_80PI']) if x.get('D_80PI') else '—'} | {pp(r.get('RD'))} {ci(r.get('RD_CI'))} (ON {pc(r.get('base'))}) | {pp(pe[0]) + ' ' + ci(pe[1:]) if pe else 'NA'} |")
    if pon.get('predictions'): o.append(f"\nRegistered secondary predictions: {pon['predictions']}.")
    if 'P5_P8a_vs_P0_plus_1pp' in lv: o.append(f"P5 / P8a minus P0 (prediction ≤ +1 pp): {', '.join(f'{k} {pp(v)}' for k, v in lv['P5_P8a_vs_P0_plus_1pp'].items())}.")
    M = A.get(mkey) or {}
    o += ['', '| manipulation check | ' + ' | '.join(k for k in M if isinstance(M[k], dict)) + ' |', '|---|' + '---|' * sum(1 for k in M if isinstance(M[k], dict))]
    o.append('| thought opened (condition) | ' + ' | '.join(w(M[k].get('opened')) for k in M if isinstance(M[k], dict)) + ' |')
    o.append('| median thought chars (condition) | ' + ' | '.join(str(M[k].get('median_chars', '—')) for k in M if isinstance(M[k], dict)) + ' |')
    o.append('| thought opened (ON, same contexts) | ' + ' | '.join(w(M[k].get('ON_opened')) if M[k].get('ON_opened') else '—' for k in M if isinstance(M[k], dict)) + ' |')
    o.append('| median thought chars (ON) | ' + ' | '.join(str(M[k].get('ON_median_chars', '—')) for k in M if isinstance(M[k], dict)) + ' |')
    if M.get('prediction'): o.append(f"\nPrediction: {M['prediction']}.")
    if A.get('claims_on_thought_subsets'):
        o += ['', 'Labelled verdicts on thought subsets (descriptive):', '| claim:subset | n | estimate | verdict |', '|---|---|---|---|']
        for k, r in A['claims_on_thought_subsets'].items():
            if r.get('removal_uncond'):
                e = r['removal_uncond']; est = f"removal {100 * e['removal']:.0f}% {ci(e['CI'], d=0)}" if e.get('removal') is not None else 'undefined'
            elif r.get('uncond'): est = f"{pp(r['uncond']['RD'])} {ci(r['uncond']['RD_CI'])}"
            else: est = r.get('note', 'NA')
            o.append(f"| {k} | {r.get('n_contexts')} | {est} | {r.get('verdict')} |")
    cp = A.get('copy_classes') or {}
    if cp:
        o += ['', '| copy classes (P1 / P6 edits) | condition | ON, same contexts |', '|---|---|---|']
        for pw in ('P1', 'P6'):
            if pw not in cp: continue
            c, on = cp[pw]['condition'], cp[pw]['ON_same_contexts']
            o.append(f"| {pw}: byte-exact copies among malformed edits | {w(c['byte_exact_copy_share_of_malformed'])} | {w(on['byte_exact_copy_share_of_malformed'])} |")
            o.append(f"| {pw}: clean rewrites of the same edit among edits | {w(c['clean_rewrite_share_of_edits'])} | {w(on['clean_rewrite_share_of_edits'])} |")
        o.append(f"\nPrediction: {cp.get('predictions')}.")
    o.append('')
    return o


out = ['## Thinking batteries on the 300 discovery gate contexts (PREREG_v2.1, PREREG_v2.2)\n']
out += section(V21, 'PREREG_v2.1: the shipped thinking-OFF flag (enable_thinking=false; the model still thinks, see the manipulation check)', 'manipulation_check_M_v2.1')
out += section(S, 'PREREG_v2.2 arm set S: thought suppressed (flag off + the template\'s closed empty thought prefilled)', 'manipulation_check_M_S')
out += section(H, 'PREREG_v2.2 arm set H: all prior reasoning stripped from the history (thinking on)', 'manipulation_check_H')
# side by side
rows = []
for nm, A in (('OFF (v2.1)', V21), ('S', S), ('H', H)):
    if not A: continue
    cc = A['claims_complete_case']; side = A['side_by_side_ON_vs_condition']
    p1 = next((r for r in cc.values() if isinstance(r, dict) and r.get('contrast') == 'RD(P1 - P0)'), None)
    p6 = next((r for r in cc.values() if isinstance(r, dict) and r.get('contrast') == 'RD(P6 - P0)'), None)
    p8 = next((r for r in cc.values() if isinstance(r, dict) and 'by P8a' in str(r.get('contrast'))), None)
    rows.append((nm, A['levels'].get('P0', {}).get('uncond'), p1, p6, p8))
if rows:
    on = (V21 or S or H)['side_by_side_ON_vs_condition']
    k1 = next(k for k in on if k != 'n_contexts')
    out += ['### Side by side (same contexts; unconditional)\n', '| condition | P0 | RD(P1 − P0) | RD(P6 − P0) | P8a removal |', '|---|---|---|---|---|']
    onp1 = on[k1]['ON']
    out.append(f"| ON (discovery) | {pc(onp1.get('base'))} | {pp(onp1.get('RD'))} {ci(onp1.get('RD_CI'))} | (see sections) | (see sections) |")
    for nm, p0, p1, p6, p8 in rows:
        f = lambda r: f"{pp(r['uncond']['RD'])} {ci(r['uncond']['RD_CI'])} — {r['verdict']}" if r else '—'
        g = lambda r: (f"{100 * r['removal_uncond']['removal']:.0f}% {ci(r['removal_uncond']['CI'], d=0)} — {r['verdict']}" if r and r['removal_uncond'].get('removal') is not None else ('—' if not r else r['verdict']))
        out.append(f"| {nm} | {pc(p0[0]) if p0 else 'NA'} | {f(p1)} | {f(p6)} | {g(p8)} |")
print('\n'.join(out))
