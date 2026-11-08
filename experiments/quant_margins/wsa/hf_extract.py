"""Teacher-forced extraction with HF transformers on ONE GPU (no prompt_logprobs, no server): for every core item one
forward pass over prompt + completion (up to the last needed position), then at the selected predicting positions:
  h      : post-final-norm hidden (fp16)                      x_L   : pre-final-norm residual (decision positions, fp16)
  zS     : PRE-softcap logits of token 52 <|"|> + the 80 look-alike ids (fp32)
  lse    : log-sum-exp of the POST-softcap logits (fp32)      lp_next: log-prob of the logged next token
  top20  : ids / log-probs                                    p_*    : exact sampler probabilities of look-alike / <|"|>
  a_down : last-layer down_proj input (decision positions, fp16)
  resid  : per-layer residual stream x_0..x_60 (D subset = new_string closers + slips, fp16)
Arms: bf16 (models/gemma-4-31b-it); qatct = bf16 skeleton overlaid with EVERY tensor of the -ct checkpoint, packed int4
weights dequantised exactly (q*scale, rounded once to bf16 = what Marlin computes); ptq = bf16 with the 410 -ct-quantised
Linear weights fake-quantised to the llama.cpp Q4_0 grid on the GPU; qatunq / qatfq = Google's QAT-unquantised release
(optionally fake-quantised).
usage: hf_extract.py --arm bf16 --out out/hf_bf16.pt [--limit N] [--items data/core_items.jsonl]"""
import argparse, json, os, sys, time, struct, random, gc
import torch
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import pnc_render as R

M = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'models')
CT = f'{M}/gemma-4-31b-it-qat-w4a16-ct/model.safetensors'
ARMS = {'bf16': dict(base=f'{M}/gemma-4-31b-it'), 'qatct': dict(base=f'{M}/gemma-4-31b-it', overlay=CT),
        'ptq': dict(base=f'{M}/gemma-4-31b-it', fakeq=True), 'qatunq': dict(base=f'{M}/gemma-4-31b-it-qat-q4_0-unquantized'),
        'qatfq': dict(base=f'{M}/gemma-4-31b-it-qat-q4_0-unquantized', fakeq=True)}
ap = argparse.ArgumentParser()
ap.add_argument('--arm', required=True, choices=sorted(ARMS)); ap.add_argument('--out', required=True)
ap.add_argument('--items', default=os.path.join(H, 'data', 'core_items.jsonl')); ap.add_argument('--limit', type=int, default=0)
ap.add_argument('--n_generic', type=int, default=12); ap.add_argument('--no_resid', action='store_true')
ap.add_argument('--wikitext_only', action='store_true', help='only the 48 wikitext-2 windows (generic-text side-effect set)')
ap.add_argument('--wikitext_split', default='test', choices=['test', 'validation'])
ap.add_argument('--lineend_only', action='store_true', help='only in-string line-end content positions (premature-close hard negatives), cap 24/item')
ap.add_argument('--cneg_only', action='store_true', help='candidate C hard negatives: postopen (first content token after an opener) and nlclose (newline before a closer)')
a = ap.parse_args()
if a.arm == 'ptq' and os.path.exists(os.path.join(H, 'SKIP_PTQ')):
    print('PTQ arm deferred (SKIP_PTQ present)', flush=True); sys.exit(0)
dev = 'cuda:0'
torch.backends.cuda.matmul.allow_tf32 = False


def ct_header():
    with open(CT, 'rb') as f:
        n = struct.unpack('<Q', f.read(8))[0]; return json.loads(f.read(n))


def fake_q4_0_(w):
    o, i = w.shape
    x = w.float().reshape(o, i // 32, 32)
    mx = torch.gather(x, -1, x.abs().argmax(-1, keepdim=True)); d = mx / -8.0
    idv = torch.where(d != 0, 1.0 / d, torch.zeros_like(d))
    q = torch.clamp(torch.floor(x * idv + 0.5), -8, 7)
    w.copy_((q * d.half().float()).reshape(o, i).to(w.dtype))


def load():
    from transformers import Gemma4ForConditionalGeneration
    cfg = ARMS[a.arm]
    model = Gemma4ForConditionalGeneration.from_pretrained(cfg['base'], dtype=torch.bfloat16, device_map=dev, attn_implementation='sdpa')
    model.eval()
    sd = model.state_dict()
    hdr = ct_header(); qmods = sorted(k[:-len('.weight_packed')] for k in hdr if k.endswith('.weight_packed'))
    info = {'arm': a.arm, 'base': cfg['base']}
    if cfg.get('overlay'):
        from safetensors import safe_open
        from compressed_tensors.compressors.pack_quantized.helpers import unpack_from_int32
        n_t = n_q = 0; missing = []
        with safe_open(cfg['overlay'], framework='pt', device=dev) as f:
            for k in f.keys():
                if k.endswith('.weight_scale') or k.endswith('.weight_shape'):
                    continue
                if k.endswith('.weight_packed'):
                    tk = k[:-len('_packed')]
                    shape = tuple(int(v) for v in f.get_tensor(k[:-len('packed')] + 'shape').tolist())
                    q = unpack_from_int32(f.get_tensor(k), 4, torch.Size(shape)).float()
                    s = f.get_tensor(k[:-len('packed')] + 'scale').float()
                    w = (q.reshape(shape[0], -1, 32) * s.reshape(shape[0], -1, 1)).reshape(shape)
                    if tk not in sd:
                        missing.append(tk); continue
                    sd[tk].copy_(w.to(sd[tk].dtype)); n_q += 1
                else:
                    if k not in sd:
                        missing.append(k); continue
                    t = f.get_tensor(k)
                    if sd[k].shape != t.shape:
                        missing.append(k + ' shape'); continue
                    sd[k].copy_(t.to(sd[k].dtype)); n_t += 1
        info.update(overlay=cfg['overlay'], overlaid_quantized=n_q, overlaid_other=n_t, overlay_missing=missing[:20])
        assert n_q == len(qmods), (n_q, len(qmods))
    if cfg.get('fakeq'):
        n = 0
        for mname in qmods:
            fake_q4_0_(sd[mname + '.weight']); n += 1
        info.update(fake_quantized=n)
    torch.cuda.empty_cache()
    return model, info


model, INFO = load()
tm = model.model.language_model
E = tm.embed_tokens.weight                       # tied unembedding (vocab x hidden), raw (no embed_scale)
SOFT = float(model.config.text_config.final_logit_softcapping)
LA = R.lookalike_ids(); SIDS = torch.tensor([R.DQ] + LA, device=dev)
tok = R.tokenizer()
SPECIAL = set(tok.all_special_ids) | {i for i in range(0, 260)} | {R.DQ}
print('loaded', INFO, 'softcap', SOFT, 'n_lookalike', len(LA), flush=True)

cap = {}


def hook_pre_norm(mod, inp):
    cap['xL'] = inp[0][0, cap['sel']].detach().float()


def hook_norm(mod, inp, out):
    cap['h'] = out[0, cap['sel']].detach().float()


def hook_down(mod, inp):
    cap['a'] = inp[0][0, cap['sel']].detach().to(torch.bfloat16)


def hook_down_out(mod, inp, out):
    cap['y'] = out[0, cap['sel']].detach().float()


def mk_layer_hook(i):
    def f(mod, inp, out):
        o = out[0] if isinstance(out, tuple) else out
        if cap.get('sel_res') is not None and len(cap['sel_res']):
            cap['res'][i + 1] = o[0, cap['sel_res']].detach().to(torch.bfloat16)
    return f


def emb_hook(mod, inp, out):
    if cap.get('sel_res') is not None and len(cap['sel_res']):
        cap['res'][0] = out[0, cap['sel_res']].detach().to(torch.bfloat16)


tm.norm.register_forward_pre_hook(hook_pre_norm)
tm.norm.register_forward_hook(hook_norm)
tm.layers[-1].mlp.down_proj.register_forward_pre_hook(hook_down)
tm.layers[-1].mlp.down_proj.register_forward_hook(hook_down_out)
if not a.no_resid:
    tm.embed_tokens.register_forward_hook(emb_hook)
    for i, L in enumerate(tm.layers):
        L.register_forward_hook(mk_layer_hook(i))


def sampler_mass(post, T, ids_list):
    """exact top-k 64 / top-p 0.95 sampler at temperature T; returns mass on each id set in ids_list and the kept-count."""
    p = torch.softmax(post / T, -1)
    v, ix = torch.topk(p, 64, dim=-1)
    keep = (torch.cumsum(v, -1) - v) < 0.95
    v = torch.where(keep, v, torch.zeros_like(v)); v = v / v.sum(-1, keepdim=True)
    outs = []
    for ids in ids_list:
        m = torch.isin(ix, ids)
        outs.append((v * m).sum(-1))
    return outs


def turn_record(eid, ti):
    with open(os.path.join(R.PNC, 'episodes', eid + '.jsonl')) as f:
        for l in f:
            t = json.loads(l)
            if t.get('record_type') == 'turn' and t['turn_index'] == ti:
                return t


if a.arm == 'qatct' and a.items == os.path.join(H, 'data', 'core_items.jsonl') and os.path.exists(os.path.join(H, 'data', 'core_items_qat.jsonl')):
    a.items = os.path.join(H, 'data', 'core_items_qat.jsonl')   # time budget: QAT-ct on 651 items (all slips + 300 calib + 300 held-out)
if a.arm == 'ptq' and a.items == os.path.join(H, 'data', 'core_items.jsonl') and os.path.exists(os.path.join(H, 'data', 'core_items_half.jsonl')):
    a.items = os.path.join(H, 'data', 'core_items_half.jsonl')   # time budget: PTQ arm on the 501-item half set (all slips + 225/225)
items = [json.loads(l) for l in open(a.items)]
if a.limit:
    items = items[:a.limit]
# generic non-agent text: 48 wikitext-2 (test) windows of 1,024 tokens, 32 random positions each; split by window parity
import pyarrow.parquet as pq
_wt = pq.read_table(os.path.join(H, 'data', 'generic', 'wikitext', 'wikitext-2-raw-v1', f'{a.wikitext_split}-00000-of-00001.parquet')).column('text').to_pylist()
_ids = R.encode(''.join(_wt))
if a.wikitext_only:
    items = []
for w in (range(0) if (a.lineend_only or a.cneg_only) else range(48)):           # every window starts with <bos> (id 2), as Gemma requires
    items.append({'text_ids': [2] + _ids[w * 1023: (w + 1) * 1023], 'episode_id': f'wikitext2_{a.wikitext_split}_w{w}', 'turn_index': -1,
                  'split': 'calib' if w % 2 == 0 else 'heldout', 'kind': 'generic_text', 'n_prior_bad': 0, 'schema': 'text', 'gen_seed': 1000 + w})
DQ_T = torch.tensor([R.DQ], device=dev); LA_T = torch.tensor(LA, device=dev)
out = {k: [] for k in ('meta', 'h', 'xL', 'a_down', 'y_down', 'zS', 'lse', 'lse_rest', 'lp_next', 'top_ids', 'top_lp', 'pLA_T1', 'pDQ_T1', 'pLA_T07',
                       'pLA_T02', 'pLA_raw', 'greedy', 'resid', 'resid_idx')}
t0 = time.time(); n_fail = 0
def save(partial):
    res = {'info': INFO, 'lookalike_ids': LA, 'softcap': SOFT, 'meta': list(out['meta']), 'n_fail': n_fail, 'partial': partial,
           'g_final': tm.norm.weight.detach().float().cpu(), 'g_postff_last': tm.layers[-1].post_feedforward_layernorm.weight.detach().float().cpu(),
           'layer_scalar_last': float(tm.layers[-1].layer_scalar.float().item()),
           'layer_scalars': [float(L.layer_scalar.float().item()) for L in tm.layers]}
    for k in ('h', 'zS', 'lse', 'lse_rest', 'lp_next', 'top_ids', 'top_lp', 'pLA_T1', 'pDQ_T1', 'pLA_T07', 'pLA_T02', 'pLA_raw', 'greedy', 'xL', 'a_down', 'y_down'):
        res[k] = torch.cat(out[k]) if out[k] else None
    res['dec_idx'] = [i for i, m in enumerate(res['meta']) if m['kind'] in ('close', 'slip', 'protected')]
    if out['resid']:
        res['resid'] = torch.cat(out['resid']); res['resid_idx'] = list(out['resid_idx'])
    torch.save(res, a.out + '.tmp'); os.replace(a.out + '.tmp', a.out)



for n_it, it in enumerate(items):
    try:
        rng = random.Random(it['gen_seed'])
        if 'text_ids' in it:                                                           # generic (non-agent) text: wikitext-2 test
            pids = it['text_ids']; cids = []; P = len(pids)
            poss = [{'pos': j - P, 'kind': 'generic_text' if a.wikitext_split == 'test' else 'generic_textval', 'logged': pids[j]} for j in rng.sample(range(16, P), 32)]
        else:
            t = turn_record(it['episode_id'], it['turn_index'])
            pids = R.encode(R.render(t['request']['messages'], it['schema']))
            if len(pids) != it['prompt_tokens']:
                n_fail += 1; print('prompt mismatch', it['episode_id'], it['turn_index'], len(pids), it['prompt_tokens'], flush=True); continue
            cids = R.encode(t['raw_completion'])
            P = len(pids)
            poss = [dict(p) for p in it['positions']]
            call_start = min([p['pos'] for p in poss] + [len(cids)])
            call_tok = next((k for k, x in enumerate(cids) if x == 48), call_start)     # 48 = <|tool_call>
            gen_c = [k for k in range(1, call_tok) if cids[k] not in SPECIAL]
            gen_p = [j for j in range(64, P) if pids[j] not in SPECIAL]
            for k in rng.sample(gen_c, min(a.n_generic, len(gen_c))):
                poss.append({'pos': k, 'kind': 'generic_completion', 'logged': cids[k]})
            for j in rng.sample(gen_p, min(a.n_generic, len(gen_p))):
                poss.append({'pos': j - P, 'kind': 'generic_prompt', 'logged': pids[j]})   # negative = prompt position
            if a.cneg_only:
                NL = {i_ for i_ in set(cids) if tok.decode([i_]).endswith('\n')}
                poss = []
                for p in [q for q in it['positions'] if q['kind'] == 'close' and q.get('arg') in ('new', 'old')]:
                    op = max([k for k in range(p['pos']) if cids[k] == R.DQ], default=None)
                    if op is None or op + 1 >= p['pos']:
                        continue
                    poss.append({'pos': op + 1, 'kind': 'postopen', 'arg': p['arg'], 'logged': cids[op + 1]})
                    if cids[p['pos'] - 1] in NL and p['pos'] - 1 > op + 1:
                        poss.append({'pos': p['pos'] - 1, 'kind': 'nlclose', 'arg': p['arg'], 'logged': cids[p['pos'] - 1]})
                if not poss:
                    continue
            if a.lineend_only:
                NL = {i_ for i_ in set(cids) if tok.decode([i_]).endswith('\n')}
                poss = []
                for p in [q for q in it['positions'] if q['kind'] == 'close' and q.get('arg') in ('new', 'old')]:
                    op = max([k for k in range(p['pos']) if cids[k] == R.DQ], default=None)
                    if op is None:
                        continue
                    cand = [k for k in range(op + 2, p['pos']) if cids[k - 1] in NL and cids[k] != R.DQ]
                    for k in rng.sample(cand, min(12, len(cand))):
                        poss.append({'pos': k, 'kind': 'lineend', 'arg': p['arg'], 'logged': cids[k]})
                if not poss:
                    continue
            # in-string CONTENT positions (must stay content: premature-close guard) and string OPENER positions
            prot = {p['pos'] for p in poss if p['kind'] == 'protected'}
            for p in ([] if (a.lineend_only or a.cneg_only) else [q for q in it['positions'] if q['kind'] == 'close' and q.get('arg') in ('new', 'old')]):
                op = max([k for k in range(p['pos']) if cids[k] == R.DQ], default=None)
                if op is None:
                    continue
                cand = [k for k in range(op + 1, p['pos']) if k not in prot and cids[k] != R.DQ]
                for k in rng.sample(cand, min(4, len(cand))):
                    poss.append({'pos': k, 'kind': 'content', 'arg': p['arg'], 'logged': cids[k]})
                poss.append({'pos': op, 'kind': 'opener', 'arg': p['arg'], 'logged': R.DQ})
        max_pos = max(p['pos'] for p in poss)
        seq = pids + cids[:max(max_pos, 0)]
        sel = [P + p['pos'] - 1 for p in poss]                                         # predicting index for each position
        is_dec = [p['kind'] in ('close', 'slip', 'protected') for p in poss]
        is_res = [(p['kind'] == 'slip') or (p['kind'] == 'close' and p.get('arg') == 'new') for p in poss]
        cap.clear()
        cap['sel'] = torch.tensor(sel, device=dev)
        cap['sel_dec'] = torch.tensor([s for s, d in zip(sel, is_dec) if d], device=dev, dtype=torch.long)
        cap['sel_res'] = torch.tensor([s for s, r in zip(sel, is_res) if r], device=dev, dtype=torch.long) if not a.no_resid else None
        cap['res'] = {}
        ids_t = torch.tensor([seq], device=dev)
        with torch.inference_mode():
            tm(input_ids=ids_t, use_cache=False)
            h = cap['h']                                                               # (n, hidden) fp32
            try:
                z = torch.cat([h @ E[c:c + 32768].float().T for c in range(0, E.shape[0], 32768)], 1)   # pre-softcap logits (fp32)
            except RuntimeError as e_:                      # cuBLAS fp32 handle failure seen on one GPU: fall back to bf16 GEMM
                if 'CUBLAS' not in str(e_):
                    raise
                INFO['logits_bf16_fallback'] = True
                z = torch.cat([(h.to(torch.bfloat16) @ E[c:c + 32768].T).float() for c in range(0, E.shape[0], 32768)], 1)
            post = SOFT * torch.tanh(z / SOFT)
            lse = torch.logsumexp(post, -1)
            lse_rest = torch.logsumexp(post.index_fill(1, SIDS, float('-inf')), -1)
            lp = post - lse[:, None]
            nxt = torch.tensor([p['logged'] for p in poss], device=dev)
            lp_next = lp.gather(1, nxt[:, None])[:, 0]
            tl, ti_ = torch.topk(lp, 20, -1)
            pla1, pdq1 = sampler_mass(post, 1.0, [LA_T, DQ_T]); pla07, = sampler_mass(post, 0.7, [LA_T]); pla02, = sampler_mass(post, 0.2, [LA_T])
            pla_raw = torch.exp(lp[:, LA_T]).sum(-1)
        for k_, p in enumerate(poss):
            out['meta'].append({'item': n_it, 'episode_id': it['episode_id'], 'turn_index': it['turn_index'], 'split': it['split'],
                                'item_kind': it['kind'], 'n_prior_bad': it['n_prior_bad'], 'schema': it['schema'], **p})
        out['h'].append(h.to(torch.float16).cpu()); out['zS'].append(z[:, SIDS].cpu()); out['lse'].append(lse.cpu()); out['lse_rest'].append(lse_rest.cpu())
        out['lp_next'].append(lp_next.cpu()); out['top_ids'].append(ti_.int().cpu()); out['top_lp'].append(tl.cpu())
        out['pLA_T1'].append(pla1.cpu()); out['pDQ_T1'].append(pdq1.cpu()); out['pLA_T07'].append(pla07.cpu()); out['pLA_T02'].append(pla02.cpu())
        out['pLA_raw'].append(pla_raw.cpu()); out['greedy'].append(ti_[:, 0].int().cpu())
        out['xL'].append(cap['xL'].cpu()); out['a_down'].append(cap['a'].cpu()); out['y_down'].append(cap['y'].cpu())
        if not a.no_resid and len(cap['sel_res']):
            out['resid'].append(torch.stack([cap['res'][i] for i in range(len(tm.layers) + 1)], 1).cpu())   # (n_res, 61, hidden)
            out['resid_idx'] += [len(out['meta']) - len(poss) + k_ for k_, r in enumerate(is_res) if r]
        del z, post, lp
    except torch.cuda.OutOfMemoryError:
        n_fail += 1; print('OOM', it['episode_id'], it['turn_index'], len(seq), flush=True); cap.clear(); gc.collect(); torch.cuda.empty_cache()
    if (n_it + 1) % 150 == 0:
        save(True)
    if (n_it + 1) % 25 == 0:
        el = time.time() - t0
        print(f'{n_it + 1}/{len(items)} items, {len(out["meta"])} positions, {el:.0f}s ({el / (n_it + 1):.2f}s/item), fails {n_fail}, '
              f'max mem {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB', flush=True)
save(False)
print('saved', a.out, len(out['meta']), 'positions', f'{time.time() - t0:.0f}s', flush=True)
