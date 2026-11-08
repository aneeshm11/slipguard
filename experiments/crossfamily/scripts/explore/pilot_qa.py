"""Operational QA of a generation file (no outcome contrasts): errors, call/no-call/unparsed counts per arm, thought
lengths, budget forcing, calls inside an unclosed thought, and example tails. usage: pilot_qa.py gen.jsonl [n_examples]"""
import json, sys, collections, statistics as S
rows = [json.loads(l) for l in open(sys.argv[1])]
nex = int(sys.argv[2]) if len(sys.argv) > 2 else 2
print('records', len(rows), 'errors', sum(1 for r in rows if r.get('error')), 'judge_errors', sum(1 for r in rows if r.get('judge_error')))
c = collections.Counter(); th = []; ct = []
for r in rows:
    j = r.get('judge') or {}
    c[(r['arm'], 'call' if j.get('opened_call') else ('UNCLOSED_THINK_CALL' if '<tool_call>' in r.get('gen', '') and '</think>' not in r.get('gen', '') else 'no_call'))] += 1
    th.append(r.get('thought_tokens') or 0); ct.append(r.get('completion_tokens') or 0)
for k, v in sorted(c.items()): print(v, k)
print('thought median', S.median(th), 'p90', sorted(th)[int(.9 * len(th))], 'max', max(th), '| completion median', S.median(ct), 'max', max(ct),
      '| budget_forced', sum(1 for r in rows if r.get('budget_forced')))
for r in rows[:nex]:
    print('---', r['arm'], r['id'][:40], repr(r.get('gen', '')[-400:]))
