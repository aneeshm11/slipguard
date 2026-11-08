"""PREREG_v2.5b §2 replay preconditions on A's E4B confirmatory run (rCe4b_v2.jsonl), CPU only, METADATA ONLY
(pathway/k/n_prompt/finish/stop/budget_forced/server/template; no s1/s2 text or judge field is read or printed):
re-render with A's frozen builders (via the E4B glue) and require len == n_prompt for P0, P1, P8a; stop semantics.
writes v25b/out/preconditions_e4b.json"""
import collections, json, os, sys
sys.argv = [sys.argv[0], 'cpu']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stack_runner_e4b as SR
A1 = {r['context_id'] for r in SR.A1}
res = collections.Counter(); mism = []; meta = collections.Counter()
for l in open(os.path.join(SR.A_DIR, 'out/main/rCe4b_v2.jsonl')):
    d = json.loads(l)
    pw, k = d.get('pathway'), d.get('k')
    if pw not in ('P0', 'P1', 'P8a') or d.get('id') not in A1:
        continue
    meta[(pw, d.get('server'), d.get('model'), d.get('temp'), d.get('top_p'), d.get('template'))] += 1
    res[(pw, 'n')] += 1
    res[(pw, 'error')] += bool(d.get('error'))
    res[(pw, 'stop49')] += (d.get('s2_stop', d.get('s1_stop')) == 49)
    res[(pw, 'finish_stop')] += (d.get('s2_finish') == 'stop')
    res[(pw, 'budget_forced')] += bool(d.get('budget_forced'))
    n = len(SR.ids_of(SR.tok(), SR.a_prompt(d['id'], pw, k)))
    ok = (n == d.get('n_prompt'))
    res[(pw, 'len_eq_n_prompt')] += ok
    if not ok:
        mism.append((d['id'], pw, n, d.get('n_prompt')))
out = {'counts': {f'{a}|{b}': v for (a, b), v in sorted(res.items())}, 'mismatches': mism[:20],
       'run_metadata': [list(k) + [v] for k, v in meta.items()]}
json.dump(out, open(os.path.join(SR.OUTD, 'preconditions_e4b.json'), 'w'), indent=1)
print(json.dumps(out, indent=1))
