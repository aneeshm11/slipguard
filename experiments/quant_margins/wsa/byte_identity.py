"""Gate (iii): valid-call byte identity. For held-out VALID PNC edit calls, regenerate the tool call greedily from the call
start (prompt + logged completion up to and including <|tool_call>) with the base model and with the repair adapter on the
same vLLM server; compare the generated call bytes, and judge both with the vLLM-faithful delimiter parser.
usage: byte_identity.py --base http://127.0.0.1:8304/v1 --models gemma-4-31b,repairA --out out/byte_identity_repairA.json"""
import argparse, asyncio, json, os, sys, re
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import pnc_render as R
from build_points import parse_call

ap = argparse.ArgumentParser(); ap.add_argument('--base', required=True); ap.add_argument('--models', required=True)
ap.add_argument('--out', required=True); ap.add_argument('--split', default='heldout'); ap.add_argument('--limit', type=int, default=300)
ap.add_argument('--conc', type=int, default=8)
ap.add_argument('--items', default=os.path.join(H, 'data', 'core_items.jsonl'))
ap.add_argument('--skip', type=int, default=0)
a = ap.parse_args()
items = [json.loads(l) for l in open(a.items)]
items = [it for it in items if it['kind'] == 'valid' and (a.split == 'all' or it['split'] == a.split)][a.skip:a.skip + a.limit]
models = a.models.split(',')


def judge(text, schema):
    E = R.EDIT[schema]
    body = text.split('<tool_call|>')[0]
    m = re.match(r'call:([\w\-\.]+)\{', body)
    if not m:
        return {'valid': False, 'why': 'no_call'}
    args, _ = parse_call(body[m.end():])
    vals = {k: v for k, v, *_ in args}
    keys = {E['path'], E['old'], E['new']}
    leak = re.compile(r'(["`\\\']+)\s*,\s*(' + '|'.join(map(re.escape, sorted(keys | set(vals), key=len, reverse=True))) + r')\s*:')
    ok = all(isinstance(vals.get(k), str) for k in keys) and not any(isinstance(v, str) and leak.search(v) for v in vals.values())
    return {'valid': bool(ok), 'name': m.group(1)}


async def main():
    import httpx
    sem = asyncio.Semaphore(a.conc); rows = []

    async def one(client, it):
        t = None
        for l in open(os.path.join(R.PNC, 'episodes', it['episode_id'] + '.jsonl')):
            d = json.loads(l)
            if d.get('record_type') == 'turn' and d['turn_index'] == it['turn_index']:
                t = d; break
        pids = R.encode(R.render(t['request']['messages'], it['schema'])); cids = R.encode(t['raw_completion'])
        k = cids.index(48) + 1
        ids = pids + cids[:k]
        row = {'episode_id': it['episode_id'], 'turn_index': it['turn_index']}
        async with sem:
            for m in models:
                r = await client.post(a.base + '/completions', json={'model': m, 'prompt': ids, 'max_tokens': 1536, 'temperature': 0,
                                                                     'stop_token_ids': [49], 'skip_special_tokens': False,
                                                                     'spaces_between_special_tokens': False}, timeout=1800)
                txt = r.json()['choices'][0]['text']
                row[m] = {'text': txt, **judge(txt, it['schema'])}
        rows.append(row)

    async with httpx.AsyncClient() as client:
        await asyncio.gather(*[one(client, it) for it in items])
    base = models[0]
    summ = {'n': len(rows), 'models': models}
    for m in models[1:]:
        summ[m] = {'byte_identical_to_base': sum(r[m]['text'] == r[base]['text'] for r in rows) / len(rows),
                   'valid_rate': sum(r[m]['valid'] for r in rows) / len(rows), 'base_valid_rate': sum(r[base]['valid'] for r in rows) / len(rows),
                   'base_valid_and_adapter_invalid': sum(r[base]['valid'] and not r[m]['valid'] for r in rows),
                   'base_invalid_and_adapter_valid': sum((not r[base]['valid']) and r[m]['valid'] for r in rows)}
    json.dump({'summary': summ, 'rows': rows}, open(a.out, 'w'), indent=1)
    print(json.dumps(summ, indent=1))


asyncio.run(main())
