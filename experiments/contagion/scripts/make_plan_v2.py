"""Confirmatory job plans from the PREREG_v2 pools (written and hash-frozen before P's corpus exists).
Arms (PREREG_v2 "Governs"):
  31B   pool A1: P0 (k 0), P1, P5, P6, P8a, P8b, P9 (k 1); pool A2: P6 at k 1, 2, 4 (C3).
        Shortfall (A2 < 150 eligible, so S1_A1k2.jsonl exists): P6 at k 1, 2 on A1k2, and k 1, 2, 4 on whatever A2 holds.
  12B / E4B   pool A1: P0, P1, P5, P6, P8a.
Every job's context must be in the meta (build_contexts_P.py v1.1) with protocol_clean, k_usable >= k and
k_unmasked >= k; any job that fails this check is listed and the script exits (no silent drops).
Order: context rank ascending, arms grouped per context (leader-first prefix caching in run_injection.py).
usage: make_plan_v2.py <pools dir> <meta.jsonl> <outdir>  -> <outdir>/plan_v2_{31b,small}.jsonl + PLAN_MANIFEST.json
"""
import json, sys, os, hashlib, time
pools, metap, outd = sys.argv[1:4]
os.makedirs(outd, exist_ok=True)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
META = {json.loads(l)['id']: json.loads(l) for l in open(metap)}


def pool(name):
    p = os.path.join(pools, f'S1_{name}.jsonl')
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


A1, A2, A1k2 = pool('A1'), pool('A2'), pool('A1k2')
ARMS31_A1 = [('P0', 0), ('P1', 1), ('P5', 1), ('P6', 1), ('P8a', 1), ('P8b', 1), ('P9', 1)]
ARMS_SMALL = [('P0', 0), ('P1', 1), ('P5', 1), ('P6', 1), ('P8a', 1)]
jobs31, small, bad = [], [], []


def emit(lst, rows, arms, tier):
    for r in sorted(rows, key=lambda r: r['rank']):
        m = META.get(r['context_id'])
        for p, k in arms:
            if m is None or not m['protocol_clean'] or m['k_usable'] < k or m.get('k_unmasked', 0) < k:
                bad.append((r['context_id'], p, k, tier)); continue
            lst.append({'id': r['context_id'], 'pathway': p, 'k': k, 'tier': tier, 'rank': r['rank'], 'half': r.get('half')})


emit(jobs31, A1, ARMS31_A1, 'A1')
emit(jobs31, A2, [('P6', 1), ('P6', 2), ('P6', 4)], 'A2')
if A1k2: emit(jobs31, A1k2, [('P6', 1), ('P6', 2)], 'A1k2')
emit(small, A1, ARMS_SMALL, 'A1')
if bad:
    print(json.dumps({'ineligible_jobs': len(bad), 'examples': bad[:10]})); sys.exit('jobs failed the eligibility re-check; nothing written')
seen = set(); dedup = []
for j in jobs31:  # an A1k2/A2 state can coincide with an A1 state at P6 k 1: run once
    key = (j['id'], j['pathway'], j['k'])
    if key in seen: continue
    seen.add(key); dedup.append(j)
for name, lst in (('plan_v2_31b.jsonl', dedup), ('plan_v2_small.jsonl', small)):
    with open(os.path.join(outd, name), 'w') as f:
        for j in lst: f.write(json.dumps(j) + '\n')
man = {'utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()), 'script_sha256': sha(os.path.abspath(__file__)),
       'pools_manifest_sha256': sha(os.path.join(pools, 'POOLS_MANIFEST.json')) if os.path.exists(os.path.join(pools, 'POOLS_MANIFEST.json')) else None,
       'meta_sha256': sha(metap), 'pools': {'A1': len(A1), 'A2': len(A2), 'A1k2': len(A1k2)},
       'jobs': {'31b': len(dedup), 'small_per_model': len(small)}}
json.dump(man, open(os.path.join(outd, 'PLAN_MANIFEST.json'), 'w'), indent=1)
print(json.dumps(man))
