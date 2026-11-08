import json, collections, statistics as S, sys
for mk in ['qwen3-32b', 'qwen3-8b', 'qwen3.5-9b']:
    by = collections.defaultdict(list); p1n = collections.Counter(); temps = collections.Counter()
    for l in open(f'data/prompts_{mk}.jsonl'):
        r = json.loads(l)
        by[r['arm']].append(r['n_prompt']); temps[(r['set'], r['temp'])] += 1
        if r['arm'] == 'P1N': p1n[(r['info'].get('p1n_outcome'), r['info'].get('diff_patch'))] += 1
    print(mk, {a: dict(n=len(v), mean=round(S.mean(v)), p95=sorted(v)[int(.95*len(v))], max=max(v), over25k=sum(x > 32768-7168 for x in v), over32k=sum(x > 32768-608 for x in v)) for a, v in by.items()})
    print('   P1N outcomes', dict(p1n)); print('   temps', dict(temps))
