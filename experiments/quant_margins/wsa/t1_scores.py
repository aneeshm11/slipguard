"""T1 protocol-fidelity scores from HF teacher-forced extractions (out/hf_<arm>.pt), on the PNC decision points.
Per arm and split: expected slip probability per string end (shipped sampler T=1/top-k 64/top-p 0.95, exact over the full
vocabulary), per-call slip probability, margin quantiles, logged-slip states, protected content, generic NLL.
Paired contrasts vs a reference arm on identical positions (episode-cluster bootstrap).
usage: t1_scores.py --arms bf16,qatct,ptq --ref bf16 --out out/t1_scores.json"""
import argparse, json, os, sys
import numpy as np, torch
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
from audit import score_records

ap = argparse.ArgumentParser(); ap.add_argument('--arms', default='bf16,qatct'); ap.add_argument('--ref', default='bf16')
ap.add_argument('--out', default=os.path.join(H, 'out', 't1_scores.json')); ap.add_argument('--boot', type=int, default=2000)
a = ap.parse_args()
SOFT = 30.0


def records(arm):
    d = torch.load(os.path.join(H, 'out', f'hf_{arm}.pt'), weights_only=False)
    post = SOFT * torch.tanh(d['zS'].float() / SOFT); lp = post - torch.logaddexp(d['lse_rest'][:, None], torch.logsumexp(post, 1, keepdim=True)) \
        if 'lse_rest' in d else post - d['lse'][:, None]
    margin = (lp[:, 0] - lp[:, 1:].max(1).values).numpy()
    la = set(d['lookalike_ids'])
    recs = []
    for i, m in enumerate(d['meta']):
        recs.append({**m, 'item': m['item'], 'pLA_T1': float(d['pLA_T1'][i]), 'pDQ_T1': float(d['pDQ_T1'][i]), 'margin': float(margin[i]),
                     'top1': int(d['greedy'][i]), 'top1_is_la': int(d['greedy'][i]) in la, 'lp_logged': float(d['lp_next'][i]),
                     'pLA_T07': float(d['pLA_T07'][i]), 'pLA_T02': float(d['pLA_T02'][i])})
    return recs, d.get('partial', False), d['info']


R_ = {}; out = {'arms': {}}
for arm in a.arms.split(','):
    if not os.path.exists(os.path.join(H, 'out', f'hf_{arm}.pt')):
        continue
    recs, partial, info = records(arm); R_[arm] = recs
    o = {'info': info, 'partial': partial, 'n_positions': len(recs)}
    for sp in ('calib', 'heldout', 'all'):
        rr = [r for r in recs if sp in ('all', r['split'])]
        o[sp] = score_records(rr)
        g = [r['lp_logged'] for r in rr if r['kind'] in ('generic_completion', 'generic_prompt')]
        w = [r['lp_logged'] for r in rr if r['kind'] == 'generic_text']
        o[sp]['generic_pnc_NLL'] = float(-np.mean(g)) if g else None
        o[sp]['generic_wikitext_NLL'] = float(-np.mean(w)) if w else None
    out['arms'][arm] = o
# paired contrasts on identical positions
rng = np.random.default_rng(0)
if a.ref in R_:
    key = lambda r: (r['episode_id'], r['turn_index'], r['pos'], r['kind'])
    ref = {key(r): r for r in R_[a.ref]}
    for arm, recs in R_.items():
        if arm == a.ref:
            continue
        for sp in ('calib', 'heldout', 'all'):
            pairs = [(r, ref[key(r)]) for r in recs if key(r) in ref and r['kind'] == 'close' and r['arg'] in ('new', 'old') and sp in ('all', r['split'])]
            if not pairs:
                continue
            x = np.array([p[0]['pLA_T1'] for p in pairs]); y = np.array([p[1]['pLA_T1'] for p in pairs])
            mx = np.array([min(p[0]['margin'], 99) for p in pairs]); my = np.array([min(p[1]['margin'], 99) for p in pairs])
            eps = sorted({p[0]['episode_id'] for p in pairs}); ix = {e: i for i, e in enumerate(eps)}
            gi = np.array([ix[p[0]['episode_id']] for p in pairs]); groups = [np.where(gi == i)[0] for i in range(len(eps))]
            bs = []
            for _ in range(a.boot):
                j = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
                bs.append((x[j].mean(), y[j].mean(), x[j].mean() / max(y[j].mean(), 1e-12)))
            bs = np.array(bs)
            out.setdefault('paired_vs_' + a.ref, {}).setdefault(arm, {})[sp] = {
                'n_positions': len(pairs), 'n_episodes': len(eps),
                'E_slip_arm': [float(x.mean())] + list(map(float, np.percentile(bs[:, 0], [2.5, 97.5]))),
                'E_slip_ref': [float(y.mean())] + list(map(float, np.percentile(bs[:, 1], [2.5, 97.5]))),
                'ratio_arm_over_ref': [float(x.mean() / max(y.mean(), 1e-12))] + list(map(float, np.percentile(bs[:, 2], [2.5, 97.5]))),
                'median_margin_arm': float(np.median(mx)), 'median_margin_ref': float(np.median(my)),
                'frac_arm_margin_smaller': float((mx < my).mean()), 'median_margin_shift': float(np.median(mx - my))}
json.dump(out, open(a.out, 'w'), indent=1)
for arm, o in out['arms'].items():
    se = o['heldout'].get('string_end_closers', {})
    print(arm, 'partial' if o['partial'] else 'final', 'heldout E_slip', se.get('E_slip_T1'), 'margin q', se.get('margin_quantiles_10_25_50_75_90'),
          'lt2', se.get('frac_margin_lt_2'), 'per-call', o['heldout'].get('per_call_slip_T1'), 'NLL pnc/wiki', o['heldout'].get('generic_pnc_NLL'), o['heldout'].get('generic_wikitext_NLL'))
print(json.dumps(out.get('paired_vs_' + a.ref, {}), indent=1)[:2000])
