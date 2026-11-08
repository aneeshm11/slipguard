"""End-to-end metrics for workstream E runs (harness and no-nudge client), with CIs.

Inputs: run dirs (per_task.jsonl + run_cfg.json) and the proxy logs (proxy_<cfg>.jsonl) that carry the
per-request raw generations; records are joined on the X-E2E-Task attempt id.
Usage: analyze.py --runs runs/A runs/B ... --proxy-logs logs/proxy_pilot --out analysis/out.json [--pairs A:B ...]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

# measured 4xL4 single-stream constants from the main track (run_eval.py): decode 35.7 tok/s, prefill 1660 tok/s
L4 = {'overhead': 0.21, 'prefill': 1660.0, 'decode': 35.7}


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def boot_mean(xs, B=4000, seed=0):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, [None, None]
    rnd = random.Random(seed)
    m = sum(xs) / len(xs)
    bs = sorted(sum(rnd.choice(xs) for _ in xs) / len(xs) for _ in range(B))
    return round(m, 4), [round(bs[int(0.025 * B)], 4), round(bs[int(0.975 * B) - 1], 4)]


def cluster_rate(groups, B=4000, seed=0):
    """groups: list of (k, n) per task -> pooled rate with task-cluster bootstrap CI + Wilson (naive)."""
    groups = [(k, n) for k, n in groups if n > 0]
    K, N = sum(k for k, _ in groups), sum(n for _, n in groups)
    if N == 0:
        return {'k': 0, 'n': 0, 'rate': None, 'wilson': [None, None], 'cluster_ci': [None, None]}
    rnd = random.Random(seed)
    bs = []
    for _ in range(B):
        s = [rnd.choice(groups) for _ in groups]
        nn = sum(n for _, n in s)
        bs.append(sum(k for k, _ in s) / nn if nn else 0)
    bs.sort()
    return {'k': K, 'n': N, 'rate': round(K / N, 4), 'wilson': wilson(K, N),
            'cluster_ci': [round(bs[int(0.025 * B)], 4), round(bs[int(0.975 * B) - 1], 4)]}


def mcnemar_exact(b, c):
    """two-sided exact binomial test on discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return round(min(1.0, 2 * p), 4)


def load_proxy(proxy_dirs):
    by_task = defaultdict(list)
    for d in proxy_dirs:
        for f in glob.glob(str(Path(d) / 'proxy_*.jsonl')):
            for line in open(f):
                try:
                    r = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if r.get('task'):
                    by_task[r['task']].append(r)
    for v in by_task.values():
        v.sort(key=lambda r: r['t'])
    return by_task


def call_level(reqs):
    """Per-task protocol stats from its proxy records."""
    st = Counter()
    edits = []  # (slipped, delivered_bad, n_prior_bad_hist) per edit_file call, in order
    prev_prompt = 0
    emu = 0.0
    for r in reqs:
        if r.get('status') != 200:
            st['req_errors'] += 1
            continue
        if r.get('n_tools', 1) == 0 or (r.get('n_tools') is None and not r.get('hist') and 'summary of the conversation' in (r.get('raw') or '')[:4000]):
            st['compaction_calls'] += 1  # ADK events-compaction summarisation (no tools): not an agent turn
            continue
        st['requests'] += 1
        pt, gt = r.get('prompt_tokens') or 0, r.get('gen_tokens') or 0
        st['prompt_tokens'] += pt
        st['gen_tokens'] += gt
        unc = pt - prev_prompt if pt >= prev_prompt else pt
        prev_prompt = pt
        emu += L4['overhead'] + max(0, unc) / L4['prefill'] + gt / L4['decode']
        ev = r.get('events') or []
        rep_tools = Counter(e['tool'] for e in ev if e['ev'] == 'ipd_repair')
        st['ipd_repairs'] += sum(1 for e in ev if e['ev'] == 'ipd_repair')
        st['ipd_false_alarms'] += sum(1 for e in ev if e['ev'] == 'ipd_no_repair')
        st['ipd_rejected'] += sum(1 for e in ev if e['ev'] == 'ipd_rejected')
        st['posthoc_repairs'] += sum(1 for e in ev if e['ev'] == 'posthoc_repair')
        st['budget_forced'] += sum(1 for e in ev if e['ev'] == 'budget_forced_end')
        st['quarantine_actions'] += len(r.get('quarantine') or [])
        calls = r.get('calls') or []
        if not calls:
            st['no_call_responses'] += 1
        if r.get('unparsed_tool_call'):
            st['unparsed_tool_call'] += 1
        if r.get('finish') == 'length':
            st['length_finish'] += 1
        hist = r.get('hist') or []
        prior_bad = sum(b for _, b in hist)
        prior_bad_edit = sum(b for n, b in hist if n == 'edit_file')
        for c in calls:
            name = c['name']
            slipped = (not c['ok_emitted']) or rep_tools.get(name, 0) > 0
            st['calls'] += 1
            st['calls_slipped'] += int(slipped)
            st['calls_bad_delivered'] += int(not c['ok_delivered'])
            st[f'{name}:calls'] += 1
            st[f'{name}:slipped'] += int(slipped)
            st[f'{name}:bad_delivered'] += int(not c['ok_delivered'])
            if name == 'edit_file':
                edits.append((int(slipped), int(not c['ok_delivered']), prior_bad, prior_bad_edit))
    st['emu_l4_s'] = round(emu, 1)
    return st, edits


def summarize(run_spec, by_task):
    """run_spec: one run dir, or several joined with '+' (e.g. the two server halves of one condition)."""
    per_task, client, cfg_name = {}, None, None
    for rd in str(run_spec).split('+'):
        pt, client, cfg_name = _per_task(Path(rd), by_task)
        per_task.update(pt)
    return _aggregate(str(run_spec), client, cfg_name, per_task), per_task


def _per_task(run_dir, by_task):
    cfg = json.loads((run_dir / 'run_cfg.json').read_text())
    recs = {}
    for line in open(run_dir / 'per_task.jsonl'):
        r = json.loads(line)
        recs[r['id']] = r
    client = cfg.get('client', 'harness')
    tag = cfg.get('tag', run_dir.name)
    prefix = f"{tag}/nonudge-{cfg['cfg']}:" if client == 'nonudge' else f"{tag}/{cfg['cfg']}:"
    ends = {}
    if (run_dir / 'client_calls.jsonl').exists():
        for line in open(run_dir / 'client_calls.jsonl'):
            c = json.loads(line)
            ends[c['task'].split(':')[-1]] = c
    per_task = {}
    for tid, r in recs.items():
        st, edits = call_level(by_task.get(prefix + tid, []))
        end = (ends.get(tid) or {}).get('end') if client == 'nonudge' else None
        per_task[tid] = {'resolved': int(r['resolved']), 'tool_calls': r.get('tool_calls'), 'llm_calls': r.get('llm_calls'),
                         'wall_s': r.get('wall_s'), 'agent_s': r.get('agent_s'), 'submitted': r.get('submitted'),
                         'error': r.get('error', '')[:120], 'st': dict(st), 'edits': edits, 'end': end}
    return per_task, client, cfg['cfg']


def _aggregate(run_name, client, cfg_name, per_task):
    n = len(per_task)
    k = sum(v['resolved'] for v in per_task.values())
    out = {'run': run_name, 'client': client, 'cfg': cfg_name, 'n_tasks': n, 'resolved': k,
           'resolve_rate': round(k / n, 4) if n else None, 'resolve_wilson': wilson(k, n)}
    for key in ('tool_calls', 'llm_calls', 'wall_s', 'agent_s'):
        out[key] = dict(zip(('mean', 'ci'), boot_mean([v[key] for v in per_task.values()])))
    for key in ('emu_l4_s', 'requests', 'gen_tokens', 'prompt_tokens', 'ipd_repairs', 'ipd_false_alarms', 'posthoc_repairs',
                'quarantine_actions', 'budget_forced', 'no_call_responses', 'unparsed_tool_call', 'length_finish', 'req_errors',
                'compaction_calls', 'ipd_rejected'):
        vals = [v['st'].get(key, 0) for v in per_task.values()]
        out[key] = {'total': sum(vals), **dict(zip(('mean', 'ci'), boot_mean(vals)))}
    for name in ('all', 'edit_file', 'write_file', 'run_command', 'read_file'):
        pre = '' if name == 'all' else f'{name}:'
        kk = 'calls_slipped' if name == 'all' else f'{name}:slipped'
        kb = 'calls_bad_delivered' if name == 'all' else f'{name}:bad_delivered'
        kn = 'calls' if name == 'all' else f'{name}:calls'
        out[f'{name}_slip'] = cluster_rate([(v['st'].get(kk, 0), v['st'].get(kn, 0)) for v in per_task.values()])
        out[f'{name}_bad_delivered'] = cluster_rate([(v['st'].get(kb, 0), v['st'].get(kn, 0)) for v in per_task.values()])
    first = [v['edits'][0][0] for v in per_task.values() if v['edits']]
    out['first_edit_slip'] = {'k': sum(first), 'n': len(first), 'rate': round(sum(first) / len(first), 4) if first else None,
                              'wilson': wilson(sum(first), len(first))}
    # contagion (as the CLIENT sent the history): edit slips by number of malformed calls already in history
    cont = defaultdict(lambda: [0, 0])
    for v in per_task.values():
        for i, (s, _, pb, _pbe) in enumerate(v['edits']):
            b = 'first' if i == 0 else ('0' if pb == 0 else ('1' if pb == 1 else '2+'))
            cont[b][0] += s
            cont[b][1] += 1
    out['edit_slip_by_hist_bad'] = {b: {'k': kv[0], 'n': kv[1], 'rate': round(kv[0] / kv[1], 4) if kv[1] else None,
                                        'wilson': wilson(*kv)} for b, kv in sorted(cont.items())}
    tasks_aff = [int(any(e[1] for e in v['edits'])) for v in per_task.values()]
    out['tasks_with_bad_delivered_edit'] = {'k': sum(tasks_aff), 'n': n, 'wilson': wilson(sum(tasks_aff), n)}
    if client == 'nonudge':
        out['episode_end'] = Counter(v['end'] for v in per_task.values())
    out['errors'] = Counter((v['error'] or '')[:60] for v in per_task.values() if v['error'])
    return out


def paired(pa, pb, name):
    common = sorted(set(pa) & set(pb))
    b = sum(1 for t in common if pa[t]['resolved'] and not pb[t]['resolved'])
    c = sum(1 for t in common if pb[t]['resolved'] and not pa[t]['resolved'])
    res = {'pair': name, 'n_common': len(common), 'A_only_resolved': b, 'B_only_resolved': c,
           'resolve_diff_B_minus_A': round((c - b) / len(common), 4) if common else None,
           'mcnemar_p': mcnemar_exact(b, c)}
    for key, get in (('tool_calls', lambda v: v['tool_calls']), ('wall_s', lambda v: v['wall_s']),
                     ('emu_l4_s', lambda v: v['st'].get('emu_l4_s')),
                     ('bad_delivered_calls', lambda v: v['st'].get('calls_bad_delivered', 0)),
                     ('slipped_calls', lambda v: v['st'].get('calls_slipped', 0))):
        d = [get(pb[t]) - get(pa[t]) for t in common if get(pa[t]) is not None and get(pb[t]) is not None]
        m, ci = boot_mean(d)
        res[f'{key}_diff_B_minus_A'] = {'mean': m, 'ci': ci}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', nargs='+', required=True)
    ap.add_argument('--proxy-logs', nargs='+', required=True)
    ap.add_argument('--pairs', nargs='*', default=[], help='runA:runB (indices into --runs)')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    by_task = load_proxy(a.proxy_logs)
    sums, pts = [], []
    for r in a.runs:
        s, p = summarize(r, by_task)
        sums.append(s)
        pts.append(p)
    pairs = []
    for pr in a.pairs:
        i, j = map(int, pr.split(':'))
        pairs.append(paired(pts[i], pts[j], f'{sums[i]["run"]} -> {sums[j]["run"]}'))
    res = {'runs': sums, 'pairs': pairs}
    Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    for s in sums:
        print(f"{s['run']}: resolved {s['resolved']}/{s['n_tasks']} {s['resolve_wilson']} | edit slip {s['edit_file_slip']['rate']} "
              f"bad-delivered {s['edit_file_bad_delivered']['rate']} | calls {s['tool_calls']['mean']} | ipd {s['ipd_repairs']['total']}")
    for p in pairs:
        print(json.dumps(p))


if __name__ == '__main__':
    main()
