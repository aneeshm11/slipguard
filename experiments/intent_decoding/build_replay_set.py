"""Sample first-edit contexts (state right before the FIRST edit_file call of an attempt, base 31B-QAT runs) for replay.
Stratified: at most CAP contexts per task, shuffled with a fixed seed."""
import json, random, collections, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
CAP = int(sys.argv[2]) if len(sys.argv) > 2 else 12
rows = []
with open(os.path.join(HERE, 'data/first_edit_contexts.jsonl')) as f:
    for l in f:
        d = json.loads(l)
        if 'gemma-4-31b' not in d['model'] or d['run'].startswith('test_'):
            continue
        d['task'] = d['attempt'].split('#')[0]
        rows.append(d)
random.Random(0).shuffle(rows)
per = collections.Counter(); out = []
for d in rows:
    if per[d['task']] >= CAP:
        continue
    per[d['task']] += 1
    out.append({k: d[k] for k in ('id', 'run', 'task', 'attempt', 'messages', 'tools', 'filepath', 'orig_bad', 'orig_why', 'prompt_tokens')})
    if len(out) >= N:
        break
with open(os.path.join(HERE, 'data/replay_first_edit.jsonl'), 'w') as fo:
    for d in out:
        fo.write(json.dumps(d) + '\n')
print('tasks available', len({d['task'] for d in rows}), 'selected', len(out), 'tasks', len(per),
      'orig malformed', sum(d['orig_bad'] for d in out))
