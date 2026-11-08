import os  # added by the repo export (paths are env/config driven)
import json, hashlib, sys
META = {}
for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')):
    m = json.loads(l); META[m['id']] = m
ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
P = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/data/replay_gemma_first_edit.jsonl')
print('md5', hashlib.md5(open(P, 'rb').read()).hexdigest())
n = 0; inmeta = 0; same_msgs = 0; same_tools = 0; first = 0; teach = 0; temps = {}
rows = []
for i, l in enumerate(open(P)):
    r = json.loads(l); n += 1
    m = META.get(r['id'])
    if m is None: continue
    inmeta += 1
    first += (m['n_prior_edits'] == 0)
    temps[m['temp']] = temps.get(m['temp'], 0) + 1
    if i < 700:
        with open(f"{ROOT}/{m['run']}/{m['file']}", 'rb') as f:
            f.seek(m['off']); d = json.loads(f.readline()); f.seek(m['tools_off']); tools = json.loads(f.readline())['tools']
        same_msgs += (d['messages'] == r['messages']); same_tools += (tools == r['tools'])
print(dict(n=n, in_A_meta=inmeta, first_edit=first, temps=temps, checked=min(700, n), same_msgs=same_msgs, same_tools=same_tools))
