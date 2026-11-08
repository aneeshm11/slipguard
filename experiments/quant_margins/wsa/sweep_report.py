"""T1 sweep report (SWEEP_PLAN.md): per checkpoint, from out/audit_sweep_<name>.records.jsonl (endpoint audit, top-20):
held-out new/old string-end margins (median, p10; censoring fraction; censored -> lower bound lp(<|"|>) - lp_20),
P(m < ln 19) (exact), E_slip (shipped sampler), onset per-call slip probability (clean-history valid calls), logged slip
states, paired contrasts vs 31B bf16 on identical positions (episode-cluster bootstrap), and the pre-registered flag rule.
usage: sweep_report.py [--ref 31b_bf16] --out out/sweep_report.json"""
import argparse, glob, json, math, os
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument('--ref', default='31b_bf16'); ap.add_argument('--out', default=os.path.join(H, 'out', 'sweep_report.json'))
ap.add_argument('--boot', type=int, default=2000)
a = ap.parse_args()
TAU = math.log(19.0)
items = {(json.loads(l)['episode_id'], json.loads(l)['turn_index']): json.loads(l) for l in open(os.path.join(H, 'data', 'audit_items_16k.jsonl'))}
rng = np.random.default_rng(0)


def load(name):
    recs = [json.loads(l) for l in open(os.path.join(H, 'out', f'audit_sweep_{name}.records.jsonl'))]
    out = {}
    for r in recs:
        top = dict((int(t), v) for t, v in r['top']); lp20 = min(top.values()); lpdq = top.get(52)
        m = r['margin']
        cens = not np.isfinite(m) or r.get('margin_censored', False)
        m_lb = (lpdq if lpdq is not None else lp20) - lp20 if not np.isfinite(m) else m
        out[(r['episode_id'], r['turn_index'], r['pos'], r['kind'])] = {**r, 'm_lb': m_lb, 'censored': bool(cens),
                                                                       'n_prior_bad': items[(r['episode_id'], r['turn_index'])]['n_prior_bad']}
    return out


def summarize(R):
    se = [r for r in R.values() if r['kind'] == 'close' and r['arg'] in ('new', 'old')]
    m = np.array([r['m_lb'] for r in se]); p = np.array([r['pLA_T1'] for r in se])
    calls = {}
    for r in se:
        if r['n_prior_bad'] == 0:
            calls.setdefault((r['episode_id'], r['turn_index']), []).append(r['pLA_T1'])
    pc = np.array([1 - np.prod([1 - x for x in v]) for v in calls.values()])
    sl = [r for r in R.values() if r['kind'] == 'slip']
    return {'n_string_ends': len(se), 'censored_frac': float(np.mean([r['censored'] for r in se])),
            'margin_median_lb': float(np.median(m)), 'margin_p10_lb': float(np.percentile(m, 10)),
            'P_m_lt_ln19': float((m < TAU).mean()), 'E_slip': float(p.mean()),
            'onset_per_call': float(pc.mean()) if len(pc) else None, 'n_onset_calls': len(pc),
            'slip_states_pLA': float(np.mean([r['pLA_T1'] for r in sl])) if sl else None, 'n_slip_states': len(sl)}


names = sorted(f.split('audit_sweep_')[1][:-len('.records.jsonl')] for f in glob.glob(os.path.join(H, 'out', 'audit_sweep_*.records.jsonl'))
               if os.path.exists(f.replace('.records.jsonl', '.json')))
data = {n: load(n) for n in names}
res = {'tau': TAU, 'reference': a.ref, 'checkpoints': {}}
ref = data.get(a.ref)
for n, R in data.items():
    o = summarize(R)
    if ref is not None and n != a.ref:
        keys = [k for k in R if k in ref and k[3] == 'close' and R[k]['arg'] in ('new', 'old')]
        x = np.array([R[k]['m_lb'] for k in keys]); y = np.array([ref[k]['m_lb'] for k in keys])
        px = np.array([R[k]['pLA_T1'] for k in keys]); py = np.array([ref[k]['pLA_T1'] for k in keys])
        eps = np.array([k[0] for k in keys]); ue = np.unique(eps); groups = [np.where(eps == e)[0] for e in ue]
        bs = []
        for _ in range(a.boot):
            j = np.concatenate([groups[g] for g in rng.integers(0, len(groups), len(groups))])
            bs.append((np.median(y[j]) - np.median(x[j]), (x[j] < TAU).mean() - (y[j] < TAU).mean(), px[j].mean() - py[j].mean()))
        bs = np.array(bs); q = lambda c: [float(np.percentile(bs[:, c], 2.5)), float(np.percentile(bs[:, c], 97.5))]
        o['paired_vs_ref'] = {'n': len(keys), 'median_deficit': [float(np.median(y) - np.median(x))] + q(0),
                              'dP_m_lt_ln19': [float((x < TAU).mean() - (y < TAU).mean())] + q(1), 'dE_slip': [float(px.mean() - py.mean())] + q(2)}
        dfc = o['paired_vs_ref']['median_deficit'][0]
        o['FLAG'] = bool(o['P_m_lt_ln19'] >= 0.005 or dfc >= 3.0)
        o['SEVERE'] = bool(o['P_m_lt_ln19'] >= 0.02 or o['E_slip'] >= 0.01)
    res['checkpoints'][n] = o
json.dump(res, open(a.out, 'w'), indent=1)
print(f"{'checkpoint':22s} {'n':>4s} {'cens':>5s} {'med':>6s} {'p10':>6s} {'P<ln19':>7s} {'E_slip':>8s} {'onset/call':>10s} {'slipP':>6s} {'deficit':>16s} flag")
for n, o in res['checkpoints'].items():
    d = o.get('paired_vs_ref', {}).get('median_deficit')
    print(f"{n:22s} {o['n_string_ends']:4d} {o['censored_frac']:5.2f} {o['margin_median_lb']:6.2f} {o['margin_p10_lb']:6.2f} {o['P_m_lt_ln19']:7.4f} {o['E_slip']:8.5f} "
          f"{(o['onset_per_call'] or 0):10.5f} {(o['slip_states_pLA'] or 0):6.3f} {('%.2f [%.2f,%.2f]' % tuple(d)) if d else '-':>16s} "
          f"{'SEVERE' if o.get('SEVERE') else ('FLAG' if o.get('FLAG') else '')}")
