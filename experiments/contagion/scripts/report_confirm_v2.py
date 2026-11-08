"""Markdown tables for the PREREG_v2 confirmatory analysis (generated from confirm_v2_analysis.py outputs; never retyped).
usage: report_confirm_v2.py <full.json> [<verified_sensitivity.json>|-] [<natural_descriptives.json>|-] > out/confirmatory/tables.md"""
import json, sys, os


def L(p): return json.load(open(p)) if p and p != '-' and os.path.exists(p) else None


F, VS, ND = L(sys.argv[1]), L(sys.argv[2] if len(sys.argv) > 2 else None), L(sys.argv[3] if len(sys.argv) > 3 else None)
pp = lambda x: f'{100 * x:+.1f} pp'
pc = lambda x: f'{100 * x:.1f}%'
ci = lambda c, s=100, d=1: f'[{s * c[0]:.{d}f}, {s * c[1]:.{d}f}]' if c and c[0] is not None else '[NA]'
PRED = {'C1': 'RD +27 pp [+11, +45]', 'C2': '+15 pp [+5, +30]', 'C3': 'Δ₂ +1.6 [0.8, 2.4]; Δ₄ +3.2 [1.8, 4.5]', 'C4': '1.00 [0.80, 1.15]',
        'C5': '1.05 [0.85, 1.20]', 'C6': '1.00 [0.75, 1.20]', 'C7': 'retention 0.85 [0.55, 1.10]', 'C8': '+4 pp [+1, +9]', 'C9': '+3 pp [0, +8]',
        'C10': '12B +2; E4B +4 pp', 'C11': '≥ 0.70 [0.40, 1.30]'}


def row(c, x, hp=None):
    if c in ('C1', 'C2'):
        u = x['uncond']; e = f"{pp(u['RD'])} {ci(u['RD_CI'])} ({pc(u['arm'])} vs {pc(u['base'])}); cond {pp(x['cond']['RD'])}"
    elif c in ('C4', 'C5', 'C6'):
        u = x['uncond']; e = f"removal {100 * u['removal']:.0f}% {ci(u['CI'], d=0)}; cond {100 * x['cond']['removal']:.0f}%" if u.get('removal') is not None else 'undefined'
    elif c == 'C7':
        e = f"RD(P9 − P0) {pp(x['RD_P9_P0']['RD'])} {ci(x['RD_P9_P0']['RD_CI'])}; retention {x['retention_point']:.2f} {ci(x.get('retention_CI_from_removal'), s=1, d=2)}"
    else: e = ''
    return f"| {c} | {e} | {hp if hp is not None else '—'} | {PRED[c]} | **{x['verdict']}** |"


def block(R, title):
    o = [f'### {title}\n']
    if not R or isinstance(R.get('31B'), str):
        return o + [f"31B: {R.get('31B') if R else 'not run'}\n"]
    b = R['31B']; hp = b.get('holm_F1c_adjusted_p', {})
    o.append(f"Pools: {R['pools']}; 31B jobs present {b['jobs_present']}; episode-cluster bootstrap B = {R['B']}. Unconditional ITT primary.\n")
    o += ['| claim | estimate [95% CI] | Holm F1c p | D 80% PI | verdict |', '|---|---|---|---|---|']
    for c in ('C1', 'C2', 'C4', 'C5', 'C6', 'C7'): o.append(row(c, b['full'][c], hp.get(c)))
    c3 = b['C3']
    if 'uncond' in c3:
        u = c3['uncond']
        o.append(f"| C3 (pool A2, n {u['n_contexts']}) | P6 at k=1/2/4 {' / '.join(pc(v) for v in u['rates'].values())}; Δ₂ {u['Delta_2'][0]:+.2f} {ci(u['Delta_2'][1], s=1, d=2)}; Δ₄ {u['Delta_4'][0]:+.2f} {ci(u['Delta_4'][1], s=1, d=2)}; Δ₄−2Δ₂ {u['Delta4_minus_2Delta2'][0]:+.2f} {ci(u['Delta4_minus_2Delta2'][1], s=1, d=2)} | — | {PRED['C3']} | **{b['C3_verdict']}** |")
    else:
        u = c3.get('k124_on_A2_underpowered', {}).get('uncond', {})
        if u.get('Delta_4'):
            o.append(f"| C3 (shortfall branch; A2 n {u['n_contexts']}) | Δ₂ {u['Delta_2'][0]:+.2f} {ci(u['Delta_2'][1], s=1, d=2)}; Δ₄ {u['Delta_4'][0]:+.2f} {ci(u['Delta_4'][1], s=1, d=2)} | — | {PRED['C3']} | see note |")
    o += ['', '| claim | half H1 (ranks 1–150) | half H2 (151–300) |', '|---|---|---|']
    for c in ('C1', 'C2'):
        o.append(f"| {c} | {pp(b['H1'][c]['uncond']['RD'])} {ci(b['H1'][c]['uncond']['RD_CI'])} ({b['H1'][c]['verdict']}) | {pp(b['H2'][c]['uncond']['RD'])} {ci(b['H2'][c]['uncond']['RD_CI'])} ({b['H2'][c]['verdict']}) |")
    for c in ('C4', 'C5', 'C6'):
        f = lambda h: f"{100 * b[h][c]['uncond']['removal']:.0f}% {ci(b[h][c]['uncond']['CI'], d=0)} ({b[h][c]['verdict']})" if b[h][c]['uncond'].get('removal') is not None else 'NA'
        o.append(f"| {c} | {f('H1')} | {f('H2')} |")
    for tag in ('12B', 'E4B'):
        if tag in R:
            x = R[tag]
            if isinstance(x, str): o.append(f'\n{tag}: {x}'); continue
            cid = 'C8' if tag == '12B' else 'C9'
            o.append(f"\n{tag}: {cid} {pp(x[cid]['uncond']['RD'])} {ci(x[cid]['uncond']['RD_CI'])} → **{x[cid]['verdict']}**; C10 RD(P6 − P1) {pp(x['C10']['RD_P6_P1']['RD'])}, RD(P6 − P0) {pp(x['C10']['RD_P6_P0']['RD'])} → {x['C10']['verdict']}; "
                     + '; '.join(f"C11 {Q} removal {100 * v['removal']:.0f}% {ci(v['CI'], d=0)} → {v['verdict']}" if v.get('removal') is not None else f'C11 {Q} undefined' for Q, v in x['C11'].items()))
    if R.get('global'): o.append(f"\n**§3.4 global statement:** the laundering loop **{R['global']['laundering_loop']}** ({R['global']['claims']}).")
    o.append('')
    return o


out = ['## PREREG_v2 confirmatory replication on workstream P\'s public SWE-bench corpus (31B QAT-ct, S1)\n']
out += block(F, 'Full corpus (primary)')
if VS: out += block(VS, 'Verified-only sensitivity (C3 via the documented sensitivity pools; see prereg_deviations_A.json)')
if ND:
    v = ND['verdicts_primary_full_corpus']
    out += ['### Natural descriptives (PREREG_v2 §4, all S1 episodes)\n', '| # | estimate [95% CI] | D 80% PI | verdict |', '|---|---|---|---|']
    for k, x in v.items():
        e = f"{x['est']:.3f}" if k in ('D5', 'D8') else (pc(x['est']) if x['est'] is not None else 'NA')
        c = ci(x['ci95'], s=1, d=3) if k in ('D5', 'D8') else ci(x['ci95'])
        out.append(f"| {k} | {e} {c} | {x['pi80']} | {x['verdict']} |")
print('\n'.join(out))
