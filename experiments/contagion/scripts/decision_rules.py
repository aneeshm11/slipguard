"""Pre-registered decision rules of UPGRADE_PLAN.md §P0-A1, applied verbatim (31B, primary estimand = UNCONDITIONAL
P(next call is a malformed edit_file) per context; conditional reported beside it). Paired attempt-cluster bootstrap B.

  induction : claimed iff RD(P6 - P0) >= +5 pp with CI_lo > 0 on BOTH the gate and the held-out halves; otherwise the
              name is "copy-on-retry". Also reported: RD on new-content edits only (malformed edits that are not retries
              of the replaced call).
  copying   : confirmed iff >= 80% of P1 malformed edits are verbatim copies AND P7 slips carry '"' well above P0's rate.
              Operationalisation of "well above" (ours, stated before seeing the final P7 numbers): the Wilson CI of the
              share of P7 malformed edits whose closer contains '"' lies entirely above the P0 share's point estimate.
  shipped quarantine works : iff P8a and P4' each remove >= 70% of the P1 excess (unconditional) with CI_lo >= 50%.
  July template : "does not fix the loop" iff NT P1/P0 >= 3x with CI_lo > 1 (unconditional).
The held-out half is read ONLY if the pre-registration file exists (lock); otherwise reported as locked.
usage: decision_rules.py [B]
"""
import json, os, sys, glob, random, math, collections
import numpy as np
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
PREREG = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/PREREG_v1.md')
B = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
random.seed(0)
META = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
ENRF = f'{D}/data/enrich_all.json'
ENR = json.load(open(ENRF)) if os.path.exists(ENRF) else {}


def wilson(k, n, z=1.96):
    if n == 0: return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4), n]


def load(files, ids):
    R = {}
    for f in files:
        if not os.path.exists(f): continue
        for l in open(f):
            d = json.loads(l)
            if d.get('error') or d['id'] not in ids: continue
            R[(d['id'], d['pathway'], d['k'])] = d
    return R


def norm(s, n=40):
    if not s: return ''
    s = s.replace('\\n', ' ').replace('\\"', '"').replace("\\'", "'")
    return ' '.join(s.split())[:n]


def is_retry(d, j):
    e = ENR.get(d['id'])
    if not e or j.get('name') != 'edit_file': return False
    h = norm(j.get('new_head'))
    for r in e['replaced_recent_first'][:max(1, d['k'])]:
        if h and r['new'] and norm(r['new']) == h and r['fp'] == j.get('fp'): return True
    return False


def outcome(d, kind):
    j = d.get('judge') or {}
    edit = j.get('is_edit', j.get('name') == 'edit_file'); mal = edit and bool(j.get('malformed'))
    if kind == 'uncond': return int(mal), 1
    if kind == 'cond': return int(mal), int(edit)
    if kind == 'newcontent_uncond': return int(mal and not is_retry(d, j)), 1
    raise ValueError(kind)


def paired_rd(R, arm, base=('P0', 0), kind='uncond'):
    ids = sorted(set(i for (i, p, k) in R if (p, k) == arm and (i,) + base in R))
    if not ids: return None
    att = collections.defaultdict(list)
    for i in ids:
        att[META[i]['task'] if i in META else i].append(outcome(R[(i,) + arm], kind) + outcome(R[(i,) + base], kind))
    keys = list(att)

    def stat(rows):
        a = sum(r[0] for r in rows) / max(1, sum(r[1] for r in rows)); b = sum(r[2] for r in rows) / max(1, sum(r[3] for r in rows))
        return a, b
    rows = [r for k in keys for r in att[k]]
    a, b = stat(rows); bs_d, bs_r = [], []
    for _ in range(B):
        rr = [r for _ in keys for r in att[keys[random.randrange(len(keys))]]]
        x, y = stat(rr); bs_d.append(x - y); bs_r.append(x / y if y > 0 else (float('inf') if x > 0 else float('nan')))
    bs_d = np.array(bs_d); rr_ = np.sort(np.array([v for v in bs_r if not math.isnan(v)]))
    pct = lambda q: (lambda v: 'inf' if math.isinf(v) else round(float(v), 3))(rr_[min(len(rr_) - 1, max(0, int(math.ceil(q / 100 * len(rr_))) - 1))]) if len(rr_) else None
    return {'n_contexts': len(ids), 'n_attempts': len(keys), 'arm': round(a, 4), 'base': round(b, 4), 'RD': round(a - b, 4),
            'RD_CI': [round(float(np.percentile(bs_d, 2.5)), 4), round(float(np.percentile(bs_d, 97.5)), 4)],
            'ratio': round(a / b, 3) if b > 0 else ('inf' if a > 0 else None), 'ratio_CI': [pct(2.5), pct(97.5)]}


def removal(R, Q, kind='uncond'):
    ids = sorted(set(i for (i, p, k) in R if (p, k) == (Q, 1) and (i, 'P1', 1) in R and (i, 'P0', 0) in R))
    if not ids: return None
    att = collections.defaultdict(list)
    for i in ids:
        att[META[i]['task']].append(outcome(R[(i, 'P1', 1)], kind) + outcome(R[(i, Q, 1)], kind) + outcome(R[(i, 'P0', 0)], kind))
    keys = list(att)

    def stat(rows):
        r1 = sum(r[0] for r in rows) / max(1, sum(r[1] for r in rows)); rq = sum(r[2] for r in rows) / max(1, sum(r[3] for r in rows))
        r0 = sum(r[4] for r in rows) / max(1, sum(r[5] for r in rows))
        return r1, rq, r0, ((r1 - rq) / (r1 - r0) if r1 != r0 else float('nan'))
    rows = [r for k in keys for r in att[k]]; r1, rq, r0, f = stat(rows)
    bs = np.array([stat([r for _ in keys for r in att[keys[random.randrange(len(keys))]]])[3] for _ in range(B)])
    return {'n_contexts': len(ids), 'P1': round(r1, 4), 'Q': round(rq, 4), 'P0': round(r0, 4), 'fraction_removed': round(f, 3),
            'CI': [round(float(np.nanpercentile(bs, 2.5)), 3), round(float(np.nanpercentile(bs, 97.5)), 3)]}


def closer_share(R, arm, has):
    mal = [d for (i, p, k), d in R.items() if (p, k) == arm and (d.get('judge') or {}).get('name') == 'edit_file' and (d.get('judge') or {}).get('malformed')]
    withc = [d for d in mal if (d['judge'].get('closer') or '')]
    return wilson(sum(1 for d in withc if has in d['judge']['closer']), len(withc))


ids_gate = set(x.strip() for x in open(f'{D}/data/ids_gate300.txt') if x.strip())
ids_ho = set(x.strip() for x in open(f'{D}/data/ids_heldout_31b.txt') if x.strip())
# completed files only (interim-safe); the P9/P8/P4' file joins once its runner has finished (PREREG: no interim looks)
M = f'{D}/out/main'
pool = [f'{M}/r31b_old_{x}.jsonl' for x in ('a', 'b', 'A', 'B', 'G', 'P6')]
if os.path.exists(f'{D}/logs/ctg-31b-A1a.log') and 'finished' in open(f'{D}/logs/ctg-31b-A1a.log').read():
    pool.append(f'{M}/r31b_old_A1a.jsonl')
G = load(pool, ids_gate)
unlocked = os.path.exists(PREREG)
ho_done = os.path.exists(f'{D}/logs/ctg-31b-HO.log') and 'finished' in open(f'{D}/logs/ctg-31b-HO.log').read()
H = load([f'{D}/out/main/r31b_heldout.jsonl'], ids_ho) if (unlocked and ho_done) else {}
NT = load([f'{D}/out/main/r31b_new_T.jsonl'], ids_gate)
res = {'estimand': 'primary = unconditional P(next call is a malformed edit_file) per context; conditional beside it',
       'prereg_file_present': unlocked, 'heldout_lock': json.load(open(f'{D}/data/heldout_lock.json'))}
# induction
ind = {'gate': {k: paired_rd(G, ('P6', 1), kind=k) for k in ('uncond', 'newcontent_uncond', 'cond')}}
ind['heldout'] = ({k: paired_rd(H, ('P6', 1), kind=k) for k in ('uncond', 'newcontent_uncond', 'cond')} if (unlocked and ho_done)
                  else 'PENDING (held-out runs not finished; analysed once, after completion)')
ok = lambda x: bool(x and x['RD'] >= 0.05 and x['RD_CI'][0] > 0)
ind['rule'] = 'claimed iff RD(P6-P0) >= +5 pp with CI_lo > 0 on both the gate and held-out halves (unconditional)'
# held-out replication block (written before any held-out outcome existed; analysed once, after the runs finished)
if unlocked and ho_done:
    res['heldout_replication'] = {'n_contexts_frozen': len(ids_ho),
                                  'P1_vs_P0': {k: paired_rd(H, ('P1', 1), kind=k) for k in ('uncond', 'cond')},
                                  'P6_vs_P0': {k: paired_rd(H, ('P6', 1), kind=k) for k in ('uncond', 'newcontent_uncond', 'cond')},
                                  'P8a_vs_P0': {k: paired_rd(H, ('P8a', 1), kind=k) for k in ('uncond', 'cond')},
                                  'P8a_removal_of_P1_excess': {'uncond': removal(H, 'P8a'), 'cond': removal(H, 'P8a', 'cond')},
                                  'jobs_present': sum(1 for _ in H), 'note': 'contexts 300-599 of the random order minus 6 seen; frozen sha256 bbe9af23'}
else:
    res['heldout_replication'] = 'PENDING'
ind['decision'] = ('claimed' if ok(ind['gate']['uncond']) and ok(ind['heldout']['uncond']) else 'not claimed -> "copy-on-retry"') if (unlocked and ho_done) else \
    ('pending held-out (gate half ' + ('meets' if ok(ind['gate']['uncond']) else 'does not meet') + ' the criterion)')
res['format_induction'] = ind
# copying
cc = json.load(open(f'{D}/out/copy_check.json')) if os.path.exists(f'{D}/out/copy_check.json') else {}
share = (cc.get('gemma-4-31b:P1k1') or {}).get('share_of_malformed_that_are_verbatim_copies')
p7 = closer_share(G, ('P7', 1), '"'); p0 = closer_share(G, ('P0', 0), '"')
cop = {'P1_share_of_malformed_that_are_verbatim_copies': share, 'P7_quote_closer_share_of_malformed': p7, 'P0_quote_closer_share_of_malformed': p0,
       'rule': '>= 80% of P1 malformed edits are verbatim copies AND P7 slips carry \'"\' well above P0 (operationalised: P7 share Wilson CI_lo > P0 share point estimate)'}
cop['decision'] = 'confirmed' if (share and share[0] >= 0.80 and p7[1] is not None and p0[0] is not None and p7[1] > p0[0]) else 'not confirmed'
res['copying'] = cop
# shipped quarantine. P4' on the gate set = its byte-identical P0 prompt (297/300 contexts; same prompt, same seed -> the P0
# record IS the P4' outcome) plus the 3 contexts where the render differs (run as P4P).
p4p_ident = json.load(open(f'{D}/out/p4prime_identity.json'))
diff_ids = set(p4p_ident['differing_ids'])
for (i, p, k), d in list(G.items()):
    if (p, k) == ('P0', 0) and i not in diff_ids and (i, 'P4P', 1) not in G:
        G[(i, 'P4P', 1)] = d
sq = {Q: removal(G, Q) for Q in ('P8a', 'P8b', 'P4P', 'P4', 'P5')}
sq['P4P_note'] = "P4' renders byte-identical to P0 in 297/300 gate contexts (out/p4prime_identity.json): at k=1 its removal is 100% by construction; its informative test is A2 (P4'-MAP)."
ok2 = lambda x: bool(x and x['fraction_removed'] >= 0.70 and x['CI'][0] >= 0.50)
sq['rule'] = 'works iff P8a and P4\' each remove >= 70% of the P1 excess (unconditional) with CI_lo >= 50%'
sq['decision'] = ('works' if ok2(sq['P8a']) and ok2(sq['P4P']) else 'does not meet the rule') if sq['P8a'] else 'pending (P8a requires E\'s frozen renderer)'
res['shipped_quarantine'] = sq
# July template
nt = paired_rd(NT, ('P1', 1)); ntc = paired_rd(NT, ('P1', 1), kind='cond')
okj = bool(nt and ((nt['ratio'] == 'inf') or (isinstance(nt['ratio'], (int, float)) and nt['ratio'] >= 3)) and
           ((nt['ratio_CI'][0] == 'inf') or (isinstance(nt['ratio_CI'][0], (int, float)) and nt['ratio_CI'][0] > 1)))
res['july_template'] = {'uncond': nt, 'cond': ntc, 'removal_P4': removal(NT, 'P4'), 'removal_P5': removal(NT, 'P5'),
                        'rule': '"does not fix the loop" iff NT P1/P0 >= 3x with CI_lo > 1 (unconditional)',
                        'decision': ('does not fix the loop' if okj else 'rule not met') if nt else 'pending'}
# other new arms at k=1 on the gate set (descriptive)
res['gate_arms_vs_P0'] = {f'{p}k{k}': {'uncond': paired_rd(G, (p, k)), 'cond': paired_rd(G, (p, k), kind='cond')}
                          for p, k in sorted(set((p, k) for (_, p, k) in G)) if (p, k) != ('P0', 0)}
json.dump(res, open(f'{D}/out/decision_rules.json', 'w'), indent=1)
for k in ('format_induction', 'copying', 'shipped_quarantine', 'july_template'):
    print(k, '->', res[k]['decision'])
print(json.dumps({k: (v['uncond'] if v['uncond'] else None) for k, v in res['gate_arms_vs_P0'].items()}, indent=None)[:1500])
