"""Export REAL natural contagion episodes of the plain base 31B (read-only over the index): attempts whose edit_file
sequence contains a malformed edit followed by at least one later edit. One line per attempt with the full edit
sequence (log line, malformed flag + reason, closer, emission order, retry-of-previous flag) and the graded outcome.
usage: export_episodes.py index.jsonl runs_root out.jsonl
"""
import json, sys, glob, os, collections
idx, root, outp = sys.argv[1:4]
res = {}
for pt in glob.glob(os.path.join(root, '*', 'per_task.jsonl')):
    for l in open(pt, errors='replace'):
        try: d = json.loads(l)
        except Exception: continue
        res[d.get('attempt')] = bool(d.get('resolved'))
att = collections.defaultdict(list); meta = {}
for l in open(idx):
    r = json.loads(l)
    if r.get('bad_line') or r['teacher'] or r['model'] != 'openai/gemma-4-31b-it-qat-w4a16-ct': continue
    for c in r['calls']:
        if c['name'] != 'edit_file': continue
        ks = c.get('keys') or []
        order = 'new_first' if ('new_string' in ks and ('old_string' not in ks or ks.index('new_string') < ks.index('old_string'))) else ('old_first' if 'old_string' in ks else 'neither')
        att[r['task']].append({'ln': r['ln'], 'off': r['off'], 'bad': c['bad_syn'], 'why': c.get('why_syn'), 'flags': c.get('flags'), 'closer': c.get('closer'),
                               'order': order, 'fp': c.get('fp'), 'nh': c.get('nh'), 'nlen': c.get('nlen')})
    meta[r['task']] = {'run': r['run'], 'file': r['file'], 'temp': r['temp']}
n = 0; stats = collections.Counter()
with open(outp, 'w') as f:
    for a, ev in att.items():
        ev.sort(key=lambda e: e['ln'])
        for i, e in enumerate(ev):
            e['retry_of_prev'] = bool(i > 0 and e['fp'] == ev[i - 1]['fp'] and e['nh'] == ev[i - 1]['nh'])
        first_bad = next((i for i, e in enumerate(ev) if e['bad']), None)
        if first_bad is None or first_bad == len(ev) - 1: continue
        later = ev[first_bad + 1:]
        rec = {'attempt': a, **meta[a], 'resolved': res.get(a), 'n_edits': len(ev), 'onset_index': first_bad,
               'n_bad_after_onset': sum(e['bad'] for e in later), 'n_after_onset': len(later),
               'recovered_clean_edit': any(not e['bad'] for e in later), 'edits': ev}
        f.write(json.dumps(rec) + '\n'); n += 1
        stats['episodes'] += 1; stats['later_edits'] += len(later); stats['later_bad'] += rec['n_bad_after_onset']
        stats['recovered'] += rec['recovered_clean_edit']
print('episodes', n, dict(stats))
