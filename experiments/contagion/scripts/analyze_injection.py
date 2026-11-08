"""Analyse injection results: per-arm rates (Wilson CIs), paired contrasts vs k=0 on the same contexts with an
attempt-cluster bootstrap, dose-response per pathway on nested context sets, quarantine removal fractions, gate metrics.

usage: analyze_injection.py --res r1.jsonl [r2.jsonl ...] --out out.json [--label 31b_old]
"""
import os  # added by the repo export (paths are env/config driven)
import json, sys, math, random, argparse, collections
import numpy as np
ap = argparse.ArgumentParser()
ap.add_argument('--res', nargs='+', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--meta', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl'))
ap.add_argument('--B', type=int, default=2000); ap.add_argument('--label', default='')
ap.add_argument('--enrich', default='', help='enrich_contexts.py output: classify edits as retry/target/other')
ap.add_argument('--ids', default='', help='restrict to context ids listed in this file (one per line)')
ap.add_argument('--arms', default='', help='restrict to these arms, e.g. P0k0,P1k1,P1k2')
a = ap.parse_args()
random.seed(0); np.random.seed(0)


def wilson(k, n, z=1.96):
    if n == 0: return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4), n]


META = {}
for l in open(a.meta):
    m = json.loads(l); META[m['id']] = m
KEEP = set(x.strip() for x in open(a.ids) if x.strip()) if a.ids else None
ARMS = set(a.arms.split(',')) if a.arms else None
R = {}
for f in a.res:
    for l in open(f):
        d = json.loads(l)
        if d.get('error'): continue
        if KEEP is not None and d['id'] not in KEEP: continue
        if ARMS is not None and f"{d['pathway']}k{d['k']}" not in ARMS: continue
        R[(d['id'], d['pathway'], d['k'])] = d


ENR = json.load(open(a.enrich)) if a.enrich else {}


def norm(s, n=40):
    if not s: return ''
    s = s.replace('\\n', ' ').replace('\\"', '"').replace("\\'", "'")
    return ' '.join(s.split())[:n]


def edit_class(d, j):
    e = ENR.get(d['id'])
    if not e or j.get('name') != 'edit_file': return None
    h = norm(j.get('new_head'))
    if not h: return 'other'
    reps = e['replaced_recent_first']
    for idx, r in enumerate(reps[:max(1, d['k'])]):
        if r['new'] and norm(r['new']) == h and (r['fp'] == j.get('fp')):
            return 'retry_most_recent' if idx == 0 else 'retry_older'
    t = e.get('target')
    if t and t['new'] and norm(t['new']) == h: return 'target'
    return 'other'


def outcome(d):
    j = d.get('judge') or {}
    name = j.get('name')
    edit = int(j.get('is_edit', name == 'edit_file'))
    mal_edit = int(edit and bool(j.get('malformed')))
    call = int(bool(d.get('opened_call')))
    mal_any = int(call and bool(j.get('malformed')))
    return {'call': call, 'edit': edit, 'mal_edit': mal_edit, 'mal_any': mal_any, 'name': name or ('<no call>' if not call else '<unparsed>'),
            'why': j.get('why'), 'order': j.get('order'), 'closer': j.get('closer'), 'fp': j.get('fp'), 'new_head': j.get('new_head'),
            'write': int(name == 'write_file'), 'cls': edit_class(d, j)}


arms = sorted(set((p, k) for (_, p, k) in R))
ctx_ids = sorted(set(i for (i, _, _) in R))
out = {'label': a.label, 'n_records': len(R), 'n_contexts': len(ctx_ids), 'arms': {}}
# ---- per-arm marginal rates
for (p, k) in arms:
    ds = [R[(i, p, k)] for i in ctx_ids if (i, p, k) in R]
    os_ = [outcome(d) for d in ds]
    n = len(os_); ne = sum(o['edit'] for o in os_)
    names = collections.Counter(o['name'] for o in os_)
    whys = collections.Counter(o['why'] for o in os_ if o['mal_edit'])
    orders = collections.Counter(o['order'] for o in os_ if o['edit'])
    closers = collections.Counter(o['closer'] for o in os_ if o['mal_edit'])
    out['arms'][f'{p}k{k}'] = {
        'n': n, 'P_call': wilson(sum(o['call'] for o in os_), n), 'P_edit': wilson(ne, n),
        'P_malformed_given_edit': wilson(sum(o['mal_edit'] for o in os_), ne),
        'P_malformed_edit_uncond': wilson(sum(o['mal_edit'] for o in os_), n),
        'P_malformed_any_call_given_call': wilson(sum(o['mal_any'] for o in os_), sum(o['call'] for o in os_)),
        'P_write_file': wilson(sum(o['write'] for o in os_), n),
        'first_call_names': dict(names.most_common(8)), 'malformed_why': dict(whys.most_common(6)),
        'edit_order': dict(orders), 'malformed_closers': dict(closers.most_common(6)),
        'budget_forced': sum(1 for d in ds if d.get('budget_forced')),
        'malformed_by_edit_class': {c: wilson(sum(o['mal_edit'] for o in os_ if o['cls'] == c), sum(1 for o in os_ if o['cls'] == c))
                                    for c in ('retry_most_recent', 'retry_older', 'target', 'other') if any(o['cls'] == c for o in os_)},
        'mean_stage1_tokens': round(float(np.mean([d.get('s1_tokens', 0) for d in ds])), 1) if ds else None}


# ---- paired contrasts vs P0 on the same contexts (cluster bootstrap over attempts)
def paired(arm, base=('P0', 0), metric='cond'):
    p, k = arm
    ids = [i for i in ctx_ids if (i, p, k) in R and (i, base[0], base[1]) in R]
    if not ids: return None
    rows = []
    for i in ids:
        ox = outcome(R[(i, p, k)]); ob = outcome(R[(i, base[0], base[1])])
        rows.append((META[i]['task'], ox['edit'], ox['mal_edit'], ob['edit'], ob['mal_edit']))
    att = collections.defaultdict(list)
    for r in rows: att[r[0]].append(r)
    keys = list(att.keys())

    def stat(rs):
        ex = sum(r[1] for r in rs); mx = sum(r[2] for r in rs); eb = sum(r[3] for r in rs); mb = sum(r[4] for r in rs)
        n = len(rs)
        if metric == 'cond':
            px = mx / ex if ex else float('nan'); pb = mb / eb if eb else float('nan')
        else:
            px = mx / n; pb = mb / n
        return px, pb
    px, pb = stat(rows)
    bs_d, bs_r = [], []
    for _ in range(a.B):
        rs = []
        for _k in keys: rs.extend(att[keys[random.randrange(len(keys))]])
        x, b = stat(rs)
        bs_d.append(x - b)
        # ratio: x/b; +inf when only the base is 0 (upper end unbounded); undefined (nan, dropped) when both are 0
        bs_r.append(x / b if b > 0 else (float('inf') if x > 0 else float('nan')))
    bs_d = np.array(bs_d); bs_r = np.array(bs_r)
    rr = np.sort(bs_r[~np.isnan(bs_r)])

    def pct(q):  # percentile without interpolation (order statistic), so +inf stays +inf and never becomes nan
        if len(rr) == 0: return None
        v = rr[min(len(rr) - 1, max(0, int(np.ceil(q / 100 * len(rr))) - 1))]
        return 'inf' if np.isinf(v) else round(float(v), 3)
    return {'n_contexts': len(ids), 'n_attempts': len(keys), 'arm': round(px, 4), 'base': round(pb, 4), 'diff': round(px - pb, 4),
            'diff_CI': [round(float(np.nanpercentile(bs_d, 2.5)), 4), round(float(np.nanpercentile(bs_d, 97.5)), 4)],
            'ratio': round(px / pb, 3) if pb > 0 else ('inf' if px > 0 else None),
            'ratio_CI': [pct(2.5), pct(97.5)],
            'ratio_boot_inf_frac': round(float(np.mean(np.isinf(bs_r))), 4), 'ratio_boot_undefined_frac': round(float(np.mean(np.isnan(bs_r))), 4)}


out['paired_vs_P0'] = {}
for (p, k) in arms:
    if p == 'P0': continue
    out['paired_vs_P0'][f'{p}k{k}'] = {'cond': paired((p, k)), 'uncond': paired((p, k), metric='uncond')}


# ---- quarantine removal fraction: (P1 - Q) / (P1 - P0) on contexts having all three arms
def removal(k, Q, metric='cond'):
    ids = [i for i in ctx_ids if (i, 'P1', k) in R and (i, Q, k) in R and (i, 'P0', 0) in R]
    if not ids: return None
    att = collections.defaultdict(list)
    for i in ids:
        o1 = outcome(R[(i, 'P1', k)]); oq = outcome(R[(i, Q, k)]); o0 = outcome(R[(i, 'P0', 0)])
        att[META[i]['task']].append((o1['edit'], o1['mal_edit'], oq['edit'], oq['mal_edit'], o0['edit'], o0['mal_edit']))
    keys = list(att.keys())

    def stat(rs):
        n = len(rs)
        def rate(ei, mi):
            e = sum(r[ei] for r in rs); m = sum(r[mi] for r in rs)
            return (m / e if e else float('nan')) if metric == 'cond' else m / n
        p1, pq, p0 = rate(0, 1), rate(2, 3), rate(4, 5)
        return p1, pq, p0, ((p1 - pq) / (p1 - p0) if p1 - p0 != 0 else float('nan'))
    rows = [r for kk in keys for r in att[kk]]
    p1, pq, p0, f = stat(rows)
    bs = []
    for _ in range(a.B):
        rs = []
        for _k in keys: rs.extend(att[keys[random.randrange(len(keys))]])
        bs.append(stat(rs)[3])
    bs = np.array(bs)
    return {'n_contexts': len(ids), 'P1': round(p1, 4), 'Q': round(pq, 4), 'P0': round(p0, 4), 'fraction_removed': round(f, 3),
            'CI': [round(float(np.nanpercentile(bs, 2.5)), 3), round(float(np.nanpercentile(bs, 97.5)), 3)]}


out['quarantine_removal'] = {}
for k in sorted(set(k for (_, k) in arms if k > 0)):
    for Q in sorted(set(p for (p, kk) in arms if kk == k and p not in ('P0', 'P1'))):
        if ('P1', k) in arms:
            out['quarantine_removal'][f'{Q}k{k}'] = {'uncond': removal(k, Q, 'uncond'), 'cond': removal(k, Q)}

# ---- dose-response on nested context sets (contexts that have every k level of the pathway)
out['dose_response'] = {}
for p in ('P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7'):
    ks = sorted(set(k for (pp, k) in arms if pp == p))
    for kmax in (1, 2, 4):
        levels = [0] + [k for k in ks if k <= kmax]
        if kmax not in levels: continue
        ids = [i for i in ctx_ids if (i, 'P0', 0) in R and all((i, p, k) in R for k in levels if k > 0)]
        if not ids: continue
        curve = {}
        for k in levels:
            key = ('P0', 0) if k == 0 else (p, k)
            os_ = [outcome(R[(i, key[0], key[1])]) for i in ids]
            ne = sum(o['edit'] for o in os_)
            curve[str(k)] = {'P_malformed_given_edit': wilson(sum(o['mal_edit'] for o in os_), ne),
                             'P_malformed_edit_uncond': wilson(sum(o['mal_edit'] for o in os_), len(os_)),
                             'P_edit': wilson(ne, len(os_))}
        out['dose_response'][f'{p}_upto_k{kmax}'] = {'n_contexts': len(ids), 'curve': curve}

# ---- replay fidelity: P0 replay vs the logged next call on the same contexts
p0ids = [i for i in ctx_ids if (i, 'P0', 0) in R]
if p0ids:
    tab = collections.Counter()
    for i in p0ids:
        o = outcome(R[(i, 'P0', 0)]); lg = META[i]['target']['bad_syn']
        tab[(lg, 'edit' if o['edit'] else 'noedit', o['mal_edit'])] += 1
    ne = sum(v for (lg, e, m), v in tab.items() if e == 'edit')
    out['replay_fidelity_P0'] = {
        'n_contexts': len(p0ids), 'logged_next_call_malformed': wilson(sum(META[i]['target']['bad_syn'] for i in p0ids), len(p0ids)),
        'replay_P_edit': wilson(ne, len(p0ids)),
        'replay_P_malformed_given_edit': wilson(sum(v for (lg, e, m), v in tab.items() if e == 'edit' and m), ne),
        'replay_malformed_when_logged_malformed': wilson(sum(v for (lg, e, m), v in tab.items() if lg == 1 and e == 'edit' and m),
                                                         sum(v for (lg, e, m), v in tab.items() if lg == 1 and e == 'edit')),
        'replay_malformed_when_logged_clean': wilson(sum(v for (lg, e, m), v in tab.items() if lg == 0 and e == 'edit' and m),
                                                     sum(v for (lg, e, m), v in tab.items() if lg == 0 and e == 'edit'))}

# ---- strata (gap to the most recent prior edit, temperature): marginal rates for the gate arms + paired ratio
STRATA = {'gap0': lambda m: m['prior'][-1]['gap_msgs'] == 0, 'gap_gt0': lambda m: m['prior'][-1]['gap_msgs'] > 0,
          'temp0.2': lambda m: m['temp'] == 0.2, 'temp0.7': lambda m: m['temp'] == 0.7}
out['strata'] = {}
for sname, fn in STRATA.items():
    keep = set(i for i in ctx_ids if fn(META[i]))
    sub = {}
    for (p, k) in arms:
        if k > 1: continue
        os_ = [outcome(R[(i, p, k)]) for i in keep if (i, p, k) in R]
        ne = sum(o['edit'] for o in os_)
        sub[f'{p}k{k}'] = {'P_malformed_given_edit': wilson(sum(o['mal_edit'] for o in os_), ne), 'P_edit': wilson(ne, len(os_))}
    out['strata'][sname] = {'n_contexts': len(keep), 'arms': sub}

# ---- gate (primary estimand: UNCONDITIONAL P(malformed edit per context); conditional reported beside it)
g = {}
for metric in ('uncond', 'cond'):
    pc = (out['paired_vs_P0'].get('P1k1') or {}).get(metric)
    if not pc: continue
    rat = pc['ratio']; lo = pc['ratio_CI'][0]
    ok = ((rat == 'inf') or (isinstance(rat, (int, float)) and rat >= 3)) and ((lo == 'inf') or (isinstance(lo, (int, float)) and lo > 1))
    g[f'G1_{metric}'] = {'ratio': rat, 'CI': pc['ratio_CI'], 'P1k1': pc['arm'], 'P0': pc['base'], 'diff': pc['diff'], 'diff_CI': pc['diff_CI'],
                         'n_contexts': pc['n_contexts'], 'n_attempts': pc['n_attempts'], 'pass(>=3, CI_lo>1)': bool(ok)}
    for Q in ('P4', 'P5', 'P4P', 'P8a', 'P8b'):
        q = (out['quarantine_removal'].get(f'{Q}k1') or {}).get(metric)
        if q: g[f'G2_{metric}_removed_by_{Q}_k1'] = {**q, 'pass(>=0.5)': bool(q['fraction_removed'] is not None and q['fraction_removed'] >= 0.5)}
pc = (out['paired_vs_P0'].get('P1k1') or {}).get('cond')
if pc:
    rat = pc['ratio']; lo = pc['ratio_CI'][0]
    ratio_ok = (rat == 'inf') or (isinstance(rat, (int, float)) and rat >= 3)
    lo_ok = (lo == 'inf') or (isinstance(lo, (int, float)) and lo > 1)
    g['G1_ratio_P1k1_over_P0'] = {'ratio': rat, 'CI': pc['ratio_CI'], 'P1k1': pc['arm'], 'P0': pc['base'], 'diff': pc['diff'], 'diff_CI': pc['diff_CI'],
                                 'n_contexts': pc['n_contexts'], 'n_attempts': pc['n_attempts'], 'pass(>=3, CI_lo>1)': bool(ratio_ok and lo_ok)}
for Q in ('P4', 'P5'):
    q = (out['quarantine_removal'].get(f'{Q}k1') or {}).get('cond')
    if q: g[f'G2_removed_by_{Q}_k1'] = {**q, 'pass(>=0.5)': bool(q['fraction_removed'] is not None and q['fraction_removed'] >= 0.5)}
out['gate'] = g
json.dump(out, open(a.out, 'w'), indent=1)
print(json.dumps({'gate': g, 'arms': {k: {kk: v[kk] for kk in ('n', 'P_edit', 'P_malformed_given_edit', 'P_malformed_edit_uncond')} for k, v in out['arms'].items()}}, indent=1))
