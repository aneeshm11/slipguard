import os  # added by the repo export (paths are env/config driven)
import json, sys
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/scripts'))
META = {}
for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')):
    m = json.loads(l); META[m['id']] = m
ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt'))]
ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
m = META[ids[0]]
path = f"{ROOT}/{m['run']}/{m['file']}"
with open(path, 'rb') as f:
    f.seek(m['off']); d = json.loads(f.readline())
    f.seek(m['tools_off']); tools = json.loads(f.readline())['tools']
print('keys of log line:', list(d.keys()))
print('meta:', {k: m[k] for k in ('id','temp','top_p','pt','k_usable','n_msgs')}, m['prior'][-1])
msgs = d['messages']
for i, x in enumerate(msgs):
    c = x.get('content')
    s = c if isinstance(c, str) else json.dumps(c)[:300]
    print(i, x.get('role'), {k: (v if k not in ('content','tool_calls') else None) for k, v in x.items() if k not in ('content',)}.keys(), repr((s or '')[:300]))
    if x.get('tool_calls'):
        for tc in x['tool_calls']:
            print('   TC', tc.get('id'), tc['function']['name'], tc['function']['arguments'][:300])
print('TOOLS:', json.dumps(tools)[:3000])
print('RESPONSE:', json.dumps(d.get('response'))[:1500])
