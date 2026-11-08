"""Benchmark precision row (EXPLORATORY; requested by the PI, not in PREREG_v2): Gemma-4-31B bf16 on the same 300 PREREG_v2
S1_A1 states, arms P0, P1, P6, P8a. Same estimands and bootstrap as confirm_v2_analysis.py: unconditional and
conditional rates; RD(P1 - P0) and RD(P6 - P0); P8a removal; episode-cluster percentile bootstrap, B = 2000, seed
20261105. Also reports bf16 - QAT paired per arm on the same states (QAT = out/main/rC31b_v2.jsonl). Written before any
bf16 output existed. It refuses to run before the runner logs 'finished'.
RE-DECLARED 2026-11-05 ~11:00 UTC, before any bf16 output (PI): the bf16 server runs with tensor-parallel 2, so KV is
ample. The PRIMARY bf16 row covers ALL 300 S1_A1 states at max_model_len 32768 with the QAT generation settings
(--subset all; plan data/confirmatory/plans/plan_bf16_core_full.jsonl). The 50-state subset below is kept only as a
SECONDARY sensitivity check (--subset le13000); its 16.4k cap no longer applies.
SUPERSEDED SUBSET RULE (pre-declared earlier the same day, before any bf16 output; PI constraint: the bf16 server's KV cache holds about 17k
tokens, so prompt + max generation must be <= 16.4k): the bf16 row is restricted to the S1_A1 states whose LONGEST arm
prompt (max over P0/P1/P6/P8a of the QAT run's rendered n_prompt; the bf16 render is identical) is <= X = 13,000 tokens:
50 of 300 states (data/confirmatory/bf16_subset_ids.txt). The runner is launched with --max_model_len 16400, so
max_tokens = min(7168, 16392 - prompt) >= 3,392. On these states, 0 of the 200 QAT jobs had prompt + generation above
16.4k, so the cap would not have bound under QAT. Every bf16 job that hits the length cap without opening a call is
counted and reported. The QAT comparison is restricted to the same 50 states.
usage: analyze_bf16_core.py --res <bf16 file> --log <runner log> --out <json>"""
import json, sys, argparse, collections, os
import numpy as np
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser(); ap.add_argument('--res', required=True); ap.add_argument('--log', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--B', type=int, default=2000); ap.add_argument('--force_incomplete', action='store_true')
ap.add_argument('--subset', choices=['all', 'le13000'], default='all', help='all = primary (300 states); le13000 = secondary sensitivity (50 states)')
a = ap.parse_args()
if not a.force_incomplete and not any(l.startswith('finished') for l in open(a.log)): sys.exit("no 'finished' line: not analysed")
META = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/confirmatory/meta_S1.jsonl')}
ids = ([json.loads(l)['context_id'] for l in open(f'{D}/data/confirmatory/pools/S1_A1.jsonl')] if a.subset == 'all'
       else [x.strip() for x in open(f'{D}/data/confirmatory/bf16_subset_ids.txt') if x.strip()])


def load(f):
    R = {}
    for l in open(f):
        try: d = json.loads(l)
        except Exception: continue
        if not d.get('error'): R[(d['id'], d['pathway'], d['k'])] = d
    return R


def y(d, kind):
    j = d.get('judge') or {}; e = bool(j.get('is_edit', j.get('name') == 'edit_file')); m = e and bool(j.get('malformed'))
    return (int(m), int(e)) if kind == 'cond' else (int(m), 1)


RB, RQ = load(a.res), load(f'{D}/out/main/rC31b_v2.jsonl')
ARMS = [('P0', 0), ('P1', 1), ('P6', 1), ('P8a', 1)]
cc = [i for i in ids if all((i,) + arm in RB for arm in ARMS)]
cl = sorted(set(META[i]['task'] for i in cc)); ci_ = {c: j for j, c in enumerate(cl)}
rng = np.random.default_rng(20261105); W = rng.multinomial(len(cl), np.full(len(cl), 1 / len(cl)), size=a.B).astype(float)


def sums(R, arm, kind, sel):
    Y = np.zeros(len(cl)); N = np.zeros(len(cl))
    for i in sel:
        m, e = y(R[(i,) + arm], kind); Y[ci_[META[i]['task']]] += m; N[ci_[META[i]['task']]] += e
    return Y, N


def pct(x): x = x[np.isfinite(x)]; return [round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4)]


out = {'label': 'EXPLORATORY benchmark precision row (bf16 vs QAT-ct), PI request; not PREREG_v2', 'complete_states': len(cc), 'episodes': len(cl),
       'missing': {f'{p}k{k}': sum(1 for i in ids if (i, p, k) not in RB) for p, k in ARMS}, 'servers': dict(collections.Counter(d.get('server') for d in RB.values())), 'B': a.B}
for kind in ('uncond', 'cond'):
    S = {arm: sums(RB, arm, kind, cc) for arm in ARMS}
    rate = lambda arm: (S[arm][0].sum() / S[arm][1].sum(), (W @ S[arm][0]) / (W @ S[arm][1]))
    blk = {f'{p}': [round(float(rate((p, k))[0]), 4)] + pct(rate((p, k))[1]) for p, k in ARMS}
    for p, k in (('P1', 1), ('P6', 1)):
        e1, d1 = rate((p, k)); e0, d0 = rate(('P0', 0)); blk[f'RD_{p}_P0'] = [round(float(e1 - e0), 4)] + pct(d1 - d0)
    e1, d1 = rate(('P1', 1)); eq, dq = rate(('P8a', 1)); e0, d0 = rate(('P0', 0))
    den = d1 - d0; rem = np.where(den > 0, (d1 - dq) / np.where(den > 0, den, 1), np.nan)
    blk['P8a_removal'] = [round(float((e1 - eq) / (e1 - e0)), 4) if e1 - e0 > 0 else None] + pct(rem) + [round(float(np.mean(den <= 0)), 4)]
    both = [i for i in cc if all((i,) + arm in RQ for arm in ARMS)]
    SQ = {arm: sums(RQ, arm, kind, both) for arm in ARMS}; SB = {arm: sums(RB, arm, kind, both) for arm in ARMS}
    blk['bf16_minus_QAT_same_states'] = {f'{p}': [round(float(SB[(p, k)][0].sum() / SB[(p, k)][1].sum() - SQ[(p, k)][0].sum() / SQ[(p, k)][1].sum()), 4)]
                                         + pct((W @ SB[(p, k)][0]) / (W @ SB[(p, k)][1]) - (W @ SQ[(p, k)][0]) / (W @ SQ[(p, k)][1])) for p, k in ARMS}
    blk['bf16_minus_QAT_same_states']['n_states'] = len(both)
    out[kind] = blk
out['subset_rule'] = 'PRIMARY: all 300 S1_A1 states (max_model_len 32768, QAT generation settings)' if a.subset == 'all' else 'SECONDARY sensitivity: the 50 states with max-arm prompt <= 13,000 tokens'
out['length_cap_hits'] = {f'{p}k{k}': sum(1 for i in cc if RB[(i, p, k)].get('s1_finish') == 'length' and not RB[(i, p, k)].get('opened_call')) for p, k in ARMS}
json.dump(out, open(a.out, 'w'), indent=1); print(json.dumps(out, indent=1)[:2500])
