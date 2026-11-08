"""P0-A2: natural post-slip states of the plain base 31B (read-only over the main-track logs).

A state = the exact logged messages of the LLM call that FOLLOWS an attempt's first malformed edit_file call, when that
malformed call is the last assistant turn of the state and its tool response is the ADK missing-mandatory-parameter error
(the laundered loop: corrupted args re-rendered + error). Tools are carried forward. One state per attempt.
We also record the onset call's parsed (corrupted) arguments, its tool_call id, and what the model actually did next in
the log (malformed edit? retry of the same content?).
usage: build_a2_states.py index.jsonl natural_episodes.jsonl out.jsonl [n=300] [seed=0]
"""
import json, sys, random, collections, re, os
sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
MISSING_ERR = 'Invoking `edit_file()` failed as the following mandatory input parameters are not present'
idx_path, ep_path, outp = sys.argv[1:4]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 300
random.seed(int(sys.argv[5]) if len(sys.argv) > 5 else 0)
by_task = collections.defaultdict(list); tools_lines = collections.defaultdict(list)
for l in open(idx_path):
    r = json.loads(l)
    if r.get('bad_line'): continue
    if r['has_tools']: tools_lines[(r['run'], r['file'])].append(r['off'])
    if r['teacher'] or r['model'] != 'openai/gemma-4-31b-it-qat-w4a16-ct': continue
    by_task[r['task']].append(r)
for v in by_task.values(): v.sort(key=lambda r: r['ln'])
eps = [json.loads(l) for l in open(ep_path)]
random.shuffle(eps)
out = []; why_skip = collections.Counter()
for e in eps:
    if len(out) >= N: break
    onset = e['edits'][e['onset_index']]
    recs = by_task[e['attempt']]
    pos = next((i for i, r in enumerate(recs) if r['ln'] == onset['ln']), None)
    if pos is None or pos + 1 >= len(recs): why_skip['no_next_call'] += 1; continue
    on_rec, nx = recs[pos], recs[pos + 1]
    path = f"{ROOT}/{nx['run']}/{nx['file']}"
    with open(path, 'rb') as f:
        f.seek(nx['off']); d = json.loads(f.readline())
    msgs = d['messages']
    # the onset call must be the last assistant turn, followed only by its tool response(s)
    ais = [i for i, m in enumerate(msgs) if m.get('role') == 'assistant']
    if not ais: why_skip['next_record_is_new_episode'] += 1; continue
    ai = ais[-1]
    tcs = msgs[ai].get('tool_calls') or []
    if len(tcs) != 1 or (tcs[0].get('function') or {}).get('name') != 'edit_file': why_skip['last_turn_not_single_edit'] += 1; continue
    tail = msgs[ai + 1:]
    if len(tail) != 1 or tail[0].get('role') != 'tool' or MISSING_ERR not in str(tail[0].get('content')): why_skip['no_adk_missing_error'] += 1; continue
    try: args = json.loads(tcs[0]['function']['arguments'])
    except Exception: why_skip['args_unparseable'] += 1; continue
    toff = max([o for o in tools_lines[(nx['run'], nx['file'])] if o <= nx['off']], default=None)
    if toff is None: why_skip['no_tools'] += 1; continue
    nxc = (nx['calls'] or [{}])[0]
    out.append({'id': f"A2:{nx['run']}:{nx['file']}:{nx['ln']}", 'attempt': e['attempt'], 'run': nx['run'], 'file': nx['file'], 'ln': nx['ln'],
                'off': nx['off'], 'tools_off': toff, 'temp': nx['temp'], 'top_p': nx['top_p'], 'pt': nx['pt'], 'onset_msg_index': ai,
                'onset_tool_call_id': tcs[0].get('id'), 'onset_args': args, 'onset_keys': list(args.keys()),
                'onset_error': tail[0].get('content'), 'onset_index_in_attempt': e['onset_index'],
                'logged_next_call': {'name': nxc.get('name'), 'bad_syn': nxc.get('bad_syn'), 'flags': nxc.get('flags'), 'fp': nxc.get('fp'), 'nh': nxc.get('nh')},
                'logged_next_is_same_content_retry': bool(nxc.get('name') == 'edit_file' and nxc.get('fp') == onset.get('fp') and nxc.get('nh') == onset.get('nh')),
                'attempt_resolved': e.get('resolved')})
with open(outp, 'w') as f:
    for s in out: f.write(json.dumps(s) + '\n')
ln = [s['logged_next_call'] for s in out]
edits = [x for x in ln if x['name'] == 'edit_file']
print('states', len(out), 'skipped', dict(why_skip))
print('logged next call: edit_file', len(edits), 'malformed', sum(x['bad_syn'] for x in edits), '| same-content retries', sum(s['logged_next_is_same_content_retry'] for s in out))
