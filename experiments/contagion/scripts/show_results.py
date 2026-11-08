import json, sys, collections
rs = [json.loads(l) for l in open(sys.argv[1])]
arm = sys.argv[2] if len(sys.argv) > 2 else None
n = int(sys.argv[3]) if len(sys.argv) > 3 else 3
c = collections.Counter()
for d in rs:
    a = f"{d['pathway']}k{d['k']}"
    if arm and a != arm: continue
    if c[a] >= n: continue
    c[a] += 1
    j = d.get('judge') or {}
    print('=' * 100); print(a, d['id'], 'err', d.get('error'), 's1', d.get('s1_finish'), d.get('s1_stop'), d.get('s1_tokens'), 'opened', d.get('opened_call'), 'judge', {k: j.get(k) for k in ('name', 'malformed', 'why', 'order', 'closer')})
    print('S1:', repr((d.get('s1_text') or '')[:700]))
    print('S2:', repr((d.get('s2_text') or '')[:500]))
