"""Endpoint audit of string-end protocol fidelity (slipguard audit-weights). Path-free: every path is an argument.

audit_endpoint(base_url, served_name, *, pnc_dir, tokenizer_dir, pack, split='heldout', kinds=('close', 'slip'),
               conc=2, max_total=None, records_out=None) -> list of per-position records
Each record: episode_id, turn_index, split, kind, arg, pos, logged, top (top-20 [id, logprob]), pLA_T1 (shipped sampler
T=1 / top-k 64 / top-p 0.95 rebuilt from the top-20), margin (log P(<|"|>) - log P(best look-alike); inf if no look-alike in
the top-20), margin_censored, top1, n_prompt.
Method: generation-mode teacher forcing (prompt = rendered PNC prompt + logged completion tokens up to the decision;
max_tokens=1, temperature 0, logprobs=20, token-id prompts). No prompt_logprobs. Keep conc low (1 for servers whose KV
cache holds about one 17k context) so prefixes stay cached."""
import asyncio, gzip, json, math, os
import numpy as np

DQ = 52


def sampler_from_top(top, T=1.0, top_k=64, top_p=0.95):
    lps = np.array([v for _, v in top[:top_k]], float) / T
    lps -= lps.max(); p = np.exp(lps); p /= p.sum()
    keep = (np.cumsum(p) - p) < top_p
    q = np.where(keep, p, 0.0); q /= q.sum()
    return {int(t): float(x) for (t, _), x in zip(top[:top_k], q) if x > 0}


def position_metrics(top, la):
    d = dict((int(t), float(v)) for t, v in top)
    q = sampler_from_top(top)
    las = [v for t, v in d.items() if t in la]
    return {'pLA_T1': sum(v for t, v in q.items() if t in la), 'pDQ_T1': q.get(DQ, 0.0),
            'margin': (d.get(DQ, min(d.values())) - max(las)) if las else float('inf'),
            'margin_censored': (DQ not in d) or not las, 'top1': int(max(d, key=d.get))}


def load_pack(pack, split):
    op = gzip.open if pack.endswith('.gz') else open
    with op(pack, 'rt') as f:
        items = [json.loads(l) for l in f]
    return [it for it in items if split in ('all', it['split'])]


async def _probe(client, base, model, ids):
    body = {'model': model, 'prompt': ids, 'max_tokens': 1, 'temperature': 0, 'logprobs': 20, 'return_tokens_as_token_ids': True}
    for t in range(6):
        try:
            r = await client.post(base + '/completions', json=body, timeout=1800)
            if r.status_code == 200:
                j = r.json(); tl = j['choices'][0]['logprobs']['top_logprobs'][0]
                return [(int(k.split(':')[1]), v) for k, v in tl.items()], j['usage']['prompt_tokens']
            if r.status_code == 400:
                raise RuntimeError(r.text[:300])
        except RuntimeError:
            raise
        except Exception:
            pass
        await asyncio.sleep(3 * (t + 1))
    raise RuntimeError('request failed')


def audit_endpoint(base_url, served_name, *, pnc_dir, tokenizer_dir, pack, split='heldout', kinds=('close', 'slip'), conc=2,
                   max_total=None, records_out=None):
    import httpx
    from .render import PNCRenderer
    R = PNCRenderer(pnc_dir, tokenizer_dir); la = set(R.lookalike_ids())
    items = load_pack(pack, split); recs = []
    fo = open(records_out, 'w') if records_out else None

    async def run():
        sem = asyncio.Semaphore(conc)
        async with httpx.AsyncClient(limits=httpx.Limits(max_connections=conc + 4)) as client:
            async def one(n, it):
                poss = [p for p in it['positions'] if p['kind'] in kinds]
                if not poss:
                    return
                t = R.turn(it['episode_id'], it['turn_index'])
                pids = R.encode(R.render(t['request']['messages'], it['schema'])); cids = R.encode(t['raw_completion'])
                if len(pids) != it['prompt_tokens']:
                    return
                async with sem:
                    for p in sorted(poss, key=lambda x: x['pos']):
                        ids = pids + cids[:p['pos']]
                        if max_total and len(ids) + 1 > max_total:
                            continue
                        top, npt = await _probe(client, base_url, served_name, ids)
                        rec = {'episode_id': it['episode_id'], 'turn_index': it['turn_index'], 'item': n, 'split': it['split'],
                               'n_prior_bad': it['n_prior_bad'], 'kind': p['kind'], 'arg': p.get('arg'), 'pos': p['pos'],
                               'logged': p['logged'], 'top': top, 'n_prompt': npt, **position_metrics(top, la)}
                        recs.append(rec)
                        if fo:
                            fo.write(json.dumps(rec) + '\n'); fo.flush()
            await asyncio.gather(*[one(n, it) for n, it in enumerate(items)])
    asyncio.run(run())
    if fo:
        fo.close()
    return recs
