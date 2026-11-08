"""Generate the RESULTS block of README.md (between <!-- RESULTS:BEGIN --> and <!-- RESULTS:END -->) from the
analysis JSONs, so every number in the README comes from results files (single source of truth).
usage: report.py"""
import json
import os
import re

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = [('qwen3-8b', 'Qwen3-8B (hermes JSON)'), ('qwen3-32b', 'Qwen3-32B-FP8 (hermes JSON)'), ('qwen3.5-9b', 'Qwen3.5-9B (qwen3_coder XML)')]
ARMS = [('P0', 'P0 original history'), ('P1L', 'P1L laundered exemplar + ADK error'), ('P1N', 'P1N native slip through own parser'),
        ('P5', 'P5 removed + note'), ('P6', 'P6 laundered exemplar + success'), ('P8a', 'P8a shipped quarantine (E, recovered)')]


def load(p):
    p = os.path.join(X, p)
    return json.load(open(p)) if os.path.exists(p) else None


def w(x):
    """Wilson triple -> 'p% [lo, hi] (n)'"""
    if not x or x[0] is None:
        return 'n/a'
    return f'{100 * x[0]:.1f}% [{100 * x[1]:.1f}, {100 * x[2]:.1f}] (n={x[3]})'


def pp(v):
    return 'n/a' if v is None else ('inf' if v == 'inf' else f'{100 * float(v):+.1f}')


def ci_pp(c):
    return '[' + ', '.join(pp(v) for v in c) + ']' if c else ''


def rat(r, c):
    if r is None:
        return 'n/a'
    f = (lambda v: 'inf' if v == 'inf' else ('n/a' if v is None else f'{float(v):.2f}'))
    return f'{f(r)} [{f(c[0])}, {f(c[1])}]'


L = []
res = load('out/results_x.json') or {}
for mk, title in MODELS:
    an = load(f'out/ana_{mk}.json')
    if not an:
        L.append(f'### {title}\n\nnot run yet.\n'); continue
    L.append(f'### {title}: battery (A\'s 300 gate contexts) and census\n')
    L.append('| arm | P(edit) | P(malformed edit), unconditional (primary) | P(malformed \\| edit) | RD vs P0, uncond. [95% CI] | ratio vs P0 [95% CI] |')
    L.append('|---|---|---|---|---|---|')
    for arm, lab in ARMS:
        s = an['arms'].get(arm)
        if not s:
            continue
        pr = (an['paired_vs_P0'].get(arm) or {}).get('uncond') if arm != 'P0' else None
        L.append(f"| {lab} | {w(s['P_edit'])} | {w(s['P_malformed_edit_uncond'])} | {w(s['P_malformed_given_edit'])} | "
                 + (f"{pp(pr['RD'])} pp {ci_pp(pr['RD_CI'])}" if pr else '-') + ' | ' + (rat(pr['ratio'], pr['ratio_CI']) if pr else '-') + ' |')
    c0 = an['arms'].get('C0')
    if c0:
        lg = (an.get('logged_gemma31b_next_call_malformed') or {}).get('C0')
        L.append(f"\nCensus (first-edit contexts, original history): P(call) {w(c0['P_call'])}; P(edit) {w(c0['P_edit'])}; "
                 f"P(malformed edit) {w(c0['P_malformed_edit_uncond'])}; P(malformed | edit) {w(c0['P_malformed_given_edit'])}; "
                 f"P(malformed | any call) {w(c0['P_malformed_any_call_given_call'])}; malformed flags {c0['malformed_edit_flags']}. "
                 f"Logged Gemma-4-31B next call on the same contexts: malformed {w(lg)}.")
    rm = an.get('removal') or {}
    for Q in ('P5', 'P8a'):
        r = (rm.get(Q) or {}).get('uncond')
        if r:
            L.append(f"\n{Q} removal of the P1L excess (uncond.): {r['fraction_removed']} [{r['CI'][0]}, {r['CI'][1]}] "
                     f"(P1L {100 * r['P1L']:.1f}%, {Q} {100 * r[Q]:.1f}%, P0 {100 * r['P0']:.1f}%; n={rm[Q].get('n_contexts')}; "
                     f"undefined when P1L shows no excess over P0).")
    rr = (res.get('models') or {}).get(mk, {}).get('rule')
    if rr:
        L.append(f"\n**Pre-registered rule:** S1 {rr['S1']}, S2 {rr['S2']} ({rr['S2_mode']}), S3 {rr['S3']} -> **{'PASS' if rr['PASS'] else 'FAIL'}**.")
    cc = an.get('copy_check') or {}
    if cc:
        L.append('\nCopy check (edits only): class n / malformed rate')
        L.append('| arm | verbatim copy of injected value | clean retry | same-content variant | new content | unparsed/other | share of malformed = copies | non-copy edits malformed |')
        L.append('|---|---|---|---|---|---|---|---|')
        for arm in ('P0', 'P1L', 'P6', 'P8a', 'P1N'):
            row = cc.get(arm)
            if not row:
                continue

            def cell(k):
                e = row.get(k)
                return f"{e['n']} / {w(e['malformed']).split(' (')[0]}" if e else '0'
            cp = row.get('copy_corrupted') or row.get('copy_corrupted_raw')
            cpk = 'copy_corrupted' if row.get('copy_corrupted') else 'copy_corrupted_raw'
            L.append(f"| {arm} | {cell(cpk)} | {cell('clean_retry')} | {cell('same_content_variant')} | {cell('new_content')} | "
                     f"{cell('unparsed_other')} | {w(row.get('share_of_malformed_that_are_verbatim_copies'))} | {w(row.get('non_copy_edits_malformed'))} |")
    L.append('')
# held-out tier, Gemma reference, exploratory protocol failure
L.append('### Held-out tier (A\'s contexts 300-599; registered secondary) -- RD vs P0, unconditional [95% CI]\n')
L.append('| model | P0 | P1L | P5 | P6 |'); L.append('|---|---|---|---|---|')
for mk, title in MODELS:
    h = load(f'out/ana_{mk}_heldout.json')
    if not h:
        L.append(f'| {title} | not run | | | |'); continue
    cells = [w(h['arms']['P0']['P_malformed_edit_uncond'])]
    for arm in ('P1L', 'P5', 'P6'):
        u = (h['paired_vs_P0'].get(arm) or {}).get('uncond')
        cells.append(f"{w(h['arms'][arm]['P_malformed_edit_uncond']).split(' (')[0]}; RD {pp(u['RD'])} {ci_pp(u['RD_CI'])}" if u else 'n/a')
    L.append(f'| {title} | ' + ' | '.join(cells) + ' |')
ref = load(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/out/ana_31b_old_gate_k1_random_sample.json'))
if ref:
    L.append('\n### Reference: Gemma-4-31B on the same 300 gate contexts (workstream A, read-only)\n')
    L.append('| A arm (X analogue) | P(malformed edit), uncond. | RD vs P0 [95% CI] |'); L.append('|---|---|---|')
    for aarm, xa in (('P0k0', 'P0'), ('P1k1', 'P1L'), ('P3k1', 'P1N (hermes analogue: raw text + nudge)'), ('P5k1', 'P5'), ('P6k1', 'P6'), ('P8ak1', 'P8a')):
        s_ = ref['arms'].get(aarm); u = ((ref.get('paired_vs_P0') or {}).get(aarm) or {}).get('uncond')
        if s_:
            L.append(f"| {aarm} ({xa}) | {w(s_['P_malformed_edit_uncond'])} | " + (f"{pp(u['diff'])} pp {ci_pp(u['diff_CI'])}" if u else '-') + ' |')
L.append('\n### EXPLORATORY: Qwen-native reasoning-delimiter slip and "any protocol failure" (PI request; not pre-registered)\n')
L.append('A call written inside an unclosed `<think>` is delivered by vLLM 0.19.1\'s reasoning parser as reasoning only (no call).')
L.append('PF_edit = registered malformed edit OR edit call dropped this way. Unconditional rates; RD vs P0 [95% CI].\n')
L.append('| model | arm | dropped call (any) | PF_edit | RD(PF_edit) vs P0 |'); L.append('|---|---|---|---|---|')
for mk, title in MODELS:
    pf = load(f'out/pf_{mk}.json')
    if not pf:
        continue
    for arm in ('C0', 'P0', 'P1L', 'P1N', 'P5', 'P6', 'P8a'):
        s_ = pf['arms'].get(arm)
        if not s_:
            continue
        u = ((pf.get('paired_vs_P0') or {}).get(arm) or {}).get('PF_edit')
        L.append(f"| {title} | {arm} | {w(s_['dropped_any']).split(' (')[0]} | {w(s_['PF_edit']).split(' (')[0]} | "
                 + (f"{pp(u['RD'])} pp {ci_pp(u['RD_CI'])}" if u else '-') + ' |')
L.append('\nFigure: `out/fig_forest_rd.{png,svg}` (numbers in `out/fig_forest_rd.json`).\n')
hm = res.get('F2_holm')
if hm:
    L.append(f"**F2 Holm** ({hm['n_tests']} tests): raw {hm['raw']}; adjusted {hm['adjusted']}.\n")
cf = res.get('cross_family_loop')
if cf:
    L.append(f"**Cross-family laundering loop (pre-registered rule): {'PASS' if cf['PASS_in_at_least_one_Qwen_model'] else 'FAIL'}** "
             f"(models evaluated: {', '.join(cf['models_evaluated'])}).\n")
fs = load('format/format_summary.json'); f31 = load('format/format_summary_v31.json')
if fs:
    L.append('### Format proposition, CPU (1,598 real Gemma slip payloads with known intent; Wilson 95%)\n')
    L.append('| variant | parser path | n | loud | exact | silent local residue | silent absorbed | silent other | delivered invalid | laundered (of silent) | judge-flagged (of silent) |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|')
    for src, S, tag in ((fs, fs['variants'], 'vLLM 0.19.1'), (f31, (f31 or {}).get('variants') or {}, 'vLLM 0.31.0')):
        for v, paths in S.items():
            for p, row in paths.items():
                if p == '_':
                    continue
                g = lambda k: (f"{100 * row[k][0]:.1f}%" if row.get(k) else '0')  # noqa: E731
                L.append(f"| {v} | {tag} {p} | {row['n']} | {g('loud')} | {g('exact')} | {g('silent_local')} | {g('silent_absorbed')} | "
                         f"{g('silent_other')} | {g('delivered_invalid')} | {g('silent_laundered_share')} | {g('silent_flagged_by_judge_share')} |")
    fp = (res.get('format') or {}).get('predictions')
    if fp:
        L.append('\nPre-registered format predictions: ' + '; '.join(f"{k}: {v.get('share')} (pass={v.get('pass(>=0.95)', v.get('pass(>=0.5)'))})" for k, v in fp.items()))
tx = load('out/teacher/teacher_xml_slips.json')
if tx:
    c = tx['counts']
    L.append(f"\nTeacher Qwen3.8-flash-next (qwen3_coder XML, same harness, descriptive only): {c.get('malformed:edit_file', 0)}/{c.get('calls:edit_file')} "
             f"edit calls malformed (schema-level: wrong/missing keys {c.get('flag:extra_key', 0)} extra-key, {c.get('flag:missing:edit_file', 0)} missing); "
             f"loud unparsed responses {c.get('loud_unparsed_response', 0)}/{c.get('responses')}; XML residue at a value end {c.get('xml_residue_at_value_end', 0)}.")
block = '\n'.join(L)
rp = os.path.join(X, 'README.md')
s = open(rp).read() if os.path.exists(rp) else '<!-- RESULTS:BEGIN -->\n<!-- RESULTS:END -->\n'
s = re.sub(r'<!-- RESULTS:BEGIN[^>]*-->.*<!-- RESULTS:END -->', lambda m: '<!-- RESULTS:BEGIN (generated by scripts/report.py) -->\n' + block + '\n<!-- RESULTS:END -->', s, flags=re.S)
open(rp, 'w').write(s)
print(block[:3000])
