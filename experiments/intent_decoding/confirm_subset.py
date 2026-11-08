"""Subset a frozen-runner output to the context_ids of another pool file (e.g. verified_only/S1_B1.jsonl), so that the
FROZEN confirm_analyze.py can be applied unchanged to the registered sub-population.
usage: confirm_subset.py <runner_output.jsonl> <pool.jsonl> <out.jsonl>"""
import json, sys
src, pool, dst = sys.argv[1:4]
ids = {json.loads(l)['context_id'] for l in open(pool)}
n = k = 0
with open(dst, 'w') as fo:
    for l in open(src):
        n += 1
        if json.loads(l).get('context_id') in ids:
            fo.write(l); k += 1
print(f'{k}/{n} records kept; pool has {len(ids)} context_ids')
