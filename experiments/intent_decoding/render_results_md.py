"""Render markdown result tables from results.json (P0-B structure) for README §4. Regenerate after make_results.py."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, 'results.json')))
L = []


def pct(d, digits=1):
    if not d or not d.get('n') or d.get('rate') is None:
        return 'n/a'
    lo, hi = d['wilson95']
    return f"{d['k']}/{d['n']} = {100*d['rate']:.{digits}f}% [{100*lo:.{digits}f}, {100*hi:.{digits}f}]"


def rr(d):
    if not d or d.get('relred_point') is None:
        return 'n/a'
    lo, hi = d['relred_wilson95']
    return f"**{100*d['relred_point']:.1f}%** [{100*lo:.1f}, {100*hi:.1f}] (n={d['before']})"


df = R['data_fix']
L.append('### 4.1 Data fix\n')
L.append(f"- Teacher runs excluded: {', '.join(df['teacher_runs_excluded'])}. {df['teacher_contexts_removed_from_replay_set']} replay contexts "
         f"removed; {df['gemma_only_contexts']} Gemma-only contexts remain.")
d = df['logged_first_edit_malformed_gemma_only']
L.append(f"- Logged first-edit malformation, Gemma-only: **{d['k']}/{d['n']} = {100*d['rate']:.1f}% "
         f"[{100*d['wilson95'][0]:.1f}, {100*d['wilson95'][1]:.1f}]**. At T=0.2 it is {df['by_temperature']['0.2']['k']}/{df['by_temperature']['0.2']['n']}; "
         f"at T=0.7 it is {df['by_temperature']['0.7']['k']}/{df['by_temperature']['0.7']['n']}. The teacher runs have 0/1,620. "
         f"The figure {df['withdrawn']} is withdrawn.\n")
L.append('### 4.2 E1: first-edit replays, paired, Wilson 95% CIs\n')
L.append('| replay | subset | contexts / edit calls (forced) | baseline census-malformed | after (i) | after IPD (i+) | after (ii) | rel. red. census, IPD | closer slips base→(i) | rel. red. slips (i) | valid calls changed (i)/(i+)/(ii) |')
L.append('|---|---|---|---|---|---|---|---|---|---|---|')
for name, rs in R.get('replays', {}).items():
    for sub in ('all', 'natural', 'forced'):
        r = rs.get(sub)
        if not r or not r.get('n_edit_calls'):
            continue
        fr = r['false_repair_real']
        ii_ok = not r.get('ii_not_run_on_invalid')
        ii_cell = pct(r['ii_census_bad']) if ii_ok else f"n/a ((ii) not run on {r['ii_not_run_on_invalid']} invalid calls)"
        L.append(f"| {name} | {sub} | {r['n_contexts']} / {r['n_edit_calls']} ({r['forced_edit']}) | {pct(r['base_census_bad'])} | {pct(r['i_nc_census_bad'])} | "
                 f"{pct(r['iplus_census_bad'])} | {ii_cell} | {rr(r['paired']['census_iplus'])} | "
                 f"{r['base_slip']['k']} → {r['i_nc_slip']['k']} | {rr(r['paired']['slip_i_nc'])} | "
                 f"{fr['i_changed_valid']}/{fr['iplus_changed_valid']}/{fr['ii_changed_valid'] if ii_ok else 'n/a'} of {fr['n_valid']} |")
L.append('')
L.append('**Unforced: the natural next call, with no forcing.**\n')
L.append('| replay | natural calls | tool distribution | census-malformed (any tool) | edit_file malformed | forced-edit share |')
L.append('|---|---|---|---|---|---|')
for name, rs in R.get('replays', {}).items():
    r = rs.get('all', {})
    nn = r.get('natural_next_call')
    if not nn:
        continue
    ed = nn['census_malformed_by_tool'].get('edit_file', {'k': 0, 'n': 0, 'wilson95': [0, 0]})
    fs = nn['forced_edit_share']
    L.append(f"| {name} | {nn['n']} | {', '.join(f'{t}:{c}' for t, c in nn['tool_distribution'][:5])} | {pct(nn['census_malformed'])} | "
             f"{ed['k']}/{ed['n']} | {fs['k']}/{fs['n']} |")
L.append('')
L.append('### 4.3 Decoder head-to-head on identical samples\n')
for name, h in R.get('head2head', {}).items():
    for sub in ('all', 'slips'):
        t = h.get(sub)
        if not t:
            continue
        ex = h.get('arms_excluded_partial') or {}
        exs = (' Omitted because they ran on only part of the samples: ' + ', '.join(f'{a} ({n}/{h["n_samples"]})' for a, n in ex.items()) + '.') if ex else ''
        L.append(f"**{name} [{sub}]**: samples={h['n_samples']}, contexts={h['n_contexts']}, slips={h['n_slips']}, forced={h['n_forced']}.{exs}\n")
        L.append('| arm | delivered-malformed | silent corruption | loud | clean |')
        L.append('|---|---|---|---|---|')
        for a, m in t.items():
            L.append(f"| {a} | {pct(m['malformed'])} | {pct(m['silent'])} | {pct(m['loud'])} | {pct(m['clean'])} |")
        L.append('')
if R.get('onset_arms'):
    L.append('### 4.4 Onset arms vs June: exemplar immunization (arm 11) and July template (arm 12), paired by context\n')
    L.append('| comparison | outcome | contexts | June (samples, Wilson 95%) | arm (samples, Wilson 95%) | difference of per-context rates (context bootstrap 95%) |')
    L.append('|---|---|---|---|---|---|')
    for arm, v in R['onset_arms'].items():
        for k, d in v.items():
            if k.startswith('edits_to_exemplar'):
                continue
            if d:
                rs, as_ = d.get('ref_samples'), d.get('arm_samples')
                ref = (f"{rs['k']}/{rs['n']} = {100*rs['k']/rs['n']:.1f}% [{100*rs['wilson95'][0]:.1f}, {100*rs['wilson95'][1]:.1f}]"
                       if rs and rs['n'] else f"{100*d['rate_ref']:.1f}%")
                arm_ = (f"{as_['k']}/{as_['n']} = {100*as_['k']/as_['n']:.1f}% [{100*as_['wilson95'][0]:.1f}, {100*as_['wilson95'][1]:.1f}]"
                        if as_ and as_['n'] else f"{100*d['rate_arm']:.1f}%")
                L.append(f"| {arm} | {k} | {d['n_contexts']} | {ref} | {arm_} | "
                         f"{100*d['diff']:+.1f} pp [{100*d['boot95'][0]:+.1f}, {100*d['boot95'][1]:+.1f}] |")
    L.append('')
    for arm, v in R['onset_arms'].items():
        c = v.get('edits_to_exemplar_file_NOTES_md') or {}
        if arm.startswith('arm11') and c:
            L.append(f"- {arm}: edit calls to the exemplar's own file `NOTES.md` (they extend the exemplar's note): forced "
                     f"{c.get('forced', 0)}/{c.get('forced_total', 0)}, natural {c.get('natural', 0)}/{c.get('natural_total', 0)}; slips among them {c.get('slips', 0)}.")
    L.append('')
g = R.get('gold', {})
if g.get('real_slips_retry_intent'):
    r = g['real_slips_retry_intent']
    L.append('### 4.5 Gold intent: real logged slips with retry-derived intent (base 31B)\n')
    L.append(f"{r['n']} records; slip site found in {r['site_found']['k']}/{r['site_found']['n']}.\n")
    L.append('| arm | exact intent | new_string exact | old_string exact | strictly valid | silent corruption |')
    L.append('|---|---|---|---|---|---|')
    for a, t in r['all'].items():
        L.append(f"| {a} | {pct(t['exact_intent'])} | {pct(t['new_exact'])} | {pct(t['old_exact'])} | {pct(t['strict_valid'])} | {pct(t['silent_corruption'])} |")
    L.append('')
if g.get('g1r_natural_closures'):
    r = g['g1r_natural_closures']
    L.append('### 4.5b Gold intent: natural closures re-sampled at the 229 real slip-prone states (G1R, k=4)\n')
    L.append(f"{r['samples']} samples from {r['states']} states. Natural slip rate {pct(r['natural_slip_rate'])}; slip runs: {r['slip_runs']}. "
             f"False repairs on clean closures: IPD changed {pct(r['false_repairs_on_clean']['IPD_changed'])}, "
             f"T1 changed {pct(r['false_repairs_on_clean']['T1_changed'])}.\n")
    for sub in ('slips', 'clean_closures'):
        L.append(f"**[{sub}]**\n")
        L.append('| arm | exact intent | new_string exact | old_string exact | strictly valid | silent corruption |')
        L.append('|---|---|---|---|---|---|')
        for a, t in r[sub].items():
            L.append(f"| {a} | {pct(t['exact_intent'])} | {pct(t['new_exact'])} | {pct(t['old_exact'])} | {pct(t['strict_valid'])} | {pct(t['silent_corruption'])} |")
        L.append('')
if g.get('combined_natural_slips'):
    r = g['combined_natural_slips']
    L.append(f"### 4.5c Gold intent, combined natural slips: G1 ({r['n_G1']}) + G1R ({r['n_G1R_slips']}) = {r['n_total']} slips from {r['n_states']} states\n")
    L.append(r['note'] + '\n')
    L.append('| arm | exact intent (Wilson 95%) | state-cluster bootstrap 95% |')
    L.append('|---|---|---|')
    for a, t in r['exact_intent'].items():
        lo, hi = t['state_cluster_boot95']
        L.append(f"| {a} | {pct(t)} | [{100*lo:.1f}, {100*hi:.1f}] |")
    L.append('')
    if r.get('paired_IPD_minus_arm'):
        L.append('Paired, same slips: IPD minus arm (exact intent), state-cluster bootstrap 95%:\n')
        L.append('| arm | IPD − arm | IPD right, arm wrong | arm right, IPD wrong |')
        L.append('|---|---|---|---|')
        for a, t in r['paired_IPD_minus_arm'].items():
            L.append(f"| {a} | {100*t['diff']:+.1f} pp [{100*t['state_cluster_boot95'][0]:+.1f}, {100*t['state_cluster_boot95'][1]:+.1f}] | {t['IPD_only']} | {t['arm_only']} |")
        L.append('')
for name, h in g.items():
    if not name.startswith('gc_'):
        continue
    L.append(f"### 4.6 Gold copy task: {name} (samples {h['n_samples']}, slips {h['n_slips']})\n")
    for sub in ('all', 'slips', 'rich_slips'):
        t = h.get(sub)
        if not t:
            continue
        L.append(f"**[{sub}]**\n")
        cols = [c for c in ('exact_intent', 'edit_applies', 'edit_correct') if c in next(iter(t.values()))]
        L.append('| arm | delivered-malformed | silent | loud | ' + ' | '.join(cols) + ' |')
        L.append('|---|---|---|---|' + '---|' * len(cols))
        for a, m in t.items():
            L.append(f"| {a} | {pct(m['malformed'])} | {pct(m['silent'])} | {pct(m['loud'])} | " + ' | '.join(pct(m[c]) for c in cols) + ' |')
        L.append('')
mf = R.get('model_free_quotestorm_free_big')
if mf:
    L.append('### 4.7 QuoteStorm, model-free, all valid calls\n')
    L.append('| set | valid calls | (i)/(ii) changed | pattern-only detector fires | regex splitter fires | census flags | synthetic slips: detected / GT in candidates / whole-run cut correct |')
    L.append('|---|---|---|---|---|---|---|')
    for gname in ('all', 'natural', 'adversarial'):
        o = mf[gname]; s = o['synthetic_slips']
        L.append(f"| {gname} | {o['calls']} | {o['i_changed']['k']} / {o['ii_changed']['k']} (Wilson upper {100*o['i_changed']['wilson95'][1]:.4f}%) | "
                 f"{o['b1_fires']['k']} | {o['b2_fires']['k']} | {o['census_flags']['k']} | {100*s['slip_detected']['rate']:.2f}% / "
                 f"{100*s['slip_gt_in_cands']['rate']:.2f}% / {100*s['slip_max_cut_correct']['rate']:.1f}% |")
    L.append('')
if R.get('intent_recovery_synthetic'):
    L.append('### 4.8 Synthetic slips with known intent, model-scored\n')
    L.append('| file | n | GT among candidates | (ii) argmax: no prior / disjoint prior / matched prior | (ii) disjoint prior τ=2: correct / wrong / abstain | (i) cut: noisy-channel / likelihood / whole-run |')
    L.append('|---|---|---|---|---|---|')
    for name, r in R['intent_recovery_synthetic'].items():
        a = r.get('all')
        if not a:
            continue
        t2 = a['ii_prior=ft_edit']['tau=2.0']
        L.append(f"| {name} | {a['n']} | {pct(a['gt_in_candidates'])} | {pct(a['ii_prior=none']['tau=0.0']['correct'])} / "
                 f"{pct(a['ii_prior=ft_edit']['tau=0.0']['correct'])} / {pct(a['ii_prior=base_edit']['tau=0.0']['correct'])} | "
                 f"{pct(t2['correct'])} / {pct(t2['wrong'])} / {pct(t2['abstain'])} | {pct(a['i_cut']['nc_ft_edit'])} / {pct(a['i_cut']['lik'])} / "
                 f"{pct(a['i_cut']['max'])} |")
print('\n'.join(L))
