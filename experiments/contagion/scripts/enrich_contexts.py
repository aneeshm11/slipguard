"""For each context id, extract the content heads of (a) the k most recent prior edit_file calls (the ones the injection
replaces) and (b) the logged target edit, so generated edits can be classified as a RETRY of a replaced call, the
logged TARGET edit, or OTHER.
usage: enrich_contexts.py meta.jsonl ids.txt|- out.json
"""
import os  # added by the repo export (paths are env/config driven)
import json, sys, re
ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
CLOSER = re.compile(r'(["`\\\']+)\s*,\s*(old_string|new_string|filepath|allow_multiple)\s*:')


def head(s, n=80):
    if not isinstance(s, str): return None
    m = CLOSER.search(s)
    if m: s = s[:m.start()]
    return ' '.join(s.split())[:n]


meta = {}
for l in open(sys.argv[1]):
    m = json.loads(l); meta[m['id']] = m
ids = [x.strip() for x in open(sys.argv[2])] if sys.argv[2] != '-' else list(meta)
out = {}
for cid in ids:
    m = meta.get(cid)
    if not m or not m['prior']: continue
    path = f"{ROOT}/{m['run']}/{m['file']}"
    with open(path, 'rb') as f:
        f.seek(m['off']); d = json.loads(f.readline())
    msgs = d['messages']
    rep = []
    for p in reversed(m['prior'][-4:]):
        tc = msgs[p['ai']]['tool_calls'][0]
        a = json.loads(tc['function']['arguments'])
        rep.append({'fp': a.get('filepath'), 'new': head(a.get('new_string')), 'old': head(a.get('old_string'))})
    tgt = None
    for tc in (d.get('response') or {}).get('tool_calls') or []:
        f_ = tc.get('function') or {}
        if f_.get('name') == 'edit_file':
            try: a = json.loads(f_.get('arguments'))
            except Exception: a = {}
            tgt = {'fp': a.get('filepath'), 'new': head(a.get('new_string')), 'old': head(a.get('old_string'))}
            break
    out[cid] = {'replaced_recent_first': rep, 'target': tgt}
json.dump(out, open(sys.argv[3], 'w'))
print('enriched', len(out))
