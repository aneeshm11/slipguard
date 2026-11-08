"""EXPLORATORY (not pre-registered; written 2026-11-06 ~13:10 UTC, after unblinding). Review items B3/B9/B10 of
paper/protocol/draft/reviews/SELF_REVIEW_R1.md. Reuses the FROZEN analysis/prereg_analysis.py (episode(), load_arm(),
load_proxy(), boot_paired()) unchanged, and for branches the pre-outcome corrected-fidelity wrapper
(prereg_branch_corrected.py), so the same episodes / branch points as the registered outputs are summarised.
Questions:
  B3  are the registered means (E2E 2.47 -> 0.27; branch 11.6 -> 0.18) driven by a few runaway episodes?
      -> share of episodes / branches with >= 1 malformed call, median, p90, max, mean excluding stuck episodes.
  B9  branch result on the natural-onset subset (descriptive; n small).
  B10 resolve and cost on the tasks whose base episode got stuck (>= 5 malformed in a row).
Usage: EXPLORATORY_distributions.py --out analysis/EXPLORATORY_distributions.json"""
import argparse
import importlib.util
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


F = _load('prereg_frozen', HERE / 'prereg_analysis.py')
W = _load('prereg_wrapper', HERE / 'prereg_branch_corrected.py')

POPS = {
    '31B': dict(base='runs/pop31r1s0_H_base+runs/pop31r1s1_H_base+runs/pop31r2s0_H_base+runs/pop31r2s1_H_base',
                fullp='runs/pop31r1s0_H_fullp+runs/pop31r1s1_H_fullp+runs/pop31r2s0_H_fullp+runs/pop31r2s1_H_fullp',
                logs=['logs/proxy_pop31r1s0', 'logs/proxy_pop31r1s1', 'logs/proxy_pop31r2s0', 'logs/proxy_pop31r2s1'],
                registered='analysis/prereg_pop31.json'),
    'E4B': dict(base='runs/popE4r1_H_base', fullp='runs/popE4r1_H_fullp', logs=['logs/proxy_popE4r1'],
                registered='analysis/prereg_popE4B.json'),
}
BR31 = dict(groups=['plan=plans/b31a.json,base=runs/b31a_base,quar=runs/b31a_quar,ipd=runs/b31a_ipd,fullp=runs/b31a_fullp',
                    'plan=plans/b31b.json,base=runs/b31b_base,quar=runs/b31b_quar,ipd=runs/b31b_ipd,fullp=runs/b31b_fullp',
                    'plan=plans/b31_2.json,base=runs/b31c_base,quar=runs/b31c_quar,ipd=runs/b31c_ipd,fullp=runs/b31c_fullp'],
            logs=['logs/proxy_b31a', 'logs/proxy_b31b', 'logs/proxy_b31c'], registered='analysis/prereg_br31.json')


def desc(x):
    x = sorted(x)
    n = len(x)
    if not n:
        return None
    return {'n': n, 'mean': round(sum(x) / n, 4), 'share_ge1': [sum(1 for v in x if v >= 1), n, F.wilson(sum(1 for v in x if v >= 1), n)],
            'median': st.median(x), 'p90': x[min(n - 1, int(0.9 * n))], 'max': x[-1],
            'share_of_total_from_top5pct': round(sum(x[-max(1, n // 20):]) / sum(x), 3) if sum(x) else None}


def population(label, cfg):
    by = F.load_proxy([str(E / d) for d in cfg['logs']])
    tasks = [t for t in open(E / 'configs/eligible_113.txt').read().split() if t]
    arms = {k: F.load_arm('+'.join(str(E / d) for d in cfg[k].split('+')), by) for k in ('base', 'fullp')}
    excl = {t for t in tasks if any(e['infra_error'] for arm in arms.values() for e in arm.get(t, []))}
    common = [t for t in tasks if t in arms['base'] and t in arms['fullp'] and t not in excl]
    pairs = [(t, r, arms['base'][t][r], arms['fullp'][t][r]) for t in common
             for r in range(min(len(arms['base'][t]), len(arms['fullp'][t])))]
    out = {'n_tasks': len(common), 'n_episode_pairs': len(pairs)}
    for arm, i in (('base', 2), ('fullp', 3)):
        out[f'Y1_{arm}'] = desc([p[i]['Y1'] for p in pairs])
    # task-cluster bootstrap of the difference in the share of episodes with >= 1 delivered-malformed call
    d_share = []
    for t in common:
        pp = [p for p in pairs if p[0] == t]
        d_share.append(sum(int(p[3]['Y1'] >= 1) - int(p[2]['Y1'] >= 1) for p in pp) / len(pp))
    out['share_ge1_diff_fullp_minus_base_taskcluster'] = F.boot_paired(d_share, seed=101)
    # B3: excluding episode pairs whose base episode was stuck (the runaway loops)
    ns = [p for p in pairs if not p[2]['stuck']]
    xb, xf = [p[2]['Y1'] for p in ns], [p[3]['Y1'] for p in ns]
    out['Y1_excluding_base_stuck_pairs'] = {'n_pairs': len(ns), 'base_mean': round(sum(xb) / len(xb), 4),
                                            'fullp_mean': round(sum(xf) / len(xf), 4),
                                            'ratio': round(sum(xf) / sum(xb), 4) if sum(xb) else None,
                                            'base_share_ge1': [sum(1 for v in xb if v >= 1), len(xb)],
                                            'fullp_share_ge1': [sum(1 for v in xf if v >= 1), len(xf)]}
    # B10: the pairs whose base episode got stuck
    sp = [p for p in pairs if p[2]['stuck']]
    out['base_stuck_pairs'] = {
        'n_pairs': len(sp), 'tasks': sorted({p[0] for p in sp}),
        'resolved_base': sum(p[2]['resolved'] for p in sp), 'resolved_fullp': sum(p[3]['resolved'] for p in sp),
        'fullp_stuck': sum(p[3]['stuck'] for p in sp),
        'Y1_base_mean': round(st.mean(p[2]['Y1'] for p in sp), 2) if sp else None,
        'Y1_fullp_mean': round(st.mean(p[3]['Y1'] for p in sp), 2) if sp else None,
        'calls_base_mean': round(st.mean(p[2]['calls'] for p in sp), 1) if sp else None,
        'calls_fullp_mean': round(st.mean(p[3]['calls'] for p in sp), 1) if sp else None,
        'gen_tokens_base_mean': round(st.mean(p[2]['gen_tokens'] for p in sp)) if sp else None,
        'gen_tokens_fullp_mean': round(st.mean(p[3]['gen_tokens'] for p in sp)) if sp else None}
    out['calls_per_episode_max'] = {'base': max(p[2]['calls'] for p in pairs), 'fullp': max(p[3]['calls'] for p in pairs)}
    reg = json.loads((E / cfg['registered']).read_text())['co_primary']['Y1']
    out['check_vs_registered'] = {'registered_base_mean': reg['base_mean'], 'registered_fullp_mean': reg['fullp_mean'],
                                  'episode_level_base_mean_here': out['Y1_base']['mean'],
                                  'note': 'registered means are task means over replicates; here episode means (equal when every task has the same replicate count)'}
    return out


def branches31():
    groups = BR31['groups']
    cmap = W.corrected_map([g.replace('plan=', f'plan={E}/').replace('=runs/', f'={E}/runs/') for g in groups])
    orig = F.load_proxy

    def load_proxy(dirs):  # identical to the wrapper's patch
        by = orig(dirs)
        for key, recs in by.items():
            rundir = key.split('/')[0]
            if rundir not in cmap:
                continue
            _, verdict = cmap[rundir]
            tid = key.split(':')[-1]
            for r in recs:
                if r.get('replayed'):
                    r['replay'] = {**(r.get('replay') or {}), 'fidelity': 'ok' if verdict.get(tid) == 'ok' else 'mismatch'}
        return by

    by = load_proxy([str(E / d) for d in BR31['logs']])
    plan, arms = {}, defaultdict(dict)
    for gi, g in enumerate(groups):  # mirrors F.branches() id selection exactly
        kv = dict(x.split('=', 1) for x in g.split(','))
        pl = json.loads((E / kv.pop('plan')).read_text())['branches']
        for t, e in pl.items():
            plan[f'{gi}:{t}'] = e
        for name, rd in kv.items():
            rd = E / rd
            rc = json.loads((rd / 'run_cfg.json').read_text())
            pref = f"{rc.get('tag', rd.name)}/{rc['cfg']}:"
            for line in open(rd / 'per_task.jsonl'):
                p = json.loads(line)
                reqs = by.get(pref + p['id'], [])
                fid_bad = any((r.get('replay') or {}).get('fidelity') == 'mismatch' for r in reqs)
                arms[name][f'{gi}:{p["id"]}'] = {**F.episode(reqs, p, after_index=pl[p['id']]['b'] if p['id'] in pl else None),
                                                 'fidelity_mismatch': fid_bad}
    ids = sorted(set.intersection(*[set(v) for v in arms.values()]) & set(plan))
    excl = [t for t in ids if any(arms[k][t]['fidelity_mismatch'] or arms[k][t]['infra_error'] for k in arms)]
    ids = [t for t in ids if t not in excl]
    out = {'n_branch_points': len(ids)}
    reg = json.loads((E / BR31['registered']).read_text())
    out['check_vs_registered_n'] = reg['n_branch_points']
    for k in arms:
        out[f'post_malformed_{k}'] = desc([arms[k][t]['post']['malformed'] for t in ids])
    # B3: exclude branch points whose BASE continuation got stuck
    ns = [t for t in ids if not arms['base'][t]['stuck']]
    out['excluding_base_stuck'] = {'n': len(ns), **{k: round(st.mean(arms[k][t]['post']['malformed'] for t in ns), 4) for k in arms}}
    out['base_stuck_n'] = len(ids) - len(ns)
    # B9: natural vs injected onsets
    for typ in sorted({plan[t]['onset'] for t in ids}):
        sub = [t for t in ids if plan[t]['onset'] == typ]
        out[f'onset_{typ}'] = {'n': len(sub), **{k: {'mean': round(st.mean(arms[k][t]['post']['malformed'] for t in sub), 3),
                                                     'share_ge1': [sum(1 for t in sub if arms[k][t]['post']['malformed'] >= 1), len(sub)],
                                                     'resolved': sum(arms[k][t]['resolved'] for t in sub)} for k in arms}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    res = {'_status': 'EXPLORATORY, not pre-registered (review items B3/B9/B10); frozen code reused unchanged',
           'population': {k: population(k, v) for k, v in POPS.items()}, 'branches_31B': branches31()}
    Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == '__main__':
    sys.exit(main())
