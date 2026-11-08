"""T3 candidate (a), evaluated exactly offline: give the quantized model the bf16 UNEMBEDDING rows of the structural and
look-alike tokens (S = <|"|> + 80 look-alikes; optionally a scaled blend). Only the S logits change:
   z'_S = E_bf16[S] . h_QAT  (pre-softcap);  log p' from lse_rest (unchanged) and the new S logits.
NOTE: not servable as a vLLM LoRA (lm_head LoRA unsupported for vocab 262,144); this is a diagnostic for the margin
decomposition (unembedding term) and for the PI's candidate list.
usage: candidate_a.py --split heldout --out out/candidate_a.json"""
import argparse, json, os, glob
import numpy as np, torch
from safetensors import safe_open
H = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument('--split', default='heldout'); ap.add_argument('--out', default=os.path.join(H, 'out', 'candidate_a.json'))
a = ap.parse_args()
SOFT = 30.0


def emb(d):
    for f_ in sorted(glob.glob(os.path.join(d, '*.safetensors'))):
        with safe_open(f_, framework='pt') as f:
            if 'model.language_model.embed_tokens.weight' in f.keys():
                return f.get_tensor('model.language_model.embed_tokens.weight').float()


Q = torch.load(os.path.join(H, 'out', 'hf_qatct.pt'), weights_only=False)
LA = Q['lookalike_ids']; S = torch.tensor([52] + LA)
EQ = emb(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))[S]; EB = emb(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it'))[S]
meta = Q['meta']; kind = np.array([m['kind'] for m in meta]); split = np.array([m['split'] for m in meta]); arg = np.array([str(m.get('arg')) for m in meta])
g = Q['g_final'].float(); xL = Q['xL'].float()
h = xL / xL.pow(2).mean(-1, keepdim=True).add(1e-6).sqrt() * g
lr = Q['lse_rest'].float()
res = {}
for name, mask in (('string_end', (kind == 'close') & np.isin(arg, ['new', 'old'])), ('logged_slips', kind == 'slip'),
                   ('generic_pnc', np.isin(kind, ['generic_completion', 'generic_prompt'])), ('generic_wikitext', kind == 'generic_text'),
                   ('protected_content', kind == 'protected'), ('in_string_content', kind == 'content'), ('opener', kind == 'opener')):
    idx = np.where(mask & (split == a.split))[0]
    if not len(idx):
        continue
    ii = torch.tensor(idx); hh = h[ii]
    out = {'n': int(len(idx))}
    for blend in (0.0, 0.5, 1.0):
        Es = (1 - blend) * EQ + blend * EB
        post = SOFT * torch.tanh((hh @ Es.T) / SOFT)
        lse = torch.logaddexp(lr[ii], torch.logsumexp(post, 1)); lp = post - lse[:, None]
        p_la = lp[:, 1:].exp().sum(1)                    # raw (untruncated) look-alike mass at T=1
        m = lp[:, 0] - lp[:, 1:].max(1).values
        out[f'blend{blend}'] = {'pLA_raw_mean': float(p_la.mean()), 'margin_median': float(m.median()), 'lp_DQ_mean': float(lp[:, 0].mean())}
    res[name] = out
json.dump(res, open(a.out, 'w'), indent=1)
print(json.dumps(res, indent=1)[:3000])
