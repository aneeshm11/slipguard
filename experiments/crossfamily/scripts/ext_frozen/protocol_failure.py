"""EXPLORATORY (requested by the PI after the Qwen3-8B discovery result; not pre-registered): per-arm "any protocol
failure" metrics that add the Qwen-native reasoning-delimiter slip to the registered malformed judge.

A generated turn whose tool call sits inside an UNCLOSED '<think>' is delivered by vLLM 0.19.1's qwen3 reasoning parser
as reasoning only -> the harness sees no call ("dropped"). Definitions per context (first call of the next turn):
  dropped_any   the turn contains a '<tool_call>' inside an unclosed thought (registered judge: no call)
  dropped_edit  dropped_any and the swallowed call is the edit tool (judged with the lenient split, vLLM 0.31 semantics)
  PF_edit       registered malformed edit OR dropped_edit
  PF_any        registered malformed call of any tool OR dropped_any
Paired unconditional RDs vs P0 with an attempt/episode-cluster bootstrap (cluster = the record's 'task' field), and
P1L-excess removal for P5 / P8a on PF_edit.
usage: protocol_failure.py --gen out/gen_<mk>.jsonl --prompts data/prompts_<mk>.jsonl --out out/pf_<mk>.json [--B 10000]
"""
import argparse
import collections
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qwenproto as qp  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--gen', nargs='+', required=True); ap.add_argument('--prompts', nargs='+', required=True)
ap.add_argument('--out', required=True); ap.add_argument('--B', type=int, default=10000)
a = ap.parse_args()
rng = np.random.default_rng(20261104)


def wilson(k, n, z=1.959964):
    if n == 0:
        return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0.0, c - h), 4), round(min(1.0, c + h), 4), n]


TOOLS = {}
for f in a.prompts:
    for line in open(f):
        r = json.loads(line); TOOLS[(r['id'], r['arm'])] = r['tools']
R = {}
for f in a.gen:
    for line in open(f):
        d = json.loads(line)
        if d.get('error') or not d.get('judge'):
            continue
        R[(d['id'], d['arm'])] = d
O = {}
for key, d in R.items():
    js = d['judge']; t = TOOLS[key]
    jl = qp.judge(d['gen'], d['fmt'], t, d['model'], lenient_reasoning=True)
    reg_call = bool(js.get('opened_call') or js.get('tools_called'))
    reg_edit = bool(js.get('is_edit', js.get('name') == 'edit_file'))
    dropped = bool(jl.get('call_in_unclosed_reasoning'))
    dropped_edit = dropped and bool(jl.get('is_edit', jl.get('name') == 'edit_file'))
    mal_edit = reg_edit and bool(js.get('malformed'))
    mal_any = reg_call and bool(js.get('malformed'))
    O[key] = {'task': d['task'], 'mal_edit': int(mal_edit), 'dropped_any': int(dropped), 'dropped_edit': int(dropped_edit),
              'PF_edit': int(mal_edit or dropped_edit), 'PF_any': int(mal_any or dropped),
              'dropped_edit_malformed': int(dropped_edit and bool(jl.get('malformed')))}
arms = sorted(set(k[1] for k in O))
METRICS = ('mal_edit', 'dropped_any', 'dropped_edit', 'PF_edit', 'PF_any', 'dropped_edit_malformed')
out = {'note': 'EXPLORATORY (PI request 2026-11-04 ~15:50 UTC, after the 8B discovery result); not pre-registered',
       'gen': a.gen, 'arms': {}, 'paired_vs_P0': {}, 'removal_PF_edit': {}}
for arm in arms:
    ks = [k for k in O if k[1] == arm]
    out['arms'][arm] = {m: wilson(sum(O[k][m] for k in ks), len(ks)) for m in METRICS}


def boot_rd(arm, base, metric):
    ids = [k[0] for k in O if k[1] == arm and (k[0], base) in O]
    if not ids:
        return None
    acc = collections.defaultdict(lambda: np.zeros(3))
    for i in ids:
        acc[O[(i, arm)]['task']] += np.array([1, O[(i, arm)][metric], O[(i, base)][metric]], float)
    S = np.array(list(acc.values())); T = S.sum(0)
    W = rng.multinomial(len(S), np.full(len(S), 1.0 / len(S)), size=a.B).astype(float); BT = W @ S
    rd_b = (BT[:, 1] - BT[:, 2]) / BT[:, 0]
    return {'n': int(T[0]), 'arm': round(T[1] / T[0], 4), 'base': round(T[2] / T[0], 4), 'RD': round((T[1] - T[2]) / T[0], 4),
            'RD_CI': [round(float(np.percentile(rd_b, 2.5)), 4), round(float(np.percentile(rd_b, 97.5)), 4)],
            'p_one_sided_RD_gt_0': round((1 + int(np.sum(rd_b <= 0))) / (a.B + 1), 5),
            'p_one_sided_RD_lt_0': round((1 + int(np.sum(rd_b >= 0))) / (a.B + 1), 5)}


for arm in arms:
    if arm in ('P0', 'C0'):
        continue
    out['paired_vs_P0'][arm] = {m: boot_rd(arm, 'P0', m) for m in ('PF_edit', 'PF_any', 'dropped_any')}
for Q in ('P5', 'P8a'):
    if Q in arms and 'P1L' in arms:
        out['removal_PF_edit'][Q] = {'RD_P1L_minus_Q': boot_rd('P1L', Q, 'PF_edit'), 'RD_Q_minus_P0': boot_rd(Q, 'P0', 'PF_edit')}
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
json.dump(out, open(a.out, 'w'), indent=1)
for arm in arms:
    s = out['arms'][arm]
    print(arm, 'mal_edit', s['mal_edit'][:3], 'dropped_any', s['dropped_any'][:3], 'dropped_edit', s['dropped_edit'][:3],
          'PF_edit', s['PF_edit'][:3], 'PF_any', s['PF_any'][:3])
for arm, v in out['paired_vs_P0'].items():
    print('RD vs P0', arm, {m: (x['RD'], x['RD_CI']) for m, x in v.items() if x})
