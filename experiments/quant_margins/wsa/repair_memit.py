"""T3 candidate (b): closed-form protocol-margin repair of the quantized checkpoint as a rank-|S| edit of the LAST decoder
layer's MLP down_proj (served as a LoRA over the W4A16 base). No gradient descent, no LLM in the loop.

Model facts (Gemma-4, last layer): y = W_down a ; f = y/rms(y)*g_pf ; x_L = (x_mid + f)*s ; h = x_L/rms(x_L)*g ; z = E h ;
post = 30 tanh(z/30). A last-layer down_proj edit dW changes only the position's own x_L (no later layer reads it), so its
effect at every extracted position is EXACT given (a, y, x_L):
    x_L' = x_L + s * (pf(y + dW a) - pf(y)),   h' = x_L'/rms(x_L')*g,   z' = E h'.
Solve (MEMIT-style, closed form):
 1. targets at calibration decision positions (valid string-end closers + logged slips), for S = {<|"|>} + 80 look-alikes:
      dz_t = 30 atanh((post^Q_t + alpha*[(post^B_t - lse_rest^B) - (post^Q_t - lse_rest^Q)])/30) - z^Q_t   (tokens with p < p_min
    in both models: dz = 0): restore the bf16 teacher's log-odds of every S token against the (unchanged) rest of the vocab.
    Output basis (Jacobian ~ kappa_i * D, kappa_i = s/(rms(x_L) rms(y)), D = diag(g*g_pf)):
      Bout = (D (E_S^T E_S + rho*Gamma) D + eps*I)^-1 D E_S^T,   Gamma = E^T E / V   (penalises total logit movement)
 2. keys -> outputs:  A = T K^T (K K^T + lam*(n/N_p)*C_p + mu*I)^-1 with T = [dz_i/kappa_i], K = calibration decision keys,
    C_p = sum of a a^T over PRESERVED calibration positions (generic PNC prompt/completion text, wikitext, legitimate look-alike
    content, in-string content, string openers).   dW = Bout A  ->  LoRA B = Bout (5376 x |S|), A (|S| x 21504).
 3. optional fixed-point refinement (--iters): re-target the exact residual dz - dz_realised and add a correction edit.
Evaluation (exact, formula above): held-out string-end slip probability under the shipped sampler, margins, logged slips;
KL / dNLL at generic PNC and wikitext positions; premature-close risk at in-string content; openers; legitimate content.
usage: repair_memit.py [--eval_split innercv|heldout] [--lams ...] [--save_adapter DIR] --out out/repair_grid.json"""
import argparse, json, os, sys, time, itertools, hashlib
import numpy as np
import torch
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)

ap = argparse.ArgumentParser()
ap.add_argument('--qat', default=os.path.join(H, 'out', 'hf_qatct.pt')); ap.add_argument('--teacher', default=os.path.join(H, 'out', 'hf_bf16.pt'))
ap.add_argument('--embed', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct/model.safetensors'))
ap.add_argument('--out', default=os.path.join(H, 'out', 'repair_grid.json'))
ap.add_argument('--lams', default='0.1,1,10'); ap.add_argument('--rhos', default='0,1'); ap.add_argument('--alphas', default='1.0')
ap.add_argument('--eps', type=float, default=1e-3); ap.add_argument('--mu', type=float, default=1e-3); ap.add_argument('--p_min', type=float, default=1e-4)
ap.add_argument('--iters', type=int, default=0)
ap.add_argument('--target_modes', default='match_all', help='comma list of: match_all | la_rel_dq | la_rel_dq_onesided')
ap.add_argument('--eval_split', default='innercv', choices=['innercv', 'heldout'])
ap.add_argument('--save_adapter', default=''); ap.add_argument('--device', default='cpu'); ap.add_argument('--threads', type=int, default=9)
ap.add_argument('--max_eval', type=int, default=0); ap.add_argument('--dump_pred', type=int, default=40)
ap.add_argument('--fit_only', action='store_true', help='fit on ALL calib and save the adapter; no evaluation (pre-gate)')
ap.add_argument('--output_span', default='S', choices=['S', 'la_only'], help='la_only = candidate C: constrained min-movement basis on look-alike rows only')
a = ap.parse_args()
torch.set_num_threads(a.threads)
dev = a.device; SOFT = 30.0; DQ = 52


def load_embed(path):
    import glob
    from safetensors import safe_open
    for f_ in ([path] if path.endswith('.safetensors') else sorted(glob.glob(os.path.join(path, '*.safetensors')))):
        with safe_open(f_, framework='pt') as f:
            if 'model.language_model.embed_tokens.weight' in f.keys():
                return f.get_tensor('model.language_model.embed_tokens.weight')
    raise KeyError('embed_tokens not found in ' + path)


Q = torch.load(a.qat, weights_only=False); T_ = torch.load(a.teacher, weights_only=False)
# wikitext: the main runs' windows lack <bos> (bug, see ANALYSIS_PLAN deviations) -> drop them; use the BOS-correct rerun if present
_keep = [i for i, m in enumerate(Q['meta']) if m['kind'] != 'generic_text']
# PI 14:2x: wikitext-2 TEST windows are a GATE-ONLY set (odd windows only: even windows were touched by earlier
# selection runs); lambda selection and preserved keys use the wikitext-2 VALIDATION split (generic_textval).
_W = a.qat.replace('.pt', '_wiki.pt'); _WV = a.qat.replace('.pt', '_wikival.pt')
_Wd = torch.load(_W, weights_only=False) if os.path.exists(_W) else None
_WVd = torch.load(_WV, weights_only=False) if os.path.exists(_WV) else None
if _Wd is not None:
    _odd = [i for i, m in enumerate(_Wd['meta']) if int(m['episode_id'].rsplit('_w', 1)[1]) % 2 == 1]
    for k_ in ('xL', 'y_down', 'a_down', 'zS', 'lse_rest'):
        _Wd[k_] = _Wd[k_][_odd]
    _Wd['meta'] = [dict(_Wd['meta'][i], split='heldout') for i in _odd]
if _WVd is not None:
    _WVd['meta'] = [dict(m, split='calib') for m in _WVd['meta']]
_LE = [a.qat.replace('.pt', f'_lineend_{sp_}.pt') for sp_ in ('calib', 'heldout')] + [a.qat.replace('.pt', f'_cneg_{sp_}.pt') for sp_ in ('calib', 'heldout')]
_LEd = []
for f_ in _LE:
    if os.path.exists(f_):
        d_ = torch.load(f_, weights_only=False); keep_ = [i for i, m in enumerate(d_['meta']) if m['kind'] in ('lineend', 'postopen', 'nlclose')]
        for k_ in ('xL', 'y_down', 'a_down', 'zS', 'lse_rest'):
            d_[k_] = d_[k_][keep_]
        d_['meta'] = [d_['meta'][i] for i in keep_]; _LEd.append(d_)
print('line-end hard negatives merged:', [len(d_['meta']) for d_ in _LEd], flush=True)
_extra = [d_ for d_ in (_Wd, _WVd) if d_ is not None] + _LEd
for k_ in ('xL', 'y_down', 'a_down', 'zS', 'lse_rest'):
    Q[k_] = torch.cat([Q[k_][_keep]] + [d_[k_] for d_ in _extra])
Q['meta'] = [Q['meta'][i] for i in _keep] + [m for d_ in _extra for m in d_['meta']]
print(f"wikitext test (gate-only, odd windows): {'merged' if _Wd is not None else 'absent'}; wikitext validation (selection/preserved): {'merged' if _WVd is not None else 'absent'}", flush=True)
meta = Q['meta']; N = len(meta)
key = lambda m: (m['episode_id'], m['turn_index'], m['pos'], m['kind'])
tix = {key(m): i for i, m in enumerate(T_['meta'])}
has_t = np.array([key(m) in tix for m in meta]); tmap = np.array([tix.get(key(m), -1) for m in meta])
LA = Q['lookalike_ids']; S = [DQ] + LA
g = Q['g_final'].to(dev); gpf = Q['g_postff_last'].to(dev); s_last = Q['layer_scalar_last']
E = load_embed(a.embed).to(dev).float(); E_S = E[S]
xL = Q['xL'].to(dev).float(); y = Q['y_down'].to(dev).float(); A_keys = Q['a_down']
zQ = Q['zS'].float(); lrQ = Q['lse_rest'].float()
zB = torch.full_like(zQ, float('nan')); lrB = torch.full_like(lrQ, float('nan'))
zB[torch.tensor(has_t)] = T_['zS'][torch.tensor(tmap[has_t])].float(); lrB[torch.tensor(has_t)] = T_['lse_rest'][torch.tensor(tmap[has_t])].float()
tpla = np.full(N, np.nan); tpla[has_t] = T_['pLA_T1'][torch.tensor(tmap[has_t])].numpy()
print(f'QAT positions {N}, with teacher {has_t.sum()}', flush=True)


def rms(v):
    return v.pow(2).mean(-1, keepdim=True).add(1e-6).sqrt()


def pf(v):
    return v / rms(v) * gpf


def hnorm(v):
    return v / rms(v) * g


# sanity: the stored pre-softcap logits must be reproduced exactly from x_L with this embedding / final-norm weight
_chk = torch.arange(0, N, max(1, N // 64))
_z = (hnorm(xL[_chk]) @ E_S.T).cpu()
_err = float((_z - zQ[_chk]).abs().max())
print(f'logit reproduction check: max |z(x_L) - z_stored| = {_err:.4f}', flush=True)
assert _err < 0.25, 'embedding / norm mismatch between --qat extraction and --embed'
kind = np.array([m['kind'] for m in meta]); split = np.array([m['split'] for m in meta]); arg = np.array([str(m.get('arg')) for m in meta])
cv = np.array([int(hashlib.sha256(('cv|' + m['episode_id']).encode()).hexdigest()[:8], 16) % 2 for m in meta])
PRES = ['generic_completion', 'generic_prompt', 'generic_textval', 'protected', 'content', 'opener', 'lineend', 'postopen', 'nlclose']   # generic_text (wikitext TEST) is gate-only
# ANALYSIS_PLAN deviation 13:00: fit on calib VALID string ends only; logged slip states are never used for fitting or
# selection (innercv excludes them); in the final held-out evaluation ALL 51 slip states are out-of-sample test states.
is_dec = (kind == 'close') & has_t
is_pres = np.isin(kind, PRES)
if a.eval_split == 'innercv':
    fit_mask = (split == 'calib') & (cv == 0); ev_mask = (split == 'calib') & (cv == 1) & (kind != 'slip') & (kind != 'generic_text')
else:
    fit_mask = split == 'calib'; ev_mask = ((split == 'heldout') | (kind == 'slip')) & (kind != 'generic_textval')
fit_dec = np.where(fit_mask & is_dec)[0]; fit_pres = np.where(fit_mask & is_pres)[0]; ev_idx = np.where(ev_mask)[0]
if a.max_eval:
    ev_idx = np.sort(np.random.default_rng(0).choice(ev_idx, min(a.max_eval, len(ev_idx)), replace=False))
print(f'fit decision {len(fit_dec)}, preserved keys {len(fit_pres)}, eval positions {len(ev_idx)}', flush=True)

postQ = SOFT * torch.tanh(zQ / SOFT); postB = SOFT * torch.tanh(zB / SOFT)
lseQ = torch.logaddexp(lrQ, torch.logsumexp(postQ, 1)); lseB = torch.logaddexp(lrB, torch.logsumexp(postB, 1))
relevant = torch.maximum(torch.exp(postQ - lseQ[:, None]), torch.nan_to_num(torch.exp(postB - lseB[:, None]))) >= a.p_min


lpB_S = postB - lseB[:, None]
mB = (lpB_S[:, 0] - lpB_S[:, 1:].max(1).values).numpy()        # bf16 teacher margin (nan where no teacher row)


def targets(alpha, mode='match_all'):
    if mode != 'match_all':
        # look-alikes relative to <|"|>: match bf16's log-odds(LA_t vs <|"|>); <|"|> vs the rest of the vocab unchanged
        rel = (postB[:, 1:] - postB[:, :1]) - (postQ[:, 1:] - postQ[:, :1])
        if mode == 'la_rel_dq_onesided':
            rel = rel.clamp(max=0.0)                            # only ever SUPPRESS look-alikes
        d_post = torch.cat([torch.zeros_like(rel[:, :1]), rel], 1)
        newpost = (postQ + alpha * d_post).clamp(-SOFT * 0.9999, SOFT * 0.9999)
        dz = SOFT * torch.atanh(newpost / SOFT) - zQ
        return torch.nan_to_num(torch.where(relevant, dz, torch.zeros_like(dz)))
    d_post = (postB - lrB[:, None]) - (postQ - lrQ[:, None])
    newpost = (postQ + alpha * d_post).clamp(-SOFT * 0.9999, SOFT * 0.9999)
    dz = SOFT * torch.atanh(newpost / SOFT) - zQ
    return torch.nan_to_num(torch.where(relevant, dz, torch.zeros_like(dz)))


kappa = (s_last / (rms(xL) * rms(y)))[:, 0]
D = g * gpf
t0 = time.time()
Gamma = (E.T @ E) / E.shape[0]


def make_Bout_la_only():
    # candidate C: minimum-movement right inverse of the look-alike rows under the metric of all OTHER logits (incl. <|"|>)
    E_LA = E_S[1:]
    G_rest = Gamma - (E_LA.T @ E_LA) / E.shape[0]
    M = D[:, None] * G_rest * D[None, :]
    M = M + a.eps * M.diagonal().mean() * torch.eye(M.shape[0], device=dev)
    K_ = D[:, None] * E_LA.T                                    # (d, 80)
    MiK = torch.linalg.solve(M, K_)
    return MiK @ torch.linalg.inv(K_.T @ MiK)                   # (d, 80): E_LA D Bout = I


def make_Bout(rho):
    M = D[:, None] * (E_S.T @ E_S + rho * Gamma) * D[None, :]
    M = M + a.eps * M.diagonal().mean() * torch.eye(M.shape[0], device=dev)
    return torch.linalg.solve(M, D[:, None] * E_S.T)


def gram(idx):
    G = torch.zeros(A_keys.shape[1], A_keys.shape[1], device=dev)
    for c in range(0, len(idx), 2048):
        k = A_keys[idx[c:c + 2048]].to(dev).float(); G += k.T @ k
    return G


Kfit = A_keys[fit_dec].to(dev).float(); Cp = gram(fit_pres); KK = Kfit.T @ Kfit
print(f'grams done {time.time() - t0:.0f}s', flush=True)
_chol = {}


def solve_A(Tk, lam):
    if lam not in _chol:
        M = KK + lam * (Kfit.shape[0] / max(1, len(fit_pres))) * Cp
        M = M + a.mu * M.diagonal().mean() * torch.eye(M.shape[0], device=dev)
        _chol[lam] = torch.linalg.cholesky(M)
    return torch.cholesky_solve((Tk @ Kfit).T, _chol[lam]).T


def sampler_mass(post, ids):
    p = torch.softmax(post, -1); v, ix = torch.topk(p, 64, -1)
    keep = (torch.cumsum(v, -1) - v) < 0.95; v = torch.where(keep, v, torch.zeros_like(v)); v = v / v.sum(-1, keepdim=True)
    return (v * torch.isin(ix, ids)).sum(-1)


LA_T = torch.tensor(LA, device=dev); NXT = torch.tensor([m['logged'] for m in meta], device=dev)


def logits_of(x):
    z = hnorm(x) @ E.T; post = SOFT * torch.tanh(z / SOFT)
    return z, post, torch.log_softmax(post, -1)


def forward_eval(idx, edits, need_base=True):
    """Exact evaluation of the edited model (dW = sum B A) at positions idx; base computed alongside (scalars only kept)."""
    R = {k: [] for k in ('pla_b', 'pla_e', 'pdq_b', 'pdq_e', 'm_b', 'm_e', 'top1_b', 'top1_e', 'dlp', 'kl', 'dz_S')}
    for c in range(0, len(idx), 256):
        ii = torch.tensor(idx[c:c + 256], device=dev)
        x0 = xL[ii]; x1 = x0
        if edits:
            y0 = y[ii]; ky = A_keys[ii.cpu()].to(dev).float(); dy = sum((ky @ Am.T) @ Bm.T for Bm, Am in edits)
            x1 = x0 + s_last * (pf(y0 + dy) - pf(y0))
        z1, post1, lp1 = logits_of(x1)
        R['pla_e'].append(sampler_mass(post1, LA_T)); R['pdq_e'].append(lp1[:, DQ].exp()); R['m_e'].append(lp1[:, DQ] - lp1[:, LA_T].max(-1).values)
        R['top1_e'].append(lp1.argmax(-1)); R['dz_S'].append(z1[:, S])
        if need_base:
            z0, post0, lp0 = logits_of(x0)
            R['pla_b'].append(sampler_mass(post0, LA_T)); R['pdq_b'].append(lp0[:, DQ].exp()); R['m_b'].append(lp0[:, DQ] - lp0[:, LA_T].max(-1).values)
            R['top1_b'].append(lp0.argmax(-1)); nx = NXT[ii][:, None]
            R['dlp'].append(lp1.gather(1, nx)[:, 0] - lp0.gather(1, nx)[:, 0]); R['kl'].append((lp1.exp() * (lp1 - lp0)).sum(-1))
            del z0, post0, lp0
        del z1, post1, lp1
    return {k: torch.cat(v).cpu().numpy() for k, v in R.items() if v}


def compare(idx, ev):
    k = kind[idx]; ar = arg[idx]; out = {}
    se = (k == 'close') & np.isin(ar, ['new', 'old']); sl = k == 'slip'
    pb, pe, mb, me, kl, dln = ev['pla_b'], ev['pla_e'], ev['m_b'], ev['m_e'], ev['kl'], ev['dlp']; t1c = ev['top1_b'] != ev['top1_e']
    out['string_end'] = {'n': int(se.sum()), 'E_slip_base': float(pb[se].mean()), 'E_slip_edit': float(pe[se].mean()),
                         'E_slip_teacher': float(np.nanmean(tpla[idx][se])), 'reduction': float(1 - pe[se].mean() / pb[se].mean()),
                         'margin_median_base': float(np.median(mb[se])), 'margin_median_edit': float(np.median(me[se])),
                         'frac_margin_lt2_base': float((mb[se] < 2).mean()), 'frac_margin_lt2_edit': float((me[se] < 2).mean()),
                         'KL_mean': float(kl[se].mean())}
    # episode-cluster bootstrap: relative reduction and gap closure G = (E_Q - E_R)/(E_Q - E_B)
    eps_ = np.array([meta[i]['episode_id'] for i in idx])[se]; ue, inv = np.unique(eps_, return_inverse=True)
    groups = [np.where(inv == j)[0] for j in range(len(ue))]; rng_ = np.random.default_rng(0)
    pt_ = tpla[idx][se]; pb_, pe_ = pb[se], pe[se]; bs = []
    for _ in range(1000):
        j = np.concatenate([groups[g] for g in rng_.integers(0, len(groups), len(groups))])
        eq, er, eb = pb_[j].mean(), pe_[j].mean(), np.nanmean(pt_[j])
        bs.append((1 - er / eq if eq > 0 else np.nan, (eq - er) / (eq - eb) if eq - eb > 0 else np.nan))
    bs = np.array(bs)
    eq, er, eb = pb_.mean(), pe_.mean(), np.nanmean(pt_)
    out['string_end']['reduction_ci95'] = [float(np.nanpercentile(bs[:, 0], 2.5)), float(np.nanpercentile(bs[:, 0], 97.5))]
    out['string_end']['gap_closure'] = float((eq - er) / (eq - eb)) if eq - eb > 0 else None
    out['string_end']['gap_closure_ci95'] = [float(np.nanpercentile(bs[:, 1], 2.5)), float(np.nanpercentile(bs[:, 1], 97.5))]
    # selection criterion (innercv): mean margin gap closure toward the bf16 teacher where the teacher margin is larger
    mt_ = mB[idx][se]; ok_ = np.isfinite(mt_) & (mt_ > mb[se] + 1e-3)
    out['string_end']['margin_gap_closure_mean'] = float(np.mean((me[se][ok_] - mb[se][ok_]) / (mt_[ok_] - mb[se][ok_]))) if ok_.any() else None
    ok1 = np.isfinite(mt_) & (mt_ > mb[se] + 1.0)          # robust (deviation 13:30): ratio of sums over deficits >= 1 nat
    out['string_end']['margin_gap_closure_ros'] = float((me[se][ok1] - mb[se][ok1]).sum() / (mt_[ok1] - mb[se][ok1]).sum()) if ok1.any() else None
    out['string_end']['n_deficit_ge1'] = int(ok1.sum())
    out['string_end']['margin_median_teacher'] = float(np.nanmedian(mt_))
    out['string_end']['margin_p10_base'] = float(np.percentile(mb[se], 10)); out['string_end']['margin_p10_edit'] = float(np.percentile(me[se], 10))
    out['string_end']['margin_p10_teacher'] = float(np.nanpercentile(mt_, 10))
    out['string_end']['pLA_raw_note'] = 'see E_pop block for the primary endpoint'
    if sl.any():
        out['logged_slips'] = {'n': int(sl.sum()), 'pla_base': float(pb[sl].mean()), 'pla_edit': float(pe[sl].mean()),
                               'pla_teacher': float(np.nanmean(tpla[idx][sl])), 'top1_la_base': float(np.isin(ev['top1_b'][sl], LA).mean()),
                               'top1_la_edit': float(np.isin(ev['top1_e'][sl], LA).mean())}
        # PRIMARY (plan deviation 13:00): population-weighted per-call slip probability E_pop, stratified episode bootstrap
        NV, NS = 4074, 51
        se_items = {}
        for j_, i_ in enumerate(idx):
            if se[j_]:
                se_items.setdefault((meta[i_]['episode_id'], meta[i_]['turn_index']), []).append(j_)
        calls = list(se_items.values())
        def pc(vals, js):
            return 1 - np.prod([1 - vals[j] for j in js])
        tp = tpla[idx]
        Vb = np.array([pc(pb, js) for js in calls]); Ve = np.array([pc(pe, js) for js in calls]); Vt = np.array([pc(tp, js) for js in calls])
        Sb, Se, St = pb[sl], pe[sl], tp[sl]
        epop = lambda v, s_: (NV * v.mean() + NS * s_.mean()) / (NV + NS)
        Eb, Ee, Et = epop(Vb, Sb), epop(Ve, Se), epop(Vt, St)
        ce = np.array([meta[idx[js[0]]]['episode_id'] for js in calls]); cs_ = np.array([meta[i_]['episode_id'] for i_ in idx[sl]])
        gv = [np.where(ce == e)[0] for e in np.unique(ce)]; gs = [np.where(cs_ == e)[0] for e in np.unique(cs_)]
        rng2 = np.random.default_rng(1); bs2 = []
        for _ in range(2000):
            jv = np.concatenate([gv[g] for g in rng2.integers(0, len(gv), len(gv))]); js_ = np.concatenate([gs[g] for g in rng2.integers(0, len(gs), len(gs))])
            b_, e_, t_ = epop(Vb[jv], Sb[js_]), epop(Ve[jv], Se[js_]), epop(Vt[jv], St[js_])
            bs2.append((b_, e_, t_, 1 - e_ / b_ if b_ > 0 else np.nan, (b_ - e_) / (b_ - t_) if b_ - t_ > 0 else np.nan))
        bs2 = np.array(bs2); q = lambda c: [float(np.nanpercentile(bs2[:, c], 2.5)), float(np.nanpercentile(bs2[:, c], 97.5))]
        out['E_pop'] = {'n_valid_calls': len(calls), 'n_slip_states': int(sl.sum()), 'weights': [NV, NS],
                        'qatct': [float(Eb)] + q(0), 'repaired': [float(Ee)] + q(1), 'bf16': [float(Et)] + q(2),
                        'relative_reduction': [float(1 - Ee / Eb)] + q(3), 'gap_closure': [float((Eb - Ee) / (Eb - Et)) if Eb > Et else None] + q(4),
                        'observed_qatct_natural_rate': 51 / 4207}
        # ---- ADDENDUM secondaries (ANALYSIS_PLAN_addendum.md, frozen before any held-out repair number) ----
        npb = np.array([meta[i_]['n_prior_bad'] for i_ in idx])
        clean_call = np.array([npb[js[0]] == 0 for js in calls]); onset_sl = sl & (npb == 0)
        NV0, NS0 = 3866, 14
        eon = lambda v, s_: (NV0 * v.mean() + NS0 * s_.mean()) / (NV0 + NS0)
        Vb0, Ve0, Vt0 = Vb[clean_call], Ve[clean_call], Vt[clean_call]; Sb0, Se0, St0 = pb[onset_sl], pe[onset_sl], tp[onset_sl]
        ce0 = ce[clean_call]; cs0 = np.array([meta[i_]['episode_id'] for i_ in idx[onset_sl]])
        gv0 = [np.where(ce0 == e)[0] for e in np.unique(ce0)]; gs0 = [np.where(cs0 == e)[0] for e in np.unique(cs0)]
        bs3 = []
        for _ in range(2000):
            jv = np.concatenate([gv0[g] for g in rng2.integers(0, len(gv0), len(gv0))]); js_ = np.concatenate([gs0[g] for g in rng2.integers(0, len(gs0), len(gs0))])
            b_, e_, t_ = eon(Vb0[jv], Sb0[js_]), eon(Ve0[jv], Se0[js_]), eon(Vt0[jv], St0[js_])
            bs3.append((b_, e_, t_, 1 - e_ / b_ if b_ > 0 else np.nan, (b_ - e_) / (b_ - t_) if b_ - t_ > 0 else np.nan,
                        Vb[jv].mean() if False else Vb0[jv].mean(), Ve0[jv].mean(), Vt0[jv].mean()))
        bs3 = np.array(bs3); q3 = lambda c: [float(np.nanpercentile(bs3[:, c], 2.5)), float(np.nanpercentile(bs3[:, c], 97.5))]
        Eb0, Ee0, Et0 = eon(Vb0, Sb0), eon(Ve0, Se0), eon(Vt0, St0)
        out['addendum_a_E_onset'] = {'n_valid_clean_calls': int(clean_call.sum()), 'n_onset_slip_states': int(onset_sl.sum()), 'weights': [NV0, NS0],
                                     'qatct': [float(Eb0)] + q3(0), 'repaired': [float(Ee0)] + q3(1), 'bf16': [float(Et0)] + q3(2),
                                     'relative_reduction': [float(1 - Ee0 / Eb0)] + q3(3),
                                     'gap_closure': [float((Eb0 - Ee0) / (Eb0 - Et0)) if Eb0 > Et0 else None] + q3(4),
                                     'onset_slip_states_pLA': {'qatct': float(Sb0.mean()), 'repaired': float(Se0.mean()), 'bf16': float(St0.mean())}}
        TAU = float(np.log(19.0)); mt_se = mB[idx][se]
        out['addendum_b_margins'] = {'R_med': float((np.median(me[se]) - np.median(mb[se])) / (np.nanmedian(mt_se) - np.median(mb[se]))),
                                     'median': {'qatct': float(np.median(mb[se])), 'repaired': float(np.median(me[se])), 'bf16': float(np.nanmedian(mt_se))},
                                     'tau': TAU, 'P_m_lt_tau': {'qatct': float((mb[se] < TAU).mean()), 'repaired': float((me[se] < TAU).mean()), 'bf16': float(np.nanmean(mt_se < TAU))},
                                     'P_m_lt_6': {'qatct': float((mb[se] < 6).mean()), 'repaired': float((me[se] < 6).mean()), 'bf16': float(np.nanmean(mt_se < 6))},
                                     'p10': {'qatct': float(np.percentile(mb[se], 10)), 'repaired': float(np.percentile(me[se], 10)), 'bf16': float(np.nanpercentile(mt_se, 10))}}
        out['addendum_c_per_call_clean'] = {'n_calls': int(clean_call.sum()), 'qatct': [float(Vb0.mean())] + q3(5), 'repaired': [float(Ve0.mean())] + q3(6),
                                            'bf16': [float(Vt0.mean())] + q3(7)}
    for name, mask in (('generic_pnc', np.isin(k, ['generic_completion', 'generic_prompt'])), ('generic_wikitext', k == 'generic_text'),
                       ('generic_wikitext_val', k == 'generic_textval'), ('in_string_lineend', k == 'lineend'),
                       ('postopen', k == 'postopen'), ('nlclose', k == 'nlclose'),
                       ('protected_content', k == 'protected'), ('in_string_content', k == 'content'), ('opener', k == 'opener')):
        if mask.any():
            o = {'n': int(mask.sum()), 'KL_mean': float(kl[mask].mean()), 'KL_p99': float(np.percentile(kl[mask], 99)),
                 'dNLL_mean': float(-dln[mask].mean()), 'top1_changed': float(t1c[mask].mean())}
            if name in ('in_string_content', 'in_string_lineend'):
                o.update(pDQ_mean_base=float(ev['pdq_b'][mask].mean()), pDQ_mean_edit=float(ev['pdq_e'][mask].mean()),
                         new_premature_close_top1=float(((ev['top1_e'][mask] == DQ) & (ev['top1_b'][mask] != DQ)).mean()))
            out[name] = o
    return out


results = []
for tmode, alpha, rho, lam in itertools.product(a.target_modes.split(','), map(float, a.alphas.split(',')), map(float, a.rhos.split(',')), map(float, a.lams.split(','))):
    t1 = time.time()
    if a.output_span == 'la_only':
        Bout = make_Bout_la_only(); dz = targets(alpha, tmode).to(dev)[:, 1:]          # look-alike rows only
    else:
        Bout = make_Bout(rho); dz = targets(alpha, tmode).to(dev)
    edits = [(Bout, solve_A((dz[fit_dec] / kappa[fit_dec, None]).T, lam))]
    for it in range(a.iters):                                   # exact fixed-point refinement on the calibration targets
        fit_ed = forward_eval(fit_dec, edits, need_base=False)
        realised = torch.tensor(fit_ed['dz_S'], device=dev) - zQ[fit_dec].to(dev)
        resid = (dz[fit_dec] - realised) * relevant[fit_dec].to(dev)
        edits.append((Bout, solve_A((resid / kappa[fit_dec, None]).T, lam)))
    if a.fit_only:
        from lora_io import write_peft_adapter
        Bcat = torch.cat([e[0] for e in edits], 1); Acat = torch.cat([e[1] for e in edits], 0)
        write_peft_adapter(a.save_adapter, {'model.layers.59.mlp.down_proj': (Acat.cpu(), Bcat.cpu())},
                           extra={'method': 'closed-form MEMIT-style last-layer down_proj protocol-margin repair', 'target_mode': tmode,
                                  'alpha': alpha, 'rho': rho, 'lam': lam, 'eps': a.eps, 'mu': a.mu, 'p_min': a.p_min, 'tokens': S,
                                  'fit_positions': int(len(fit_dec)), 'preserved_keys': int(len(fit_pres)), 'fit_split': 'calib (all)',
                                  'note': 'fit_only: no evaluation run at save time'})
        print('saved adapter (fit only)', a.save_adapter, flush=True)
        break
    ev = forward_eval(ev_idx, edits)
    summ = compare(ev_idx, ev)
    summ.update(target_mode=tmode, alpha=alpha, rho=rho, lam=lam, iters=a.iters, seconds=round(time.time() - t1))
    G = {}
    if 'E_pop' in summ:
        G['G1_Epop_reduction>=0.5_and_CIlo>0'] = summ['E_pop']['relative_reduction'][0] >= 0.5 and summ['E_pop']['relative_reduction'][1] > 0
    for nm in ('generic_pnc', 'generic_wikitext', 'generic_wikitext_val'):
        if nm in summ:
            G[f'G2_{nm}_dNLL<=0.01'] = summ[nm]['dNLL_mean'] <= 0.01
            G[f'G3_{nm}_KL<=0.01_flip<=1%'] = summ[nm]['KL_mean'] <= 0.01 and summ[nm]['top1_changed'] <= 0.01
    if 'protected_content' in summ:
        pc = summ['protected_content']
        G['G3_protected_KL<=0.01_flip<=1%_dlp>=-0.05'] = pc['KL_mean'] <= 0.01 and pc['top1_changed'] <= 0.01 and -pc['dNLL_mean'] >= -0.05
    if 'in_string_content' in summ:
        G['G3_premature_close<=0.5%'] = summ['in_string_content']['new_premature_close_top1'] <= 0.005
    for nm in ('postopen', 'nlclose'):
        if nm in summ:
            G[f'C_{nm}_top1_changed<=0.5%'] = summ[nm]['top1_changed'] <= 0.005
    if 'in_string_lineend' in summ:
        G['B_lineend_premature_close<=0.5%'] = summ['in_string_lineend']['new_premature_close_top1'] <= 0.005
    summ['offline_gate'] = G; summ['offline_gate_pass'] = all(G.values())
    results.append(summ)
    se = summ['string_end']
    print(f"{tmode} alpha={alpha} rho={rho} lam={lam}: closure_ros {se.get('margin_gap_closure_ros'):.3f} (n {se.get('n_deficit_ge1')}); p10 {se['margin_p10_base']:.2f}->{se['margin_p10_edit']:.2f} (bf16 {se['margin_p10_teacher']:.2f}); bf16 median {se['margin_median_teacher']:.2f}; lt2 {se['frac_margin_lt2_base']:.3f}->{se['frac_margin_lt2_edit']:.3f}; E_slip {se['E_slip_base']:.4f} -> {se['E_slip_edit']:.4f} (teacher {se['E_slip_teacher']:.4f}, "
          f"red {se['reduction']:.2f}); margin {se['margin_median_base']:.2f}->{se['margin_median_edit']:.2f}; "
          + '; '.join(f"{n} KL {o['KL_mean']:.4f} dNLL {o['dNLL_mean']:+.4f} t1chg {o['top1_changed']:.3f}" for n, o in summ.items()
                      if isinstance(o, dict) and 'KL_p99' in o)
          + (f"; premature {summ['in_string_content']['new_premature_close_top1']:.4f}" if 'in_string_content' in summ else ''), flush=True)
    if a.save_adapter and len(results) == 1 and a.dump_pred:
        # exact offline predictions (base and edited) at the first held-out string ends: checked later against vLLM + LoRA
        k_ = kind[ev_idx]; se_idx = ev_idx[(k_ == 'close') & np.isin(arg[ev_idx], ['new', 'old'])][:a.dump_pred]
        preds = []
        for e_ in (False, True):
            for c in range(0, len(se_idx), 64):
                ii = torch.tensor(se_idx[c:c + 64]); x0 = xL[ii.to(dev)]
                if e_:
                    y0 = y[ii.to(dev)]; ky = A_keys[ii].to(dev).float(); dy = sum((ky @ Am.T) @ Bm.T for Bm, Am in edits)
                    x0 = x0 + s_last * (pf(y0 + dy) - pf(y0))
                _, _, lp_ = logits_of(x0)
                tv, ti = torch.topk(lp_, 20, -1)
                for r_, i_ in enumerate(se_idx[c:c + 64]):
                    preds.append({'edited': e_, 'episode_id': meta[i_]['episode_id'], 'turn_index': meta[i_]['turn_index'], 'pos': meta[i_]['pos'],
                                  'top': [[int(t), float(v)] for t, v in zip(ti[r_], tv[r_])], 'lp_DQ': float(lp_[r_, DQ])})
        os.makedirs(a.save_adapter, exist_ok=True); json.dump(preds, open(os.path.join(a.save_adapter, 'offline_predictions.json'), 'w'))
    if a.save_adapter and len(results) == 1:
        from lora_io import write_peft_adapter
        Bcat = torch.cat([e[0] for e in edits], 1); Acat = torch.cat([e[1] for e in edits], 0)
        write_peft_adapter(a.save_adapter, {'model.layers.59.mlp.down_proj': (Acat.cpu(), Bcat.cpu())},
                           extra={'method': 'closed-form MEMIT-style last-layer down_proj protocol-margin repair', 'alpha': alpha, 'rho': rho,
                                  'lam': lam, 'eps': a.eps, 'mu': a.mu, 'p_min': a.p_min, 'iters': a.iters, 'tokens': S,
                                  'fit_positions': int(len(fit_dec)), 'preserved_keys': int(len(fit_pres)), 'eval_split': a.eval_split,
                                  'offline_eval': summ})
json.dump({'args': vars(a), 'results': results}, open(a.out, 'w'), indent=1)
print('wrote', a.out, flush=True)
