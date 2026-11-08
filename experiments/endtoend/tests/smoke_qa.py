"""Operational QA of a campaign's proxy logs (no outcome metrics): HTTP status, record completeness (tool-output
hashes, n_tools, events), common seeds identical across arms at equal request index, compaction events, replay
fidelity (branch campaigns). Usage: smoke_qa.py <proxy_log_dir> [<proxy_log_dir> ...]"""
import glob
import json
import sys
from collections import Counter, defaultdict

recs = []
for d in sys.argv[1:]:
    for f in glob.glob(f'{d}/proxy_*.jsonl'):
        recs += [json.loads(l) for l in open(f)]
print('records', len(recs), 'status', dict(Counter(r.get('status') for r in recs)))
print('exceptions', sum(1 for r in recs if r.get('exception')))
tr = [t for r in recs for t in r.get('tool_results') or []]
print('tool results', len(tr), 'with hash', sum(1 for t in tr if len(t) > 3 and t[3]), 'error types', dict(Counter(t[2] for t in tr if t[2])))
print('compaction calls', sum(1 for r in recs if r.get('compaction_call')), 'compaction applied', sum(1 for r in recs if r.get('compaction_applied')))
seeds = defaultdict(dict)
for r in recs:
    c = r.get('crn') or r.get('branch')
    if c and c.get('seed') is not None:
        task = r['task'].split(':')[-1]
        seeds[(task, c['i'])][r['cfg']] = c['seed']
pairs = [v for v in seeds.values() if len(v) > 1]
print('requests with seeds', sum(len(v) for v in seeds.values()), 'index pairs across arms', len(pairs),
      'identical', sum(1 for v in pairs if len(set(v.values())) == 1))
fid = Counter((r.get('replay') or {}).get('fidelity') for r in recs if r.get('replayed'))
if fid:
    print('replay fidelity', dict(fid))
ev = Counter(e['ev'] for r in recs for e in r.get('events') or [])
print('events (counts only)', dict(ev))
