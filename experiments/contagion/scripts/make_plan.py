"""Select contexts and arms for the injection experiment.

Eligible context: plain base 31B, protocol-clean history (no malformed/raw tool call, no missing-parameter error), and
its k most recent prior edit_file calls valid + successful (k_usable >= 1).
Tiers (jobs ordered tier by tier; arms of one context adjacent for prefix-cache reuse):
  T1  P0 + P1..P5 at k=1 on the main sample
  T2  P1..P5 at k=4 (+ k=2) on contexts with k_usable >= 4 (all of them), plus their T1 arms if not in the main sample
  T3  P1..P5 at k=2 on main-sample contexts with k_usable >= 2
usage: make_plan.py meta.jsonl out_plan.jsonl --n_main N [--seed S] [--pilot N] [--arms ...]
"""
import json, sys, random, argparse, collections
ap = argparse.ArgumentParser()
ap.add_argument('meta'); ap.add_argument('out')
ap.add_argument('--n_main', type=int, default=1800); ap.add_argument('--seed', type=int, default=0)
ap.add_argument('--pilot', type=int, default=0); ap.add_argument('--exclude', default='')
ap.add_argument('--tiers', default='T1,T2,T3'); ap.add_argument('--pathways', default='P1,P2,P3,P4,P5')
ap.add_argument('--ids', default='', help='restrict to ids listed in this file (one per line)')
a = ap.parse_args()
random.seed(a.seed)
metas = [json.loads(l) for l in open(a.meta)]
elig = [m for m in metas if m['protocol_clean'] and m['k_usable'] >= 1]
if a.ids:
    keep = set(x.strip() for x in open(a.ids) if x.strip()); elig = [m for m in elig if m['id'] in keep]
excl = set()
if a.exclude:
    for l in open(a.exclude): excl.add(json.loads(l)['id'])
elig = [m for m in elig if m['id'] not in excl]
random.shuffle(elig)
PW = a.pathways.split(',')
jobs = []
if a.pilot:
    sel = [m for m in elig if m['k_usable'] >= 2][:a.pilot]
    for m in sel:
        jobs.append({'id': m['id'], 'pathway': 'P0', 'k': 0})
        for p in PW: jobs.append({'id': m['id'], 'pathway': p, 'k': 1})
else:
    main = elig[:a.n_main]; main_ids = set(m['id'] for m in main)
    k4 = [m for m in elig if m['k_usable'] >= 4]
    tiers = a.tiers.split(',')
    if 'T1' in tiers:
        for m in main:
            jobs.append({'id': m['id'], 'pathway': 'P0', 'k': 0, 'tier': 'T1'})
            for p in PW: jobs.append({'id': m['id'], 'pathway': p, 'k': 1, 'tier': 'T1'})
    if 'T2' in tiers:
        for m in k4:
            if m['id'] not in main_ids:
                jobs.append({'id': m['id'], 'pathway': 'P0', 'k': 0, 'tier': 'T2'})
                for p in PW: jobs.append({'id': m['id'], 'pathway': p, 'k': 1, 'tier': 'T2'})
            for p in PW: jobs.append({'id': m['id'], 'pathway': p, 'k': 4, 'tier': 'T2'})
            for p in PW: jobs.append({'id': m['id'], 'pathway': p, 'k': 2, 'tier': 'T2'})
    if 'T3' in tiers:
        k4ids = set(m['id'] for m in k4)
        for m in main:
            if m['k_usable'] >= 2 and m['id'] not in k4ids:
                for p in PW: jobs.append({'id': m['id'], 'pathway': p, 'k': 2, 'tier': 'T3'})
with open(a.out, 'w') as f:
    for j in jobs: f.write(json.dumps(j) + '\n')
c = collections.Counter((j.get('tier'), j['pathway'], j['k']) for j in jobs)
print('eligible', len(elig), 'jobs', len(jobs), 'contexts', len(set(j['id'] for j in jobs)))
print(sorted(c.items()))
