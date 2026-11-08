"""Analysis of the real-slip gold split (rs279.py output): per decoder arm, exact intent / new_string exact /
old_string exact / strictly valid / silent corruption, Wilson 95% CIs; subsets by temperature, by whether the gold cut
is the whole look-alike run, and by thought truncation."""
import json, sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from stats import wilson

ORDER = ['i_nc', 'i_max', 'retry_x2', 'greedy', 'forbid', 'forbid_strict', 'grammar', 'T1_assumed_tail', 'ii_assumed_tail']


def W(k, n):
    return {'k': k, 'n': n, 'rate': (k / n) if n else None, 'wilson95': wilson(k, n)}


def summarize(path):
    rows = [json.loads(l) for l in open(path)]
    st = collections.Counter(r.get('status') for r in rows)
    rows = [r for r in rows if r.get('status') == 'ok']
    out = {'file': os.path.basename(path), 'status': dict(st), 'n': len(rows),
           'site_found': W(sum(bool(r.get('site_found')) for r in rows), len(rows))}
    subsets = {'all': rows, 'T=0.2': [r for r in rows if r['T'] == 0.2], 'T=0.7': [r for r in rows if r['T'] == 0.7],
               'thought_full': [r for r in rows if not r['thought_truncated']]}
    for name, ss in subsets.items():
        tab = {}
        for a in ORDER:
            xs = [r['arms'][a] for r in ss if a in r.get('arms', {})]
            if xs:
                tab[a] = {k: W(sum(bool(x.get(k)) for x in xs), len(xs)) for k in
                          ('exact_intent', 'new_exact', 'old_exact', 'strict_valid', 'silent_corruption')}
        out[name] = tab
    return out


if __name__ == '__main__':
    r = summarize(sys.argv[1])
    print(r['file'], r['status'], 'n', r['n'], 'slip site found', r['site_found']['k'], '/', r['site_found']['n'])
    for name in ('all', 'T=0.2', 'T=0.7'):
        print('==', name)
        for a, t in r[name].items():
            f = lambda d: f"{d['k']}/{d['n']}={100*(d['rate'] or 0):.1f}% [{100*d['wilson95'][0]:.1f},{100*d['wilson95'][1]:.1f}]"
            print(f"  {a:16s} exact {f(t['exact_intent'])}  new {f(t['new_exact'])}  old {f(t['old_exact'])}  valid {f(t['strict_valid'])}  silent {f(t['silent_corruption'])}")
