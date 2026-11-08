"""Markdown tables from results.json (so README numbers are generated, never retyped).
usage: report_tables.py [results.json] > out/tables.md"""
import os  # added by the repo export (paths are env/config driven)
import json, sys
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/results.json')))


def w(x, pct=True):
    if not x or x[0] is None: return 'NA'
    p, lo, hi = x[0], x[1], x[2]; n = x[3] if len(x) > 3 else None
    s = f'{100 * p:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]'
    return s + (f' (n={n})' if n is not None else '')


def frac(k, n): return f'{k}/{n}'


o = R['observational']
print('### Observational (main-track logs; edits as Wilson 95% CIs; cluster bootstrap over attempts in brackets where given)\n')
print('| quantity | synthesis population (incl. teacher runs) | plain base 31B-QAT | team adapters r*/rl* |')
print('|---|---|---|---|')
S, Bq, F = o['SYN_replication'], o['BASE_plain_31b_qat'], o['FT_adapters']
rows = [('edit calls / attempts', lambda d: f"{d['edits']} / {d['attempts']}"), ('malformed edits', lambda d: w(d['malformed_rate'])),
        ('first edit malformed', lambda d: w(d['first_edit'])), ('later edit, clean history', lambda d: w(d['later_clean_history']))]
for k in ('1', '2', '3', '4'):
    rows.append((f'later edit after {k if k != "4" else ">=4"} prior malformed', lambda d, k=k: w(d['later_by_prior_bad'].get(k))))
for name, fn in rows:
    print(f'| {name} | {fn(S)} | {fn(Bq)} | {fn(F)} |')
for name, d in (('synthesis', S), ('base', Bq), ('adapters', F)):
    pn = d['perm_null_P_bad_given_prev_bad']
    print(f'\n- {name}: P(bad | previous bad) = {pn["observed"]:.3f} vs within-attempt permutation null mean {pn["mean"]:.3f} '
          f'(max {pn["max"]:.3f}, {pn["n_perm"]} permutations, p = {pn["p_value"]:.4f})', end='')
    if 'cluster_bootstrap_95CI' in d: print(f'; attempt-cluster bootstrap 95% CIs: {json.dumps(d["cluster_bootstrap_95CI"])}', end='')
print('\n')
ep = o['natural_episodes_BASE']
print(f"- Natural episodes (base): {ep['episodes']} attempts with a malformed edit followed by later edits; later edits malformed "
      f"{ep['later_malformed']}/{ep['later_edits']}; retries of the same content {frac(ep['after_onset_retry_same_content'][1], ep['after_onset_retry_same_content'][0])}; "
      f"new content {frac(ep['after_onset_new_content'][1], ep['after_onset_new_content'][0])}; recover a clean edit {frac(*ep['recovered_clean_edit'])}.")
if 'hazard_model_BASE' in o:
    hz = o['hazard_model_BASE']['hazard']
    print('- Hazard model (base; logistic, run fixed effects, attempt-cluster bootstrap): ' + '; '.join(
        f"{k} OR {v['odds_ratio']} [{v['OR_CI95'][0]}, {v['OR_CI95'][1]}]" for k, v in hz.items() if isinstance(v, dict)))
print()
ARM_NAME = {'P0k0': 'P0 original history', 'P1k1': 'P1 corrupted re-render + error', 'P2k1': 'P2 error message only', 'P3k1': 'P3 raw slip text + nudge',
            'P6k1': 'P6 corrupted re-render + success', 'P7k1': 'P7 = P1 with a double-quote closer', 'P4k1': 'P4 canonical old-first re-render',
            'P5k1': 'P5 removed + note'}
for g, v in R['injection'].items():
    gk = v.get('gate_k1_random_sample')
    if not gk or 'arms' not in gk: continue
    print(f'### Injection, {g}: k = 1 pathways on the random sample ({gk["n_contexts"]} contexts)\n')
    print('| arm | P(next call is edit_file) | P(malformed \\| edit) | paired diff vs P0 [cluster bootstrap] | ratio vs P0 | malformed among retries of the replaced call | among other edits | emitted order |')
    print('|---|---|---|---|---|---|---|---|')
    for arm in ('P0k0', 'P1k1', 'P2k1', 'P3k1', 'P6k1', 'P7k1', 'P4k1', 'P5k1'):
        a = gk['arms'].get(arm)
        if not a: continue
        pr = (gk['paired_vs_P0'].get(arm) or {}).get('cond') if arm != 'P0k0' else None
        mc = a['malformed_by_edit_class']

        def kn(x): return (0, 0) if not x or x[0] is None else (round(x[0] * x[3]), x[3])
        rk, rn = kn(mc.get('retry_most_recent'))
        oth = [kn(mc.get(c)) for c in ('target', 'other', 'retry_older')]
        ok_, on = sum(x[0] for x in oth), sum(x[1] for x in oth)
        print(f"| {ARM_NAME.get(arm, arm)} | {w(a['P_edit'])} | {w(a['P_malformed_given_edit'])} | "
              + (f"{100 * pr['diff']:+.1f} pp [{100 * pr['diff_CI'][0]:+.1f}, {100 * pr['diff_CI'][1]:+.1f}]" if pr else '-') + ' | '
              + (f"{pr['ratio']} [{pr['ratio_CI'][0]}, {pr['ratio_CI'][1]}]" if pr else '-')
              + f" | {rk}/{rn} | {ok_}/{on} | {a['edit_order']} |")
    cl = {arm: gk['arms'][arm]['malformed_closers'] for arm in ('P0k0', 'P1k1', 'P3k1', 'P6k1', 'P7k1') if arm in gk['arms']}
    print('\nClosers of malformed next edits (injected closer: backtick in P1/P3/P6, double quote in P7): ' + '; '.join(f'{k} {v}' for k, v in cl.items()))
    print()
    gt = gk.get('gate', {})
    if gt:
        g1 = gt.get('G1_ratio_P1k1_over_P0')
        if g1: print(f"- **G1** P(slip | k=1, P1) / P(slip | k=0) = {g1['ratio']} [{g1['CI'][0]}, {g1['CI'][1]}] ({100 * g1['P1k1']:.1f}% vs {100 * g1['P0']:.1f}%, "
                     f"paired diff {100 * g1['diff']:+.1f} pp [{100 * g1['diff_CI'][0]:+.1f}, {100 * g1['diff_CI'][1]:+.1f}], {g1['n_contexts']} contexts / {g1['n_attempts']} attempts) -> {'PASS' if g1['pass(>=3, CI_lo>1)'] else 'FAIL'} (needs >= 3 and CI_lo > 1)")
        for q in ('P4', 'P5'):
            x = gt.get(f'G2_removed_by_{q}_k1')
            if x: print(f"- **G2 ({q})** fraction of the P1 excess removed = {x['fraction_removed']} [{x['CI'][0]}, {x['CI'][1]}] "
                        f"(P1 {100 * x['P1']:.1f}%, {q} {100 * x['Q']:.1f}%, P0 {100 * x['P0']:.1f}%; {x['n_contexts']} contexts) -> {'PASS' if x['pass(>=0.5)'] else 'FAIL'} (needs >= 0.5)")
        print()
    rf = gk.get('replay_fidelity_P0')
    if rf: print(f"- Replay fidelity (P0 vs logged next call on the same contexts): logged malformed {w(rf['logged_next_call_malformed'])}; replay P(edit) {w(rf['replay_P_edit'])}; replay malformed | edit {w(rf['replay_P_malformed_given_edit'])}.\n")
for g, v in R['injection'].items():
    dk = v.get('dose_k4_nested_set')
    if not dk or not dk.get('dose_response'): continue
    print(f'### Dose-response, {g} (nested set: contexts with >= 4 clean prior edits; P(malformed | edit), Wilson 95%)\n')
    print('| pathway | contexts | k=0 | k=1 | k=2 | k=4 |')
    print('|---|---|---|---|---|---|')
    for p in ('P1', 'P2', 'P3', 'P6', 'P4', 'P5'):
        cur = dk['dose_response'].get(f'{p}_upto_k4')
        if not cur:
            continue
        c = cur['curve']
        print(f"| {p} | {cur['n_contexts']} | " + ' | '.join(w(c[k]['P_malformed_given_edit']) if k in c else '-' for k in ('0', '1', '2', '4')) + ' |')
    print()
