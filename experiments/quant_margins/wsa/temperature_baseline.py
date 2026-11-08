"""Is the quantization defect temperature-like? Exact offline check from the HF extractions: scale the PRE-softcap logits of
the quantized model globally (z -> c z, equivalent to scaling the final RMSNorm weight g, or to a sampling temperature
before the softcap) and report, per c: held-out string-end E_slip (shipped sampler), median margin, generic PNC / wikitext
NLL. A global c that restores bf16-level margins without hurting NLL would mean "dilution" (D's hypothesis); a gap that
only closes at large NLL cost means the defect is delimiter-specific.
usage: temperature_baseline.py --arm qatct --ref bf16 --out out/temperature_baseline.json"""
import argparse, json, os, sys
import numpy as np, torch
H = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument('--arm', default='qatct'); ap.add_argument('--ref', default='bf16')
ap.add_argument('--embed', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
ap.add_argument('--cs', default='0.8,0.9,1.0,1.1,1.2,1.3,1.5,1.7,2.0'); ap.add_argument('--split', default='heldout')
ap.add_argument('--out', default=os.path.join(H, 'out', 'temperature_baseline.json')); ap.add_argument('--threads', type=int, default=9)
a = ap.parse_args()
torch.set_num_threads(a.threads)
sys.path.insert(0, H)
import importlib.util
spec = importlib.util.spec_from_file_location('rm_embed', os.path.join(H, 'repair_memit.py'))
from safetensors import safe_open
import glob


def load_embed(path):
    for f_ in sorted(glob.glob(os.path.join(path, '*.safetensors'))):
        with safe_open(f_, framework='pt') as f:
            if 'model.language_model.embed_tokens.weight' in f.keys():
                return f.get_tensor('model.language_model.embed_tokens.weight').float()


d = torch.load(os.path.join(H, 'out', f'hf_{a.arm}.pt'), weights_only=False)
E = load_embed(a.embed); g = d['g_final'].float(); LA = torch.tensor(d['lookalike_ids']); SOFT = 30.0
meta = d['meta']; xL = d['xL'].float()
kind = np.array([m['kind'] for m in meta]); split = np.array([m['split'] for m in meta]); arg = np.array([str(m.get('arg')) for m in meta])
se = np.where((kind == 'close') & np.isin(arg, ['new', 'old']) & (split == a.split))[0]
gp = np.where(np.isin(kind, ['generic_completion', 'generic_prompt']) & (split == a.split))[0]
gw = np.where((kind == 'generic_text') & (split == a.split))[0]
nxt = torch.tensor([m['logged'] for m in meta])


def zof(idx):
    x = xL[idx]; h = x / x.pow(2).mean(-1, keepdim=True).add(1e-6).sqrt() * g
    return h @ E.T


def sampler_mass(post):
    p = torch.softmax(post, -1); v, ix = torch.topk(p, 64, -1)
    keep = (torch.cumsum(v, -1) - v) < 0.95; v = torch.where(keep, v, torch.zeros_like(v)); v = v / v.sum(-1, keepdim=True)
    return (v * torch.isin(ix, LA)).sum(-1)


cs = [float(c) for c in a.cs.split(',')]
acc = {c: {'pla': [], 'm': [], 'nll_pnc': [], 'nll_wiki': []} for c in cs}
for name, idx in (('se', se), ('gp', gp), ('gw', gw)):
    for ch in range(0, len(idx), 256):
        ii = torch.tensor(idx[ch:ch + 256]); z = zof(ii)
        for c in cs:
            post = SOFT * torch.tanh(c * z / SOFT); lp = torch.log_softmax(post, -1)
            if name == 'se':
                acc[c]['pla'].append(sampler_mass(post)); acc[c]['m'].append(lp[:, 52] - lp[:, LA].max(-1).values)
            else:
                acc[c]['nll_pnc' if name == 'gp' else 'nll_wiki'].append(-lp.gather(1, nxt[ii][:, None])[:, 0])
res = {'arm': a.arm, 'split': a.split, 'n_string_end': int(len(se)), 'n_generic_pnc': int(len(gp)), 'n_wikitext': int(len(gw)), 'by_c': {}}
for c in cs:
    o = acc[c]
    res['by_c'][str(c)] = {'E_slip': float(torch.cat(o['pla']).mean()), 'margin_median': float(torch.cat(o['m']).median()),
                           'NLL_pnc': float(torch.cat(o['nll_pnc']).mean()) if o['nll_pnc'] else None,
                           'NLL_wikitext': float(torch.cat(o['nll_wiki']).mean()) if o['nll_wiki'] else None}
    print(c, res['by_c'][str(c)], flush=True)
json.dump(res, open(a.out, 'w'), indent=1)
