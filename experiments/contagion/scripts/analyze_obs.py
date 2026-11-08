"""Observational contagion in the main-track logs (read-only index from extract_index.py).

Populations
  SYN   : synthesis definition ('gemma-4-31b' in model name)  -> INCLUDES Qwen/DeepSeek teacher runs served under that name
  BASE  : model == openai/gemma-4-31b-it-qat-w4a16-ct and run not a teacher run (the plain base model)
  FT    : team fine-tuned adapters (r*, rl*)
Per population: malformed rate, first-edit rate, hazard by number of prior malformed edits, transition probabilities with a
within-attempt permutation null, share of malformed edits that follow a malformed edit, retry-vs-new decomposition,
key-order and closer tables, resolve association.  CIs: Wilson (events treated as independent) and attempt-cluster
bootstrap (B resamples of attempts).
usage: analyze_obs.py index.jsonl runs_root out.json
"""
import json, sys, collections, random, math, glob, os
import numpy as np

random.seed(0); np.random.seed(0)
B = 1000


def wilson(k, n, z=1.96):
    if n == 0: return [None, None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4)]


idx_path, runs_root, outp = sys.argv[1], sys.argv[2], sys.argv[3]
recs = [json.loads(l) for l in open(idx_path)]
res = {}
for pt in glob.glob(os.path.join(runs_root, '*', 'per_task.jsonl')):
    for l in open(pt, errors='replace'):
        try: d = json.loads(l)
        except Exception: continue
        res[d.get('attempt')] = bool(d.get('resolved'))


def popkey(r):
    m = r['model']
    if 'gemma-4-31b' in m: syn = True
    else: syn = False
    if r['teacher']: base = False
    else: base = (m == 'openai/gemma-4-31b-it-qat-w4a16-ct')
    ft = ('gemma-4-31b' not in m)
    return syn, base, ft


# attempt -> ordered edit events; also raw events
att_events = {'SYN': collections.defaultdict(list), 'BASE': collections.defaultdict(list), 'FT': collections.defaultdict(list)}
att_meta = {}
for r in recs:
    if r.get('bad_line'): continue
    syn, base, ft = popkey(r)
    key = r['task']  # task ids embed the harness pid, unique per log file
    for c in r['calls']:
        if c['name'] != 'edit_file': continue
        bad_ref = int(bool(c.get('flags')))
        ev = {'ln': r['ln'], 'bad': c['bad_syn'], 'bad_ref': bad_ref, 'keys': c.get('keys'), 'closer': c.get('closer'),
              'fp': c.get('fp'), 'nh': c.get('nh'), 'oh': c.get('oh'), 'run': r['run'], 'temp': r['temp'], 'why': c.get('why_syn')}
        if syn: att_events['SYN'][key].append(ev)
        if base: att_events['BASE'][key].append(ev)
        if ft: att_events['FT'][key].append(ev)
    att_meta.setdefault(key, (r['run'], r['model'], r['temp']))
for P in att_events:
    for a in att_events[P]: att_events[P][a].sort(key=lambda e: e['ln'])


def stats(E, flag='bad'):
    """E: dict attempt -> list of events. Returns the core contagion numbers."""
    ev = [e for v in E.values() for e in v]
    out = {'attempts': len(E), 'edits': len(ev), 'malformed': sum(e[flag] for e in ev)}
    out['malformed_rate'] = wilson(out['malformed'], out['edits'])
    first = [v[0][flag] for v in E.values()]
    out['first_edit'] = wilson(sum(first), len(first)) + [len(first)]
    kb = collections.defaultdict(lambda: [0, 0]); lc = [0, 0]; lb = [0, 0]
    follow_bad = 0; onsets = 0
    for v in E.values():
        sb = 0
        for i, e in enumerate(v):
            if i > 0:
                kk = min(sb, 4); kb[kk][0] += 1; kb[kk][1] += e[flag]
                if sb: lb[0] += 1; lb[1] += e[flag]
                else: lc[0] += 1; lc[1] += e[flag]
                if e[flag] and v[i - 1][flag]: follow_bad += 1
            if e[flag] and (i == 0 or not v[i - 1][flag]): onsets += 1
            sb += e[flag]
    out['later_clean_history'] = wilson(lc[1], lc[0]) + [lc[0]]
    out['later_after_ge1_bad'] = wilson(lb[1], lb[0]) + [lb[0]]
    out['later_by_prior_bad'] = {str(k): wilson(b, n) + [n] for k, (n, b) in sorted(kb.items())}
    out['share_bad_following_bad'] = round(follow_bad / max(1, out['malformed']), 4)
    out['malformed_per_onset'] = round(out['malformed'] / max(1, onsets), 3)
    # transitions
    c = collections.Counter()
    for v in E.values():
        for x, y in zip(v, v[1:]): c[(x[flag], y[flag])] += 1
    p1 = c[(1, 1)] / max(1, c[(1, 1)] + c[(1, 0)]); p0 = c[(0, 1)] / max(1, c[(0, 1)] + c[(0, 0)])
    out['P_bad_given_prev_bad'] = wilson(c[(1, 1)], c[(1, 1)] + c[(1, 0)])
    out['P_bad_given_prev_ok'] = wilson(c[(0, 1)], c[(0, 1)] + c[(0, 0)])
    # within-attempt permutation null for P(bad|prev bad)
    seqs = [[e[flag] for e in v] for v in E.values() if len(v) >= 2]
    nulls = []
    for _ in range(1000):
        cc11 = cc10 = 0
        for f in seqs:
            g = f[:]; random.shuffle(g)
            for x, y in zip(g, g[1:]):
                if x: cc11 += y; cc10 += (1 - y)
        nulls.append(cc11 / max(1, cc11 + cc10))
    nulls.sort()
    out['perm_null_P_bad_given_prev_bad'] = {'mean': round(float(np.mean(nulls)), 4), 'q975': round(nulls[974], 4), 'max': round(nulls[-1], 4),
                                             'observed': round(p1, 4), 'p_value': (sum(x >= p1 for x in nulls) + 1) / (len(nulls) + 1), 'n_perm': len(nulls)}
    # recovery after first bad
    rec_ = [any(e[flag] == 0 for e in v[next(i for i, e in enumerate(v) if e[flag]) + 1:]) for v in E.values() if any(e[flag] for e in v)]
    out['after_first_bad_later_clean_edit'] = wilson(sum(rec_), len(rec_))
    out['attempts_with_ge1_bad'] = wilson(len(rec_), len(E))
    # retry vs new decomposition (same filepath & same new_string fingerprint == retry of the same edit)
    dec = collections.defaultdict(lambda: [0, 0])
    for v in E.values():
        sb = 0
        for i, e in enumerate(v):
            if i > 0:
                prev = v[i - 1]
                retry = (e['fp'] == prev['fp'] and e['nh'] == prev['nh'])
                key = ('prev_bad' if prev[flag] else 'prev_ok') + ('/retry' if retry else '/new')
                dec[key][0] += 1; dec[key][1] += e[flag]
                if not retry:
                    k2 = 'new_edit/' + ('history_has_bad' if sb else 'clean_history')
                    dec[k2][0] += 1; dec[k2][1] += e[flag]
            sb += e[flag]
    out['retry_vs_new'] = {k: wilson(b, n) + [n] for k, (n, b) in sorted(dec.items())}
    # attempt-cluster bootstrap for the key conditional rates
    keys = list(E.keys()); bs = collections.defaultdict(list)
    for _ in range(B):
        samp = [E[keys[random.randrange(len(keys))]] for _ in keys]
        lc_ = [0, 0]; k1 = [0, 0]; k4 = [0, 0]; fe = [0, 0]; nb = [0, 0]
        for v in samp:
            sb = 0
            fe[0] += 1; fe[1] += v[0][flag]
            for i, e in enumerate(v):
                if i > 0:
                    if sb == 0: lc_[0] += 1; lc_[1] += e[flag]
                    elif sb == 1: k1[0] += 1; k1[1] += e[flag]
                    if sb >= 4: k4[0] += 1; k4[1] += e[flag]
                    if sb and not v[i - 1]['fp'] == e['fp']: pass
                sb += e[flag]
            nb[0] += len(v); nb[1] += sum(e[flag] for e in v)
        bs['malformed_rate'].append(nb[1] / max(1, nb[0])); bs['first_edit'].append(fe[1] / max(1, fe[0]))
        bs['later_clean_history'].append(lc_[1] / max(1, lc_[0])); bs['after_1_bad'].append(k1[1] / max(1, k1[0]))
        bs['after_ge4_bad'].append(k4[1] / max(1, k4[0]))
    out['cluster_bootstrap_95CI'] = {k: [round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4)] for k, x in bs.items()}
    # key order (emission order of the parsed args) and closers
    ordc = collections.defaultdict(lambda: [0, 0]); clo = collections.Counter()
    for e in ev:
        ks = [k for k in (e['keys'] or []) if k in ('old_string', 'new_string')]
        ks_all = e['keys'] or []
        if 'new_string' in ks_all and ('old_string' not in ks_all or ks_all.index('new_string') < ks_all.index('old_string')): o = 'new_first'
        elif 'old_string' in ks_all: o = 'old_first'
        else: o = 'neither'
        ordc[o][0] += 1; ordc[o][1] += e[flag]
        if e[flag]: clo[e['closer'] or 'NONE'] += 1
    out['by_emission_order'] = {k: wilson(b, n) + [n] for k, (n, b) in ordc.items()}
    out['closers_among_malformed'] = dict(clo.most_common(10))
    # resolve association
    clean_att = [a for a, v in E.items() if a in res and not any(e[flag] for e in v)]
    bad_att = [a for a, v in E.items() if a in res and any(e[flag] for e in v)]
    out['resolve_clean_attempts'] = wilson(sum(res[a] for a in clean_att), len(clean_att)) + [len(clean_att)]
    out['resolve_attempts_with_bad'] = wilson(sum(res[a] for a in bad_att), len(bad_att)) + [len(bad_att)]
    return out


R = {}
for P in ('SYN', 'BASE', 'FT'):
    E = {a: v for a, v in att_events[P].items() if v}
    R[P] = {'synthesis_criterion': stats(E, 'bad')}
    if P == 'BASE':
        R[P]['refined_criterion'] = stats(E, 'bad_ref')
        # by run and by temperature
        byrun = collections.defaultdict(lambda: [0, 0]); byT = collections.defaultdict(lambda: [0, 0])
        for v in E.values():
            for e in v: byrun[e['run']][0] += 1; byrun[e['run']][1] += e['bad']; byT[str(e['temp'])][0] += 1; byT[str(e['temp'])][1] += e['bad']
        R[P]['by_run'] = {k: wilson(b, n) + [n] for k, (n, b) in sorted(byrun.items(), key=lambda kv: -kv[1][0])}
        R[P]['by_temperature'] = {k: wilson(b, n) + [n] for k, (n, b) in byT.items()}
        # excluding run-39 (T=0.7, 42% of base edits) as a robustness check
        E2 = {a: [e for e in v if e['run'] != 'run-39'] for a, v in E.items()}
        E2 = {a: v for a, v in E2.items() if v}
        R[P]['excluding_run-39'] = stats(E2, 'bad')
    print('==', P, json.dumps({k: R[P]['synthesis_criterion'][k] for k in ('attempts', 'edits', 'malformed_rate', 'first_edit', 'later_clean_history', 'later_by_prior_bad', 'share_bad_following_bad', 'malformed_per_onset', 'perm_null_P_bad_given_prev_bad', 'retry_vs_new', 'by_emission_order', 'cluster_bootstrap_95CI')}, indent=None))
# teacher-only (to document the contamination)
Et = collections.defaultdict(list)
for r in recs:
    if r.get('bad_line') or not r['teacher']: continue
    for c in r['calls']:
        if c['name'] == 'edit_file': Et[r['run']].append(c['bad_syn'])
R['TEACHER_runs_in_SYN'] = {k: wilson(sum(v), len(v)) + [len(v)] for k, v in Et.items()}
json.dump(R, open(outp, 'w'), indent=1)
print('wrote', outp)
