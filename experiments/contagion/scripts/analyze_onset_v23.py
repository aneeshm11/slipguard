"""PREREG_v2.3 (onset transplant; sha256 7111525f...) primary family O0 vs O1 on P's first 600 S1_B1 states. Written and
hash-frozen before any transplant output existed; analysed once, after the runner logged 'finished'.

Outcomes (A's vLLM-parse judge, S1 keys). The runner judges the FIRST call of the next turn: it stops at the first
closed call, as in every A battery. "The next turn contains an edit call ..." is therefore read as "the next turn's
first call is ...".
  closer slip (primary): the first call is an edit call (judge is_edit) and one of its string values contains a
      look-alike closer followed by ',<declared key>:' (judge 'closer' is not None); unconditional per state
  census-malformed: the first call is malformed in any class, for any tool (judge 'malformed'); unconditional
  escaped-closer share: among closer slips, the share whose closer run contains '"' (this covers \\" and ")
  string-mode drift share: among edit calls, the share with a new/old string value containing a literal backslash-n or
      backslash-quote sequence that occurs nowhere in the state's NATIVE (O0) tool-result texts (a per-state stand-in
      for "where the file has none")
  P(next turn's first call is an edit)
Statistics (PREREG_v2.3 §4):
  - paired by state; each B1 state is its own episode, so the episode-cluster bootstrap over states uses B = 2000,
    seed 20261105, percentile 95% CI;
  - exact one-sided McNemar test on discordant pairs as the sensitivity check;
  - G = (O1 - O0)/(0.174 - O0);
  - verdict: CI_lo(RD) > 0 and G >= 0.50 -> SERIALIZATION INDUCES ONSET, EXPLAINS MOST OF THE GAP;
    CI_lo > 0 and G < 0.50 -> ... PARTIAL; CI_hi(RD) < +2.0 pp -> NO MATERIAL EFFECT; otherwise INCONCLUSIVE;
  - mechanism corroboration (reported only with an INDUCES verdict): the escaped-closer share or the drift share under
    O1 exceeds O0's with bootstrap CI_lo > 0.
Missing or errored jobs are reported per arm; the analysis is complete-case over states with both arms.
usage: analyze_onset_v23.py --out <json> [--res <file>] [--log <runner log>] [--B 2000] [--force_incomplete]
"""
import json, sys, os, math, argparse, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemma_protocol as gp
import variants as V
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True); ap.add_argument('--res', default=f'{D}/out/main/rO_v23.jsonl')
ap.add_argument('--log', default=f'{D}/logs/ctg-O23.log'); ap.add_argument('--B', type=int, default=2000)
ap.add_argument('--force_incomplete', action='store_true')
a = ap.parse_args()
if not a.force_incomplete and not (os.path.exists(a.log) and any(l.startswith('finished') for l in open(a.log))):
    sys.exit("runner log has no 'finished' line -> not analysed (no interim looks)")
MAN = json.load(open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json')))
gp.set_profile(MAN['tool_profile'], tools=MAN['tools'], responses=MAN['harness'].get('responses'))
P = gp.PROFILE
ids = [json.loads(l)['context_id'] for l in open(f'{D}/data/confirmatory/pools/S1_B1.jsonl')][:600]
META = {}
for l in open(f'{D}/data/confirmatory/meta_S1.jsonl'):
    m = json.loads(l)
    if m['id'] in set(ids): META[m['id']] = m
R = {}
for l in open(a.res):
    try: d = json.loads(l)
    except Exception: continue
    if d.get('error'): continue
    R[(d['id'], d['pathway'])] = d
miss = {arm: sum(1 for i in ids if (i, arm) not in R) for arm in ('O0', 'O1')}
cc = [i for i in ids if (i, 'O0') in R and (i, 'O1') in R]
NATIVE = {}


def native_text(i):
    if i not in NATIVE:
        msgs, _ = V.load_context(META[i]); NATIVE[i] = '\n'.join(x['content'] for x in msgs if x['role'] == 'tool' and isinstance(x.get('content'), str))
    return NATIVE[i]


def outcome(i, arm):
    d = R[(i, arm)]; j = d.get('judge') or {}
    edit = bool(j.get('is_edit', False))
    cl = j.get('closer') if edit else None
    o = {'edit': int(edit), 'closer_slip': int(edit and cl is not None), 'census_malformed': int(bool(j.get('malformed'))),
         'escaped_closer': int(cl is not None and '"' in cl), 'drift': 0}
    if edit:
        m = gp.TOOL_CALL_RE.search('<|tool_call>' + (d.get('s2_text') or '') + '<tool_call|>')
        args = gp.parse_args(m.group(2)) if m else {}
        nat = native_text(i)
        for k in (P['new_key'], P['old_key']):
            v = args.get(k)
            if isinstance(v, str) and (('\\n' in v and '\\n' not in nat) or ('\\"' in v and '\\"' not in nat)): o['drift'] = 1
    return o


O = {arm: [outcome(i, arm) for i in cc] for arm in ('O0', 'O1')}
n = len(cc)
X = {arm: {k: np.array([o[k] for o in O[arm]], float) for k in O[arm][0]} for arm in O} if n else {}
rng = np.random.default_rng(20261105)
IDX = rng.integers(0, n, size=(a.B, n)) if n else None


def pct(x): return [round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4)]


def wilson(k, nn, z=1.96):
    if nn == 0: return None
    p = k / nn; dd = 1 + z * z / nn; c = (p + z * z / (2 * nn)) / dd; h = z * math.sqrt(p * (1 - p) / nn + z * z / (4 * nn * nn)) / dd
    return [round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4), nn]


def rd(key):
    x1, x0 = X['O1'][key], X['O0'][key]
    bs = x1[IDX].mean(1) - x0[IDX].mean(1)
    return {'O0': wilson(int(x0.sum()), n), 'O1': wilson(int(x1.sum()), n), 'RD': round(float(x1.mean() - x0.mean()), 4), 'RD_CI': pct(bs)}


def share(num, den):
    """share num/den per arm + O1 - O0 difference (bootstrap over states)."""
    out = {}
    for arm in ('O0', 'O1'):
        out[arm] = wilson(int(X[arm][num].sum()), int(X[arm][den].sum()))
    with np.errstate(divide='ignore', invalid='ignore'):
        d1 = X['O1'][num][IDX].sum(1) / X['O1'][den][IDX].sum(1); d0 = X['O0'][num][IDX].sum(1) / X['O0'][den][IDX].sum(1)
    dd = d1 - d0; dd = dd[np.isfinite(dd)]
    e1 = X['O1'][num].sum() / X['O1'][den].sum() if X['O1'][den].sum() else float('nan')
    e0 = X['O0'][num].sum() / X['O0'][den].sum() if X['O0'][den].sum() else float('nan')
    out['O1_minus_O0'] = [round(float(e1 - e0), 4) if np.isfinite(e1 - e0) else None] + (pct(dd) if len(dd) else [None, None])
    out['finite_draws'] = int(len(dd))
    return out


res = {'prereg': 'PREREG_v2.3_onsetTransplant.md sha256 7111525f15d76787280b78e6b55494a00edb64c3456a1214f7aebfcdd0ee67cb', 'states_planned': len(ids),
       'complete_case_states': n, 'missing_or_error_jobs': miss, 'episodes_distinct': len(set(META[i]['task'] for i in cc)), 'B': a.B,
       'servers': dict(collections.Counter(R[k].get('server') for k in R))}
if n:
    prim = rd('closer_slip')
    b = int(((X['O1']['closer_slip'] == 1) & (X['O0']['closer_slip'] == 0)).sum()); c = int(((X['O1']['closer_slip'] == 0) & (X['O0']['closer_slip'] == 1)).sum())
    p_mc = sum(math.comb(b + c, k) for k in range(b, b + c + 1)) / 2 ** (b + c) if b + c else 1.0
    o0 = float(X['O0']['closer_slip'].mean()); o1 = float(X['O1']['closer_slip'].mean())
    G = (o1 - o0) / (0.174 - o0) if 0.174 - o0 > 0 else None
    lo, hi = prim['RD_CI']
    if lo > 0: verdict = 'SERIALIZATION INDUCES ONSET, EXPLAINS MOST OF THE GAP' if (G is not None and G >= 0.50) else 'SERIALIZATION INDUCES ONSET, PARTIAL'
    elif hi < 0.020: verdict = 'NO MATERIAL EFFECT'
    else: verdict = 'INCONCLUSIVE'
    res['primary_closer_slip'] = {**prim, 'mcnemar_discordant_O1only_O0only': [b, c], 'mcnemar_exact_one_sided_p': round(p_mc, 6),
                                  'gap_fraction_G': round(G, 4) if G is not None else None, 'verdict': verdict,
                                  'D_80PI': {'O0': '1.2% [0.3, 3.0]', 'O1': '3.5% [1.0, 10.0]', 'RD': '+2.3 pp [0, +8]'}}
    res['secondary'] = {'census_malformed': {**rd('census_malformed'), 'D_80PI_O1': '5% [2, 13]'},
                        'P_edit': rd('edit'),
                        'escaped_closer_share_among_slips': {**share('escaped_closer', 'closer_slip'), 'D_80PI': 'O0 <= 0.20; O1 0.40 [0.15, 0.75]'},
                        'string_mode_drift_share_among_edits': {**share('drift', 'edit'), 'D_80PI': 'O0 <= 1%; O1 5% [1, 15]'},
                        'closer_runs': {arm: dict(collections.Counter((R[(i, arm)].get('judge') or {}).get('closer') for i in cc if O[arm][cc.index(i)]['closer_slip'])) for arm in ('O0', 'O1')}}
    if verdict.startswith('SERIALIZATION INDUCES'):
        e, dft = res['secondary']['escaped_closer_share_among_slips']['O1_minus_O0'], res['secondary']['string_mode_drift_share_among_edits']['O1_minus_O0']
        res['mechanism_corroboration'] = bool((e[1] is not None and e[1] > 0) or (dft[1] is not None and dft[1] > 0))
ver = f'{D}/out/onset_o1_verification.json'
if os.path.exists(ver):
    v = json.load(open(ver))
    res['manipulation'] = {'tool_results_with_escaped_quote': {'O0': [v['native_dq_escape'], v['adk_serializer_total']], 'O1': [v['o1_dq_escape'], v['adk_serializer_total']]},
                           'adk_serializer_equal': f"{v['adk_serializer_equal']}/{v['adk_serializer_total']}",
                           'library_pipeline_segments_identical': f"{sum(1 for p in v['pipeline_check'] if p.get('rendered_segments_identical'))}/{len(v['pipeline_check'])} states",
                           'prompt_tokens_mean': [round(v['tokens']['O0_mean'], 1), round(v['tokens']['O1_mean'], 1)]}
json.dump(res, open(a.out, 'w'), indent=1)
print(json.dumps({'complete_case': n, 'missing': miss, 'primary': res.get('primary_closer_slip')}, indent=1))
