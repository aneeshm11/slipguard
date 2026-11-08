"""PREREG_v2.4 injected-slip repair battery -- FROZEN ANALYSIS (sha256 logged in PROGRESS.md before any data).
usage: analyze_battery.py <run_output.jsonl> [--inputs v24/battery_inputs.jsonl] [--out <json>] [--B 4000]

Arms and delivery (B's semantics, as in the discovery/confirmatory analyses):
  lenient    emission, vLLM 0.19.1 gemma4 parse (lenient delivery)
  fail_loud  emission, delivered only if strictly valid (B's reference parser + schema), else loud
  T1         emission if strictly valid, else the longest-closer text-only reading if complete and valid, else loud
  IPD        rollback/resume result; delivered only if strictly valid, else loud
  grammar_CD arm_grammar result, lenient delivery (always grammatical)
  retry_x2   emission if strictly valid, else the first strictly valid of <= 2 whole-call resamples, else loud
  greedy     arm_greedy result (T=0 from the call head), lenient delivery
Outcomes (mutually exclusive, in this order):
  loud         no call delivered (strict arm and not strictly valid; or nothing)
  exact        delivered arguments byte-equal to gold (every key, no extra key)
  malformed    delivered call malformed under the census judge (A's/E's criterion: vLLM parse, missing required /
               unknown key / look-alike+declared-key leak / special token in a value) or unfinished
  silent       otherwise, and the delivered arguments carry SLIP DAMAGE relative to gold:
               (a) a look-alike(+ws)','(ws)<declared key>':' residue or a special token in a value, more often than in gold;
               (b) a lost / extra / misassigned argument (key sets differ; a value equals another key's gold value;
                   gold old_string inside new_string);
               (c) new_string differs from gold by look-alike characters at the cut: it extends gold by a look-alike
                   character (stray injected closer, doubling or content continuation), or gold extends it by
                   look-alike characters only, or both remainders after the common prefix are look-alike-only
  other_valid  otherwise (a valid call that differs from gold without slip damage, e.g. a resampled edit)
  For the lenient-delivery arms a census-clean delivered call is judged on its delivered arguments (operationalisation
  logged in PREREG_DEVIATIONS.md before data).
Injection mechanics (emission continuation after the injected closer): closer doubling = starts with <|"|>; slip pattern =
  [ws],[ws]<declared key other than new_string>[ws]: or [ws]} or (empty and finished); content continuation = otherwise.
Detectable subset = emission not strictly valid (or unfinished).
Estimation: strata reweighted to BT .865 / DQ .082 / EQ .037 / TB .016 (renormalised over strata present in the subset);
single rates: Wilson (per stratum) and Wilson at Kish effective n (reweighted); contrasts paired by state, episode-cluster
bootstrap (B resamples, percentile 95% CI, one-sided p = (1 + #{D* <= 0})/(B + 1)), Holm over the 12 tests of family F-R.
"""
import argparse, collections, json, math, os, random, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
B_DIR = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(B_DIR, 'confirm'))
from gemma_protocol import D, TC_START, TC_END, schema_from_tools, is_valid, parse_strict, census_judge, repair_candidates  # noqa: E402

CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
STRATA = ['BT', 'DQ', 'EQ', 'TB']
WEIGHT = {'BT': 0.865, 'DQ': 0.082, 'EQ': 0.037, 'TB': 0.016}
ARMS = ['IPD', 'T1', 'lenient', 'fail_loud', 'grammar_CD', 'retry_x2', 'greedy']
BASELINES = ['lenient', 'fail_loud', 'T1', 'grammar_CD', 'retry_x2', 'greedy']
OUTCOMES = ['exact', 'silent', 'other_valid', 'malformed', 'loud']
LA = set('`"\'\\')
SPECIALS = ('<|"|>', '<|tool_call>', '<tool_call|>', '<|channel>', '<channel|>', '<|turn>', '<turn|>', '<|tool_response>')
RESID = re.compile(r'[`"\'\\]+[ \t\r\n]*,[ \t\r\n]*([A-Za-z_][A-Za-z0-9_\-\.]*)[ \t\r\n]*:')
KEYCONT = re.compile(r'[ \t\r\n]*,[ \t\r\n]*([A-Za-z_][A-Za-z0-9_\-\.]*)[ \t\r\n]*:')

MAN = json.load(open(os.path.join(CORPUS, 'manifest.json')))
SCHEMA = schema_from_tools(MAN['tools'])
E = MAN['harness']['edit_tool']
EDIT, PATHK, OLDK, NEWK = E['name'], E['path_key'], E['old_key'], E['new_key']
PROPS = SCHEMA[EDIT]['props']


# ------------------------------------------------------------------------------------------------ per-state judgement
def strictly_valid(text, fin):
    return bool(text is not None and fin and is_valid(text, SCHEMA))


def t1(text, fin):
    if strictly_valid(text, fin):
        return text
    name = parse_strict(text).name
    for c in repair_candidates(text, SCHEMA, finished=fin):
        if all(s_ is not None and cp == s_.cut_positions()[0] for (k, cp, cl), s_ in zip(c.cuts, c.sites)):
            return c.text(name)
    return None


def residue_count(v):
    return sum(1 for m in RESID.finditer(v) if m.group(1) in PROPS) + sum(v.count(s) for s in SPECIALS)


def damage(args, gold):
    if set(args) != set(gold):
        return 'key_set'
    for k, v in args.items():
        if isinstance(v, str) and residue_count(v) > residue_count(gold.get(k) or ''):
            return 'residue'
    for k in gold:
        if args.get(k) != gold[k] and any(args.get(k) == gold[k2] for k2 in gold if k2 != k):
            return 'misassigned'
    go, gn, dn = gold.get(OLDK) or '', gold.get(NEWK) or '', args.get(NEWK) or ''
    if go and go in dn and go not in gn:
        return 'misassigned'
    if dn != gn:
        if dn.startswith(gn) and dn[len(gn)] in LA:
            return 'lookalike_extension'
        if gn.startswith(dn) and set(gn[len(dn):]) <= LA:
            return 'lookalike_truncation'
        cp = 0
        while cp < min(len(dn), len(gn)) and dn[cp] == gn[cp]:
            cp += 1
        if dn[cp:] and gn[cp:] and set(dn[cp:]) <= LA and set(gn[cp:]) <= LA:
            return 'lookalike_swap'
    return None


def classify(text, fin, policy, gold):
    """-> dict(outcome, new_exact, old_exact, damage)"""
    out = {'outcome': 'loud', 'new_exact': False, 'old_exact': False, 'damage': None}
    if text is None:
        return out
    sv = strictly_valid(text, fin)
    if policy == 'strict' and not sv:
        return out
    if fin:
        ok, why, vargs = census_judge(text, SCHEMA, tool=EDIT)
    else:
        ok, why, vargs = False, 'unfinished', {}
    args = parse_strict(text).args() if sv else (vargs or {})
    out['new_exact'] = args.get(NEWK) == gold[NEWK]
    out['old_exact'] = args.get(OLDK) == gold[OLDK]
    if args == gold:
        out['outcome'] = 'exact'
    elif not ok:
        out['outcome'] = 'malformed'
    else:
        dmg = damage(args, gold)
        out['outcome'], out['damage'] = ('silent', dmg) if dmg else ('other_valid', None)
    return out


def mechanics(cont, fin):
    if cont.startswith(D):
        return 'doubling'
    m = KEYCONT.match(cont)
    if (m and m.group(1) in PROPS and m.group(1) != NEWK) or re.match(r'[ \t\r\n]*\}', cont) or (cont == '' and fin):
        return 'slip_pattern'
    return 'content_continuation'


def judge_state(r, x):
    gold = x['gold']
    em, fin = r['emission'], r['live']['finished']
    A = r['arms']
    det = not strictly_valid(em, fin)
    deliv = {'lenient': (em, fin, 'lenient'), 'fail_loud': (em, fin, 'strict'), 'T1': (t1(em, fin), True, 'strict'),
             'IPD': (A['IPD']['text'], A['IPD']['finished'], 'strict'),
             'grammar_CD': (A['grammar_CD']['final_text'], A['grammar_CD']['finished'], 'lenient'),
             'greedy': (A['greedy']['final_text'], A['greedy']['finished'], 'lenient')}
    if not det:
        deliv['retry_x2'] = (em, fin, 'strict')
    else:
        rt = A.get('retry_x2') or {}
        deliv['retry_x2'] = (rt.get('final_text'), True, 'strict')
    res = {a: classify(*deliv[a], gold) for a in ARMS}
    live_tok, live_lat = r['live'].get('tokens') or 0, r['live'].get('latency') or 0.0
    cost = {a: {'tokens': live_tok, 'latency': live_lat} for a in ('lenient', 'fail_loud', 'T1')}
    cost['IPD'] = {'tokens': live_tok + (A['IPD'].get('tokens') or 0), 'latency': live_lat + (A['IPD'].get('latency') or 0.0)}
    cost['grammar_CD'] = {'tokens': live_tok + (A['grammar_CD'].get('tokens') or 0), 'latency': live_lat + (A['grammar_CD'].get('latency') or 0.0)}
    rt = A.get('retry_x2') or {}
    cost['retry_x2'] = {'tokens': live_tok + (rt.get('tokens') or 0), 'latency': live_lat + (rt.get('latency') or 0.0)}
    cost['greedy'] = {'tokens': A['greedy'].get('tokens') or 0, 'latency': A['greedy'].get('latency') or 0.0}
    return {'id': x['context_id'], 'episode': x['episode_id'], 'stratum': x['stratum'], 'detectable': det,
            'mechanics': mechanics(r['live']['continuation'], fin), 'arms': res, 'cost': cost}


# ------------------------------------------------------------------------------------------------ estimators
def wilson(k, n, z=1.959963984540054):
    if n <= 0:
        return [float('nan'), float('nan')]
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / den
    return [max(0.0, c - h), min(1.0, c + h)]


def reweighted(rows, f):
    by = collections.defaultdict(list)
    for r in rows:
        by[r['stratum']].append(f(r))
    ws = {s: WEIGHT[s] for s in STRATA if by.get(s)}
    if not ws:
        return float('nan')
    tot = sum(ws.values())
    return sum(ws[s] / tot * (sum(by[s]) / len(by[s])) for s in ws)


def rate_block(rows, f):
    """per-stratum Wilson + reweighted point with Kish-effective-n Wilson."""
    out = {}
    by = collections.defaultdict(list)
    for r in rows:
        by[r['stratum']].append(1.0 if f(r) else 0.0)
    for s in STRATA:
        v = by.get(s, [])
        out[s] = {'k': int(sum(v)), 'n': len(v), 'rate': (sum(v) / len(v)) if v else None, 'wilson95': wilson(sum(v), len(v))}
    ws = {s: WEIGHT[s] for s in STRATA if by.get(s)}
    if ws:
        tot = sum(ws.values())
        u = []
        for s in ws:
            u += [(ws[s] / tot / len(by[s]), y) for y in by[s]]
        p = sum(w * y for w, y in u)
        neff = 1.0 / sum(w * w for w, _ in u)
        out['reweighted'] = {'rate': p, 'n_eff_kish': neff, 'wilson95_kish': wilson(p * neff, neff), 'n': len(rows)}
    else:
        out['reweighted'] = {'rate': None, 'n_eff_kish': 0, 'wilson95_kish': [float('nan')] * 2, 'n': 0}
    pooled = [1.0 if f(r) else 0.0 for r in rows]
    out['pooled_unweighted'] = {'k': int(sum(pooled)), 'n': len(pooled), 'rate': (sum(pooled) / len(pooled)) if pooled else None,
                                'wilson95': wilson(sum(pooled), len(pooled))}
    return out


class Boot:
    def __init__(self, rows, B, seed=20261105):
        self.rows = rows
        cl = collections.defaultdict(list)
        for r in rows:
            cl[r['episode']].append(r)
        self.clusters = list(cl.values())
        rng = random.Random(seed)
        self.samples = [[self.clusters[rng.randrange(len(self.clusters))] for _ in self.clusters] for _ in range(B)]
        self.B = B

    def contrast(self, subset, g, weighted=True):
        """g(row) -> per-state value (e.g. y_IPD - y_base); subset(row) -> bool. -> point, CI, one-sided p (H: > 0)."""
        est = (lambda rs: reweighted(rs, g)) if weighted else (lambda rs: (sum(g(r) for r in rs) / len(rs)) if rs else float('nan'))
        pt = est([r for r in self.rows if subset(r)])
        vals = []
        for smp in self.samples:
            rs = [r for c in smp for r in c if subset(r)]
            v = est(rs)
            if v == v:
                vals.append(v)
        vals.sort()
        if not vals:
            return {'point': pt, 'ci95': [float('nan')] * 2, 'p_one_sided': float('nan'), 'B_used': 0}
        lo, hi = vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]
        p = (1 + sum(1 for v in vals if v <= 0)) / (len(vals) + 1)
        return {'point': pt, 'ci95': [lo, hi], 'p_one_sided': p, 'B_used': len(vals)}


def holm(pv):
    order = sorted(pv.items(), key=lambda kv: kv[1]); m = len(order); out = {}; run = 0.0
    for i, (k, p) in enumerate(order):
        run = max(run, min(1.0, (m - i) * p)); out[k] = run
    return out


# ------------------------------------------------------------------------------------------------ main
def analyze(rows, B):
    det = lambda r: r['detectable']
    allr = lambda r: True
    res = {'n_states': len(rows), 'n_detectable': sum(r['detectable'] for r in rows),
           'detectable_by_stratum': {s: sum(r['detectable'] for r in rows if r['stratum'] == s) for s in STRATA},
           'n_by_stratum': {s: sum(r['stratum'] == s for r in rows) for s in STRATA}}
    res['mechanics_ITT'] = {m: rate_block(rows, lambda r, m=m: r['mechanics'] == m) for m in ('slip_pattern', 'doubling', 'content_continuation')}
    res['detectable_share_ITT'] = rate_block(rows, det)
    for scope, sel in (('detectable', det), ('ITT', allr)):
        sub = [r for r in rows if sel(r)]
        tab = {}
        for a in ARMS:
            tab[a] = {o: rate_block(sub, lambda r, a=a, o=o: r['arms'][a]['outcome'] == o) for o in OUTCOMES}
            tab[a]['new_string_exact'] = rate_block(sub, lambda r, a=a: r['arms'][a]['new_exact'])
            tab[a]['old_string_exact'] = rate_block(sub, lambda r, a=a: r['arms'][a]['old_exact'])
            tab[a]['damage_types'] = dict(collections.Counter(r['arms'][a]['damage'] for r in sub if r['arms'][a]['outcome'] == 'silent'))
        res['outcomes_' + scope] = tab
    # mutual exclusivity check
    for r in rows:
        for a in ARMS:
            assert r['arms'][a]['outcome'] in OUTCOMES
    # costs
    res['cost_per_arm'] = {a: {'mean_tokens': sum(r['cost'][a]['tokens'] for r in rows) / max(1, len(rows)),
                               'mean_latency_s': sum(r['cost'][a]['latency'] for r in rows) / max(1, len(rows))} for a in ARMS}
    bt = Boot(rows, B)
    y = lambda a, o: (lambda r: 1.0 if r['arms'][a]['outcome'] == o else 0.0)
    # family F-R: 12 one-sided paired tests on the detectable subset, reweighted
    fam, pv = {}, {}
    for b in BASELINES:
        e = bt.contrast(det, lambda r, b=b: y('IPD', 'exact')(r) - y(b, 'exact')(r))
        s_ = bt.contrast(det, lambda r, b=b: y(b, 'silent')(r) - y('IPD', 'silent')(r))
        fam[f'exact_IPD_gt_{b}'] = e; pv[f'exact_IPD_gt_{b}'] = e['p_one_sided']
        fam[f'silent_IPD_lt_{b}'] = s_; pv[f'silent_IPD_lt_{b}'] = s_['p_one_sided']
    hp = holm(pv)
    for k in fam:
        fam[k]['holm_p'] = hp[k]
    res['family_F_R'] = fam
    c = fam['exact_IPD_gt_T1']
    beats = c['holm_p'] < 0.05
    tie = (c['ci95'][0] >= -0.02) and (c['ci95'][1] <= 0.02)
    res['IPD_vs_T1_exact'] = {'contrast_reweighted': c['point'], 'ci95': c['ci95'], 'holm_p': c['holm_p'],
                              'verdict': 'IPD BEATS T1' if beats else ('TIE' if tie else 'INCONCLUSIVE')}
    comp = lambda r: r['detectable'] and r['stratum'] in ('EQ', 'TB')
    ce = bt.contrast(comp, lambda r: y('IPD', 'exact')(r) - y('T1', 'exact')(r), weighted=False)
    cn = bt.contrast(comp, lambda r: float(r['arms']['IPD']['new_exact']) - float(r['arms']['T1']['new_exact']), weighted=False)
    res['secondary_unadjusted'] = {
        'composite_EQ_TB_exact_IPD_minus_T1': {**ce, 'IPD beats T1 on composite closers': bool(ce['ci95'][0] > 0)},
        'composite_EQ_TB_new_string_exact_IPD_minus_T1': {**cn, 'IPD beats T1 on composite closers (new_string)': bool(cn['ci95'][0] > 0)},
        'BT_exact_IPD_minus_T1': bt.contrast(lambda r: r['detectable'] and r['stratum'] == 'BT',
                                             lambda r: y('IPD', 'exact')(r) - y('T1', 'exact')(r), weighted=False),
        'reweighted_new_string_exact_IPD_minus_T1': bt.contrast(det, lambda r: float(r['arms']['IPD']['new_exact']) - float(r['arms']['T1']['new_exact']))}
    # per-claim rules R1-R8 (detectable, reweighted; single-rate CIs = Wilson at Kish n_eff)
    T = res['outcomes_detectable']
    rw = lambda a, o: T[a][o]['reweighted']
    r1 = rw('IPD', 'exact')
    R = {}
    R['R1_IPD_recovers_intent'] = ('REPLICATES' if (r1['rate'] >= 0.85 and r1['wilson95_kish'][0] >= 0.75) else
                                   'ATTENUATED' if r1['rate'] >= 0.60 else 'FAILS')
    r2 = rw('IPD', 'malformed')
    R['R2_IPD_never_malformed'] = 'REPLICATES' if (r2['rate'] <= 0.01 and r2['wilson95_kish'][1] <= 0.03) else 'FAILS'
    r3 = rw('IPD', 'silent')
    R['R3_IPD_no_silent_on_detectable'] = ('REPLICATES' if (r3['rate'] <= 0.02 and r3['wilson95_kish'][1] <= 0.05) else
                                           'ATTENUATED' if r3['rate'] <= 0.05 else 'FAILS')
    r4 = rw('grammar_CD', 'silent')
    R['R4_grammarCD_corrupts_silently'] = ('REPLICATES' if (r4['rate'] >= 0.80 and r4['wilson95_kish'][0] >= 0.60) else
                                           'ATTENUATED' if r4['rate'] >= 0.50 else 'FAILS')
    r5 = reweighted([r for r in rows if r['detectable']], lambda r: 1.0 if r['arms']['lenient']['outcome'] in ('malformed', 'silent') else 0.0)
    R['R5_lenient_malformed_or_corrupted'] = {'rate': r5, 'verdict': 'REPLICATES' if r5 >= 0.80 else ('ATTENUATED' if r5 >= 0.50 else 'FAILS')}
    fl = [r for r in rows if r['detectable'] and r['arms']['fail_loud']['outcome'] != 'loud']
    R['R6_fail_loud_always_loud'] = {'verdict': 'REPLICATES' if not fl else 'FAILS', 'defect_case_ids': [r['id'] for r in fl]}
    r7 = rw('retry_x2', 'exact')
    R['R7_retry_rarely_recovers'] = 'REPLICATES' if r7['rate'] <= 0.35 else 'FAILS'
    r8 = rw('greedy', 'exact')
    R['R8_greedy_rarely_recovers'] = 'REPLICATES' if r8['rate'] <= 0.60 else 'FAILS'
    res['rules'] = R
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_output')
    ap.add_argument('--inputs', default=os.path.join(HERE, 'battery_inputs.jsonl'))
    ap.add_argument('--out', default=None)
    ap.add_argument('--B', type=int, default=4000)
    a = ap.parse_args()
    X = {}
    for l in open(a.inputs):
        x = json.loads(l)
        X[x['context_id']] = x
    st = collections.Counter(); rows = []
    for l in open(a.run_output):
        r = json.loads(l)
        st[r.get('status')] += 1
        if r.get('status') == 'ok' and r['context_id'] in X:
            rows.append(judge_state(r, X[r['context_id']]))
    res = {'prereg': 'PREREG_v2.4_injectedSlipRepair.md sha256 e7af894ba355a03a5fb7b023c3c7ad860a5e8c3d666a4ab80e6ff6c7ea102090',
           'run_status': dict(st), 'n_inputs': len(X), 'missing_states': len(X) - len(rows), **analyze(rows, a.B)}
    dst = a.out or a.run_output.replace('.jsonl', '_analysis.json')
    json.dump(res, open(dst, 'w'), indent=1, default=str)
    with open(dst.replace('.json', '_states.jsonl'), 'w') as fo:
        for r in rows:
            fo.write(json.dumps(r, default=str) + '\n')
    T = res['outcomes_detectable']
    print(json.dumps({'states': res['n_states'], 'detectable': res['n_detectable'], 'run_status': res['run_status'],
                      'IPD_exact_rw': T['IPD']['exact']['reweighted']['rate'], 'T1_exact_rw': T['T1']['exact']['reweighted']['rate'],
                      'IPD_vs_T1': res['IPD_vs_T1_exact'], 'rules': res['rules']}, indent=1, default=str))


if __name__ == '__main__':
    main()
