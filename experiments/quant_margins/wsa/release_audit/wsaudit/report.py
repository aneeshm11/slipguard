"""Audit report and pre-registered flag rule (SWEEP_PLAN.md, F 2026-11-05). Path-free.

summarize(records) -> dict          per-checkpoint metrics on held-out new/old string ends
compare(records, reference) -> dict  paired deficits vs a reference checkpoint (same states), episode-cluster bootstrap
flag(summary, paired) -> (FLAG, SEVERE)
Metrics: margin m = log P(<|"|>) - log P(best look-alike) (top-20; censored -> lower bound lp(<|"|>) - lp_20, censoring
fraction reported); P(m < ln 19) (exact: a look-alike with m < ln 19 is in the top-20); E_slip = mean shipped-sampler
look-alike probability; onset per-call slip probability (clean-history calls, 1 - prod(1 - p) over new/old closers).
Flag rule: FLAG if P(m < ln 19) >= 0.5% or the median deficit vs the same-family bf16 reference >= 3 nats;
SEVERE if P(m < ln 19) >= 2% or E_slip >= 1%."""
import math
import numpy as np

TAU = math.log(19.0)
SCHEMA = 'slipguard.weights.audit/v1'


def _m_lb(r):
    m = r['margin']
    if isinstance(m, (int, float)) and math.isfinite(m):
        return m
    top = dict((int(t), v) for t, v in r['top']); lp20 = min(top.values())
    return top.get(52, lp20) - lp20


def summarize(records):
    se = [r for r in records if r['kind'] == 'close' and r.get('arg') in ('new', 'old')]
    m = np.array([_m_lb(r) for r in se]); p = np.array([r['pLA_T1'] for r in se])
    calls = {}
    for r in se:
        if r.get('n_prior_bad', 0) == 0:
            calls.setdefault((r['episode_id'], r['turn_index']), []).append(r['pLA_T1'])
    pc = [1 - np.prod([1 - x for x in v]) for v in calls.values()]
    sl = [r['pLA_T1'] for r in records if r['kind'] == 'slip']
    return {'schema': SCHEMA, 'n_string_ends': len(se), 'censored_frac': float(np.mean([r.get('margin_censored', False) for r in se])),
            'margin_median_lb': float(np.median(m)), 'margin_p10_lb': float(np.percentile(m, 10)), 'P_m_lt_ln19': float((m < TAU).mean()),
            'E_slip': float(p.mean()), 'onset_per_call': float(np.mean(pc)) if pc else None, 'n_onset_calls': len(pc),
            'slip_states_pLA': float(np.mean(sl)) if sl else None, 'n_slip_states': len(sl)}


def compare(records, reference, boot=2000, seed=0):
    key = lambda r: (r['episode_id'], r['turn_index'], r['pos'], r['kind'])
    ref = {key(r): r for r in reference}
    keys = [key(r) for r in records if key(r) in ref and r['kind'] == 'close' and r.get('arg') in ('new', 'old')]
    rec = {key(r): r for r in records}
    x = np.array([_m_lb(rec[k]) for k in keys]); y = np.array([_m_lb(ref[k]) for k in keys])
    eps = np.array([k[0] for k in keys]); groups = [np.where(eps == e)[0] for e in np.unique(eps)]
    rng = np.random.default_rng(seed)
    bs = [np.median(y[j]) - np.median(x[j]) for j in (np.concatenate([groups[g] for g in rng.integers(0, len(groups), len(groups))]) for _ in range(boot))]
    return {'n': len(keys), 'median_deficit': [float(np.median(y) - np.median(x)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


def flag(summary, paired=None):
    deficit = paired['median_deficit'][0] if paired else 0.0
    return (bool(summary['P_m_lt_ln19'] >= 0.005 or deficit >= 3.0),
            bool(summary['P_m_lt_ln19'] >= 0.02 or summary['E_slip'] >= 0.01))
