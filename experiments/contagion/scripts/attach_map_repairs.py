"""Attach B's MAP repairs (experiments/intent_decoding/out/a2_map_repairs.jsonl: state_id, context_ref, repaired_call
{arguments dict, canonical new-first}, cut, abstain, logp_margin) to the A2 metadata and write the Q4M/Q8M plan.
Abstentions and missing repairs are excluded and counted.
usage: attach_map_repairs.py [repairs.jsonl]"""
import os  # added by the repo export (paths are env/config driven)
import json, sys
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/out/a2_map_repairs.jsonl')
reps = {}
for l in open(src):
    r = json.loads(l); reps[r['state_id']] = r
metas = [json.loads(l) for l in open(f'{D}/data/a2_meta.jsonl')]
n = ab = miss = 0
with open(f'{D}/data/a2_meta_map.jsonl', 'w') as fm, open(f'{D}/data/plan_a2_map.jsonl', 'w') as fp:
    for m in metas:
        r = reps.get(m['id'])
        if r is None: miss += 1; continue
        if r.get('abstain'): ab += 1; continue
        rc = r['repaired_call']; args = rc.get('arguments', rc) if isinstance(rc, dict) else None
        if isinstance(args, str): args = json.loads(args)
        if not isinstance(args, dict): miss += 1; continue
        m2 = dict(m, map_repair=args, map_cut=r.get('cut'), map_logp_margin=r.get('logp_margin')); fm.write(json.dumps(m2) + '\n'); n += 1
        for pw in ('Q4M', 'Q8M'): fp.write(json.dumps({'id': m['id'], 'pathway': pw, 'k': 1, 'tier': 'A2map'}) + '\n')
print(json.dumps({'states': len(metas), 'with_repair': n, 'abstained': ab, 'missing': miss, 'plan_jobs': 2 * n}))
