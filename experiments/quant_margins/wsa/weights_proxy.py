"""Weights-only protocol proxy (T1): unembedding geometry of <|"|> vs look-alike closers, read from the checkpoint files
(no forward pass). The effective readout of token t from the normalised residual x/rms(x) is r_t = g * e_t (g = final
RMSNorm weight, e_t = tied embedding row). Reported per checkpoint: ||e||, ||r|| of <|"|> and of the look-alikes relative
to the vocabulary median, cos(r_DQ, r_LA) and the readout separation ||r_DQ - r_LA|| / median ||r||, for the 80 look-alikes
and for the 6 most frequent slip closers (` `, " ", ...).
usage: weights_proxy.py --out out/weights_proxy.json  (checkpoint list inside)"""
import json, os, sys, argparse, glob
import torch
from safetensors import safe_open
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pnc_render as R
M = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'models')
CKPTS = {'31b_bf16': f'{M}/gemma-4-31b-it', '31b_qatct': f'{M}/gemma-4-31b-it-qat-w4a16-ct', '31b_qatunq': f'{M}/gemma-4-31b-it-qat-q4_0-unquantized',
         '31b_ptq_q40': f'{M}/gemma-4-31b-it', '12b_qatct': f'{M}/gemma-4-12b-it-qat-w4a16-ct', 'e4b_bf16': f'{M}/gemma-4-e4b-it',
         'e4b_qatct': f'{M}/gemma-4-e4b-it-qat-w4a16-ct', 'e2b_qatct': f'{M}/gemma-4-e2b-it-qat-w4a16-ct'}
ap = argparse.ArgumentParser(); ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'weights_proxy.json'))
a = ap.parse_args()
tok = R.tokenizer(); LA = R.lookalike_ids()
FREQ = [tok.convert_tokens_to_ids(t) for t in ['`,', '`', '",', '"', "',", '\\",']]


def tensor(d, name):
    files = glob.glob(os.path.join(d, '*.safetensors'))
    for f in files:
        with safe_open(f, framework='pt') as h:
            if name in h.keys():
                return h.get_tensor(name)
    raise KeyError(name)


res = {}
torch.manual_seed(0); sample = torch.randint(300, 262144, (20000,))
for name, d in CKPTS.items():
    if not os.path.isdir(d) or not glob.glob(os.path.join(d, '*.safetensors')):
        res[name] = {'missing': True}; continue
    E = tensor(d, 'model.language_model.embed_tokens.weight').float(); g = tensor(d, 'model.language_model.norm.weight').float()
    r = E * g; en = E.norm(dim=1); rn = r.norm(dim=1)
    med_e, med_r = float(en[sample].median()), float(rn[sample].median())
    rdq = r[52]
    def stats(ids):
        ids = torch.tensor(ids)
        cos = torch.nn.functional.cosine_similarity(r[ids], rdq[None], dim=1)
        sep = (r[ids] - rdq[None]).norm(dim=1) / med_r
        return {'cos_mean': float(cos.mean()), 'cos_max': float(cos.max()), 'sep_mean': float(sep.mean()), 'sep_min': float(sep.min()),
                'rnorm_rel_mean': float((rn[ids] / med_r).mean())}
    res[name] = {'dir': d, 'd_model': E.shape[1], 'e_DQ_norm_rel': float(en[52] / med_e), 'r_DQ_norm_rel': float(rn[52] / med_r),
                 'g_norm_rms': float(g.pow(2).mean().sqrt()), 'lookalike80': stats(LA), 'frequent6': stats(FREQ),
                 'note': 'PTQ keeps the bf16 embedding and final norm -> identical proxy to bf16' if name == '31b_ptq_q40' else None}
    print(name, json.dumps({k: v for k, v in res[name].items() if k not in ('dir', 'note')})[:400], flush=True)
    del E, r
json.dump(res, open(a.out, 'w'), indent=1)
