"""FROZEN confirmatory analysis for workstream B (PREREG_v2 §3.2 C12-C15; F3c family with Holm; halves; strata).
usage: confirm_analyze.py <runner_output.jsonl> <corpus manifest.json> [--out results_confirm.json]
Definitions are the discovery definitions (analyze_replay / analyze_h2h), schema taken from P's manifest tools:
  census-malformed = vLLM-0.19.1 lenient parse + missing required / unknown key / look-alike+key leak / special token;
  slip = first_slip_site fires on the base call;
  delivery: IPD/T1/retry -> strictly valid or loud; greedy / grammar-CD / lenient -> lenient delivery;
  clean = delivered & strictly valid & no leak; silent = delivered & accepted & (strict-invalid or leak).
"""
import json, math, os, sys, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import schema_from_tools, is_valid, repair_candidates, parse_strict, runtime_view, census_judge
from stats import wilson


def W(k, n):
    return {'k': k, 'n': n, 'rate': (k / n) if n else None, 'wilson95': wilson(k, n)}


def t1(text, finished, S):
    if finished and is_valid(text, S):
        return text
    name = parse_strict(text).name
    for c in repair_candidates(text, S, finished=finished):
        if all(s_ is not None and cp == s_.cut_positions()[0] for (k, cp, cl), s_ in zip(c.cuts, c.sites)):
            return c.text(name)
    return None


def deliver(text, finished, policy, S):
    if text is None:
        return {'delivered': False, 'malformed': False, 'silent': False, 'clean': False}
    v = runtime_view(text, finished, S)
    if policy == 'strict' and not v['strict_valid']:
        return {'delivered': False, 'malformed': False, 'silent': False, 'clean': False}
    return {'delivered': True, 'malformed': not v['census_ok'], 'silent': v['silent_corruption'],
            'clean': v['strict_valid'] and not v['leak_text']}


def per_sample(r, S):
    base, fin = r['call'], r['finished']
    A = r.get('arms', {})
    out = {'lenient': deliver(base, fin, 'lenient', S), 'fail_loud': deliver(base, fin, 'strict', S)}
    out['T1'] = deliver(t1(base, fin, S), True, 'strict', S)
    ipd = A.get('IPD') or {'text': base, 'finished': fin}
    out['IPD'] = deliver(ipd['text'], ipd['finished'], 'strict', S)
    out['IPD_census_malformed_text'] = not census_judge(ipd['text'], S)[0] if ipd['finished'] else True
    if r['base']['strict_valid']:
        out['retry_x2'] = deliver(base, fin, 'strict', S)
        out['retry_x2_lenient'] = deliver(base, fin, 'lenient', S)
        out['grammar_CD'] = deliver(base, fin, 'lenient', S)
    else:
        rt = A.get('retry_x2') or {}
        out['retry_x2'] = deliver(rt.get('final_text'), True, 'strict', S)
        last = (rt.get('tries') or [{}])[-1]
        out['retry_x2_lenient'] = (deliver(rt['final_text'], True, 'lenient', S) if rt.get('final_text') else
                                   deliver(last.get('text'), last.get('finished', False), 'lenient', S))
        g = A.get('grammar_CD') or {}
        out['grammar_CD'] = deliver(g.get('final_text'), g.get('finished', False), 'lenient', S)
    gr = A.get('greedy') or {}
    out['greedy'] = deliver(gr.get('final_text'), gr.get('finished', False), 'lenient', S)
    out['_ipd_changed_valid'] = bool(r['base']['strict_valid'] and (A.get('IPD') or {}).get('changed'))
    return out


def paired_residual(before, after):
    b = sum(before); stay = sum(x and y for x, y in zip(before, after)); new = sum((not x) and y for x, y in zip(before, after))
    k = min(stay + new, b)
    lo, hi = wilson(k, b) if b else (float('nan'), float('nan'))
    return {'before': b, 'still': stay, 'new': new, 'relred_point': (1 - (stay + new) / b) if b else None,
            'relred_wilson95': [1 - hi, 1 - lo] if b else None}


def mcnemar_exact(x, y):
    """two-sided exact McNemar on paired binary outcomes x (arm A) and y (arm B)."""
    b = sum(1 for p, q in zip(x, y) if p and not q); c = sum(1 for p, q in zip(x, y) if q and not p)
    n = b + c
    if n == 0:
        return 1.0, b, c
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p), b, c


def rd_boot(x, y, B=4000, seed=0):
    rng = random.Random(seed); n = len(x)
    pt = (sum(y) - sum(x)) / n if n else float('nan')
    bs = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        bs.append((sum(y[i] for i in idx) - sum(x[i] for i in idx)) / n)
    bs.sort()
    return {'rd': pt, 'boot95': [bs[int(0.025 * (B - 1))], bs[int(0.975 * (B - 1))]]} if n else None


def holm(pvals):
    order = sorted(pvals, key=lambda kv: kv[1]); m = len(order); out = {}; run = 0.0
    for i, (name, p) in enumerate(order):
        run = max(run, min(1.0, (m - i) * p)); out[name] = run
    return out


def rule_c15(name, d, ineq, thr):
    pt = d['rate']; lo, hi = d['wilson95']
    if pt is None:
        return 'NOT_ESTIMABLE'
    sat = (pt >= thr) if ineq == '>=' else (pt <= thr)
    ci_ok = lo > 0.5 if ineq == '>=' else hi < 0.5
    if sat and ci_ok:
        return 'REPLICATES'
    return 'ATTENUATED' if ((pt > 0.5) if ineq == '>=' else (pt < 0.5)) else 'FAILS'


def analyze(rows, S):
    calls = [r for r in rows if r.get('status') == 'call']
    ps = [per_sample(r, S) for r in calls]
    slip = [r.get('site') is not None for r in calls]
    base_bad = [not r['base']['census_ok'] for r in calls]
    res = {'n_states': len(rows), 'status': {s: sum(r.get('status') == s for r in rows) for s in
                                              ('call', 'no_call', 'render_mismatch', 'error')},
           'n_calls': len(calls), 'forced': sum(bool(r.get('forced')) for r in calls)}
    res['C12_census_malformed'] = {'all': W(sum(base_bad), len(calls)),
                                   'natural': W(sum(b for b, r in zip(base_bad, calls) if not r.get('forced')), sum(not r.get('forced') for r in calls)),
                                   'forced': W(sum(b for b, r in zip(base_bad, calls) if r.get('forced')), sum(bool(r.get('forced')) for r in calls)),
                                   'closer_slips': W(sum(slip), len(calls))}
    ipd_bad = [p['IPD_census_malformed_text'] for p in ps]
    c13 = paired_residual(base_bad, ipd_bad)
    v = c13
    c13['verdict'] = ('NOT_ESTIMABLE' if v['relred_point'] is None else
                      'REPLICATES' if (v['relred_wilson95'][0] >= 0.50 and v['relred_point'] >= 0.75) else
                      'ATTENUATED' if v['relred_wilson95'][0] > 0 else 'FAILS')
    res['C13_IPD_relred_malformed'] = c13
    nvalid = sum(r['base']['strict_valid'] for r in calls)
    changed = [r['context_id'] for r, p in zip(calls, ps) if p['_ipd_changed_valid']]
    res['C14_byte_identity'] = {'valid_calls': nvalid, 'changed': len(changed), 'changed_cases': changed,
                                'verdict': 'REPLICATES' if not changed else 'FAILS'}
    sl = [p for p, s in zip(ps, slip) if s]
    tab = {}
    for arm in ('IPD', 'T1', 'retry_x2', 'retry_x2_lenient', 'greedy', 'grammar_CD', 'lenient', 'fail_loud'):
        n = len(sl)
        tab[arm] = {k: W(sum(x[arm][k] for x in sl), n) for k in ('clean', 'malformed', 'silent')}
        tab[arm]['loud'] = W(sum(not x[arm]['delivered'] for x in sl), n)
    rules = {'IPD': rule_c15('IPD', tab['IPD']['clean'], '>=', 0.90), 'T1': rule_c15('T1', tab['T1']['clean'], '>=', 0.90),
             'retry_x2': rule_c15('retry_x2', tab['retry_x2']['loud'], '>=', 0.50),
             'greedy': rule_c15('greedy', tab['greedy']['malformed'], '>=', 0.60),
             'grammar_CD': rule_c15('grammar_CD', tab['grammar_CD']['silent'], '>=', 0.80)}
    ipd_c = [x['IPD']['clean'] for x in sl]; t1_c = [x['T1']['clean'] for x in sl]
    d = rd_boot(t1_c, ipd_c) if sl else None
    rules['IPD_minus_T1_clean'] = {'diff': d, 'within_5pp': (abs(d['rd']) <= 0.05) if d else None}
    res['C15_head_to_head_on_slips'] = {'n_slips': len(sl), 'table': tab, 'verdicts': rules}
    # F3c: C13 vs base + IPD vs each baseline on delivered-malformed (paired, exact McNemar, Holm)
    ipd_dm = [p['IPD']['malformed'] for p in ps]
    comps = {}
    for arm in ('lenient', 'T1', 'retry_x2_lenient', 'greedy', 'grammar_CD'):
        other = [p[arm]['malformed'] for p in ps]
        pval, b, c = mcnemar_exact(ipd_dm, other)
        comps[arm] = {'IPD_rate': W(sum(ipd_dm), len(ps)), 'arm_rate': W(sum(other), len(ps)),
                      'rd_arm_minus_IPD': rd_boot(ipd_dm, other), 'mcnemar_p': pval, 'discordant_IPD_only': b, 'discordant_arm_only': c}
    adj = holm([(k, v['mcnemar_p']) for k, v in comps.items()])
    for k in comps:
        comps[k]['holm_p'] = adj[k]
    res['F3c_IPD_vs_baselines_delivered_malformed'] = comps
    return res


def main():
    out_path = sys.argv[1]; man = json.load(open(sys.argv[2]))
    S = schema_from_tools(man['tools'])
    rows = [json.loads(l) for l in open(out_path)]
    res = {'source': os.path.basename(out_path), 'prereg': 'PREREG_v2 §3.2 (C12-C15); F3c Holm', 'full': analyze(rows, S)}
    for h in sorted({r.get('half') for r in rows if r.get('half') is not None}):
        res[f'half_{h}'] = analyze([r for r in rows if r.get('half') == h], S)
    dst = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else out_path.replace('.jsonl', '_analysis.json')
    json.dump(res, open(dst, 'w'), indent=1, default=str)
    f = res['full']
    print(json.dumps({'n_calls': f['n_calls'], 'C12': f['C12_census_malformed']['all'], 'C13': {k: f['C13_IPD_relred_malformed'][k] for k in ('relred_point', 'relred_wilson95', 'verdict')},
                      'C14': {k: f['C14_byte_identity'][k] for k in ('valid_calls', 'changed', 'verdict')},
                      'C15': f['C15_head_to_head_on_slips']['verdicts']}, default=str, indent=1))


if __name__ == '__main__':
    main()
