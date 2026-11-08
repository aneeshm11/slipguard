"""PREREG_v2.1 (thinking-OFF flag, sha256 bb3696da...) and PREREG_v2.2 (arm set S: thought suppressed; arm set H:
reasoning-stripped history, sha256 ec9164ff...) analysis on the 300 discovery gate contexts (June template, logged
sampling). Written and hash-frozen BEFORE any output of these batteries existed. Each battery is analysed once, after
its runner logged 'finished' (the script refuses otherwise).

Conventions (PREREG_v2 §3, v2.1 §4, v2.2): primary = unconditional ITT P(next call is a malformed edit_file) per context,
secondary = P(malformed | next call is an edit). Paired by context on the contexts complete in every arm of the battery
(complete-case); if an arm misses > 5% of its jobs, the all-available analysis is reported too. Attempt-cluster
percentile bootstrap, B = 2000 (seed 20261104). One-sided bootstrap p = (1 + #{RD* <= 0}) / (B + 1). Removal =
(P1 - Q)/(P1 - P0) (draws with P1 - P0 <= 0 are undefined and counted). Holm: v2.1 over {P1-P0, P6-P0, P1-P8a, P1-P5}
(T1-T4); S over {P1-P0, P6-P0, P1-P8a} (S1-S3); H is a one-test family (alpha 0.05).
Rules: RD claims REPLICATES iff CI_lo > 0, Holm p < 0.05 and est >= 0.5 theta_D; ATTENUATED iff CI_lo > 0 and Holm p
< 0.05 but est < 0.5 theta_D; FAILS otherwise (theta_D: +35.3 pp for P1, +21.3 pp for P6). Removal claims REPLICATES
iff removal >= 0.70, CI_lo >= 0.50 and Holm p(RD(P1 - Q) > 0) < 0.05; ATTENUATED iff removal >= 0.40 with CI_lo > 0
but not REPLICATES; FAILS otherwise; not evaluable if the battery's P1 claim FAILS.
Manipulation checks (operationalised here, before data):
  thought opened  = the generated text (record field s1_text: everything the model generated before '<|tool_call>', or
                    all of it if no call opened) contains '<|channel>'; for S this is a RE-opening after the prefill;
  thought length  = characters between '<|channel>thought\\n' (or '<|channel>') and the next '<channel|>' (or the end);
  M-v2.1          = share opened per arm and pooled (prediction >= 0.95) + median length (prediction 680 [450, 900]) vs
                    the thinking-ON gate runs' median on the same contexts and arms. If the pooled share < 0.80, every
                    v2.1 verdict is labelled 'mixed condition'; if an arm's share < 0.80, every verdict involving that
                    arm is. Labelled verdicts are also reported on the opened / not-opened subsets (contexts where every
                    arm of the contrast opened / did not open a thought). Known before data (out/v21_v22_render_check.json):
                    in 188/300 P5 contexts the June template itself ends the OFF prompt with its closed empty thought
                    (P5 removes the last edit call, so the template restarts the model turn); M-v2.1 is also reported
                    for P5 split by template-closed vs not.
  M-S             = share re-opened per arm and pooled (prediction <= 0.05). If the pooled share or an arm's share >
                    0.10, S is labelled 'thought-prefilled' and S1-S3 are also reported on the contexts where no arm of
                    the contrast re-opened.
Secondary (no rule): levels vs D's PIs; paired condition - ON on the same contexts (ON = A's thinking-ON gate runs,
r31b_old_{A,G,a,b,P6,A1a}); P(edit) condition - ON per arm (v2.1: within +-10 pp); byte-exact copies among malformed P1
edits and clean rewrites of the same edit under P1 (copy_check.py's classes, recomputed here on the same 300 contexts
for ON and the condition).
usage: analyze_v21_v22.py --battery v21|S|H --out <json> [--B 2000] [--force_incomplete]
"""
import json, sys, os, math, argparse, collections, statistics
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemma_protocol as gp
import variants as V

D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser()
ap.add_argument('--battery', required=True, choices=['v21', 'S', 'H']); ap.add_argument('--out', required=True)
ap.add_argument('--B', type=int, default=2000); ap.add_argument('--force_incomplete', action='store_true')
ap.add_argument('--smoke_file', default='', help='SMOKE ONLY: analyse this file instead of the battery output')
a = ap.parse_args()
SEED = 20261104
META = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
IDS = [x.strip() for x in open(f'{D}/data/ids_gate300.txt') if x.strip()]
ON_FILES = [f'{D}/out/main/r31b_old_{x}.jsonl' for x in ('A', 'G', 'a', 'b', 'P6', 'A1a')]
BAT = {'v21': dict(file=f'{D}/out/main/r31b_v21off.jsonl', log=f'{D}/logs/ctg-31b-v21.log', plan=f'{D}/data/plan_v21_off.jsonl',
                   arms=['P0', 'P1', 'P5', 'P6', 'P8a'], prereg='PREREG_v2.1_thinkingOFF.md sha256 bb3696da3772d0c7ac67eae9f7f76162dbff11ca357161c34e3c5ca53fb44839',
                   claims=[('T1', 'RD', 'P1', 'P0', 0.353), ('T2', 'RD', 'P6', 'P0', 0.213), ('T3', 'REM', 'P1', 'P8a', None), ('T4', 'REM', 'P1', 'P5', None)],
                   pred={'T1': '+38 pp [+22, +52]', 'T2': '+22 pp [+8, +38]', 'T3': '1.05 [0.85, 1.20]', 'T4': '1.00 [0.80, 1.15]'},
                   levels={'P0': (0.03, 0.12), 'P1': (0.28, 0.60), 'P6': (0.14, 0.45)}),
       'S': dict(file=f'{D}/out/main/r31b_v22S.jsonl', log=f'{D}/logs/ctg-31b-v22S.log', plan=f'{D}/data/plan_v22_S.jsonl',
                 arms=['P0', 'P1', 'P6', 'P8a'], prereg='PREREG_v2.2_thoughtSuppressed.md sha256 ec9164ffa833f351618c3eb7ec69aa2e471e096307de7f5fd61e6c72e07f09d3',
                 claims=[('S1', 'RD', 'P1', 'P0', 0.353), ('S2', 'RD', 'P6', 'P0', 0.213), ('S3', 'REM', 'P1', 'P8a', None)],
                 pred={'S1': '+38 pp [+22, +55]', 'S2': '+24 pp [+8, +40]', 'S3': '1.05 [0.80, 1.20]'},
                 levels={'P0': (0.03, 0.13), 'P1': (0.28, 0.63)}),
       'H': dict(file=f'{D}/out/main/r31b_v22H.jsonl', log=f'{D}/logs/ctg-31b-v22H.log', plan=f'{D}/data/plan_v22_H.jsonl',
                 arms=['P0', 'P1'], prereg='PREREG_v2.2_thoughtSuppressed.md sha256 ec9164ffa833f351618c3eb7ec69aa2e471e096307de7f5fd61e6c72e07f09d3 (§3)',
                 claims=[('H1', 'RD', 'P1', 'P0', 0.353)], pred={'H1': '+33 pp [+16, +50]'}, levels={'P0': (0.02, 0.11)})}
BB = BAT[a.battery]
if a.smoke_file: BB = dict(BB, file=a.smoke_file)
KOF = {'P0': 0}


def kof(arm): return 0 if arm == 'P0' else 1


def load(files, cond=None):
    R = {}
    for f in files:
        if not os.path.exists(f): continue
        for l in open(f):
            d = json.loads(l)
            if d.get('error') or d['id'] not in META: continue
            if cond is not None and d.get('cond') not in ((cond,) if isinstance(cond, str) else cond): continue
            if cond is None and d.get('template', 'old') != 'old': continue
            R[(d['id'], d['pathway'], d['k'])] = d
    return R


def y_of(d):
    j = d.get('judge') or {}
    e = int(j.get('name') == 'edit_file'); return int(e and bool(j.get('malformed'))), e


def thought(d):
    s = d.get('s1_text') or ''
    i = s.find('<|channel>')
    if i < 0: return False, None
    st = i + len('<|channel>thought\n') if s.startswith('<|channel>thought\n', i) else i + len('<|channel>')
    j = s.find('<channel|>', st)
    return True, (j if j >= 0 else len(s)) - st


def wilson(k, n, z=1.96):
    if n == 0: return None
    p = k / n; dd = 1 + z * z / n; c = (p + z * z / (2 * n)) / dd; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / dd
    return [round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4), n]


def pct(x): return [round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4)]


class Boot:
    """Attempt-cluster bootstrap over a fixed context set; rates of (cond, arm) cells via multinomial cluster weights."""
    def __init__(self, ids, cells):  # cells: name -> {context_id: record}
        self.ids = list(ids)
        cl = sorted(set(META[i]['task'] for i in self.ids)); ci = {c: j for j, c in enumerate(cl)}
        self.C = len(cl); self.N = np.zeros(self.C)
        self.Y = {}; self.E = {}
        for i in self.ids: self.N[ci[META[i]['task']]] += 1
        for name, recs in cells.items():
            Y = np.zeros(self.C); E = np.zeros(self.C)
            for i in self.ids:
                y, e = y_of(recs[i]); Y[ci[META[i]['task']]] += y; E[ci[META[i]['task']]] += e
            self.Y[name] = Y; self.E[name] = E
        rng = np.random.default_rng(SEED)
        self.W = rng.multinomial(self.C, np.full(self.C, 1 / self.C), size=a.B).astype(float) if self.C else None

    def rate(self, name, kind='uncond'):
        den = self.N if kind == 'uncond' else self.E[name]
        est = self.Y[name].sum() / den.sum() if den.sum() else float('nan')
        with np.errstate(divide='ignore', invalid='ignore'):
            dr = (self.W @ self.Y[name]) / (self.W @ den)
        return est, dr

    def rd(self, x, y, kind='uncond'):
        ex, dx = self.rate(x, kind); ey, dy = self.rate(y, kind); d = dx - dy; d = d[np.isfinite(d)]
        return {'n_contexts': len(self.ids), 'n_attempts': self.C, 'arm': round(ex, 4), 'base': round(ey, 4), 'RD': round(ex - ey, 4),
                'RD_CI': pct(d), 'p_one_sided': round((1 + int((d <= 0).sum())) / (len(d) + 1), 5)}

    def removal(self, p1, q, p0, kind='uncond'):
        e1, d1 = self.rate(p1, kind); eq, dq = self.rate(q, kind); e0, d0 = self.rate(p0, kind)
        den = d1 - d0; ok = den > 0
        r = np.where(ok, (d1 - dq) / np.where(ok, den, 1), np.nan)
        est = (e1 - eq) / (e1 - e0) if e1 - e0 > 0 else float('nan')
        rr = r[np.isfinite(r)]
        return {'P1': round(e1, 4), 'Q': round(eq, 4), 'P0': round(e0, 4), 'removal': round(est, 4) if np.isfinite(est) else None,
                'CI': pct(rr) if len(rr) and ok.mean() >= 0.975 else None, 'undefined_draw_frac': round(1 - float(ok.mean()), 4)}


def holm(ps):
    names = sorted(ps, key=lambda k: ps[k]); m = len(names); out = {}; run = 0.0
    for r, k in enumerate(names):
        run = max(run, min(1.0, (m - r) * ps[k])); out[k] = round(run, 5)
    return out


def verdict(kind, est, ci, hp, theta=None, p1_fails=False):
    if kind == 'RD':
        if ci[0] > 0 and hp < 0.05: return 'REPLICATES' if est >= 0.5 * theta else 'ATTENUATED'
        return 'FAILS'
    if p1_fails: return 'NOT EVALUABLE (P1 claim FAILS)'
    if est is None or ci is None: return 'FAILS (removal undefined)'
    if est >= 0.70 and ci[0] >= 0.50 and hp < 0.05: return 'REPLICATES'
    if est >= 0.40 and ci[0] > 0: return 'ATTENUATED'
    return 'FAILS'


def claims_block(idsets, cells, label):
    """Primary claims + Holm. idsets: claim name -> context ids (the same list for complete-case)."""
    res = {'label': label}; ps = {}
    for name, kind, x, y, th in BB['claims']:
        ids = idsets[name]
        if len(ids) < 10: res[name] = {'n_contexts': len(ids), 'note': 'too few contexts', 'verdict': 'NOT EVALUABLE'}; continue
        need = sorted({x, y, 'P0'})
        b = Boot(ids, {arm: cells[arm] for arm in need})
        r = b.rd(x, y); ps[name] = r['p_one_sided']
        res[name] = {'contrast': f'RD({x} - {y})', 'n_contexts': len(ids), 'n_attempts': b.C, 'uncond': r, 'cond': b.rd(x, y, 'cond')}
        if kind == 'REM':
            res[name]['removal_uncond'] = b.removal('P1', y, 'P0'); res[name]['removal_cond'] = b.removal('P1', y, 'P0', 'cond')
            res[name]['contrast'] = f'removal of the P1 excess by {y}; Holm test RD(P1 - {y}) > 0'
    hp = holm(ps) if ps else {}
    p1_name = BB['claims'][0][0]
    for name, kind, x, y, th in BB['claims']:
        r = res[name]
        if name not in hp: continue
        r['holm_p'] = hp[name]; r['prediction_80PI'] = BB['pred'][name]
        if kind == 'RD':
            r['verdict'] = verdict('RD', r['uncond']['RD'], r['uncond']['RD_CI'], hp[name], th); r['theta_D'] = th
        else:
            rem = r['removal_uncond']
            r['verdict'] = verdict('REM', rem['removal'], rem['CI'], hp[name], p1_fails=res[p1_name].get('verdict') == 'FAILS')
    return res


# ------------------------------------------------------------------ completeness gate (no interim looks)
log_ok = os.path.exists(BB['log']) and any(l.startswith('finished') for l in open(BB['log']))
if not log_ok and not a.force_incomplete:
    sys.exit(f"battery {a.battery}: runner log has no 'finished' line yet -> not analysed (no interim looks)")
COND = {'v21': 'OFF', 'S': ('S', 'SON'), 'H': 'H'}[a.battery]   # SON only if the S operationalisation is switched (logged)
RC = load([BB['file']], cond=COND); RON = load(ON_FILES)
plan = [json.loads(l) for l in open(BB['plan'])]
out = {'battery': a.battery, 'prereg': BB['prereg'], 'cond': sorted(set(d.get('cond') for d in RC.values())), 'B': a.B, 'file': os.path.relpath(BB['file'], D),
       'servers': dict(collections.Counter(d.get('server') for d in RC.values())), 'on_servers': dict(collections.Counter(RON[(i, p, kof(p))].get('server') for i in IDS for p in BB['arms'] if (i, p, kof(p)) in RON))}
miss = {arm: sum(1 for i in IDS if (i, arm, kof(arm)) not in RC) for arm in BB['arms']}
out['missing_jobs'] = miss
cells = {arm: {i: RC[(i, arm, kof(arm))] for i in IDS if (i, arm, kof(arm)) in RC} for arm in BB['arms']}
cells_on = {arm: {i: RON[(i, arm, kof(arm))] for i in IDS if (i, arm, kof(arm)) in RON} for arm in ('P0', 'P1', 'P5', 'P6', 'P8a')}
cc = [i for i in IDS if all(i in cells[arm] for arm in BB['arms'])]
out['complete_case_contexts'] = len(cc)

# ------------------------------------------------------------------ manipulation checks
man = {}
for arm in BB['arms']:
    th = [thought(cells[arm][i]) for i in cc]; on = [thought(cells_on[arm][i]) for i in cc if i in cells_on[arm]]
    lens = [x[1] for x in th if x[0]]; lon = [x[1] for x in on if x[0]]
    man[arm] = {'opened': wilson(sum(x[0] for x in th), len(th)), 'median_chars': statistics.median(lens) if lens else None,
                'iqr_chars': [float(np.percentile(lens, 25)), float(np.percentile(lens, 75))] if lens else None,
                'ON_opened': wilson(sum(x[0] for x in on), len(on)), 'ON_median_chars': statistics.median(lon) if lon else None}
allth = [thought(cells[arm][i]) for arm in BB['arms'] for i in cc]
man['pooled'] = {'opened': wilson(sum(x[0] for x in allth), len(allth)),
                 'median_chars': statistics.median([x[1] for x in allth if x[0]]) if any(x[0] for x in allth) else None,
                 'ON_median_chars': statistics.median([x[1] for arm in BB['arms'] for i in cc if i in cells_on[arm] for x in [thought(cells_on[arm][i])] if x[0]])}
if a.battery == 'v21':
    rc = json.load(open(f'{D}/out/v22_thought_form_check.json')) if os.path.exists(f'{D}/out/v22_thought_form_check.json') else None
    import run_cond as RCnd
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
    RCnd.install('OFF'); tc = set()
    for i in cc:
        p, _ = V.build_prompt(tok, META[i], 'P5', 1)
        if p.endswith('<|turn>model\n' + RCnd.PRE): tc.add(i)
    RCnd.install('ON')
    for nm, sel in (('P5_template_closed', [i for i in cc if i in tc]), ('P5_not_template_closed', [i for i in cc if i not in tc])):
        th = [thought(cells['P5'][i]) for i in sel]
        man[nm] = {'n': len(sel), 'opened': wilson(sum(x[0] for x in th), len(th)), 'malformed_uncond': wilson(sum(y_of(cells['P5'][i])[0] for i in sel), len(sel))}
    out['manipulation_check_M_v2.1'] = man
    out['manipulation_check_M_v2.1']['prediction'] = 'opened >= 0.95 (point 0.99); median 680 chars [450, 900]'
    low_arms = [arm for arm in BB['arms'] if man[arm]['opened'] and man[arm]['opened'][0] < 0.80]
    pooled_low = man['pooled']['opened'][0] < 0.80
elif a.battery == 'S':
    out['manipulation_check_M_S'] = dict(man, prediction='re-opened <= 0.05; > 0.10 -> label thought-prefilled and report on non-reopened contexts')
    low_arms = [arm for arm in BB['arms'] if man[arm]['opened'] and man[arm]['opened'][0] > 0.10]
    pooled_low = man['pooled']['opened'][0] > 0.10
else:
    out['manipulation_check_H'] = dict(man, note='thinking ON; the history carries no prior reasoning (render check 600/600)')
    low_arms, pooled_low = [], False

# ------------------------------------------------------------------ primary claims
out['claims_complete_case'] = claims_block({c[0]: cc for c in BB['claims']}, cells, 'complete-case')
if any(v > 0.05 * 300 for v in miss.values()):
    out['claims_all_available'] = claims_block({name: [i for i in IDS if all(i in cells[arm] for arm in {x, y, 'P0'})] for name, kind, x, y, th in BB['claims']},
                                               cells, 'all-available (contexts with every arm of the claim)')
lab = {'v21': 'mixed condition', 'S': 'thought-prefilled', 'H': None}[a.battery]
flags = {}
for name, kind, x, y, th in BB['claims']:
    involved = {x, y, 'P0'} if kind == 'REM' else {x, y}
    flags[name] = lab if (lab and (pooled_low or involved & set(low_arms))) else None
out['condition_labels'] = flags
if any(flags.values()):
    sub = {}
    for tag, want in (('thought_opened', True), ('thought_not_opened', False)) if a.battery == 'v21' else (('not_reopened', False),):
        for name, kind, x, y, th in BB['claims']:
            if not flags[name]: continue
            involved = sorted({x, y, 'P0'})
            ids2 = [i for i in cc if all(thought(cells[arm][i])[0] == want for arm in involved)]
            blk = claims_block({c[0]: ids2 for c in BB['claims']}, cells, f'{tag} subset (all of {involved})')
            sub[f'{name}:{tag}'] = dict(blk.get(name, {}), subset=f'{tag}: contexts where all of {involved} {"opened" if want else "did not open"} a thought', descriptive=True)
    out['claims_on_thought_subsets'] = sub

# ------------------------------------------------------------------ secondary
b = Boot(cc, {arm: cells[arm] for arm in BB['arms']})
lev = {}
for arm in BB['arms']:
    e, dr = b.rate(arm); ec, drc = b.rate(arm, 'cond')
    lev[arm] = {'uncond': [round(e, 4)] + pct(dr[np.isfinite(dr)]), 'cond': [round(ec, 4)] + pct(drc[np.isfinite(drc)]),
                'P_edit': wilson(int(b.E[arm].sum()), len(cc)), 'D_80PI': BB['levels'].get(arm)}
out['levels'] = lev
if a.battery == 'v21':
    out['levels']['P5_P8a_vs_P0_plus_1pp'] = {arm: round(lev[arm]['uncond'][0] - lev['P0']['uncond'][0], 4) for arm in ('P5', 'P8a')}
# paired condition - ON on the same contexts
pon = {}
for arm in BB['arms']:
    ids2 = [i for i in cc if i in cells_on[arm]]
    bb = Boot(ids2, {'C': cells[arm], 'ON': cells_on[arm]})
    r = bb.rd('C', 'ON'); r_c = bb.rd('C', 'ON', 'cond')
    pe_c = sum(y_of(cells[arm][i])[1] for i in ids2) / len(ids2); pe_o = sum(y_of(cells_on[arm][i])[1] for i in ids2) / len(ids2)
    # P(edit) difference with its own cluster bootstrap
    cl = sorted(set(META[i]['task'] for i in ids2)); ci_ = {c: j for j, c in enumerate(cl)}
    Ec = np.zeros(len(cl)); Eo = np.zeros(len(cl)); Nn = np.zeros(len(cl))
    for i in ids2:
        j = ci_[META[i]['task']]; Ec[j] += y_of(cells[arm][i])[1]; Eo[j] += y_of(cells_on[arm][i])[1]; Nn[j] += 1
    Wd = bb.W; dd = (Wd @ Ec - Wd @ Eo) / (Wd @ Nn)
    pon[arm] = {'RD_malformed_uncond': r, 'RD_malformed_cond': r_c, 'P_edit_cond_minus_ON': [round(pe_c - pe_o, 4)] + pct(dd)}
if a.battery == 'v21':
    pon['predictions'] = 'OFF - ON: P1 +5 pp [-5, +15]; P0 +1.5 pp [-2, +6]; P(edit) within +-10 pp in every arm'
elif a.battery == 'S':
    pon['predictions'] = 'S - ON: P1 +5 pp [-5, +18]'
out['paired_vs_thinking_ON'] = pon
# rel. ON gate claims on the same complete-case contexts (side-by-side)
on_ids = [i for i in cc if all(i in cells_on[arm] for arm in BB['arms'])]
bon = Boot(on_ids, {arm: cells_on[arm] for arm in BB['arms']})
side = {'n_contexts': len(on_ids)}
for name, kind, x, y, th in BB['claims']:
    side[name] = {'ON': bon.rd(x, y) if kind == 'RD' else bon.removal('P1', y, 'P0'),
                  'cond': b.rd(x, y) if kind == 'RD' else b.removal('P1', y, 'P0')}
out['side_by_side_ON_vs_condition'] = side


# copy classes (copy_check.py's definitions) for P1 / P6 under the condition and ON, same contexts
def copy_classes(recs, ids, pathway):
    tab = collections.Counter(); CL = {'P1': '`', 'P6': '`'}
    for i in ids:
        d = recs.get(i); j = (d or {}).get('judge') or {}
        if d is None or j.get('name') != 'edit_file': continue
        msgs, _ = V.load_context(META[i]); p = META[i]['prior'][-1]
        args = json.loads(msgs[p['ai']]['tool_calls'][0]['function']['arguments']); order = list(args.keys())
        sk = V.slip_key_for(order)
        inj = gp.parse_args(gp.raw_args(args, order, slip_key=sk, closer=CL[pathway])).get(sk); orig = args.get(sk)
        m = gp.TOOL_CALL_RE.search('<|tool_call>' + (d.get('s2_text') or '') + '<tool_call|>')
        gen = gp.parse_args(m.group(2)).get(sk) if m else None
        if gen is None: cls = 'unparsed_or_no_key'
        elif gen == inj: cls = 'copy_corrupted'
        elif gen == orig: cls = 'clean_retry'
        elif isinstance(orig, str) and gen[:40].strip() == orig[:40].strip(): cls = 'same_content_other'
        else: cls = 'other_edit'
        tab[(cls, bool(j.get('malformed')))] += 1
    edits = sum(tab.values()); mal = sum(v for (c, bb_), v in tab.items() if bb_)
    return {'edits': edits, 'classes': {c: tab[(c, True)] + tab[(c, False)] for c in ('copy_corrupted', 'clean_retry', 'same_content_other', 'other_edit', 'unparsed_or_no_key')},
            'byte_exact_copy_share_of_malformed': wilson(tab[('copy_corrupted', True)], mal) if mal else None,
            'clean_rewrite_share_of_edits': wilson(tab[('clean_retry', False)] + tab[('clean_retry', True)], edits) if edits else None}


cp = {}
for pw in [x for x in ('P1', 'P6') if x in BB['arms']]:
    ids2 = [i for i in cc if i in cells_on[pw]]
    cp[pw] = {'condition': copy_classes(cells[pw], ids2, pw), 'ON_same_contexts': copy_classes(cells_on[pw], ids2, pw)}
cp['predictions'] = {'v21': 'byte-exact copies >= 80% of malformed P1 edits (ON 85.4%)',
                     'S': 'clean rewrites under P1 lower than ON (ON 30%, 80/266): S 15% [5, 30]; byte-exact copies >= 80%',
                     'H': 'none registered'}[a.battery]
out['copy_classes'] = cp
json.dump(out, open(a.out, 'w'), indent=1)
summ = {k: ((v.get('removal_uncond') or {}).get('removal') if 'removal_uncond' in v else v.get('uncond', {}).get('RD'), v.get('verdict'))
        for k, v in out['claims_complete_case'].items() if isinstance(v, dict) and 'verdict' in v}
print(json.dumps({'battery': a.battery, 'complete_case': len(cc), 'missing': miss, 'claims': summ, 'labels': flags}, indent=1))
