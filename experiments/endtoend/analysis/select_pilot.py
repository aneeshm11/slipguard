"""Pilot task selection: tasks gradable in OUR Docker sandbox (gold patch resolves AND empty patch does not),
seeded stratified sample approximating the public repo mix, one random order shared by all conditions.
Usage: select_pilot.py runs/gold_routed/gold.jsonl configs/pilot_tasks.txt [n=40] [seed=20261104]"""
import collections
import json
import random
import sys

src, out = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 20261104
rows = collections.defaultdict(dict)
for line in open(src):
    r = json.loads(line)
    rows[r['id']][r['kind']] = r['resolved']
elig = sorted(t for t, k in rows.items() if k.get('gold') is True and k.get('empty') is False)
by_repo = collections.defaultdict(list)
for t in elig:
    by_repo[t.split('_')[0]].append(t)
public_mix = {'fastapi': 67, 'rich': 48, 'requests': 13, 'httpx': 1}
tot = sum(public_mix.values())
rnd = random.Random(seed)
quota = {r: min(len(by_repo[r]), round(n * public_mix[r] / tot)) for r in public_mix}
while sum(quota.values()) < n and any(quota[r] < len(by_repo[r]) for r in quota):  # fill shortfalls
    r = max((r for r in quota if quota[r] < len(by_repo[r])), key=lambda r: len(by_repo[r]) - quota[r])
    quota[r] += 1
while sum(quota.values()) > n:
    r = max(quota, key=lambda r: quota[r])
    quota[r] -= 1
pick = []
for r in sorted(quota):
    pick += rnd.sample(sorted(by_repo[r]), quota[r])
rnd.shuffle(pick)
open(out, 'w').write('\n'.join(pick) + '\n')
meta = {'source': src, 'seed': seed, 'n_eligible': len(elig), 'eligible_by_repo': {r: len(v) for r, v in by_repo.items()},
        'quota': quota, 'tasks': pick}
open(out.replace('.txt', '.json'), 'w').write(json.dumps(meta, indent=1))
print(json.dumps({k: v for k, v in meta.items() if k != 'tasks'}))
