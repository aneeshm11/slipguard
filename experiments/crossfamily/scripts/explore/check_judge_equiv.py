"""v2 judge (prof auto, strict reasoning) must reproduce the stored discovery judge exactly on S0 contexts."""
import json, sys
sys.path.insert(0, 'scripts')
import qwenproto as qp
P = {}
for l in open('data/prompts_qwen3-8b.jsonl'):
    r = json.loads(l); P[(r['id'], r['arm'])] = r['tools']
n = same = 0; diff = []
for f in sys.argv[1:]:
    for l in open(f):
        d = json.loads(l)
        if d.get('error') or not d.get('judge'): continue
        j2 = qp.judge(d['gen'], d['fmt'], P[(d['id'], d['arm'])], d['model'])
        j1 = dict(d['judge'])
        j2b = {k: v for k, v in j2.items() if k not in ('is_edit', 'call_in_unclosed_reasoning')}
        n += 1; same += int(j1 == j2b)
        if j1 != j2b and len(diff) < 3: diff.append((d['id'], d['arm'], {k: (j1.get(k), j2b.get(k)) for k in set(j1) | set(j2b) if j1.get(k) != j2b.get(k)}))
print('records', n, 'identical', same, diff)
