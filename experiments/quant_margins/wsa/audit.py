"""slipguard weight audit (T1): protocol-fidelity score of ANY Gemma-4 checkpoint behind an OpenAI-compatible endpoint
that returns logprobs (vLLM /v1/completions), measured on fixed string-end decision points from the PUBLIC PNC corpus.

Library API
    audit_checkpoint(base_url, model, split='heldout', items=CORE, kinds=('close', 'slip'), conc=8, max_total=None,
                     out_jsonl=None) -> dict      # summary; per-position records optionally written to out_jsonl
    score_records(records) -> dict                # summary from per-position records (used for endpoint and HF records)

Method: teacher forcing in GENERATION mode (prompt = rendered PNC prompt + logged completion tokens up to the decision;
max_tokens=1, temperature=0, logprobs=20, token-id prompts; no prompt_logprobs). The shipped Gemma-4 sampler
(T=1, top-k 64, top-p 0.95) is rebuilt from the top-20 (exact whenever the nucleus lies inside the top-20; the
remaining mass is reported). Scores:
  * E_slip   : mean sampler probability of a look-alike closer at valid new/old string-end closers ("expected slip
               probability per string end"), with an episode-cluster bootstrap CI;
  * per-call : P(at least one of the call's new/old closers slips) = 1 - prod(1 - p);
  * margins  : log P(<|"|>) - log P(best look-alike) quantiles; share of closers with margin < 2 / < 4 nats.
CLI: python audit.py --base http://127.0.0.1:8303/v1 --model gemma-4-31b --out out/audit_<name>.json"""
import argparse, asyncio, json, math, os, sys, time, hashlib
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import pnc_render as R

CORE = os.path.join(H, 'data', 'core_items.jsonl')


def _turn(eid, ti):
    with open(os.path.join(R.PNC, 'episodes', eid + '.jsonl')) as f:
        for l in f:
            t = json.loads(l)
            if t.get('record_type') == 'turn' and t['turn_index'] == ti:
                return t


def sampler_from_top(top, T=1.0, top_k=64, top_p=0.95):
    lps = np.array([v for _, v in top[:top_k]], float) / T
    lps -= lps.max(); p = np.exp(lps); p /= p.sum()
    keep = (np.cumsum(p) - p) < top_p
    q = np.where(keep, p, 0.0); q /= q.sum()
    return {int(t): float(x) for (t, _), x in zip(top[:top_k], q) if x > 0}


def position_metrics(top, la, dq=R.DQ):
    d = dict((int(t), float(v)) for t, v in top)
    lp20 = min(d.values())
    q = sampler_from_top(top)
    las = [v for t, v in d.items() if t in la]
    return {'pLA_T1': sum(v for t, v in q.items() if t in la), 'pDQ_T1': q.get(dq, 0.0),
            'margin': (d.get(dq, lp20) - max(las)) if las else float('inf'), 'margin_censored': (dq not in d) or not las,
            'top1': int(max(d, key=d.get)), 'resid_mass': max(0.0, 1 - sum(math.exp(v) for v in d.values()))}


def score_records(recs, boot=2000, seed=0):
    """recs: dicts with keys kind, arg, episode_id, item, pLA_T1, margin (+ optional). Returns the summary."""
    rng = np.random.default_rng(seed)
    out = {}
    cl = [r for r in recs if r['kind'] == 'close' and r.get('arg') in ('new', 'old')]
    if cl:
        eps = sorted({r['episode_id'] for r in cl}); idx = {e: i for i, e in enumerate(eps)}
        p = np.array([r['pLA_T1'] for r in cl]); g = np.array([idx[r['episode_id']] for r in cl])
        groups = [np.where(g == i)[0] for i in range(len(eps))]
        bs = [p[np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])].mean() for _ in range(boot)]
        m = np.array([min(r['margin'], 99.0) for r in cl])
        out['string_end_closers'] = {
            'n_positions': len(cl), 'n_episodes': len(eps),
            'E_slip_T1': [float(p.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
            'margin_quantiles_10_25_50_75_90': [float(np.percentile(m, q)) for q in (10, 25, 50, 75, 90)],
            'frac_margin_lt_2': float((m < 2).mean()), 'frac_margin_lt_4': float((m < 4).mean()),
            'frac_top1_not_delimiter': float(np.mean([r['top1'] != R.DQ for r in cl]))}
        for arg in ('new', 'old'):
            pa = np.array([r['pLA_T1'] for r in cl if r['arg'] == arg])
            out['string_end_closers'][f'E_slip_T1_{arg}'] = float(pa.mean()) if len(pa) else None
        calls = {}
        for r in cl:
            calls.setdefault((r['episode_id'], r['item']), []).append(r['pLA_T1'])
        pc = np.array([1 - np.prod([1 - x for x in v]) for v in calls.values()])
        out['per_call_slip_T1'] = {'n_calls': len(pc), 'mean': float(pc.mean())}
    sl = [r for r in recs if r['kind'] == 'slip']
    if sl:
        out['logged_slip_states'] = {'n': len(sl), 'mean_pLA_T1': float(np.mean([r['pLA_T1'] for r in sl])),
                                     'frac_top1_lookalike': float(np.mean([r.get('top1_is_la', False) for r in sl]))}
    pr = [r for r in recs if r['kind'] == 'protected']
    if pr:
        out['protected_content'] = {'n': len(pr), 'mean_lp_logged': float(np.mean([r.get('lp_logged', float('nan')) for r in pr]))}
    return out


async def _probe(client, base, model, ids, logged=None):
    body = {'model': model, 'prompt': ids, 'max_tokens': 1, 'temperature': 0, 'logprobs': 20,
            'return_tokens_as_token_ids': True, 'skip_special_tokens': False}
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


async def _run(base, model, items, kinds, conc, max_total, out_jsonl, la):
    import httpx
    sem = asyncio.Semaphore(conc); recs = []; fo = open(out_jsonl, 'a') if out_jsonl else None
    done = set()
    if out_jsonl and os.path.exists(out_jsonl):
        for l in open(out_jsonl):
            r = json.loads(l); recs.append(r); done.add((r['episode_id'], r['turn_index'], r['pos']))

    async def one_item(client, n, it):
        poss = [p for p in it['positions'] if p['kind'] in kinds and (it['episode_id'], it['turn_index'], p['pos']) not in done]
        if not poss:
            return
        t = _turn(it['episode_id'], it['turn_index'])
        pids = R.encode(R.render(t['request']['messages'], it['schema'])); cids = R.encode(t['raw_completion'])
        if len(pids) != it['prompt_tokens']:
            return
        async with sem:
            for p in sorted(poss, key=lambda x: x['pos']):
                ids = pids + cids[:p['pos']]
                if max_total and len(ids) + 1 > max_total:
                    continue
                top, npt = await _probe(client, base, model, ids)
                m = position_metrics(top, la)
                r = {'episode_id': it['episode_id'], 'turn_index': it['turn_index'], 'item': n, 'split': it['split'], 'kind': p['kind'],
                     'arg': p.get('arg'), 'pos': p['pos'], 'logged': p['logged'], 'top': top, 'n_prompt': npt, **m,
                     'top1_is_la': m['top1'] in la, 'lp_logged': dict(top).get(p['logged'])}
                recs.append(r)
                if fo:
                    fo.write(json.dumps(r) + '\n'); fo.flush()

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=conc + 4)) as client:
        await asyncio.gather(*[one_item(client, n, it) for n, it in enumerate(items)])
    if fo:
        fo.close()
    return recs


def audit_checkpoint(base_url, model, split='heldout', items=CORE, kinds=('close', 'slip'), conc=8, max_total=None, out_jsonl=None,
                     limit=0):
    its = [json.loads(l) for l in open(items)]
    its = [it for it in its if split in ('all', it['split'])]
    if limit:
        its = its[:limit]
    la = set(R.lookalike_ids())
    t0 = time.time()
    recs = asyncio.run(_run(base_url, model, its, set(kinds), conc, max_total, out_jsonl, la))
    summ = score_records(recs)
    summ.update({'base_url': base_url, 'model': model, 'split': split, 'items_file': items, 'n_items': len(its),
                 'n_records': len(recs), 'seconds': round(time.time() - t0), 'sampler': 'T=1.0, top-k 64, top-p 0.95 (from top-20)',
                 'items_sha256': hashlib.sha256(open(items, 'rb').read()).hexdigest()[:16]})
    return summ


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True); ap.add_argument('--model', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--split', default='heldout'); ap.add_argument('--items', default=CORE); ap.add_argument('--conc', type=int, default=8)
    ap.add_argument('--max_total', type=int, default=0); ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--kinds', default='close,slip')
    a = ap.parse_args()
    s = audit_checkpoint(a.base, a.model, a.split, a.items, tuple(a.kinds.split(',')), a.conc, a.max_total or None,
                         a.out.replace('.json', '.records.jsonl'), a.limit)
    json.dump(s, open(a.out, 'w'), indent=1)
    print(json.dumps(s, indent=1)[:3000])
