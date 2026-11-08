"""Analysis of G1R (natural closures at real slip-prone states with known intent).
Per arm, on (a) natural SLIPS (the gold-intent slip set) and (b) samples that closed correctly (false-repair check):
exact intent, new_string exact, old_string exact, strictly valid, silent corruption; (ii) decided offline at tau.
Also T1 text-only computed here on the REAL emitted tail.  Wilson 95% CIs; states are the clusters."""
import json, os, sys, collections, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import schema_from_tools, is_valid, parse_strict, repair_candidates, runtime_view
from stats import wilson

S = schema_from_tools(json.load(open(os.path.join(HERE, 'data/tools_official.json'))))
GOLD = {}


def W(k, n):
    return {'k': k, 'n': n, 'rate': (k / n) if n else None, 'wilson95': wilson(k, n)}


def gold_for(rid):
    if not GOLD:
        CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')
        for l in open(CORPUS):
            d = json.loads(l)
            if d.get('intent_from_retry') and d['model_family'] == 'base':
                args = json.loads(d['arguments_json']); lab = d['labels']['absorbed'][0]
                GOLD[d['id']] = {'filepath': args.get('filepath'), 'new_string': (args.get(lab['host_key']) or '')[:lab['offset']],
                                 'old_string': d['intent_from_retry']['old_string']}
    return GOLD.get(rid)


def sc(text, finished, gold):
    if text is None:
        return {'strict_valid': False, 'silent_corruption': False, 'exact_intent': False, 'new_exact': False, 'old_exact': False}
    v = runtime_view(text, finished, S)
    ok = bool(finished and is_valid(text, S))
    a = parse_strict(text).args() if ok else {}
    return {'strict_valid': ok, 'silent_corruption': v['silent_corruption'],
            'exact_intent': ok and a.get('filepath') == gold['filepath'] and a.get('new_string') == gold['new_string'] and a.get('old_string') == gold['old_string'],
            'new_exact': ok and a.get('new_string') == gold['new_string'], 'old_exact': ok and a.get('old_string') == gold['old_string']}


def t1(text, finished):
    if finished and is_valid(text, S):
        return text
    for c in repair_candidates(text, S, finished=finished):
        if all(s_ is not None and cp == s_.cut_positions()[0] for (k, cp, cl), s_ in zip(c.cuts, c.sites)):
            return c.text('edit_file')
    return None


def summarize(path, taus=(0.0, 2.0)):
    rows = [json.loads(l) for l in open(path)]
    st = collections.Counter(r.get('status') for r in rows)
    rows = [r for r in rows if r.get('status') == 'ok']
    for r in rows:
        g = gold_for(r['id'])
        r['_g'] = g
        A = r['arms']
        r['_arms'] = {'1_lenient_or_failloud': sc(r['call'], r['finished'], g)}   # lenient/fail-loud: the emitted call itself
        r['_arms']['3_T1_text_only'] = sc(t1(r['call'], r['finished']), True, g)
        r['_arms']['4_i_max'] = A['i_max'] if 'i_max' in A else None
        r['_arms']['5_IPD'] = A['IPD']
        for tau in taus:
            ii = A.get('ii') or {}
            if 'cands' not in ii:                       # valid sample: identity
                r['_arms'][f'6_ii_tau{tau}'] = sc(r['call'], r['finished'], g)
            else:
                cands = ii['cands']
                if not cands:
                    r['_arms'][f'6_ii_tau{tau}'] = sc(None, False, g)
                else:
                    adj = [c['ll'] + c['prior'] for c in cands]
                    order = sorted(range(len(adj)), key=lambda i: -adj[i])
                    m = adj[order[0]] - adj[order[1]] if len(adj) > 1 else math.inf
                    r['_arms'][f'6_ii_tau{tau}'] = sc(cands[order[0]]['text'] if m >= tau else None, True, g)
        r['_arms']['7_retry_x2'] = A['retry_x2']
        r['_arms']['8_greedy'] = A['greedy']
        r['_arms']['9b_forbid_strict'] = A['forbid_strict']
        r['_arms']['10_grammar_CD'] = A['grammar']
    states = {r['id'] for r in rows}
    slips = [r for r in rows if r['slip']]
    clean = [r for r in rows if r['base']['strict_valid']]
    out = {'file': os.path.basename(path), 'status': dict(st), 'samples': len(rows), 'states': len(states),
           'natural_slip_rate': W(len(slips), len(rows)), 'clean_closure_rate': W(len(clean), len(rows)),
           'slip_runs': collections.Counter(r['slip_run'] for r in slips).most_common(8)}
    for name, ss in (('slips', slips), ('clean_closures', clean), ('all', rows)):
        tab = {}
        arms = sorted({a for r in ss for a in r['_arms'] if r['_arms'][a] is not None}, key=lambda x: (int(x.split('_')[0][:2].rstrip('b')) if x[0].isdigit() else 99, x))
        for a in arms:
            xs = [r['_arms'][a] for r in ss if r['_arms'].get(a) is not None]
            tab[a] = {k: W(sum(bool(x.get(k)) for x in xs), len(xs)) for k in ('exact_intent', 'new_exact', 'old_exact', 'strict_valid', 'silent_corruption')}
        out[name] = tab
    # false repairs: IPD / (ii) / T1 must leave every clean closure byte-identical
    out['false_repairs_on_clean'] = {
        'IPD_changed': W(sum(bool(r['arms']['IPD'].get('changed')) for r in clean), len(clean)),
        'T1_changed': W(sum(t1(r['call'], r['finished']) != r['call'] for r in clean), len(clean))}
    return out


if __name__ == '__main__':
    r = summarize(sys.argv[1])
    print(r['file'], r['status'], 'samples', r['samples'], 'states', r['states'], 'natural slip rate', r['natural_slip_rate']['k'], '/', r['natural_slip_rate']['n'],
          'runs', r['slip_runs'])
    print('false repairs on clean closures:', r['false_repairs_on_clean'])
    for name in ('slips', 'clean_closures'):
        print('==', name)
        for a, t in r[name].items():
            f = lambda d: f"{d['k']}/{d['n']}={100*(d['rate'] or 0):.1f}%"
            print(f"  {a:22s} exact {f(t['exact_intent'])}  new {f(t['new_exact'])}  old {f(t['old_exact'])}  valid {f(t['strict_valid'])}  silent {f(t['silent_corruption'])}")
