"""PREREG_v2.5b (E4B; sha256 c78e7512...) -- v2.5 analysis (b9cc42d2...) restricted to F1/R1 on E4B. Diffs: imports the
E4B glue; C1 = A's rCe4b_v2.jsonl; no F2/F3 (O23 not loaded); the confirmatory family is H1-E4B alone (alpha 0.05, no
Holm across families); verdict labels and the paper sentence follow PREREG_v2.5b §5.
PREREG_v2.5 (stack gain; sha256 50f8a395...) -- FROZEN ANALYSIS (sha256 logged in PROGRESS.md before any v2.5 output is
opened).  usage: analyze_v25.py [--primary R1|L1] [--B 4000] [--out v25/out/analysis_v25.json]

Classification (PREREG_v2.5 §2), per state, on the next turn's first call as the stack DELIVERS it:
  STOCK (A's logged emission, vLLM lenient):  harmful = first call is an edit and A's judge flags it malformed
          (+ in F2: string-mode drift, v2.3 definition); clean = edit, no flag (no drift); no_edit otherwise.
  SLIPGUARD (B's IPD on the base emission, then slipguard's strict parse):
          loud     = the first call is an edit (by name) and the strict parser refuses the delivered text;
          harmful  = delivered (strictly valid) edit that A's judge flags (silent corruption), or F2 drift;
          clean    = delivered edit, no flag, no drift;  no_edit = otherwise (no call, or a non-edit call).
H1 (F1): P(harmful) per state, STOCK P1 (C1) vs SLIPGUARD (R1 replay of C1 P8a, or L1 under the switch rule);
H2a (F2 drift, unconditional per state) and H2b (F2 closer-slip harmful), STOCK O1 vs SLIPGUARD (O0 replay);
H3 (F3): thought opened ('<|channel>' then 'thought' within 32 tokens), STOCK vs GUARDED template.
Tests: exact one-sided McNemar on discordant pairs; Holm over {H1, H2a, H2b, H3}.  CIs: episode-cluster bootstrap
(B resamples, percentile, seed 20261105) for RDs / relative reduction; Wilson for single rates.
No-harm: N1 (CPU), N2 (within-sample C14 on every replay + live sample), N3 (P0 RD point <= 0 and CI_hi <= +1 pp),
N4 (P0 loud, descriptive).  Parser disagreements (slipguard strict vs B's is_valid) are counted, never reclassify.
"""
import argparse, collections, json, math, os, random, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv_saved = list(sys.argv); sys.argv = [sys.argv[0], 'cpu']        # stack_runner parses no args at import
sys.path.insert(0, HERE)
import stack_runner_e4b as SR  # noqa: E402   (A's judge / pathway builder, B's frozen protocol, slipguard; no generation)
sys.argv = sys.argv_saved
AGP, BGP = SR.AGP, SR.BGP
OUT = SR.OUTD
A_DIR = SR.A_DIR
OPEN_RE = re.compile(r'<\|channel>\s*thought')


def W(k, n, z=1.959963984540054):
    if n == 0:
        return {'k': k, 'n': n, 'rate': None, 'wilson95': [None, None]}
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {'k': k, 'n': n, 'rate': p, 'wilson95': [max(0.0, c - h), min(1.0, c + h)]}


def mcnemar_one_sided(b, c):
    """H: the first arm has MORE events than the second; b = first-only, c = second-only. P(X >= b), X~Bin(b+c, 1/2)."""
    n = b + c
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(b, n + 1)) / 2 ** n


def holm(pv):
    order = sorted(pv.items(), key=lambda kv: kv[1]); m = len(order); out = {}; run = 0.0
    for i, (k, p) in enumerate(order):
        run = max(run, min(1.0, (m - i) * p)); out[k] = run
    return out


def boot(rows, stat, B, seed=20261105):
    cl = collections.defaultdict(list)
    for r in rows:
        cl[r['episode']].append(r)
    cls = list(cl.values()); rng = random.Random(seed); vals = []
    for _ in range(B):
        s = [x for _ in cls for x in cls[rng.randrange(len(cls))]]
        v = stat(s)
        if v is not None and v == v:
            vals.append(v)
    vals.sort()
    if not vals:
        return [None, None]
    return [vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]]


def is_edit_j(j):
    return bool(j.get('is_edit', j.get('name') == AGP.PROFILE['edit_tool']))


NATIVE = {}


def native_text(cid):
    if cid not in NATIVE:
        msgs, _ = SR.ctx(cid)
        NATIVE[cid] = '\n'.join(x['content'] for x in msgs if x['role'] == 'tool' and isinstance(x.get('content'), str))
    return NATIVE[cid]


def drift_of(call_text, cid):
    m = AGP.TOOL_CALL_RE.search('<|tool_call>' + (call_text or '') + '<tool_call|>')
    args = AGP.parse_args(m.group(2)) if m else {}
    nat = native_text(cid)
    for k in (AGP.PROFILE['new_key'], AGP.PROFILE['old_key']):
        v = args.get(k)
        if isinstance(v, str) and (('\\n' in v and '\\n' not in nat) or ('\\"' in v and '\\"' not in nat)):
            return 1
    return 0


def stock_class(d, f2=False):
    if d is None or d.get('error'):
        return None
    j = d.get('judge') or {}
    if not d.get('opened_call') or not is_edit_j(j):
        return {'cls': 'no_edit', 'harmful': 0, 'edit': 0, 'drift': 0, 'closer_slip': 0, 'closer': None}
    dr = drift_of(d.get('s2_text'), d['id']) if f2 else 0
    mal = bool(j.get('malformed'))
    return {'cls': 'harmful' if (mal or dr) else 'clean', 'harmful': int(mal or bool(dr)), 'edit': 1, 'drift': dr,
            'closer_slip': int(j.get('closer') is not None), 'closer': j.get('closer')}


def sg_class(r, f2=False):
    """r: replay/live record (status ok | no_call)."""
    if r is None or r.get('status') not in ('ok', 'no_call'):
        return None
    if r['status'] == 'no_call':
        return {'cls': 'no_edit', 'harmful': 0, 'edit': 0, 'loud': 0, 'drift': 0, 'closer_slip': 0}
    jf = AGP.judge(r['final_text'], bool(r['final_finished']))
    if not is_edit_j(jf):
        return {'cls': 'no_edit', 'harmful': 0, 'edit': 0, 'loud': 0, 'drift': 0, 'closer_slip': 0}
    if not r['strict_sg']:
        return {'cls': 'loud', 'harmful': 0, 'edit': 1, 'loud': 1, 'drift': 0, 'closer_slip': 0}
    dr = drift_of(r['final_text'], r['id']) if f2 else 0
    mal = bool(jf.get('malformed'))
    return {'cls': 'harmful' if (mal or dr) else 'clean', 'harmful': int(mal or bool(dr)), 'edit': 1, 'loud': 0,
            'drift': dr, 'closer_slip': int(mal and jf.get('closer') is not None)}


def n2_violation(r, base_judge_malformed):
    """C14 within-sample: valid base -> byte-identical; any change only at a call A's judge flags malformed."""
    if r is None or r.get('status') != 'ok':
        return None
    if r['base_strictly_valid_B'] and (r['ipd_changed'] or r['final_text'] is None):
        return 'valid_base_changed'
    if r['ipd_changed'] and not base_judge_malformed:
        return 'intervention_on_unflagged_call'
    return None


def load(path, key):
    out = {}
    if os.path.exists(path):
        for l in open(path):
            try:
                d = json.loads(l)
            except Exception:
                continue
            out[key(d)] = d
    return out


def paired_block(rows, B, label_a='STOCK', label_b='SLIPGUARD', field='harmful'):
    n = len(rows)
    ka = sum(r['a'][field] for r in rows); kb = sum(r['b'][field] for r in rows)
    b = sum(1 for r in rows if r['a'][field] and not r['b'][field]); c = sum(1 for r in rows if r['b'][field] and not r['a'][field])
    rd = (kb - ka) / n if n else None
    rr = (1 - kb / ka) if ka else None
    return {'n_states': n, label_a: W(ka, n), label_b: W(kb, n), 'discordant_' + label_a + '_only': b,
            'discordant_' + label_b + '_only': c, 'mcnemar_one_sided_p': mcnemar_one_sided(b, c),
            'RD_' + label_b + '_minus_' + label_a: rd,
            'RD_ci95': boot(rows, lambda s: (sum(x['b'][field] for x in s) - sum(x['a'][field] for x in s)) / len(s) if s else None, B),
            'relative_reduction': rr,
            'relative_reduction_ci95': boot(rows, lambda s: (1 - sum(x['b'][field] for x in s) / sum(x['a'][field] for x in s))
                                            if sum(x['a'][field] for x in s) else None, B)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--primary', default='R1', choices=['R1', 'L1'])
    ap.add_argument('--B', type=int, default=4000)
    ap.add_argument('--out', default=os.path.join(OUT, 'analysis_v25b.json'))
    a = ap.parse_args()
    res = {'prereg': 'PREREG_v2.5b_stackGainE4B.md sha256 c78e7512485a6f3e98e2fd71f319638aa72ff10f2eb5f6deedc89415a94ffb7d (copies v2.5 F1)',
           'F1_primary_source': a.primary}
    cpu = json.load(open(os.path.join(OUT, 'cpu_checks.json')))
    res['cpu_checks'] = cpu['summary']
    ident = {x['id'] for x in cpu['detail']['r1_identity'] if x.get('identical')}
    i2 = {x['id'] for x in cpu['detail']['i2'] if x.get('identical')}
    ep_a1 = {r['context_id']: r['episode_id'] for r in SR.A1}
    ep_b1 = {r['context_id']: r.get('episode_id', r['context_id']) for r in SR.B1}
    C1 = load(os.path.join(A_DIR, 'out/main/rCe4b_v2.jsonl'), lambda d: (d.get('id'), d.get('pathway'), d.get('k')))
    O23 = {}   # v2.5b: no F2
    RP = load(os.path.join(OUT, 'replay.jsonl'), lambda d: (d['id'], d['pathway']))
    L1 = load(os.path.join(OUT, 'live_l1.jsonl'), lambda d: d['id'])
    LF2 = load(os.path.join(OUT, 'live_f2.jsonl'), lambda d: d['id'])
    res['replay_status'] = dict(collections.Counter((k[1], d.get('status')) for k, d in RP.items()))
    res['replay_status'] = {f'{k[0]}|{k[1]}': v for k, v in res['replay_status'].items()}
    res['parser_disagreements'] = {
        'replay': sum(1 for d in RP.values() if d.get('parser_disagreement')),
        'live_l1': sum(1 for d in L1.values() if d.get('parser_disagreement')),
        'cases': [(d['id'], d.get('pathway', 'L1'), d.get('strict_sg_why')) for d in list(RP.values()) + list(L1.values())
                  if d.get('parser_disagreement')][:20]}
    # ---------------- F1
    rows_r1, rows_l1, skipped = [], [], collections.Counter()
    for r in SR.A1:
        cid = r['context_id']
        st = stock_class(C1.get((cid, 'P1', 1)))
        if st is None:
            skipped['stock_missing'] += 1; continue
        if cid in ident:
            sg = sg_class(RP.get((cid, 'P8a')))
            if sg is None:
                skipped['r1_missing_or_mismatch'] += 1
            else:
                rows_r1.append({'id': cid, 'episode': ep_a1[cid], 'a': st, 'b': sg})
        else:
            skipped['identity_fails'] += 1
        lv = sg_class(L1.get(cid))
        if lv is not None:
            rows_l1.append({'id': cid, 'episode': ep_a1[cid], 'a': st, 'b': lv})
    res['F1_skipped'] = dict(skipped)
    res['F1_R1'] = paired_block(rows_r1, a.B)
    res['F1_L1_secondary'] = paired_block(rows_l1, a.B) if rows_l1 else {'n_states': 0, 'note': 'not run / no records'}
    for nm, rows in (('F1_R1', rows_r1), ('F1_L1_secondary', rows_l1)):
        if rows:
            n = len(rows)
            res[nm]['SLIPGUARD_loud'] = W(sum(x['b']['loud'] for x in rows), n)
            res[nm]['SLIPGUARD_harmful_plus_loud'] = W(sum(x['b']['harmful'] + x['b']['loud'] for x in rows), n)
            ne_a = sum(x['a']['edit'] for x in rows); ne_b = sum(x['b']['edit'] for x in rows)
            res[nm]['conditional_given_edit'] = {'STOCK': W(sum(x['a']['harmful'] for x in rows), ne_a),
                                                 'SLIPGUARD': W(sum(x['b']['harmful'] for x in rows), ne_b)}
            res[nm]['STOCK_harmful_by_closer'] = dict(collections.Counter(str(x['a']['closer']) for x in rows if x['a']['harmful']))
            res[nm]['class_counts'] = {'STOCK': dict(collections.Counter(x['a']['cls'] for x in rows)),
                                       'SLIPGUARD': dict(collections.Counter(x['b']['cls'] for x in rows))}
    # pre-declared sensitivity (A/D, before outcomes): exclude budget-forced base records (thought cut at 4,096 tokens)
    bf1 = {cid for (cid, pw), d in RP.items() if pw == 'P8a' and d.get('budget_forced')} | \
          {k[0] for k, d in C1.items() if k[1] in ('P1', 'P8a') and d.get('budget_forced')}
    rows_r1_s = [x for x in rows_r1 if x['id'] not in bf1]
    res['F1_R1_sensitivity_excl_budget_forced'] = {'excluded_states': sorted(bf1), **paired_block(rows_r1_s, a.B)}
    prim = res['F1_R1'] if a.primary == 'R1' else res['F1_L1_secondary']
    # ---------------- no-harm
    n1 = cpu['summary']['N1']
    N1_ok = (n1['msgs_identical'] == n1['n'] == 300 and n1['render_identical'] == 300 and not n1['exceptions'])
    viol = []
    for (cid, pw), d in RP.items():
        base = C1.get((cid, pw, 0 if pw == 'P0' else 1)) if pw in ('P8a', 'P0') else O23.get((cid, pw))
        bj = bool(((base or {}).get('judge') or {}).get('malformed'))
        v = n2_violation(d, bj)
        if v:
            viol.append((cid, pw, v))
    for cid, d in L1.items():
        if d.get('status') == 'ok':
            bj = bool(AGP.judge(d['s2_text'], bool(d['base_finished'])).get('malformed'))
            v = n2_violation(d, bj)
            if v:
                viol.append((cid, 'L1', v))
    n2_checked = sum(1 for d in list(RP.values()) + list(L1.values()) if d.get('status') == 'ok')
    rows_p0 = []
    for r in SR.A1:
        cid = r['context_id']
        st = stock_class(C1.get((cid, 'P0', 0))); sg = sg_class(RP.get((cid, 'P0')))
        if st is not None and sg is not None:
            rows_p0.append({'id': cid, 'episode': ep_a1[cid], 'a': st, 'b': sg})
    n3 = paired_block(rows_p0, a.B)
    N3_ok = bool(rows_p0) and (n3['RD_SLIPGUARD_minus_STOCK'] <= 0) and (n3['RD_ci95'][1] is not None and n3['RD_ci95'][1] <= 0.01)
    n4 = W(sum(x['b']['loud'] for x in rows_p0), len(rows_p0))
    res['no_harm'] = {'N1': {'holds': N1_ok, **n1},
                      'N2': {'samples_checked': n2_checked, 'violations': len(viol), 'cases': viol[:30], 'holds': not viol},
                      'N3': {'holds': N3_ok, **n3}, 'N4_P0_loud': {**n4, 'gain_sentence_must_state_it': bool(n4['rate'] and n4['rate'] > 0.02)}}
    # ---------------- F2
    rows_f2, sk2 = [], collections.Counter()
    for r in SR.B1:
        cid = r['context_id']
        if cid not in i2:
            sk2['i2_fails'] += 1; continue
        st = stock_class(O23.get((cid, 'O1')), f2=True); sg = sg_class(RP.get((cid, 'O0')), f2=True)
        if st is None or sg is None:
            sk2['missing'] += 1; continue
        rows_f2.append({'id': cid, 'episode': ep_b1[cid], 'a': st, 'b': sg})
    f2 = {'skipped': dict(sk2), 'I2_identity': cpu['summary']['I2'],
          'drift_unconditional': paired_block(rows_f2, a.B, field='drift'),
          'closer_slip_harmful': paired_block(rows_f2, a.B, field='closer_slip'),
          'total_harmful': paired_block(rows_f2, a.B, field='harmful')}
    ne_a = sum(x['a']['edit'] for x in rows_f2); ne_b = sum(x['b']['edit'] for x in rows_f2)
    f2['drift_among_edits'] = {'STOCK': W(sum(x['a']['drift'] for x in rows_f2), ne_a), 'SLIPGUARD': W(sum(x['b']['drift'] for x in rows_f2), ne_b)}
    f2['SLIPGUARD_loud'] = W(sum(x['b']['loud'] for x in rows_f2), len(rows_f2))
    lf2 = [sg_class(d, f2=True) for d in LF2.values()]
    lf2 = [x for x in lf2 if x is not None]
    f2['live_first100_secondary'] = {'n': len(lf2), 'drift_edits': sum(x['drift'] for x in lf2), 'edits': sum(x['edit'] for x in lf2),
                                     'closer_slips': sum(x['closer_slip'] for x in lf2), 'harmful': sum(x['harmful'] for x in lf2),
                                     'loud': sum(x['loud'] for x in lf2)}
    bf2 = {k[0] for k, d in O23.items() if d.get('budget_forced')} | {cid for (cid, pw), d in RP.items() if pw == 'O0' and d.get('budget_forced')}
    rows_f2_s = [x for x in rows_f2 if x['id'] not in bf2]
    f2['sensitivity_excl_budget_forced'] = {'excluded_states': sorted(bf2),
                                            'drift_unconditional': paired_block(rows_f2_s, a.B, field='drift'),
                                            'closer_slip_harmful': paired_block(rows_f2_s, a.B, field='closer_slip')}
    res['F2'] = f2
    # ---------------- F3
    F3 = load(os.path.join(OUT, 'f3.jsonl'), lambda d: (d['id'], d['arm']))
    rows_f3, sk3 = [], collections.Counter()
    for r in SR.A1:
        cid = r['context_id']
        s, g = F3.get((cid, 'STOCK')), F3.get((cid, 'GUARDED'))
        if not s or not g or s.get('error') or g.get('error'):
            sk3['missing'] += 1; continue
        if not s.get('last_is_tool'):
            sk3['last_not_tool'] += 1; continue
        rows_f3.append({'id': cid, 'episode': ep_a1[cid], 'a': {'open': int(bool(OPEN_RE.search(s['text'])))},
                        'b': {'open': int(bool(OPEN_RE.search(g['text'])))}})
    f3 = {'skipped': dict(sk3), 'Tcheck': cpu['summary']['Tcheck'], **paired_block(rows_f3, a.B, 'STOCK', 'GUARDED', field='open')}
    res['F3'] = f3
    # ---------------- Holm family
    pv = {'H1': prim['mcnemar_one_sided_p'] if prim.get('n_states') else 1.0}   # v2.5b: H1-E4B only
    hp = holm(pv)
    res['holm'] = {k: {'p': pv[k], 'holm_p': hp[k]} for k in pv}
    # ---------------- verdicts
    rr, rr_ci = prim.get('relative_reduction'), prim.get('relative_reduction_ci95') or [None, None]
    gain_conf = hp['H1'] < 0.05 and rr is not None and rr >= 0.90 and rr_ci[0] is not None and rr_ci[0] >= 0.75
    gain_att = hp['H1'] < 0.05 and rr is not None and rr >= 0.50 and rr_ci[0] is not None and rr_ci[0] > 0
    nh = N1_ok and (not viol) and N3_ok
    v1 = ('STACK GAIN CONFIRMED (E4B)' if gain_conf and nh else 'STACK GAIN ATTENUATED (E4B)' if gain_att and nh else
          'GAIN WITH HARM' if (gain_conf or gain_att) and not nh else 'FAILS')
    # consistency L1 vs R1
    cons = None
    if rows_l1 and rows_r1:
        l1r = res['F1_L1_secondary']['SLIPGUARD']; r1r = res['F1_R1']['SLIPGUARD']
        cons = bool((r1r['wilson95'][0] <= l1r['rate'] <= r1r['wilson95'][1]) or (l1r['rate'] <= 0.01 and r1r['rate'] <= 0.01))
    res['verdicts'] = {'F1_E4B': v1, 'F1_no_harm_holds': nh,
                       'L1_consistent_with_R1': cons,
                       'L1_partial': (len(rows_l1) < 300) if rows_l1 else None}
    res['paper_sentence'] = None
    if prim.get('n_states') and rr is not None and rr_ci[0] is not None:
        p_b = prim['SLIPGUARD']['rate']; c_ = prim['SLIPGUARD_loud']['rate']
        if v1 == 'STACK GAIN CONFIRMED (E4B)':
            res['paper_sentence'] = (f"The same stack carries to Gemma-4-E4B: on the 300 contaminated public states it removes "
                                     f"{100 * rr:.0f}% [{100 * rr_ci[0]:.0f}, {100 * rr_ci[1]:.0f}] of harmful edits "
                                     f"({100 * prim['STOCK']['rate']:.1f}% -> {100 * p_b:.1f}%) and changes no valid call; "
                                     f"{100 * c_:.1f}% of turns become loud refusals.")
        elif v1 == 'STACK GAIN ATTENUATED (E4B)':
            res['paper_sentence'] = f"...reduces harmful edits on E4B by {100 * rr:.0f}% [{100 * rr_ci[0]:.0f}, {100 * rr_ci[1]:.0f}]..."
        else:
            res['paper_sentence'] = 'no cross-size claim; the result goes to the limitations'
    json.dump(res, open(a.out, 'w'), indent=1, default=str)
    print(json.dumps({'verdicts': res['verdicts'], 'holm': res['holm'],
                      'F1_primary': {k: prim.get(k) for k in ('n_states', 'STOCK', 'SLIPGUARD', 'relative_reduction', 'relative_reduction_ci95')},
                      'no_harm': {k: v.get('holds') for k, v in res['no_harm'].items() if isinstance(v, dict)}}, indent=1, default=str))


if __name__ == '__main__':
    main()
