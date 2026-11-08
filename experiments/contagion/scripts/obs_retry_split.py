"""Observational next-edit malformed rate (plain base 31B) after a clean history vs after exactly one prior malformed
edit (the immediately preceding one), split by whether the next edit is a same-content retry (same filepath and same
hash of the first 200 chars of new_string, cut at a leak). Read-only over data/index.jsonl.
usage: obs_retry_split.py index.jsonl out.json"""
import json, sys, collections, math
def w(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(c - h, 4), round(c + h, 4), n]
att = collections.defaultdict(list)
for l in open(sys.argv[1]):
    r = json.loads(l)
    if r.get('bad_line') or r['teacher'] or r['model'] != 'openai/gemma-4-31b-it-qat-w4a16-ct': continue
    for c in r['calls']:
        if c['name'] == 'edit_file': att[r['task']].append((r['ln'], c['bad_syn'], c.get('fp'), c.get('nh')))
t = collections.Counter()
for v in att.values():
    v.sort(); nb = 0
    for i, e in enumerate(v):
        if i > 0:
            kind = 'same_content_retry' if (e[2] == v[i - 1][2] and e[3] == v[i - 1][3]) else 'other_edit'
            if nb == 1 and v[i - 1][1] == 1: t[('after_exactly_one_malformed_prev', kind, e[1])] += 1
            if nb == 0: t[('clean_history', kind, e[1])] += 1
        nb += e[1]
out = {f'{h}/{kind}': w(t[(h, kind, 1)], t[(h, kind, 1)] + t[(h, kind, 0)]) for h in ('clean_history', 'after_exactly_one_malformed_prev')
       for kind in ('same_content_retry', 'other_edit') if t[(h, kind, 1)] + t[(h, kind, 0)]}
json.dump(out, open(sys.argv[2], 'w'), indent=1); print(json.dumps(out))
