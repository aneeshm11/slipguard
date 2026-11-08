"""Quick population stats over the index: models x runs, edit calls, multi-call responses, token sizes."""
import json, collections, sys
recs = [json.loads(l) for l in open(sys.argv[1])]
pop = collections.Counter(); edits = collections.Counter(); bad = collections.Counter()
runs = collections.defaultdict(collections.Counter)
multi = collections.Counter(); ct_edit = []; pt_edit = []; rlen = []
for r in recs:
    if r.get('bad_line'): continue
    m = r['model']; key = ('TEACHER' if r['teacher'] else ('BASE' if m == 'openai/gemma-4-31b-it-qat-w4a16-ct' else ('SYN-other31b' if 'gemma-4-31b' in m else 'FT:' + m.split('/')[-1])))
    pop[key] += 1
    e = [c for c in r['calls'] if c['name'] == 'edit_file']
    edits[key] += len(e); bad[key] += sum(c['bad_syn'] for c in e)
    runs[key][r['run']] += len(e)
    if len(r['calls']) > 1: multi[(key, tuple(sorted(set(c['name'] for c in r['calls']))) if any(c['name']=='edit_file' for c in r['calls']) else 'noedit')] += 1
    if key == 'BASE' and r['calls'] and r['calls'][0]['name'] == 'edit_file':
        ct_edit.append(r['ct'] or 0); pt_edit.append(r['pt'] or 0); rlen.append(r['rlen'])
for k in sorted(pop): print(k, 'llm_calls', pop[k], 'edit calls', edits[k], 'bad_syn', bad[k], '%.3f' % (bad[k] / max(1, edits[k])))
print('\nBASE runs (edit calls):', dict(runs['BASE'].most_common()))
print('\nTEACHER runs (edit calls):', dict(runs['TEACHER'].most_common()))
print('\nmulti-call responses w/ edit (top):', [(k, v) for k, v in multi.most_common(12) if k[1] != 'noedit'][:10])
import statistics as st
def q(x, p): x = sorted(x); return x[int(p * (len(x) - 1))]
print('\nBASE first-call-edit responses:', len(ct_edit))
for nm, x in [('completion_tokens', ct_edit), ('prompt_tokens', pt_edit), ('reasoning_chars', rlen)]:
    print(nm, 'median', q(x, .5), 'p90', q(x, .9), 'p99', q(x, .99), 'max', max(x), 'mean %.0f' % st.mean(x))
print('frac reasoning empty', sum(1 for x in rlen if x == 0) / len(rlen))
