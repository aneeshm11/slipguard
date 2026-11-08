"""Assemble results.json (P0-B structure) from all available outputs; re-runnable any time (partial runs carry n)."""
import json, os, sys, glob, datetime, collections, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_replay as AR
import analyze_quotestorm as AQ
import analyze_h2h as AH
import analyze_rs279 as RS
import analyze_g1r as G1R
from stats import wilson, cluster_bootstrap

OUT = os.path.join(HERE, 'out')
CTX = os.path.join(HERE, 'data/replay_gemma_first_edit.jsonl')
res = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
       'notes': ['Gemma-only contexts (546 teacher-run contexts excluded); primary 31B arms use the log-faithful June-5 '
                 'chat template; July (2026-07-09) template = arm 12.',
                 'rates: Wilson 95% CI; relative reductions: paired residual Wilson 95% CI and context-cluster bootstrap.',
                 'outputs in out/old_v1/ are superseded (old code, teacher contexts, July-as-primary) and not used.',
                 'arms 11/12 (exemplar, July) are onset comparisons; their later segments ran onset + (i) only. In head2head an '
                 'arm that ran on only part of a file is excluded for that file (arms_excluded_partial); in replays the (ii) '
                 'column is n/a when ii_not_run_on_invalid > 0.',
                 'arm 11 side effect: with the exemplar in context, part of the FORCED edits extend the exemplar file NOTES.md '
                 '(onset_arms.*.edits_to_exemplar_file_NOTES_md); natural-only paired onset is reported alongside.']}
# --- data fix
res['data_fix'] = {'teacher_runs_excluded': ['t1_qwen', 't2_qwen_rebench', 't3_qwen_rebench', 'dsprobe'],
                   'teacher_contexts_removed_from_replay_set': 546, 'gemma_only_contexts': 954,
                   'logged_first_edit_malformed_gemma_only': {'k': 472, 'n': 2753, 'rate': 472 / 2753, 'wilson95': wilson(472, 2753)},
                   'by_temperature': {'0.2': {'k': 215, 'n': 1550, 'wilson95': wilson(215, 1550)},
                                      '0.7': {'k': 257, 'n': 1203, 'wilson95': wilson(257, 1203)}},
                   'teacher_first_edit_malformed': {'k': 0, 'n': 1620},
                   'withdrawn': '10.8% (diluted by teacher runs)'}
for name in ('quotestorm_free_big', 'quotestorm_free'):
    p = os.path.join(OUT, name + '.json')
    if os.path.exists(p):
        res['model_free_' + name] = json.load(open(p))
# --- replays: gate metrics + head-to-head
REPLAYS = ['v3_r31_on_june', 'v3_r31_off_june', 'v4_r31_on_june_exm', 'v4_r31_off_june_exm', 'v2_r31_on_july',
           'v2_r31_off_july', 'v2_re4_on', 'v2_re4_off']
res['replays'], res['head2head'] = {}, {}
for name in REPLAYS:
    p = os.path.join(OUT, name + '.jsonl')
    if not (os.path.exists(p) and os.path.getsize(p) > 0):
        continue
    res['replays'][name] = {s or 'all': AR.summarize(p, CTX, tau=0.0, B=1000, subset=s) for s in (None, 'natural', 'forced')}
    hp = os.path.join(OUT, 'h2h_' + name + '.jsonl')
    res['head2head'][name] = AH.summarize(p, tau=2.0, h2h=hp if os.path.exists(hp) else None)


# --- onset comparisons (arm 11 exemplar, arm 12 July) vs June, paired by context (thinking ON: 1 sample per context)
def onset_by_ctx(path, key, natural_only=False):
    d = collections.defaultdict(list)
    for l in open(path):
        r = json.loads(l)
        if r.get('status') == 'call' and r.get('tool') == 'edit_file' and not (natural_only and r.get('forced')):
            d[r['id']].append(1 if (r.get('site') is not None if key == 'slip' else not r['base']['census_ok']) else 0)
    return {k: (sum(v), len(v)) for k, v in d.items()}


def paired_diff(a, b, B=2000, seed=0):
    """context-paired difference arm - ref of per-context rates; context-cluster bootstrap 95% CI; Wilson on the
    pooled sample counts of each side (over the paired contexts)."""
    ids = sorted(set(a) & set(b))
    if not ids:
        return None
    rng = random.Random(seed)
    da = [a[i][0] / a[i][1] for i in ids]; db = [b[i][0] / b[i][1] for i in ids]
    pt = sum(db) / len(ids) - sum(da) / len(ids)
    bs = []
    for _ in range(B):
        idx = [rng.randrange(len(ids)) for _ in ids]
        bs.append(sum(db[i] for i in idx) / len(ids) - sum(da[i] for i in idx) / len(ids))
    bs.sort()
    ka, na = sum(a[i][0] for i in ids), sum(a[i][1] for i in ids)
    kb, nb = sum(b[i][0] for i in ids), sum(b[i][1] for i in ids)
    return {'n_contexts': len(ids), 'rate_ref': sum(da) / len(ids), 'rate_arm': sum(db) / len(ids), 'diff': pt,
            'boot95': [bs[int(0.025 * (B - 1))], bs[int(0.975 * (B - 1))]],
            'ref_samples': {'k': ka, 'n': na, 'wilson95': wilson(ka, na)}, 'arm_samples': {'k': kb, 'n': nb, 'wilson95': wilson(kb, nb)}}


res['onset_arms'] = {}
for arm, ref, alt in [('arm11_exemplar_on', 'v3_r31_on_june', 'v4_r31_on_june_exm'),
                      ('arm11_exemplar_off', 'v3_r31_off_june', 'v4_r31_off_june_exm'),
                      ('arm12_july_on', 'v3_r31_on_june', 'v2_r31_on_july'),
                      ('arm12_july_off', 'v3_r31_off_june', 'v2_r31_off_july')]:
    pr, pa = os.path.join(OUT, ref + '.jsonl'), os.path.join(OUT, alt + '.jsonl')
    if os.path.exists(pr) and os.path.exists(pa) and os.path.getsize(pa) > 0:
        res['onset_arms'][arm] = {k: paired_diff(onset_by_ctx(pr, k), onset_by_ctx(pa, k)) for k in ('slip', 'census_malformed')}
        for k in ('slip', 'census_malformed'):
            res['onset_arms'][arm][k + '_natural_only'] = paired_diff(onset_by_ctx(pr, k, True), onset_by_ctx(pa, k, True))
        # exemplar copying: edit calls whose filepath is the exemplar's NOTES.md (all of them extend the exemplar's note)
        import re as _re
        cp = collections.Counter()
        for l in open(pa):
            r = json.loads(l)
            if r.get('status') == 'call' and r.get('tool') == 'edit_file':
                m = _re.search(r'filepath\s*:\s*<\|"\|>(.*?)<\|"\|>', r.get('call') or '', _re.S)
                if m and m.group(1).strip().endswith('NOTES.md'):
                    cp['forced' if r.get('forced') else 'natural'] += 1
                    cp['slips'] += r.get('site') is not None
                cp['forced_total' if r.get('forced') else 'natural_total'] += 1
        res['onset_arms'][arm]['edits_to_exemplar_file_NOTES_md'] = dict(cp)
# --- gold splits
res['gold'] = {}
p = os.path.join(OUT, 'rs279_31b.jsonl')
if os.path.exists(p) and os.path.getsize(p) > 0:
    res['gold']['real_slips_retry_intent'] = RS.summarize(p)
p = os.path.join(OUT, 'g1r_31b.jsonl')
if os.path.exists(p) and os.path.getsize(p) > 0:
    res['gold']['g1r_natural_closures'] = G1R.summarize(p)
for p in sorted(glob.glob(os.path.join(OUT, 'gc_*.jsonl'))):
    if os.path.getsize(p) > 0:
        res['gold'][os.path.basename(p)] = AH.summarize(p, tau=2.0, gold_ctx=os.path.join(HERE, 'data/gold_all_ctx.jsonl'))
# --- combined gold (>=500 natural slips): G1 real logged slips + G1R natural slips re-sampled at the same states.
# Clustered by state (corpus record id): a state contributes its G1 record and up to 4 G1R samples.
def gold_combined():
    p1, p2 = os.path.join(OUT, 'rs279_31b.jsonl'), os.path.join(OUT, 'g1r_31b.jsonl')
    if not (os.path.exists(p1) and os.path.exists(p2)):
        return None
    items = collections.defaultdict(list)   # state id -> list of {arm: bool}
    m1 = {'IPD': 'i_nc', 'i_max': 'i_max', 'T1_text_only': 'T1_assumed_tail', 'ii_tau2': 'ii_assumed_tail', 'retry_x2': 'retry_x2',
          'greedy': 'greedy', 'forbid_strict': 'forbid_strict', 'grammar_CD': 'grammar'}
    n1 = n2 = 0
    for l in open(p1):
        r = json.loads(l)
        if r.get('status') != 'ok':
            continue
        n1 += 1
        x = {a: bool((r['arms'].get(b) or {}).get('exact_intent')) for a, b in m1.items()}
        mg = (r['arms'].get('ii_assumed_tail') or {}).get('margin')      # G1 (ii) was scored at tau=0: apply tau=2 here
        x['ii_tau2'] = x['ii_tau2'] and (mg == 'inf' or (isinstance(mg, (int, float)) and mg >= 2.0))
        items[r['id']].append(x | {'_src': 'G1'})
    for l in open(p2):
        r = json.loads(l)
        if r.get('status') != 'ok' or not r.get('slip'):
            continue
        n2 += 1
        g = G1R.gold_for(r['id']); A = r['arms']
        x = {'IPD': bool(A['IPD'].get('exact_intent')), 'i_max': bool((A.get('i_max') or {}).get('exact_intent')),
             'T1_text_only': G1R.sc(G1R.t1(r['call'], r['finished']), True, g)['exact_intent'],
             'retry_x2': bool(A['retry_x2'].get('exact_intent')), 'greedy': bool(A['greedy'].get('exact_intent')),
             'forbid_strict': bool(A['forbid_strict'].get('exact_intent')), 'grammar_CD': bool(A['grammar'].get('exact_intent'))}
        ii = A.get('ii') or {}
        cands = ii.get('cands')
        if cands is None:
            x['ii_tau2'] = G1R.sc(r['call'], r['finished'], g)['exact_intent']
        elif not cands:
            x['ii_tau2'] = False
        else:
            adj = sorted((c['ll'] + c['prior'], c['text']) for c in cands)[::-1]
            m = adj[0][0] - adj[1][0] if len(adj) > 1 else float('inf')
            x['ii_tau2'] = G1R.sc(adj[0][1] if m >= 2.0 else None, True, g)['exact_intent']
        items[r['id']].append(x | {'_src': 'G1R'})
    clusters = list(items.values())
    out = {'n_G1': n1, 'n_G1R_slips': n2, 'n_total': n1 + n2, 'n_states': len(clusters),
           'note': ('G1 = logged slips replayed from the exact logged prefix (229 base-31B); G1R = natural slips of the model '
                    're-sampled (k=4, T=0.2) at the first 105 of the same states. T1 and (ii) use an ASSUMED tail on G1 (the '
                    'emitted tail was lost at serving time) and the real emitted tail on G1R. CI: Wilson on items and a '
                    'state-cluster bootstrap (B=2000).'),
           'exact_intent': {}}
    for arm in ('IPD', 'i_max', 'T1_text_only', 'ii_tau2', 'retry_x2', 'greedy', 'forbid_strict', 'grammar_CD'):
        flat = [x[arm] for c in clusters for x in c]
        k, n = sum(flat), len(flat)
        pt, lo, hi = cluster_bootstrap(clusters, lambda rs, a=arm: sum(x[a] for x in rs) / len(rs), B=2000, seed=1)
        out['exact_intent'][arm] = {'k': k, 'n': n, 'rate': k / n if n else None, 'wilson95': wilson(k, n),
                                    'state_cluster_boot95': [lo, hi]}
    out['paired_IPD_minus_arm'] = {}
    for arm in ('i_max', 'T1_text_only', 'ii_tau2', 'retry_x2', 'greedy'):
        flat = [c_ for c in clusters for c_ in c]
        b = sum(x['IPD'] and not x[arm] for x in flat); c2 = sum(x[arm] and not x['IPD'] for x in flat)
        pt, lo, hi = cluster_bootstrap(clusters, lambda rs, a=arm: (sum(x['IPD'] for x in rs) - sum(x[a] for x in rs)) / len(rs),
                                       B=2000, seed=2)
        out['paired_IPD_minus_arm'][arm] = {'diff': pt, 'state_cluster_boot95': [lo, hi], 'IPD_only': b, 'arm_only': c2}
    return out


gc = gold_combined()
if gc:
    res['gold']['combined_natural_slips'] = gc
# --- synthetic intent recovery (QuoteStorm / self-slips)
res['intent_recovery_synthetic'] = {}
for p in sorted(glob.glob(os.path.join(OUT, 'v2_qsm_*.jsonl')) + glob.glob(os.path.join(OUT, 'v3_selfslip_*.jsonl'))):
    if os.path.getsize(p) > 0:
        res['intent_recovery_synthetic'][os.path.basename(p)] = AQ.syn([p])
# ---------------- explicit claim blocks (for R's claims ledger) ----------------
G = res['replays'].get('v3_r31_on_june', {}).get('all')
if G:
    fr = G['false_repair_real']
    res['gate_31b_think_on_final'] = {
        'source': 'out/v3_r31_on_june.jsonl', 'model': 'gemma-4-31b-it-qat-w4a16-ct', 'template': 'june (log-faithful)',
        'thinking': True, 'temperature': 0.2, 'contexts_requested': 600, 'n_calls': G['n_edit_calls'],
        'no_call': G['status'].get('no_call', 0), 'forced_edits': G['forced_edit'], 'natural_edits': G['natural_edit'],
        'baseline_closer_slips': G['base_slip'], 'baseline_census_malformed': G['base_census_bad'],
        'after_IPD_census_malformed': G['iplus_census_bad'], 'after_i_census_malformed': G['i_nc_census_bad'],
        'after_ii_tau0_census_malformed': G['ii_census_bad'],
        'relred_census_IPD_paired': G['paired']['census_iplus'], 'relred_census_i_paired': G['paired']['census_i_nc'],
        'relred_slips_i_paired': G['paired']['slip_i_nc'],
        'false_repairs_valid_calls_altered': {'IPD': fr['iplus_changed_valid'], 'i': fr['i_changed_valid'],
                                              'ii': fr['ii_changed_valid'], 'n_valid': fr['n_valid'], 'wilson95_i': fr['wilson95_i']},
        'natural_subset': {k: res['replays']['v3_r31_on_june']['natural'][k] for k in ('base_census_bad', 'iplus_census_bad')}
                          | {'relred_census_IPD_paired': res['replays']['v3_r31_on_june']['natural']['paired']['census_iplus']},
        'status': 'FINAL'}
GO = res['replays'].get('v3_r31_off_june', {}).get('all')
if GO:
    fro = GO['false_repair_real']
    res['gate_31b_think_off_final'] = {
        'source': 'out/v3_r31_off_june.jsonl', 'template': 'june (log-faithful)', 'thinking': False, 'temperature': 0.2,
        'contexts_requested': 300, 'samples_per_context': 2, 'n_calls': GO['n_edit_calls'], 'no_call': GO['status'].get('no_call', 0),
        'forced_edits': GO['forced_edit'], 'baseline_closer_slips': GO['base_slip'], 'baseline_census_malformed': GO['base_census_bad'],
        'after_IPD_census_malformed': GO['iplus_census_bad'], 'relred_census_IPD_paired': GO['paired']['census_iplus'],
        'relred_census_i_paired': GO['paired']['census_i_nc'], 'relred_slips_i_paired': GO['paired']['slip_i_nc'],
        'false_repairs_valid_calls_altered': {'IPD': fro['iplus_changed_valid'], 'n_valid': fro['n_valid'], 'wilson95_i': fro['wilson95_i']},
        'status': 'FINAL'}
H = res['head2head'].get('v3_r31_on_june')
if H:
    names = {'5_IPD': 'IPD (i+)', '4_i_max': '(i)-max', '3_T1_text_only': 'T1 text-only longest-closer',
             '6_ii_tau': '(ii) tau=2', '7_retry_x2': 'retry x2 (T=0.2), loud fallback', '7b_retry_x2_lenient': 'retry x2 (T=0.2), lenient fallback',
             '8_greedy': 'greedy (T=0)', '9_forbid': 'forbid-trigger (one-step ban after <look-alike>,)',
             '9b_forbid_strict': 'forbid-trigger strict (ban at key start)', '10_grammar_CD': 'grammar-constrained decoding (exact emulation)',
             '1_lenient': 'lenient (status quo)', '2_fail_loud': 'strict fail-loud'}
    res['head2head_31b_think_on_slips'] = {
        'source': 'out/v3_r31_on_june.jsonl (+ out/h2h_v3_r31_on_june.jsonl for 9b)', 'n_slips': H['n_slips'], 'n_samples': H['n_samples'],
        'definitions': {'clean': 'delivered and strictly valid, no look-alike+key text', 'loud': 'nothing delivered (error raised)',
                        'delivered_malformed': 'census criterion on the delivered call',
                        'silent_corruption': 'delivered and accepted by the runtime but strict-invalid or carrying look-alike+key text'},
        'decoders': {names.get(a, a): {'clean': t['clean'], 'loud': t['loud'], 'delivered_malformed': t['malformed'],
                                        'silent_corruption': t['silent']} for a, t in H['slips'].items()}}
    allt = H['all']
    res['retry_lenient_all_calls'] = {'n_calls': H['n_samples'],
                                      'retry_x2_lenient_delivered_malformed': allt['7b_retry_x2_lenient']['malformed'],
                                      'retry_x2_loudfallback_loud': allt['7_retry_x2']['loud'],
                                      'IPD_delivered_malformed': allt['5_IPD']['malformed'], 'IPD_loud': allt['5_IPD']['loud'],
                                      'lenient_status_quo_delivered_malformed': allt['1_lenient']['malformed']}
rp = os.path.join(OUT, 'rs279_31b.jsonl')
if os.path.exists(rp) and os.path.getsize(rp) > 0:
    rr = RS.summarize(rp)
    res['gold_retry_subset'] = {
        'selection_rule': ("records of workstream C's corpus (slips/release/gemma4_slips.jsonl) with intent_from_retry "
                           "(old_string recovered from a later clean retry with the same filepath and new_string == payload "
                           "before the look-alike closer), restricted to model_family == 'base' and run_status == 'ok'"),
        'n_corpus_with_retry_intent': 279, 'n_base_selected': 229, 'n_excluded_team_finetune': 50,
        'gold_cut_whole_lookalike_run': 219, 'gold_cut_partial_composite_run': 10,
        'n_evaluated': rr['n'], 'status': 'FINAL' if rr['n'] >= 229 else f"INTERIM ({rr['n']}/229)",
        'note': ('IPD/(i)-max/retry/greedy/forbid/grammar run from the exact logged prefix; T1 and (ii) are scored on an '
                 'ASSUMED tail (retry old_string), because the emitted tail was lost at serving time'),
        'per_decoder': {a: {k: t[k] for k in ('exact_intent', 'new_exact', 'old_exact', 'strict_valid', 'silent_corruption')}
                        for a, t in rr['all'].items()},
        'by_temperature': {T: {a: t['exact_intent'] for a, t in rr[T].items()} for T in ('T=0.2', 'T=0.7') if rr.get(T)}}
# --- thinking-OFF manipulation check: a thought channel is still emitted with enable_thinking=False
def _thought_stats(path):
    import statistics
    n = k = 0; L = []
    for l in open(path):
        r = json.loads(l)
        if r.get('status') != 'call':
            continue
        n += 1
        t = r.get('A_text') or ''
        if '<|channel>thought' in t:
            k += 1
            L.append(len(t.split('<|channel>thought', 1)[1].split('<channel|>')[0]))
    return {'call_samples': n, 'with_thought_channel': {'k': k, 'n': n, 'rate': k / n if n else None, 'wilson95': wilson(k, n)},
            'median_thought_chars': statistics.median(L) if L else None}


res['thinking_off_manipulation_check'] = {
    'june_off': _thought_stats(os.path.join(OUT, 'v3_r31_off_june.jsonl')),
    'july_off': _thought_stats(os.path.join(OUT, 'v2_r31_off_july.jsonl')),
    'june_on': _thought_stats(os.path.join(OUT, 'v3_r31_on_june.jsonl')),
    'history_note': ('OFF prompts carry no <|think|> flag, but 298/300 OFF contexts render earlier logged (thinking-ON) '
                     'thoughts into the history; a thought is emitted in 579/583 samples of those contexts and 4/4 of the 2 '
                     'contexts without (render check 2026-11-04 17:28 UTC, progress.md)')}
# --- confirmatory run (PREREG_v2 §3.2, frozen confirm/ package, workstream P's corpus)
def _conf(name):
    pth = os.path.join(OUT, f'confirm_{name}_analysis.json')
    if not os.path.exists(pth):
        return None
    A = json.load(open(pth))['full']
    t = A['C15_head_to_head_on_slips']
    return {'n_states': A['n_states'], 'status': A['status'], 'n_calls': A['n_calls'], 'forced': A['forced'],
            'C12_census_malformed': A['C12_census_malformed'], 'C13_IPD_relred_malformed': A['C13_IPD_relred_malformed'],
            'C14_byte_identity': {k: A['C14_byte_identity'][k] for k in ('valid_calls', 'changed', 'changed_cases', 'verdict')},
            'C15_head_to_head_on_slips': {'n_slips': t['n_slips'], 'table': t['table'], 'verdicts': t['verdicts']},
            'F3c_IPD_vs_baselines_delivered_malformed': A['F3c_IPD_vs_baselines_delivered_malformed']}


if os.path.exists(os.path.join(OUT, 'confirm_S1_B1_analysis.json')):
    s1 = _conf('S1_B1')
    lo, hi = s1['C12_census_malformed']['all']['wilson95']
    res['confirmatory_PREREG_v2'] = {
        'status': 'FINAL',
        'prereg': 'PREREG_v2 sha256 5da75e6170243f838fe0fe1dcb4250a21b8132fc97161e22d149f46fae0d73ac, §3.2 (C12-C16), F3c Holm',
        'frozen_package': {'path': 'confirm/', 'combined_sha256': '2ee89869735ea76514908f0a3626c362bfd58ec93de40ab608536cee4a84e2b0',
                           'frozen_utc': '2026-11-04T15:45Z', 'hashes_reverified_utc': '2026-11-05T07:03Z'},
        'pools': {'manifest': 'contagion/data/confirmatory/pools/POOLS_MANIFEST.json', 'applied_utc': '2026-11-05 07:02:24',
                  'S1_B1': 600, 'S1_B1_verified_only': 236, 'S2_B1': 82},
        'run': {'server': ':8302 gemma-4-31b QAT-ct (vLLM 0.19.1)', 'S1': '07:05-08:42 UTC', 'S2': '08:44-08:53 UTC',
                'sampling': "P's manifest: T=1.0, top_p 0.95, top_k 64, thinking budget 4096 (emulated), max_tokens 8192",
                'template': "P's manifest chat_template.jinja (md5 f016bd4b..., July 2026-07-09), path relative to the manifest; "
                            'the frozen runner was launched with cwd = manifest directory (no code change)',
                'render_check': 'rendered token count == logged prompt_tokens for 600/600 (S1) and 82/82 (S2) states',
                'operational': 'S1 restarted once at 172 records (07:27) to raise workers 10 -> 14 (resumable; same per-context seeds)'},
        'S1_B1_full': s1,
        'C12_descriptive_verdict': {'observed_wilson95': [lo, hi], 'prediction_80PI': [0.06, 0.26],
                                    'verdict': 'CONSISTENT' if (hi >= 0.06 and lo <= 0.26) else ('LOWER' if hi < 0.06 else 'HIGHER')},
        'S1_B1_verified_only': _conf('S1_B1_verified'),
        'S1_B1_rank_halves_posthoc': {'label': 'post-hoc split (PREREG halves defined for A1 only): ranks 1-300 / 301-600',
                                      'H1_r1_300': _conf('S1_B1_H1r1-300'), 'H2_r301_600': _conf('S1_B1_H2r301-600')},
        'S2_B1_separate_stratum': _conf('S2_B1'),
        'C16_IPD_exact_intent_real_P_slips': {
            'k': 0, 'n': 0, 'verdict': 'NOT_ESTIMABLE',
            'reason': ("the frozen confirm_gold.py found 0 S1 B1 states whose logged first edit is a new_string closer slip with "
                       "a later clean retry of the same file_path and new_string == payload (the registered G1 rule). Not a "
                       "missing-field artifact by documentation: CONTEXT_SCHEMA §3 lists outcomes.raw_response_text; P's "
                       "build_contexts.py writes it from raw_completion and P's integrity.py requires raw_completion non-empty; "
                       "outcomes.jsonl exists (17.5 MB). Field presence was not checked by opening outcomes (PI: docs and file "
                       "existence only). Expected slips at B1 are few (base onset 2.2% x 600 ~ 13) before the retry-match filter.")}}
for _key, _path in (('prereg_v24_injected_slip_battery', os.path.join(HERE, 'v24/battery_run_analysis.json')),
                    ('prereg_v25_stack_gain', os.path.join(HERE, 'v25/out/analysis_v25.json')),
                    ('prereg_v25b_stack_gain_e4b', os.path.join(HERE, 'v25b/out/analysis_v25b.json'))):
    if os.path.exists(_path):
        _A = json.load(open(_path))
        res[_key] = {'source': os.path.relpath(_path, HERE), 'status': 'FINAL', **_A}
pe = os.path.join(OUT, 'proxy_equivalence.json')
if os.path.exists(pe):
    P = json.load(open(pe))
    res['proxy_equivalence'] = {'source': 'out/proxy_equivalence.json (proxy_equivalence.py analyze)',
                                'generated_utc': P.get('generated_utc'), 'code': P.get('code'),
                                'findings': {k: {kk: vv for kk, vv in v.items() if not kk.startswith(('p1e_', 'p1_', 'decode_time'))}
                                             for k, v in (P.get('findings') or {}).items()},
                                'P1_byte_identity': {k: v for k, v in ((P.get('findings') or {}).get('F2_P1_byte_identity') or {}).items()
                                                     if k.startswith(('p1e_', 'decode_time'))},
                                'offline_deterministic_prefix': {k: v for k, v in (P.get('offline_deterministic_prefix') or {}).items()
                                                                 if k in ('valid_calls_changed', 'slips', 'render')},
                                'offline_deterministic_postfix': P.get('offline_deterministic_postfix'),
                                'tf_gate': P.get('tf_gate'), 'tf_g1': P.get('tf_g1'), 'live_http': P.get('live_http')}
json.dump(res, open(os.path.join(HERE, 'results.json'), 'w'), indent=1, default=str)
print('wrote results.json:', {k: (list(v.keys()) if isinstance(v, dict) else v) for k, v in res.items() if k not in ('notes', 'data_fix')})
