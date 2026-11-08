"""EXPLORATORY (not pre-registered; PI 2026-11-06 ~13:13 UTC; review item B13). Sensitivity of the audit-weights
deficit ranking to top-20 censoring. Reads the frozen sweep records (out/audit_sweep_<name>.records.jsonl) read-only;
writes out/EXPLORATORY_censoring.json.
Censoring types at a string end (kind 'close', arg new/old):
  LA  : no look-alike in the top-20  -> true margin >= recorded value (lower bound; recorded = lp(<|"|>) - lp_20)
  DQ  : <|"|> itself not in the top-20 -> true margin <= recorded value (UPPER bound; recorded = lp_20 - max lp(LA))
Statistics per checkpoint vs its same-family bf16 reference (identical positions):
  (1) registered: median(ref) - median(ckpt) on lower-bound values (reproduced here as a check);
  (2) both-uncensored pairs only: median deficit + mean paired deficit, episode-cluster bootstrap 95% CI;
  (3) Gehan-type score: (#pairs ckpt<ref certain - #pairs ckpt>ref certain) / n, using bounds (both-censored and
      ambiguous pairs count 0) -- a censoring-robust direction of damage."""
import json, math, os
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
TAU = math.log(19.0)
DQ, B = 52, 2000


def load(name):
    out = {}
    for line in open(os.path.join(H, 'out', f'audit_sweep_{name}.records.jsonl')):
        r = json.loads(line)
        if r['kind'] != 'close' or r['arg'] not in ('new', 'old'):
            continue
        top = dict((int(t), v) for t, v in r['top'])
        lp20 = min(top.values())
        m = r['margin']
        if not np.isfinite(m):  # no look-alike in top-20 (and DQ present): registered lower bound
            m = (top.get(DQ, lp20)) - lp20
        typ = 'none'
        if DQ not in top:
            typ = 'DQ'
        elif not r.get('margin_censored', False) and np.isfinite(r['margin']):
            typ = 'none'
        else:
            typ = 'LA'
        out[(r['episode_id'], r['turn_index'], r['pos'])] = (m, typ)
    return out


def certain_less(a, b):
    """True if true value of a is certainly < true value of b. a,b = (value, type)."""
    (va, ta), (vb, tb) = a, b
    a_hi = va if ta in ('none', 'DQ') else math.inf   # upper bound of a
    b_lo = vb if tb in ('none', 'LA') else -math.inf  # lower bound of b
    return a_hi < b_lo


def compare(R, ref, rng):
    keys = sorted(k for k in R if k in ref)
    x = np.array([R[k][0] for k in keys]); y = np.array([ref[k][0] for k in keys])
    unc = np.array([R[k][1] == 'none' and ref[k][1] == 'none' for k in keys])
    less = np.array([certain_less(R[k], ref[k]) for k in keys]); more = np.array([certain_less(ref[k], R[k]) for k in keys])
    eps = np.array([k[0] for k in keys]); groups = [np.where(eps == e)[0] for e in np.unique(eps)]
    bs = []
    for _ in range(B):
        j = np.concatenate([groups[g] for g in rng.integers(0, len(groups), len(groups))])
        ju = j[unc[j]]
        bs.append((np.median(y[ju]) - np.median(x[ju]) if len(ju) else np.nan, (y[ju] - x[ju]).mean() if len(ju) else np.nan,
                   (less[j].sum() - more[j].sum()) / len(j)))
    bs = np.array(bs)
    ci = lambda c: [round(float(np.nanpercentile(bs[:, c], 2.5)), 3), round(float(np.nanpercentile(bs[:, c], 97.5)), 3)]
    return {'n_pairs': len(keys),
            'registered_median_deficit_lb': round(float(np.median(y) - np.median(x)), 3),
            'n_both_uncensored': int(unc.sum()),
            'median_deficit_uncensored': [round(float(np.median(y[unc]) - np.median(x[unc])), 3)] + ci(0),
            'mean_paired_deficit_uncensored': [round(float((y[unc] - x[unc]).mean()), 3)] + ci(1),
            'gehan_score': [round(float((less.sum() - more.sum()) / len(keys)), 3)] + ci(2),
            'certain_lower_than_ref': int(less.sum()), 'certain_higher_than_ref': int(more.sum())}


def main():
    rng = np.random.default_rng(0)
    names = sorted(f.split('audit_sweep_')[1][:-len('.records.jsonl')] for f in os.listdir(os.path.join(H, 'out'))
                   if f.startswith('audit_sweep_') and f.endswith('.records.jsonl'))
    data = {n: load(n) for n in names}
    res = {'_status': 'EXPLORATORY (review B13); frozen records read-only', 'censoring_types': {}, 'vs_reference': {}}
    for n, R in data.items():
        t = [v[1] for v in R.values()]
        res['censoring_types'][n] = {'n': len(t), 'LA_lower_bound': t.count('LA'), 'DQ_upper_bound': t.count('DQ'), 'uncensored': t.count('none')}
    for n in names:
        ref = '31b_bf16' if n.startswith('31b_') else ('e4b_bf16' if n.startswith('e4b_') else None)
        if ref is None or n == ref:
            continue
        res['vs_reference'][n] = {'reference': ref, **compare(data[n], data[ref], rng)}
    json.dump(res, open(os.path.join(H, 'out', 'EXPLORATORY_censoring.json'), 'w'), indent=1)
    print(json.dumps(res['censoring_types'], indent=0))
    print(f"{'checkpoint':22s} {'reg_lb':>7s} {'n_unc':>5s} {'med_unc [CI]':>24s} {'mean_unc [CI]':>24s} {'gehan [CI]':>24s}")
    for n, o in sorted(res['vs_reference'].items(), key=lambda kv: -kv[1]['registered_median_deficit_lb']):
        print(f"{n:22s} {o['registered_median_deficit_lb']:7.2f} {o['n_both_uncensored']:5d} {str(o['median_deficit_uncensored']):>24s} "
              f"{str(o['mean_paired_deficit_uncensored']):>24s} {str(o['gehan_score']):>24s}")


if __name__ == '__main__':
    main()
