"""Workstream X analysis for one model: census summary, per-arm rates, paired contrasts vs P0 (attempt-cluster
bootstrap), removal fractions (P5, P8a), copy-check decomposition, natural-slip format classes.
Primary endpoint (pre-registered, prereg.md): unconditional P(next call is a malformed edit_file) per context.
usage: analyze.py --mk <model_key> --gen out/gen_<mk>.jsonl [more.jsonl] --out out/ana_<mk>.json [--B 10000]
"""
import argparse
import collections
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ap = argparse.ArgumentParser()
ap.add_argument('--mk', required=True); ap.add_argument('--gen', nargs='+', required=True)
ap.add_argument('--out', required=True); ap.add_argument('--B', type=int, default=10000)
ap.add_argument('--no_copy', action='store_true')
ap.add_argument('--contexts', default='', help='v2: context records JSONL (id, messages, tools, ...); default = A\'s main-track index')
ap.add_argument('--harness', default='adk')
ap.add_argument('--manifest', default='', help='v2: workstream P corpus manifest (CONTEXT_SCHEMA.md); never reads outcomes')
ap.add_argument('--ids', default='', help='restrict to context ids listed in this file (e.g. PREREG_v2 halves H1/H2)')
a = ap.parse_args()
rng = np.random.default_rng(20261104)


def wilson(k, n, z=1.959964):
    if n == 0:
        return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0.0, c - h), 4), round(min(1.0, c + h), 4), n]


import arms as AR  # noqa: E402
import qwenproto as qp  # noqa: E402
if a.contexts or a.manifest:  # v2: generic context records (workstream P's corpus or re-keyed tests)
    import arms_v2 as A2
    META, CTX = {}, {}
    if a.manifest:
        recs_, HP = A2.load_p_corpus(a.manifest)
    else:
        recs_, HP = [json.loads(line) for line in open(a.contexts)], a.harness
    a.harness = HP
    for rec in recs_:
        m_, c_ = A2.context_from_record(rec, HP); META[rec['id']] = m_; CTX[rec['id']] = c_
else:
    META = AR.load_meta(); CTX = None


def get_ctx(cid):
    return CTX[cid] if CTX is not None else AR.load_context(META[cid])
R = {}
KEEP = set(x.strip() for x in open(a.ids) if x.strip()) if a.ids else None
n_err = collections.Counter()
for f in a.gen:
    for line in open(f):
        d = json.loads(line)
        if d.get('model') != a.mk:
            continue
        if d.get('error') or d.get('judge') is None:
            n_err[str(d.get('error') or d.get('judge_error'))[:40]] += 1
            continue
        if KEEP is not None and d['id'] not in KEEP:
            continue
        R[(d['id'], d['arm'])] = d


def outcome(d):
    j = d.get('judge') or {}
    call = int(bool(j.get('opened_call') or j.get('tools_called')))
    edit = int(j.get('is_edit', j.get('name') == 'edit_file'))
    mal = bool(j.get('malformed'))
    return {'call': call, 'edit': edit, 'mal_edit': int(edit and mal), 'mal_any': int(call and mal),
            'gem_mal_edit': int(edit and bool(j.get('gemma_flags'))), 'loud_edit': int(edit and j.get('why') == 'unparsed'),
            'strict_bad_edit': int(edit and not j.get('strict_ok')), 'name': j.get('name') or ('<no call>' if not call else '<unparsed>'),
            'flags': j.get('flags') or [], 'why': j.get('why')}


def arm_summary(ds):
    os_ = [outcome(d) for d in ds]
    n = len(os_); ne = sum(o['edit'] for o in os_); nc = sum(o['call'] for o in os_)
    return {
        'n': n, 'P_call': wilson(nc, n), 'P_edit': wilson(ne, n),
        'P_malformed_edit_uncond': wilson(sum(o['mal_edit'] for o in os_), n),
        'P_malformed_given_edit': wilson(sum(o['mal_edit'] for o in os_), ne),
        'P_malformed_any_call_given_call': wilson(sum(o['mal_any'] for o in os_), nc),
        'P_malformed_edit_uncond_gemma_definition': wilson(sum(o['gem_mal_edit'] for o in os_), n),
        'P_loud_edit_uncond': wilson(sum(o['loud_edit'] for o in os_), n),
        'P_strict_reject_given_edit': wilson(sum(o['strict_bad_edit'] for o in os_), ne),
        'first_call_names': dict(collections.Counter(o['name'] for o in os_).most_common(8)),
        'malformed_edit_why': dict(collections.Counter(o['why'] for o in os_ if o['mal_edit']).most_common(8)),
        'malformed_edit_flags': dict(collections.Counter(f for o in os_ if o['mal_edit'] for f in o['flags']).most_common(12)),
        'budget_forced': sum(1 for d in ds if d.get('budget_forced')),
        'thought_tokens_median': float(np.median([d.get('thought_tokens') or 0 for d in ds])) if ds else None,
        'edit_order': dict(collections.Counter((d['judge'] or {}).get('order') for d in ds if outcome(d)['edit']))}


ids_by_arm = collections.defaultdict(list)
for (cid, arm) in R:
    ids_by_arm[arm].append(cid)
out = {'model': a.mk, 'n_records': len(R), 'errors': dict(n_err), 'arms': {}}
for arm in sorted(ids_by_arm):
    out['arms'][arm] = arm_summary([R[(i, arm)] for i in sorted(ids_by_arm[arm])])
# reference: the LOGGED Gemma-4-31B next call on the same contexts (A's index; target.bad_syn = synthesis criterion)
out['logged_gemma31b_next_call_malformed'] = {
    arm: wilson(sum(int(META[i]['target']['bad_syn']) for i in ids_by_arm[arm]), len(ids_by_arm[arm]))
    for arm in ('C0', 'P0') if arm in ids_by_arm and all('target' in META[i] for i in ids_by_arm[arm])}


# ---------------------------------------------------------------------------------------------- paired statistics
def cluster_sums(rows):
    """rows: (cluster, x, b, ex, eb) -> cluster keys, (K x 5) sums [n, x, b, ex, eb]"""
    acc = collections.defaultdict(lambda: np.zeros(5))
    for c, x, b, ex, eb in rows:
        acc[c] += np.array([1, x, b, ex, eb], dtype=float)
    keys = list(acc)
    return keys, np.array([acc[k] for k in keys])


def boot_totals(S, B):
    K = S.shape[0]
    W = rng.multinomial(K, np.full(K, 1.0 / K), size=B).astype(float)  # B x K cluster weights
    return W @ S  # B x 5


def pct(v, q):
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return None
    s = np.sort(v); x = s[min(len(s) - 1, max(0, int(np.ceil(q / 100 * len(s))) - 1))]
    return 'inf' if np.isinf(x) else round(float(x), 4)


def paired(arm, base='P0'):
    ids = [i for i in ids_by_arm[arm] if (i, base) in R]
    if not ids:
        return None
    rows = []; n10 = n01 = 0
    for i in ids:
        ox, ob = outcome(R[(i, arm)]), outcome(R[(i, base)])
        rows.append((META[i]['task'], ox['mal_edit'], ob['mal_edit'], ox['edit'], ob['edit']))
        n10 += int(ox['mal_edit'] and not ob['mal_edit']); n01 += int(ob['mal_edit'] and not ox['mal_edit'])
    keys, S = cluster_sums(rows)
    T = S.sum(0); BT = boot_totals(S, a.B)
    n, x, b, ex, eb = T
    res = {'n_contexts': int(n), 'n_attempts': len(keys), 'events_arm': int(x), 'events_base': int(b),
           'discordant_arm_only': n10, 'discordant_base_only': n01}
    # unconditional (primary)
    rd = (x - b) / n; rd_b = (BT[:, 1] - BT[:, 2]) / BT[:, 0]
    with np.errstate(divide='ignore', invalid='ignore'):
        rr_b = np.where(BT[:, 2] > 0, BT[:, 1] / BT[:, 2], np.where(BT[:, 1] > 0, np.inf, np.nan))
    res['uncond'] = {'arm': round(x / n, 4), 'base': round(b / n, 4), 'RD': round(rd, 4),
                     'RD_CI': [pct(rd_b, 2.5), pct(rd_b, 97.5)],
                     'p_one_sided_RD_gt_0': round((1 + int(np.sum(rd_b <= 0))) / (a.B + 1), 5),
                     'p_one_sided_RD_lt_0': round((1 + int(np.sum(rd_b >= 0))) / (a.B + 1), 5),
                     'ratio': (round(x / b, 3) if b > 0 else ('inf' if x > 0 else None)),
                     'ratio_CI': [pct(rr_b, 2.5), pct(rr_b, 97.5)],
                     'ratio_haldane': round(((x + 0.5) / (n + 1)) / ((b + 0.5) / (n + 1)), 3)}
    # exact McNemar (one-sided, arm > base), on discordant pairs
    m = n10 + n01
    res['uncond']['mcnemar_exact_p_one_sided'] = round(sum(math.comb(m, k) for k in range(n10, m + 1)) / 2 ** m, 6) if m else 1.0
    # conditional on an edit (secondary)
    with np.errstate(divide='ignore', invalid='ignore'):
        cx = BT[:, 1] / BT[:, 3]; cb = BT[:, 2] / BT[:, 4]
    if ex > 0 and eb > 0:
        res['cond'] = {'arm': round(x / ex, 4), 'base': round(b / eb, 4), 'RD': round(x / ex - b / eb, 4),
                       'RD_CI': [pct(cx - cb, 2.5), pct(cx - cb, 97.5)],
                       'ratio': (round((x / ex) / (b / eb), 3) if b > 0 else ('inf' if x > 0 else None)),
                       'ratio_CI': [pct(np.where(cb > 0, cx / cb, np.where(cx > 0, np.inf, np.nan)), 2.5),
                                    pct(np.where(cb > 0, cx / cb, np.where(cx > 0, np.inf, np.nan)), 97.5)],
                       'n_edits_arm': int(ex), 'n_edits_base': int(eb)}
    # P(edit) difference (post-treatment selection check)
    res['P_edit'] = {'arm': round(ex / n, 4), 'base': round(eb / n, 4), 'RD': round((ex - eb) / n, 4),
                     'RD_CI': [pct((BT[:, 3] - BT[:, 4]) / BT[:, 0], 2.5), pct((BT[:, 3] - BT[:, 4]) / BT[:, 0], 97.5)]}
    return res


def removal(Q, X='P1L', base='P0'):
    ids = [i for i in ids_by_arm[X] if (i, Q) in R and (i, base) in R]
    if not ids:
        return None
    acc = collections.defaultdict(lambda: np.zeros(7))
    for i in ids:
        o1, oq, o0 = outcome(R[(i, X)]), outcome(R[(i, Q)]), outcome(R[(i, base)])
        acc[META[i]['task']] += np.array([1, o1['mal_edit'], oq['mal_edit'], o0['mal_edit'], o1['edit'], oq['edit'], o0['edit']], float)
    S = np.array(list(acc.values())); T = S.sum(0)
    W = rng.multinomial(len(S), np.full(len(S), 1.0 / len(S)), size=a.B).astype(float); BT = W @ S
    res = {'n_contexts': int(T[0])}
    for metric in ('uncond', 'cond'):
        if metric == 'uncond':
            p1, pq, p0 = T[1] / T[0], T[2] / T[0], T[3] / T[0]
            b1, bq, b0 = BT[:, 1] / BT[:, 0], BT[:, 2] / BT[:, 0], BT[:, 3] / BT[:, 0]
        else:
            if min(T[4], T[5], T[6]) == 0:
                continue
            p1, pq, p0 = T[1] / T[4], T[2] / T[5], T[3] / T[6]
            with np.errstate(divide='ignore', invalid='ignore'):
                b1, bq, b0 = BT[:, 1] / BT[:, 4], BT[:, 2] / BT[:, 5], BT[:, 3] / BT[:, 6]
        with np.errstate(divide='ignore', invalid='ignore'):
            fb = np.where(b1 - b0 != 0, (b1 - bq) / (b1 - b0), np.nan)
        rdq = b1 - bq
        res[metric] = {X: round(p1, 4), Q: round(pq, 4), base: round(p0, 4),
                       'fraction_removed': (round((p1 - pq) / (p1 - p0), 3) if p1 != p0 else None),
                       'CI': [pct(fb, 2.5), pct(fb, 97.5)],
                       f'RD_{X}_minus_{Q}': round(p1 - pq, 4), 'RD_CI': [pct(rdq, 2.5), pct(rdq, 97.5)],
                       'p_one_sided_removal_gt_0': round((1 + int(np.sum(rdq <= 0))) / (a.B + 1), 5)}
    return res


out['paired_vs_P0'] = {arm: paired(arm) for arm in sorted(ids_by_arm) if arm not in ('P0', 'C0')}
out['removal'] = {Q: removal(Q) for Q in ('P5', 'P8a', 'P1N', 'P6') if Q in ids_by_arm and 'P1L' in ids_by_arm}


# ---------------------------------------------------------------------------------------------- copy check
def norm40(s):
    return ' '.join((s or '').split())[:40]


if not a.no_copy and 'P1L' in ids_by_arm:
    INJ = {}
    for cid in sorted(set(ids_by_arm.get('P1L', []) + ids_by_arm.get('P6', []) + ids_by_arm.get('P1N', []) + ids_by_arm.get('P8a', []))):
        meta = META[cid]; msgs, tools = get_ctx(cid); p = meta['prior'][-1]
        orig = json.loads(msgs[p['ai']]['tool_calls'][0]['function']['arguments'])
        if CTX is None:
            sk = AR.AV.slip_key_for(list(orig))
            vm, _, _ = AR.AV.make_variant(msgs, meta['prior'], 'P1', 1)
        else:
            prof_ = qp.profile_from_tools(tools)
            sk = A2.slip_key(list(orig), ('old_string', 'new_string') if prof_ is None else (prof_.old, prof_.new))
            vm, _ = A2.make_variant(msgs, meta['prior'], 'P1L', tools, 'hermes', a.harness)
        laundered = json.loads(vm[p['ai']]['tool_calls'][0]['function']['arguments'])
        esc = json.dumps(orig[sk], ensure_ascii=False)[:-1]
        prof_ = qp.profile_from_tools(tools)
        INJ[cid] = {'sk': sk, 'sk_field': 'new_string' if sk == ('new_string' if prof_ is None else prof_.new) else 'old_string',
                    'orig': orig[sk], 'fp': orig.get('filepath' if prof_ is None else prof_.path), 'laundered': laundered.get(sk),
                    'raw_junction': esc[-40:] + '`'}
    tab = collections.defaultdict(collections.Counter)
    for arm in ('P0', 'P1L', 'P6', 'P8a', 'P1N'):
        for cid in ids_by_arm.get(arm, []):
            if cid not in INJ:
                continue
            d = R[(cid, arm)]; j = d.get('judge') or {}
            if not j.get('is_edit', j.get('name') == 'edit_file'):
                continue
            inj = INJ[cid]; sk = inj['sk']
            if arm == 'P1N':
                injected = ((d.get('info') or {}).get('p1n_args') or {}).get(sk)
            elif arm in ('P1L', 'P6'):
                injected = inj['laundered']
            else:
                injected = None
            g = j.get(inj['sk_field'])
            if g is None:
                raw = j.get('raw_call') or ''
                cls = 'copy_corrupted_raw' if (arm == 'P1N' and inj['raw_junction'] in raw) else ('unparsed_other' if j.get('why') == 'unparsed' else 'key_missing')
            elif injected is not None and g == injected:
                cls = 'copy_corrupted'
            elif g == inj['orig'] and j.get('fp') == inj['fp']:
                cls = 'clean_retry'
            elif norm40(g) == norm40(inj['orig']):
                cls = 'same_content_variant'
            else:
                cls = 'new_content'
            tab[arm][(cls, bool(j.get('malformed')))] += 1
    cc = {}
    for arm, c in tab.items():
        row = {}
        for cls in ('copy_corrupted', 'copy_corrupted_raw', 'clean_retry', 'same_content_variant', 'new_content', 'unparsed_other', 'key_missing'):
            n = c[(cls, True)] + c[(cls, False)]
            if n:
                row[cls] = {'n': n, 'malformed': wilson(c[(cls, True)], n)}
        tot = sum(c.values()); mal = sum(v for (cls, b), v in c.items() if b)
        copies = c[('copy_corrupted', True)] + c[('copy_corrupted_raw', True)]
        row['all_edits'] = {'n': tot, 'malformed': wilson(mal, tot)}
        row['share_of_malformed_that_are_verbatim_copies'] = wilson(copies, mal) if mal else None
        nc_n = sum(v for (cls, b), v in c.items() if cls in ('new_content',)); nc_m = c[('new_content', True)]
        row['new_content_edits_malformed'] = wilson(nc_m, nc_n)
        noncopy_n = sum(v for (cls, b), v in c.items() if not cls.startswith('copy')); noncopy_m = sum(v for (cls, b), v in c.items() if b and not cls.startswith('copy'))
        row['non_copy_edits_malformed'] = wilson(noncopy_m, noncopy_n)
        cc[arm] = row
    out['copy_check'] = cc

# ---------------------------------------------------------------------------------------------- natural slips (census + P0)
nat = collections.Counter(); ex = {}
for (cid, arm), d in R.items():
    if arm not in ('C0', 'P0'):
        continue
    j = d.get('judge') or {}
    if not (j.get('opened_call') or j.get('tools_called')):
        continue
    key = 'edit' if j.get('is_edit', j.get('name') == 'edit_file') else 'other'
    if j.get('malformed'):
        kind = 'loud_unparsed' if j.get('why') == 'unparsed' else 'silent_parsed_malformed'
        nat[(arm, key, kind)] += 1
        ex.setdefault(f'{arm}:{key}:{kind}', [])
        if len(ex[f'{arm}:{key}:{kind}']) < 3:
            ex[f'{arm}:{key}:{kind}'].append({'id': cid, 'flags': j.get('flags'), 'raw': (j.get('raw_call') or '')[:800],
                                              'new_head': (j.get('new_string') or '')[:200]})
    else:
        nat[(arm, key, 'ok_strict_ok' if j.get('strict_ok') else 'ok_but_strict_reject:' + str(j.get('strict_code')).split(':')[0])] += 1
out['natural_calls'] = {f'{k[0]}|{k[1]}|{k[2]}': v for k, v in sorted(nat.items())}
out['natural_examples'] = ex
json.dump(out, open(a.out, 'w'), indent=1)
show = {k: {kk: v[kk] for kk in ('n', 'P_edit', 'P_malformed_edit_uncond', 'P_malformed_given_edit')} for k, v in out['arms'].items()}
print(json.dumps(show, indent=0))
print(json.dumps({k: (v or {}).get('uncond') for k, v in out['paired_vs_P0'].items()}, indent=0))
