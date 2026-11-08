"""Baseline: RETRY-ON-INVALID (resample the whole call, new seed) for every strictly-invalid edit call of a replay output.
Same detection as (i) (strict validity), different repair: full resample from the same prefix (context + own thought
+ <|tool_call> [+ forced 'call:edit_file{' if the replay forced the tool]).  Up to R retries.
Compares slip removal and token cost against (i)'s targeted rollback/resume.  Runs incrementally on a growing replay file.
"""
import argparse, asyncio, json, os, sys, time
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import TC_START, TC_END, schema_from_tools, is_valid, first_slip_site, census_judge, parse_strict
from intent_decode import Server
from replay_utils import fix_msgs

ap = argparse.ArgumentParser()
ap.add_argument('--replay', required=True)
ap.add_argument('--contexts', default=os.path.join(HERE, 'data/replay_first_edit.jsonl'))
ap.add_argument('--base', required=True)
ap.add_argument('--model', required=True)
ap.add_argument('--tok', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--R', type=int, default=2)
ap.add_argument('--conc', type=int, default=8)
ap.add_argument('--temp', type=float, default=0.2)
ap.add_argument('--call_max', type=int, default=2048)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tok)


async def one(srv, c, r, fo, lock):
    schema = schema_from_tools(c['tools'])
    p0 = tok.apply_chat_template(fix_msgs(c['messages']), tools=c['tools'], add_generation_prompt=True, tokenize=False,
                                 enable_thinking=bool(r['think']))
    H = 'call:edit_file{' if r.get('forced') else ''
    prefix = p0 + (r.get('A_text') or '') + TC_START + H
    rec = {'id': r['id'], 'seed': r['seed'], 'sample': r.get('sample', 0), 'model': a.model, 'think': r['think'],
           'base_slip': r.get('site') is not None, 'tries': []}
    try:
        for t in range(a.R):
            B = await srv.complete(prefix, max_tokens=a.call_max, stop=[TC_END], temperature=a.temp, top_p=0.95,
                                   seed=(r['seed'] * 100 + r.get('sample', 0)) * 1000 + 77 + t, tag='retry')
            text = H + B['text']
            fin = B.get('finish_reason') == 'stop' and B.get('stop_reason') == TC_END
            ok, why, _ = census_judge(text, schema) if fin else (False, 'no_close', {})
            sv = fin and is_valid(text, schema)
            rec['tries'].append({'census_ok': ok, 'census_why': why, 'strict_valid': sv,
                                 'slip': first_slip_site(text, schema, finished=fin) is not None,
                                 'tool': parse_strict(text).name, 'gen_tokens': B['_usage'].get('completion_tokens'),
                                 'latency': B['_latency']})
            if sv:
                break
        rec['status'] = 'ok'
    except Exception as e:
        rec['status'] = 'error'; rec['err'] = repr(e)[:300]
    async with lock:
        fo.write(json.dumps(rec) + '\n'); fo.flush()


async def main():
    recs = [json.loads(l) for l in open(a.replay)]
    recs = [r for r in recs if r.get('status') == 'call' and r.get('tool') == 'edit_file' and not r['base']['strict_valid']]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            d = json.loads(l)
            if d.get('status') == 'ok':
                done.add((d['id'], d['seed'], d.get('sample', 0)))
    recs = [r for r in recs if (r['id'], r['seed'], r.get('sample', 0)) not in done]
    need = {r['id'] for r in recs}
    ctx = {}
    with open(a.contexts) as f:
        for l in f:
            d = json.loads(l)
            if d['id'] in need:
                ctx[d['id']] = d
    print(len(recs), 'invalid edit calls to retry', flush=True)
    srv = Server(a.base, a.model, conc=a.conc)
    lock = asyncio.Lock()
    q = asyncio.Queue()
    for r in recs:
        q.put_nowait(r)
    with open(a.out, 'a') as fo:
        async def worker():
            while True:
                try:
                    r = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(srv, ctx[r['id']], r, fo, lock)
        await asyncio.gather(*[worker() for _ in range(a.conc)])
    print('done', dict(srv.stats), flush=True)
    await srv.close()

asyncio.run(main())
