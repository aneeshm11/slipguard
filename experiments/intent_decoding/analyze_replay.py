"""Summarize real-context replays: baseline vs (i) rollback/resume vs (ii) likelihood repair.
usage: python analyze_replay.py out/r31_off_s0.jsonl [contexts.jsonl] [--tau 1.0]"""
import json, sys, os, collections, math, statistics, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import (first_slip_site, first_opener_site, schema_from_tools, is_valid, parse_strict, census_judge, D)
from stats import wilson, cluster_bootstrap

TOOLS = json.load(open(os.path.join(HERE, 'data/tools_official.json')))
PRIOR_ON = True
_TK = None
S = schema_from_tools(TOOLS)


def haystack(msgs):
    parts = []
    def walk(x):
        if isinstance(x, str):
            parts.append(x)
            try:
                y = json.loads(x)
                if not isinstance(y, str):
                    walk(y)
            except Exception:
                pass
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for m in msgs:
        walk(m.get('content'))
    return '\n'.join(parts)


def key_order(text):
    sp = parse_strict(text)
    ks = re.findall(r'(?:\{|,)(filepath|new_string|old_string|allow_multiple):', text)
    if 'new_string' in ks and 'old_string' in ks:
        return 'new_first' if ks.index('new_string') < ks.index('old_string') else 'old_first'
    if 'new_string' in ks:
        return 'new_first'
    if 'old_string' in ks:
        return 'old_first'
    return 'none'


def outcome(rec, tau):
    """per-record flags for baseline / (i) noisy-channel / (i) max / (ii) at threshold tau"""
    b = rec['base']
    slip_b = rec.get('site') is not None
    out = {'base_census_bad': not b['census_ok'], 'base_strict_bad': not b['strict_valid'], 'base_slip': slip_b,
           'base_silent': b['census_ok'] and not b['strict_valid']}
    for arm in ('i_nc', 'i_max'):
        r = rec.get(arm)
        if arm == 'i_max' and r == 'same':
            r = rec.get('i_nc')
        if r is None or not slip_b:
            out[arm + '_census_bad'] = out['base_census_bad']; out[arm + '_strict_bad'] = out['base_strict_bad']
            out[arm + '_slip'] = slip_b; out[arm + '_changed'] = False
            continue
        j = r['judge']
        out[arm + '_census_bad'] = not j['census_ok']
        out[arm + '_strict_bad'] = not j['strict_valid']
        out[arm + '_slip'] = first_slip_site(r['text'], S, finished=r['finished']) is not None
        out[arm + '_changed'] = r['changed']
    ip = rec.get('i_plus')
    fin = ip if ip else (rec.get('i_nc') if slip_b else None)
    if fin is None:
        out['iplus_census_bad'] = out['base_census_bad']; out['iplus_strict_bad'] = out['base_strict_bad']
        out['iplus_slip'] = slip_b; out['iplus_changed'] = False
    else:
        out['iplus_census_bad'] = not fin['judge']['census_ok']; out['iplus_strict_bad'] = not fin['judge']['strict_valid']
        out['iplus_slip'] = first_slip_site(fin['text'], S, finished=fin['finished']) is not None
        out['iplus_changed'] = fin['changed']
    ipp = rec.get('_ipp')
    if ipp is None:
        out['ipp_census_bad'] = out['iplus_census_bad']; out['ipp_strict_bad'] = out['iplus_strict_bad']
    else:
        out['ipp_census_bad'] = not ipp['judge']['census_ok']; out['ipp_strict_bad'] = not ipp['judge']['strict_valid']
    ii = rec.get('ii')
    if ii is not None and ii.get('cands') and 'll' in ii['cands'][0]:
        use_prior = PRIOR_ON
        adj = [c['ll'] + (c['prior'] if use_prior else 0.0) for c in ii['cands']]
        order = sorted(range(len(adj)), key=lambda i: -adj[i])
        m = adj[order[0]] - adj[order[1]] if len(adj) > 1 else math.inf
        ii = dict(ii); ii['margin'] = m; ii['judge'] = ii.get('judge') if order[0] == ii.get('best') else None
        ii['_best_text'] = ii['cands'][order[0]]['text']
    if ii is None or ii.get('decision') in (None, 'identity'):
        out['ii_census_bad'] = out['base_census_bad']; out['ii_strict_bad'] = out['base_strict_bad']
        out['ii_slip'] = slip_b; out['ii_changed'] = False; out['ii_abstain'] = False
    else:
        cands = ii.get('cands') or []
        margin = ii.get('margin')
        margin = math.inf if margin is None or margin == 'inf' else margin
        if not cands or margin < tau:
            out['ii_census_bad'] = out['base_census_bad']; out['ii_strict_bad'] = out['base_strict_bad']
            out['ii_slip'] = slip_b; out['ii_changed'] = False; out['ii_abstain'] = True
        else:
            j = ii['judge']
            if j is None:   # offline decision differs from the logged one -> judge the offline argmax
                ok, why, _ = census_judge(ii['_best_text'], S)
                j = {'census_ok': ok, 'strict_valid': is_valid(ii['_best_text'], S)}
            out['ii_census_bad'] = not j['census_ok']; out['ii_strict_bad'] = not j['strict_valid']
            out['ii_slip'] = False; out['ii_changed'] = True; out['ii_abstain'] = False
    return out


def summarize(path, ctx_path=None, tau=1.0, B=2000, subset=None):
    recs = [json.loads(l) for l in open(path)]
    ipp_path = path.replace('/v2_r', '/v2_ipp_r')
    IPP = {}
    if ipp_path != path and os.path.exists(ipp_path):
        for l in open(ipp_path):
            d = json.loads(l)
            if d.get('status') == 'ok':
                IPP[(d['id'], d['seed'], d.get('sample', 0))] = d['i_pp']
    for r in recs:
        r['_ipp'] = IPP.get((r.get('id'), r.get('seed'), r.get('sample', 0)))
    if subset == 'natural':
        recs = [r for r in recs if not r.get('forced')]
    elif subset == 'forced':
        recs = [r for r in recs if r.get('forced')]
    st = collections.Counter(r['status'] for r in recs)
    calls = [r for r in recs if r['status'] == 'call' and r.get('tool') == 'edit_file']
    for r in calls:
        r['_o'] = outcome(r, tau)
    by_ctx = collections.defaultdict(list)
    for r in calls:
        by_ctx[r['id']].append(r)
    clusters = list(by_ctx.values())
    res = {'file': os.path.basename(path), 'ipp_records': len(IPP), 'status': dict(st), 'n_edit_calls': len(calls), 'n_contexts': len(clusters),
           'natural_edit': sum(not r.get('forced') for r in calls), 'forced_edit': sum(bool(r.get('forced')) for r in calls),
           'tau': tau,
           'ii_not_run_on_invalid': sum(1 for r in calls if not r['base']['strict_valid'] and r['finished'] and 'ii' not in r)}
    def rate(key):
        k = sum(r['_o'][key] for r in calls); n = len(calls)
        pt, lo, hi = cluster_bootstrap(clusters, lambda xs: sum(x['_o'][key] for x in xs) / max(len(xs), 1), B=B)
        return {'k': k, 'n': n, 'rate': k / max(n, 1), 'wilson95': wilson(k, n), 'cluster_boot95': [lo, hi]}
    for key in ('base_census_bad', 'base_strict_bad', 'base_slip', 'base_silent',
                'i_nc_census_bad', 'i_nc_strict_bad', 'i_nc_slip',
                'i_max_census_bad', 'i_max_strict_bad', 'i_max_slip',
                'ii_census_bad', 'ii_strict_bad', 'ii_slip', 'ii_abstain', 'iplus_census_bad', 'iplus_strict_bad', 'iplus_slip',
                'ipp_census_bad', 'ipp_strict_bad'):
        res[key] = rate(key)
    def relred(before, after):
        def f(xs):
            b = sum(x['_o'][before] for x in xs)
            a = sum(x['_o'][after] for x in xs)
            return 1 - a / b if b else float('nan')
        pt, lo, hi = cluster_bootstrap(clusters, f, B=B)
        return {'point': pt, 'boot95': [lo, hi]}
    def paired(before, after):
        """paired residual: samples positive after repair (incl. new positives) / samples positive before.
        relative reduction = 1 - residual; Wilson CI on the residual (exact handling of zero residual events)."""
        b = sum(r['_o'][before] for r in calls)
        stay = sum(r['_o'][before] and r['_o'][after] for r in calls)
        new_pos = sum((not r['_o'][before]) and r['_o'][after] for r in calls)
        k = stay + new_pos
        lo, hi = wilson(min(k, b), b) if b else (float('nan'), float('nan'))
        return {'before': b, 'still_positive': stay, 'new_positive': new_pos,
                'relred_point': (1 - k / b) if b else None, 'relred_wilson95': [1 - hi, 1 - lo] if b else None}
    res['paired'] = {
        'slip_i_nc': paired('base_slip', 'i_nc_slip'), 'census_i_nc': paired('base_census_bad', 'i_nc_census_bad'),
        'census_iplus': paired('base_census_bad', 'iplus_census_bad'), 'slip_ii': paired('base_slip', 'ii_slip'),
        'census_ii': paired('base_census_bad', 'ii_census_bad'), 'strict_iplus': paired('base_strict_bad', 'iplus_strict_bad'),
        'census_ipp': paired('base_census_bad', 'ipp_census_bad'), 'strict_ipp': paired('base_strict_bad', 'ipp_strict_bad'),
        'slip_i_max': paired('base_slip', 'i_max_slip')}
    res['relred'] = {
        'slip_i_nc': relred('base_slip', 'i_nc_slip'),
        'census_i_nc': relred('base_census_bad', 'i_nc_census_bad'),
        'strict_i_nc': relred('base_strict_bad', 'i_nc_strict_bad'),
        'slip_i_max': relred('base_slip', 'i_max_slip'),
        'census_i_max': relred('base_census_bad', 'i_max_census_bad'),
        'slip_ii': relred('base_slip', 'ii_slip'),
        'census_ii': relred('base_census_bad', 'ii_census_bad'),
        'strict_ii': relred('base_strict_bad', 'ii_strict_bad'),
        'census_iplus': relred('base_census_bad', 'iplus_census_bad'),
        'strict_iplus': relred('base_strict_bad', 'iplus_strict_bad'),
        'slip_iplus': relred('base_slip', 'iplus_slip'),
    }
    # false repairs on real data: any change to a baseline strictly-valid call
    valid = [r for r in calls if not r['_o']['base_strict_bad']]
    fr_i = sum(r['_o']['i_nc_changed'] for r in valid)
    fr_ii = sum(r['_o']['ii_changed'] for r in valid)
    fr_ip = sum(r['_o']['iplus_changed'] for r in valid)
    res['false_repair_real'] = {'n_valid': len(valid), 'i_changed_valid': fr_i, 'ii_changed_valid': fr_ii, 'iplus_changed_valid': fr_ip,
                                'wilson95_i': wilson(fr_i, len(valid)), 'wilson95_ii': wilson(fr_ii, len(valid))}
    # slip anatomy
    slips = [r for r in calls if r['_o']['base_slip']]
    res['slip_anatomy'] = {
        'n': len(slips),
        'site_key->next': collections.Counter(f"{r['site']['key']}->{r['site']['next_key'] or '}'}" for r in slips).most_common(8),
        'run': collections.Counter(r['site']['run'] for r in slips).most_common(10),
        'key_order': collections.Counter(key_order(r['call']) for r in slips).most_common(),
        'natural_vs_forced': collections.Counter('forced' if r.get('forced') else 'natural' for r in slips).most_common(),
        'json_escaped_content': sum(1 for r in slips if '\\n' in r['call'] and '\n' not in r['call']),
    }
    def cat(r):
        if r['base']['strict_valid']:
            return 'valid'
        if r.get('site') is not None:
            return 'closer_slip:' + r['site']['kind']
        if not r['finished']:
            return 'unfinished(no <tool_call|>)'
        if first_opener_site(r['call'], S) is not None:
            return 'opener_drift'
        sp = parse_strict(r['call'])
        return 'other:' + (sp.error if not sp.ok else (r['base']['strict_probs'] or ['?'])[0].split(':')[0])
    res['invalid_anatomy'] = collections.Counter(cat(r) for r in calls if not r['base']['strict_valid']).most_common()
    res['key_order_all'] = collections.Counter(key_order(r['call']) for r in calls).most_common()
    ko = collections.defaultdict(lambda: [0, 0])
    for r in calls:
        k = key_order(r['call']); ko[k][0] += r['_o']['base_slip']; ko[k][1] += 1
    res['slip_rate_by_order'] = {k: {'k': v[0], 'n': v[1], 'rate': v[0] / v[1], 'wilson95': wilson(v[0], v[1])} for k, v in ko.items()}
    # (i) cost
    ic = [r['i_nc'] for r in slips if r.get('i_nc')]
    rounds = [len(x['rounds']) for x in ic]
    gen = [sum(rr['gen_tokens'] for rr in x['rounds']) for x in ic]
    disc = [sum(rr['discarded_chars'] for rr in x['rounds']) for x in ic]
    lat = [sum(rr['latency'] for rr in x['rounds']) for x in ic]
    cutreq = [sum(rr['cut_choice'].get('extra_requests', 0) for rr in x['rounds']) for x in ic]
    base_lat = [r.get('B_latency') or 0 for r in calls]
    base_tok = [r.get('B_tokens') or 0 for r in calls]
    def q(v):
        if not v:
            return None
        v = sorted(v)
        return {'mean': statistics.mean(v), 'median': v[len(v) // 2], 'p90': v[int(0.9 * (len(v) - 1))], 'max': v[-1]}
    try:
        global _TK
        if _TK is None:
            from transformers import AutoTokenizer
            _TK = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
        _tk = _TK
        call_tok = [len(_tk.encode(r['call'], add_special_tokens=False)) for r in calls]
        thought_tok = [len(_tk.encode(r.get('A_text') or '', add_special_tokens=False)) for r in calls]
    except Exception:
        call_tok, thought_tok = [], []
    res['baseline_tokens_per_edit_call'] = {'call': q(call_tok), 'thought_and_preamble': q(thought_tok)}
    if call_tok:
        res['extra_tokens_relative_to_call_plus_thought'] = sum(gen) / max(sum(call_tok) + sum(thought_tok), 1)
    res['cost_i'] = {'interventions': len(ic), 'rounds': q(rounds), 'rounds_hist': collections.Counter(rounds).most_common(),
                     'resume_gen_tokens': q(gen), 'discarded_chars': q(disc), 'extra_latency_s': q(lat),
                     'cut_requests': q(cutreq), 'baseline_call_latency_s': q(base_lat), 'baseline_call_tokens': q(base_tok),
                     'amortized_extra_tokens_per_edit_call': sum(gen) / max(len(calls), 1),
                     'amortized_extra_latency_per_edit_call_s': sum(lat) / max(len(calls), 1),
                     'amortized_extra_requests_per_edit_call': (sum(rounds) + sum(cutreq)) / max(len(calls), 1)}
    iic = [r['ii'] for r in calls if r.get('ii') and r['ii'].get('cands')]
    res['cost_ii'] = {'scored_calls': len(iic), 'cands': q([len(x['cands']) for x in iic]),
                      'latency_s': q([x.get('latency') or 0 for x in iic]),
                      'scoring_requests': q([(x.get('wctf') or {}).get('requests', 0) for x in iic])}
    # (i) noisy-channel cut decisions vs likelihood-only and whole-run ('max')
    cuts = collections.Counter()
    for r in slips:
        ic0 = r.get('i_nc')
        if not ic0 or not ic0['rounds']:
            continue
        c0 = ic0['rounds'][0]['cut_choice']
        cuts[(len(c0.get('cands', [])), c0.get('k'), c0.get('k_lik'))] += 1
    res['nc_cut_choice'] = [(f'{a}cands:k_nc={b},k_lik={c}', v) for (a, b, c), v in sorted(cuts.items(), key=str)]
    # intent proxy: old_string present verbatim in context
    if ctx_path:
        ids = {r['id'] for r in calls}
        hay = {}
        with open(ctx_path) as f:
            for l in f:
                d = json.loads(l)
                if d['id'] in ids:
                    hay[d['id']] = haystack(d['messages'])
        def old_in_ctx(text, rid):
            sp = parse_strict(text)
            if not sp.ok:
                return None
            o = sp.args().get('old_string')
            if not isinstance(o, str) or not o.strip():
                return None
            return o in hay.get(rid, '')
        vb = [old_in_ctx(r['call'], r['id']) for r in valid]
        vb = [x for x in vb if x is not None]
        rep_i = [old_in_ctx(r['i_nc']['text'], r['id']) for r in slips if r.get('i_nc') and r['_o']['i_nc_strict_bad'] is False]
        rep_i = [x for x in rep_i if x is not None]
        rep_ii = [old_in_ctx(r['ii'].get('text') or '', r['id']) for r in slips if r['_o']['ii_changed'] and not r['_o']['ii_strict_bad']]
        rep_ii = [x for x in rep_ii if x is not None]
        res['intent_proxy_old_in_context'] = {
            'baseline_valid': {'k': sum(vb), 'n': len(vb), 'rate': sum(vb) / max(len(vb), 1), 'wilson95': wilson(sum(vb), len(vb))},
            'repaired_i': {'k': sum(rep_i), 'n': len(rep_i), 'rate': sum(rep_i) / max(len(rep_i), 1), 'wilson95': wilson(sum(rep_i), len(rep_i))},
            'repaired_ii': {'k': sum(rep_ii), 'n': len(rep_ii), 'rate': sum(rep_ii) / max(len(rep_ii), 1), 'wilson95': wilson(sum(rep_ii), len(rep_ii))}}
    # (i) vs (ii) agreement on the repaired slipped argument
    agree = tot = 0
    for r in slips:
        if r.get('i_nc') and r['_o']['ii_changed']:
            k = r['site']['key']
            a1 = parse_strict(r['i_nc']['text']).args().get(k) if parse_strict(r['i_nc']['text']).ok else None
            a2 = parse_strict(r['ii']['text']).args().get(k) if parse_strict(r['ii']['text']).ok else None
            if a1 is not None and a2 is not None:
                tot += 1; agree += a1 == a2
    res['i_vs_ii_same_repaired_value'] = {'k': agree, 'n': tot}
    # unforced analysis: the NATURAL next call (whatever tool the model chose), no forcing
    nat_rows = [r for r in recs if r.get('status') == 'call']
    def nat_bad(r):
        if not r.get('forced'):
            return not r['base']['strict_valid'], not r['base']['census_ok'], 'edit_file'
        nc = r.get('natural_call')
        if not nc:
            return None, None, None
        return not nc['judge']['strict_valid'], not nc['judge']['census_ok'], r.get('natural_tool')
    tools = collections.Counter(); sb = cb = n_nat = 0; per_tool = collections.defaultdict(lambda: [0, 0])
    for r in nat_rows:
        s_bad, c_bad, t = nat_bad(r)
        if t is None:
            continue
        n_nat += 1; tools[t] += 1; sb += s_bad; cb += c_bad
        per_tool[t][0] += c_bad; per_tool[t][1] += 1
    res['natural_next_call'] = {'n': n_nat, 'tool_distribution': tools.most_common(),
                                'census_malformed': {'k': cb, 'n': n_nat, 'rate': cb / max(n_nat, 1), 'wilson95': wilson(cb, n_nat)},
                                'strict_invalid': {'k': sb, 'n': n_nat, 'rate': sb / max(n_nat, 1), 'wilson95': wilson(sb, n_nat)},
                                'census_malformed_by_tool': {t: {'k': v[0], 'n': v[1], 'wilson95': wilson(v[0], v[1])} for t, v in per_tool.items()},
                                'forced_edit_share': {'k': sum(bool(r.get('forced')) for r in nat_rows), 'n': len(nat_rows),
                                                      'wilson95': wilson(sum(bool(r.get('forced')) for r in nat_rows), len(nat_rows))},
                                'no_call': sum(r.get('status') == 'no_call' for r in recs)}
    # all-tools census of natural non-edit calls
    nat = [r['natural_call'] for r in recs if r.get('natural_call')]
    res['natural_non_edit_calls'] = {'n': len(nat), 'strict_bad': sum(not x['judge']['strict_valid'] for x in nat),
                                     'slip': sum(x['site'] is not None for x in nat)}
    return res


if __name__ == '__main__':
    path = sys.argv[1]
    ctx = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    tau = float(sys.argv[sys.argv.index('--tau') + 1]) if '--tau' in sys.argv else 1.0
    if '--noprior' in sys.argv:
        PRIOR_ON = False
    r = summarize(path, ctx, tau)
    print(json.dumps(r, indent=1, default=str))
