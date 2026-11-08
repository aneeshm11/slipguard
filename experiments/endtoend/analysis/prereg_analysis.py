"""Confirmatory analysis for PREREG_E.md (frozen with the code; self-contained).

population: python prereg_analysis.py population --label 31B --base runs/A[+runs/B] --fullp runs/C[+runs/D] \
                 --proxy-logs logs/proxy_X [logs/proxy_Y] --tasks configs/eligible_113.txt --out analysis/prereg_pop31.json
branches:   python prereg_analysis.py branches --label 31B --plan plans/b31.json --arm base=runs/b31_base \
                 --arm quar=runs/b31_quar --arm ipd=runs/b31_ipd --arm fullp=runs/b31_fullp --proxy-logs logs/proxy_b31 \
                 --out analysis/prereg_br31.json
'+' joins run dirs of the same arm (replicates / server halves): an episode is (task, replicate) with the replicate =
the run dir's position in the '+' list of its arm; replicates are averaged within task and arm before pairing.
"""
import os  # added by the repo export (paths are env/config driven)
import argparse
import glob
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

PROTO_ERR = {'MissingParameters', 'UnexpectedArgument', 'TypeError', 'ValueError', 'MalformedToolCall', 'UnknownTool',
             'ValidationError', 'JSONDecodeError'}
ORPHAN = re.compile(r'(?:^|[^>])call:[\w\-\.]+\{')
L4 = {'overhead': 0.21, 'prefill': 1660.0, 'decode': 35.7}
B = 10000


# ------------------------------------------------------------------------------------------------ statistics
def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def boot_paired(diffs, seed=0):
    """mean of per-unit differences, percentile 95% CI, two-sided bootstrap p (sign flips around the CI's 0 side)."""
    d = [x for x in diffs if x is not None]
    if not d:
        return {'n': 0}
    rnd = random.Random(seed)
    n = len(d)
    m = sum(d) / n
    bs = sorted(sum(rnd.choice(d) for _ in range(n)) / n for _ in range(B))
    lo, hi = bs[int(0.025 * B)], bs[int(0.975 * B) - 1]
    p = 2 * min(sum(x <= 0 for x in bs), sum(x >= 0 for x in bs)) / B
    return {'n': n, 'mean_diff': round(m, 4), 'ci95': [round(lo, 4), round(hi, 4)], 'p_boot': round(min(1.0, p), 5)}


def boot_ratio(a, b, seed=1):
    """ratio of means (b/a) over paired units with a task-cluster bootstrap CI (second-line estimate)."""
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs or sum(x for x, _ in pairs) == 0:
        return {'ratio': None, 'ci95': None}
    rnd = random.Random(seed)
    r0 = sum(y for _, y in pairs) / sum(x for x, _ in pairs)
    rs = []
    for _ in range(B):
        s = [rnd.choice(pairs) for _ in pairs]
        den = sum(x for x, _ in s)
        if den > 0:
            rs.append(sum(y for _, y in s) / den)
    rs.sort()
    if not rs:
        return {'ratio': round(r0, 4), 'ci95': None}
    return {'ratio': round(r0, 4), 'ci95': [round(rs[int(0.025 * len(rs))], 4), round(rs[int(0.975 * len(rs)) - 1], 4)]}


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [None] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        adj[i] = round(run, 5)
    return adj


def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else round(min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n), 5)


# ------------------------------------------------------------------------------------------------ episodes
def load_proxy(dirs):
    by = defaultdict(list)
    for d in dirs:
        for f in glob.glob(str(Path(d) / 'proxy_*.jsonl')):
            for line in open(f):
                try:
                    r = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if r.get('task'):
                    by[r['task']].append(r)
    for v in by.values():
        v.sort(key=lambda r: r['t'])
    return by


def unparsed_turn(r):
    if r.get('unparsed_tool_call'):
        return True
    if r.get('calls'):
        return False
    raw = r.get('raw') or ''
    ans = raw[raw.rfind('<channel|>') + len('<channel|>'):] if '<channel|>' in raw else raw
    return '<tool_call|>' in ans or bool(ORPHAN.search(ans))


def episode(reqs, per_task_rec, after_index=None):
    """metrics of one episode from its proxy records. after_index: only requests with branch.i > after_index count
    toward the 'post' metrics (branch mode)."""
    turns = [r for r in reqs if r.get('status') == 200 and r.get('n_tools', 1) != 0]
    t0 = reqs[0]['t'] if reqs else None
    seq, prev_bad, wasted, unparsed, first_edit = [], [], 0, 0, None
    emu, prev_pt, prev_gen, llm_s, gen = 0.0, 0, 0, 0.0, 0
    post = {'malformed': 0, 'calls': 0}
    for i, r in enumerate(turns):
        res = r.get('tool_results') or []
        for j, tr in enumerate(res):
            name, st, et = tr[0], tr[1], tr[2]
            if et in PROTO_ERR or (j < len(prev_bad) and prev_bad[j]):
                wasted += 1
            if first_edit is None and name in ('edit_file', 'write_file') and st == 'ok':
                first_edit = {'turns': i, 'seconds': round(r['t'] - t0, 1)}
        wasted += sum(prev_bad[len(res):])
        calls = r.get('calls') or []
        prev_bad = [int(not c['ok_delivered']) for c in calls]
        if unparsed_turn(r):
            unparsed += 1
        pt, g = int(r.get('prompt_tokens') or 0), int(r.get('gen_tokens') or 0)
        emu += L4['overhead'] + max(0, pt - (prev_pt + prev_gen)) / L4['prefill'] + g / L4['decode']
        prev_pt, prev_gen = pt, g
        llm_s += float(r.get('latency_s') or 0)
        gen += g
        hist_bad = sum(b for _, b in (r.get('hist') or []))
        bi = (r.get('branch') or {}).get('i')
        for c in calls:
            bad = int(not c['ok_delivered'])
            seq.append((bad, hist_bad))
            if after_index is not None and bi is not None and bi > after_index:
                post['malformed'] += bad
                post['calls'] += 1
    wasted += sum(prev_bad)  # malformed calls of the final turn
    run, stuck = 0, False
    for bad, _ in seq:
        run = run + 1 if bad else 0
        stuck = stuck or run >= 5
    tool_s = max(0.0, float(per_task_rec.get('agent_s') or per_task_rec.get('wall_s') or 0) - llm_s)
    return {'Y1': sum(b for b, _ in seq), 'Y2': wasted + unparsed, 'calls': len(seq), 'unparsed_turns': unparsed,
            'stuck': int(stuck), 'gen_tokens': gen, 'emu_l4_s': round(emu + tool_s, 1), 'first_applied_edit': first_edit,
            'resolved': int(bool(per_task_rec.get('resolved'))), 'seq': seq, 'post': post,
            'infra_error': per_task_rec.get('error', '').startswith(('Sandbox execution error: litellm', 'Container'))}


def load_arm(spec, by):
    """-> {task: [episode per replicate]}"""
    out = defaultdict(list)
    for rep, rd in enumerate(spec.split('+')):
        rd = Path(rd)
        rc = json.loads((rd / 'run_cfg.json').read_text())
        pref = f"{rc.get('tag', rd.name)}/{rc['cfg']}:"
        for line in open(rd / 'per_task.jsonl'):
            p = json.loads(line)
            out[p['id']].append(episode(by.get(pref + p['id'], []), p))
    return out


def task_mean(eps, key):
    v = [e[key] for e in eps if e.get(key) is not None]
    return sum(v) / len(v) if v else None


# ------------------------------------------------------------------------------------------------ analyses
def population(a):
    by = load_proxy(a.proxy_logs)
    tasks = [t for t in open(a.tasks).read().split() if t]
    arms = {'base': load_arm(a.base, by), 'fullp': load_arm(a.fullp, by)}
    excl = sorted(t for t in tasks if any(e['infra_error'] for arm in arms.values() for e in arm.get(t, [])))
    common = [t for t in tasks if t in arms['base'] and t in arms['fullp'] and t not in excl]
    out = {'label': a.label, 'n_tasks_registered': len(tasks), 'n_tasks_analysed': len(common), 'excluded_infra': excl,
           'replicates': {k: Counter(len(v[t]) for t in common) for k, v in arms.items()}}
    prim = {}
    for key in ('Y1', 'Y2'):
        xb = [task_mean(arms['base'][t], key) for t in common]
        xf = [task_mean(arms['fullp'][t], key) for t in common]
        prim[key] = {'base_mean': round(sum(xb) / len(xb), 4), 'fullp_mean': round(sum(xf) / len(xf), 4),
                     'diff_fullp_minus_base': boot_paired([f - b for b, f in zip(xb, xf)], seed=hash(key) % 1000),
                     'ratio_fullp_over_base': boot_ratio(xb, xf)}
    adj = holm([prim['Y1']['diff_fullp_minus_base']['p_boot'], prim['Y2']['diff_fullp_minus_base']['p_boot']])
    prim['Y1']['p_holm'], prim['Y2']['p_holm'] = adj
    r1 = prim['Y1']['ratio_fullp_over_base']['ratio']
    ci1 = prim['Y1']['diff_fullp_minus_base']['ci95']
    prim['success_Y1_reduction_ge_70pct_ci_excludes_0'] = bool(r1 is not None and r1 <= 0.30 and ci1 and ci1[1] < 0)
    out['co_primary'] = prim
    sec = {}
    for key in ('gen_tokens', 'emu_l4_s'):
        xb = [task_mean(arms['base'][t], key) for t in common]
        xf = [task_mean(arms['fullp'][t], key) for t in common]
        sec[key] = {'base_mean': round(sum(xb) / len(xb), 2), 'fullp_mean': round(sum(xf) / len(xf), 2),
                    'diff': boot_paired([f - b for b, f in zip(xb, xf)], seed=7)}
    for key in ('stuck', 'resolved'):
        sec[key] = {}
        for rep in range(max(len(arms['base'][t]) for t in common)):
            pairs = [(arms['base'][t][rep][key], arms['fullp'][t][rep][key]) for t in common
                     if len(arms['base'][t]) > rep and len(arms['fullp'][t]) > rep]
            kb, kf, n = sum(p[0] for p in pairs), sum(p[1] for p in pairs), len(pairs)
            bb = sum(1 for x, y in pairs if x and not y)
            cc = sum(1 for x, y in pairs if y and not x)
            d = boot_paired([y - x for x, y in pairs], seed=11 + rep)
            sec[key][f'replicate{rep + 1}'] = {'base': [kb, n, wilson(kb, n)], 'fullp': [kf, n, wilson(kf, n)],
                                               'paired_diff': d, 'mcnemar_p': mcnemar(bb, cc), 'discordant': [bb, cc]}
            if key == 'resolved':
                sec[key][f'replicate{rep + 1}']['non_inferior_at_-3pp'] = bool(d.get('ci95') and d['ci95'][0] > -0.03)
    for arm in ('base', 'fullp'):
        fe = [e['first_applied_edit'] for t in common for e in arms[arm][t]]
        reached = [x for x in fe if x]
        sec.setdefault('first_applied_edit', {})[arm] = {
            'reached': [len(reached), len(fe), wilson(len(reached), len(fe))],
            'median_turns': sorted(x['turns'] for x in reached)[len(reached) // 2] if reached else None,
            'median_seconds': sorted(x['seconds'] for x in reached)[len(reached) // 2] if reached else None}
        seqs = [e['seq'] for t in common for e in arms[arm][t]]
        onset_k = onset_n = post_k = post_n = 0
        for s in seqs:
            seen = False
            for bad, _ in s:
                if not seen:
                    onset_n += 1
                    onset_k += bad
                else:
                    post_n += 1
                    post_k += bad
                seen = seen or bool(bad)
        sec.setdefault('hazards', {})[arm] = {'onset': [onset_k, onset_n, wilson(onset_k, onset_n)],
                                              'post_onset': [post_k, post_n, wilson(post_k, post_n)]}
    out['secondary'] = sec
    return out


def branches(a):
    """groups: one per plan file (a plan holds <= 1 branch point per task); branch points are keyed (group, task)."""
    by = load_proxy(a.proxy_logs)
    groups = []
    if a.plan:
        groups.append((a.plan, a.arm or []))
    for g in a.group or []:
        kv = dict(x.split('=', 1) for x in g.split(','))
        groups.append((kv.pop('plan'), [f'{k}={v}' for k, v in kv.items()]))
    plan, arms = {}, defaultdict(dict)
    for gi, (plan_path, arm_specs) in enumerate(groups):
        pl = json.loads(Path(plan_path).read_text())['branches']
        for t, e in pl.items():
            plan[f'{gi}:{t}'] = e
        for spec in arm_specs:
            name, rd = spec.split('=', 1)
            rd = Path(rd)
            rc = json.loads((rd / 'run_cfg.json').read_text())
            pref = f"{rc.get('tag', rd.name)}/{rc['cfg']}:"
            for line in open(rd / 'per_task.jsonl'):
                p = json.loads(line)
                reqs = by.get(pref + p['id'], [])
                fid_bad = any((r.get('replay') or {}).get('fidelity') == 'mismatch' for r in reqs)
                arms[name][f'{gi}:{p["id"]}'] = {**episode(reqs, p, after_index=pl[p['id']]['b'] if p['id'] in pl else None),
                                                 'fidelity_mismatch': fid_bad}
    ids = sorted(set.intersection(*[set(v) for v in arms.values()]) & set(plan))
    excl = sorted(t for t in ids if any(arms[k][t]['fidelity_mismatch'] or arms[k][t]['infra_error'] for k in arms))
    ids = [t for t in ids if t not in excl]
    out = {'label': a.label, 'n_branch_points': len(ids), 'excluded_fidelity_or_infra': excl,
           'onset_types': Counter(plan[t]['onset'] for t in ids)}
    base = [arms['base'][t]['post']['malformed'] for t in ids]
    res = {}
    for k in arms:
        if k == 'base':
            continue
        x = [arms[k][t]['post']['malformed'] for t in ids]
        d = boot_paired([y - b0 for b0, y in zip(base, x)], seed=hash(k) % 1000)
        r = boot_ratio(base, x)
        res[k] = {'post_onset_malformed_mean': round(sum(x) / len(x), 4) if x else None, 'diff_vs_base': d, 'ratio_vs_base': r,
                  'success_reduction_ge_50pct': bool(r['ratio'] is not None and r['ratio'] <= 0.5 and d.get('ci95') and d['ci95'][1] < 0)}
        rb, rk = [arms['base'][t]['resolved'] for t in ids], [arms[k][t]['resolved'] for t in ids]
        res[k]['conditional_resolve'] = {'base': [sum(rb), len(rb)], k: [sum(rk), len(rk)],
                                         'mcnemar_p': mcnemar(sum(1 for x, y in zip(rb, rk) if x and not y),
                                                              sum(1 for x, y in zip(rb, rk) if y and not x))}
    res['base'] = {'post_onset_malformed_mean': round(sum(base) / len(base), 4) if base else None}
    qr = {}
    for k in arms:
        cnt = defaultdict(lambda: [0, 0])
        for t in ids:
            for bad, hb in arms[k][t]['seq']:
                key = str(hb) if hb < 4 else '4+'
                cnt[key][0] += bad
                cnt[key][1] += 1
        qr[k] = {r: [v[0], v[1], wilson(v[0], v[1])] for r, v in sorted(cnt.items())}
    out['post_onset'] = res
    out['q_r_by_arm'] = qr
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('population')
    p.add_argument('--label', required=True)
    p.add_argument('--base', required=True)
    p.add_argument('--fullp', required=True)
    p.add_argument('--proxy-logs', nargs='+', required=True)
    p.add_argument('--tasks', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/configs/eligible_113.txt'))
    p.add_argument('--out', required=True)
    q = sub.add_parser('branches')
    q.add_argument('--label', required=True)
    q.add_argument('--plan', default=None)
    q.add_argument('--arm', action='append', default=None)
    q.add_argument('--group', action='append', default=None,
                   help='plan=PATH,base=DIR,quar=DIR,ipd=DIR,fullp=DIR (repeatable; one per plan file)')
    q.add_argument('--proxy-logs', nargs='+', required=True)
    q.add_argument('--out', required=True)
    a = ap.parse_args()
    res = population(a) if a.cmd == 'population' else branches(a)
    Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    print(f'written {a.out}')


if __name__ == '__main__':
    main()
