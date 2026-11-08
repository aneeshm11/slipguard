"""Smoke input for natural_descriptives_v2.py built from DISCOVERY data only (main-track logs, base 31B, teacher-free):
CONTEXT_SCHEMA §3b requests.jsonl + manifest.json (profile main_track, June template md5) for the first N attempts of
the given runs that contain an edit_file call. Attempt id = the logged task key (no chain reconstruction; smoke only).
Also writes an 'S2' copy of the first 100 attempts so the S2 code path runs (numbers meaningless there).
usage: smoke_build_discovery_requests.py <outdir> [N=400] [runs=run-39]
"""
import json, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import variants as V
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
out = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 400
RUNS = set((sys.argv[3] if len(sys.argv) > 3 else 'run-39').split(','))
rows = collections.defaultdict(list); order = []
for l in open(f'{D}/data/index.jsonl'):
    r = json.loads(l)
    if r.get('bad_line') or r['teacher'] or r['model'] != 'openai/gemma-4-31b-it-qat-w4a16-ct' or r['run'] not in RUNS: continue
    if r['task'] not in rows: order.append(r['task'])
    rows[r['task']].append(r)
tasks = [t for t in order if any(c['name'] == 'edit_file' for r in rows[t] for c in r['calls'])][:N]
meta0 = json.loads(open(f'{D}/data/contexts_meta.jsonl').readline()); _, tools = V.load_context(meta0)
man = {'corpus_id': 'SMOKE-discovery-main-track', 'tool_profile': 'main_track', 'tools': tools,
       'render': {'chat_template_md5': 'd6c5bd0d (June, main-track)'}, 'harness': {'responses': {}},
       'files': {'requests': 'requests.jsonl (smoke; discovery data only)'}}
for sub, strat, sel in (('S1', 'S1', tasks), ('S2', 'S2', tasks[:100])):
    os.makedirs(f'{out}/{sub}', exist_ok=True); json.dump(man, open(f'{out}/{sub}/manifest.json', 'w'), indent=1)
    n = 0
    with open(f'{out}/{sub}/requests.jsonl', 'w') as fo:
        for i, t in enumerate(sel):
            for j, r in enumerate(sorted(rows[t], key=lambda r: (r['file'], r['ln']))):
                with open(f"{ROOT}/{r['run']}/{r['file']}", 'rb') as f:
                    f.seek(r['off']); d = json.loads(f.readline())
                resp = d.get('response') or {}
                fo.write(json.dumps({'episode_id': t, 'task_id': t.split('#')[0], 'request_index': j, 'stratum': strat,
                                     'split': 'verified' if i % 2 == 0 else 'swebench_test_ext',
                                     'response': {'content': resp.get('content'), 'reasoning_content': resp.get('reasoning_content'),
                                                  'tool_calls': resp.get('tool_calls')},
                                     'finish_reason': resp.get('finish_reason'), 'tool_results': []}) + '\n'); n += 1
    print(sub, 'episodes', len(sel), 'requests', n)
