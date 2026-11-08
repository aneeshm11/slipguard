"""A2: split next edits into 'retry of the onset edit' (same file and same first 40 chars of the replacement value,
leak tail cut) vs 'new content', per arm; malformed rates with Wilson CIs (unconditional base = states).
usage: a2_split.py out.json"""
import os  # added by the repo export (paths are env/config driven)
import json, sys, math, re, collections
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
CL = re.compile(r'(["`\\\']+)\s*,\s*(old_string|new_string|filepath|allow_multiple)\s*:')
def wilson(k, n, z=1.96):
    if n == 0: return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4), n]
norm = lambda s: ' '.join((s or '').replace('\\n', ' ').split())[:40]
st = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/a2_states.jsonl')}
res = collections.defaultdict(lambda: collections.Counter())
for l in open(f'{D}/out/main/r31b_a2.jsonl'):
    d = json.loads(l)
    if d.get('error'): continue
    arm = {'P0': 'L', 'P5': 'P5', 'Q8b': 'Q8b'}[d['pathway']]; j = d.get('judge') or {}
    s = st[d['id']]; a = s['onset_args']; ns = a.get('new_string') or ''; m = CL.search(ns)
    onset_head = norm(ns[:m.start()] if m else ns)
    if j.get('name') != 'edit_file': res[arm]['no_edit'] += 1; continue
    retry = (j.get('fp') == a.get('filepath') and norm(j.get('new_head')) == onset_head)
    res[arm][('retry' if retry else 'new', bool(j.get('malformed')))] += 1
out = {}
for arm, c in res.items():
    n = sum(c.values())
    r_n = c[('retry', True)] + c[('retry', False)]; n_n = c[('new', True)] + c[('new', False)]
    out[arm] = {'states': n, 'next_is_retry_of_onset': wilson(r_n, n), 'malformed_among_retries': wilson(c[('retry', True)], r_n),
                'malformed_among_new_content': wilson(c[('new', True)], n_n), 'unconditional_malformed_retry_share_of_states': wilson(c[('retry', True)], n),
                'unconditional_malformed_new_share_of_states': wilson(c[('new', True)], n), 'no_edit': c['no_edit']}
json.dump(out, open(sys.argv[1], 'w'), indent=1); print(json.dumps(out, indent=1))
