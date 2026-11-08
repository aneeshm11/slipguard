"""A2 with B's MAP repairs (run on :8303): h = 1 - q(arm)/q(L) with L re-run on the SAME server (pairing).
Arms: Q4M = P4'-MAP (repaired call, new-first, success response), Q8M = P8a-MAP (E's renderer recovering B's call +
MalformedToolCall), Q8b (E's renderer, sanitized). ITT: the 18 abstained states keep Q8b in both MAP arms.
Reported overall (ITT, 300 states) and on the repaired 282; context-clustered bootstrap; plus a server check (L on
:8300 vs :8303) and the retry vs new-content split.
usage: a2_map_analysis.py out.json [B]"""
import os  # added by the repo export (paths are env/config driven)
import json, sys, math, random, re, collections
import numpy as np
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); B = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
random.seed(0)
CL = re.compile(r'(["`\\\']+)\s*,\s*(old_string|new_string|filepath|allow_multiple)\s*:')
norm = lambda s: ' '.join((s or '').replace('\\n', ' ').split())[:40]


def wilson(k, n, z=1.96):
    if n == 0: return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4), n]


def load(f):
    R = {}
    for l in open(f):
        d = json.loads(l)
        if not d.get('error'): R[(d['id'], d['pathway'])] = d
    return R


mal = lambda d: int(bool((d.get('judge') or {}).get('name') == 'edit_file' and (d.get('judge') or {}).get('malformed')))
st = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/a2_states.jsonl')}
rep = set(json.loads(l)['id'] for l in open(f'{D}/data/a2_meta_map.jsonl'))
R = load(f'{D}/out/main/r31b_a2_8303.jsonl'); R0 = load(f'{D}/out/main/r31b_a2.jsonl')
ids = sorted(st)
res = {'states': len(ids), 'repaired': len(rep), 'abstained_ITT_as_Q8b': len(ids) - len(rep)}


def arm_outcome(i, arm):
    if arm in ('Q4M', 'Q8M'):
        key = (i, arm) if i in rep else (i, 'Q8b')  # ITT
    else: key = (i, arm)
    return R.get(key)


def h_block(sel, arm):
    use = [i for i in sel if (i, 'P0') in R and arm_outcome(i, arm) is not None]
    rows = [(mal(R[(i, 'P0')]), mal(arm_outcome(i, arm))) for i in use]
    est = lambda rr: (1 - (sum(r[1] for r in rr) / len(rr)) / (sum(r[0] for r in rr) / len(rr)), sum(r[0] for r in rr) / len(rr), sum(r[1] for r in rr) / len(rr))
    e = est(rows); bs = []
    for _ in range(B):
        rr = [rows[random.randrange(len(rows))] for _ in rows]
        try: bs.append(est(rr)[0])
        except ZeroDivisionError: pass
    return {'n': len(use), 'h': [round(e[0], 4), [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]],
            'q(L)': round(e[1], 4), 'q(arm)': round(e[2], 4)}


for scope, sel in (('ITT_all_300', ids), ('repaired_282', sorted(rep))):
    res[scope] = {arm: h_block(sel, arm) for arm in ('Q4M', 'Q8M')}
res['server_check_L'] = {'L_on_8300': wilson(sum(mal(R0[(i, 'P0')]) for i in ids if (i, 'P0') in R0), sum(1 for i in ids if (i, 'P0') in R0)),
                         'L_on_8303': wilson(sum(mal(R[(i, 'P0')]) for i in ids if (i, 'P0') in R), sum(1 for i in ids if (i, 'P0') in R)),
                         'Q8b_on_8300_abstained18': wilson(sum(mal(R0[(i, 'Q8b')]) for i in ids if i not in rep and (i, 'Q8b') in R0), sum(1 for i in ids if i not in rep and (i, 'Q8b') in R0)),
                         'Q8b_on_8303_abstained18': wilson(sum(mal(R[(i, 'Q8b')]) for i in ids if i not in rep and (i, 'Q8b') in R), sum(1 for i in ids if i not in rep and (i, 'Q8b') in R))}
split = {}
for arm in ('P0', 'Q4M', 'Q8M'):
    c = collections.Counter()
    for i in sorted(rep):
        d = R.get((i, arm))
        if not d: continue
        j = d.get('judge') or {}
        if j.get('name') != 'edit_file': c['no_edit'] += 1; continue
        a = st[i]['onset_args']; ns = a.get('new_string') or ''; m = CL.search(ns)
        retry = (j.get('fp') == a.get('filepath') and norm(j.get('new_head')) == norm(ns[:m.start()] if m else ns))
        c[('retry' if retry else 'new', bool(j.get('malformed')))] += 1
    split[arm] = {'malformed_among_retries': wilson(c[('retry', True)], c[('retry', True)] + c[('retry', False)]),
                  'malformed_among_new': wilson(c[('new', True)], c[('new', True)] + c[('new', False)]), 'no_edit': c['no_edit']}
res['retry_split_on_repaired'] = split
res['rule'] = 'h >= 0.7: quarantine is the dominant lever for 31B; h <= 0.4: content stickiness dominates (IPD-first)'
json.dump(res, open(sys.argv[1], 'w'), indent=1); print(json.dumps(res, indent=1))
