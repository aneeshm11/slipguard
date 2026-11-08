"""Decoder head-to-head arms (retry x2, greedy, forbid-trigger, grammar-CD) for replay outputs that were produced
WITHOUT inline arms (E4B replays, July runs). Same arm code as replay.py's inline arms (arms.py), prefix pinned.
Output: out/h2h_<replay>.jsonl {id, seed, sample, arms{...}}; analyze_h2h.py merges it with the replay records.
"""
import argparse, asyncio, json, os, sys
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import TC_START, schema_from_tools
from intent_decode import Server, ids_of, Pin
from replay_utils import render_prompt
import arms as ARM

ap = argparse.ArgumentParser()
ap.add_argument('--replay', required=True)
ap.add_argument('--contexts', default=os.path.join(HERE, 'data/replay_gemma_first_edit.jsonl'))
ap.add_argument('--base', required=True)
ap.add_argument('--model', required=True)
ap.add_argument('--tok', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--arms', default='retry,greedy,forbid,grammar')
ap.add_argument('--conc', type=int, default=4)
ap.add_argument('--workers', type=int, default=3)
ap.add_argument('--temp', type=float, default=0.2)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tok)
ARMS = a.arms.split(',')
BAN = None


async def one(srv, c, r, fo, lock):
    schema = schema_from_tools(c['tools'])
    tpl = r.get('template') if r.get('template') in ('june', 'july') else None
    msgs = c['messages']
    if r.get('exemplar'):
        from replay_utils import with_exemplar
        msgs = with_exemplar(msgs)
    p0 = render_prompt(tok, msgs, c['tools'], r['think'], tpl)
    head = 'call:edit_file{' if r.get('forced') else ''
    pid = ids_of(tok, p0 + (r.get('A_text') or '') + TC_START)
    sk = (r['seed'] * 100 + r.get('sample', 0)) * 10000
    out = {'id': r['id'], 'seed': r['seed'], 'sample': r.get('sample', 0), 'arms': {}}
    try:
        async with Pin(srv, pid):
            if 'greedy' in ARMS:
                out['arms']['greedy'] = await ARM.arm_greedy(srv, tok, pid, head, schema)
            if 'retry' in ARMS and not r['base']['strict_valid']:
                out['arms']['retry'] = await ARM.arm_retry(srv, tok, pid, head, schema, sk, temp=a.temp)
            if 'forbid' in ARMS and r.get('site') is not None:
                out['arms']['forbid'] = await ARM.arm_forbid(srv, tok, pid, r['call'], r['finished'], schema, BAN, sk, temp=a.temp)
            if 'forbid2' in ARMS and r.get('site') is not None:
                out['arms']['forbid2'] = await ARM.arm_forbid2(srv, tok, pid, r['call'], r['finished'], schema, BAN, sk, temp=a.temp)
            if 'grammar' in ARMS and not r['base']['strict_valid']:
                out['arms']['grammar'] = await ARM.arm_grammar(srv, tok, pid, r['call'], r['finished'], schema, sk, temp=a.temp)
        out['status'] = 'ok'
    except Exception as e:
        out['status'] = 'error'; out['err'] = repr(e)[:300]
    async with lock:
        fo.write(json.dumps(out) + '\n'); fo.flush()


async def main():
    global BAN
    recs = [json.loads(l) for l in open(a.replay)]
    recs = [r for r in recs if r.get('status') == 'call' and r.get('tool') == 'edit_file' and (not r.get('h2h') or ARMS == ['forbid2'])]
    if ARMS == ['forbid2']:
        recs = [r for r in recs if r.get('site') is not None]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            d = json.loads(l)
            if d.get('status') == 'ok' and (('forbid2' in d.get('arms', {})) if ARMS == ['forbid2'] else ('greedy' in d.get('arms', {}))):
                done.add((d['id'], d['seed'], d.get('sample', 0)))
    recs = [r for r in recs if (r['id'], r['seed'], r.get('sample', 0)) not in done]
    need = {r['id'] for r in recs}
    ctx = {}
    for l in open(a.contexts):
        d = json.loads(l)
        if d['id'] in need:
            ctx[d['id']] = d
    recs = [r for r in recs if r['id'] in ctx]
    if 'forbid' in ARMS or 'forbid2' in ARMS:
        BAN = ARM.banned_key_tokens(tok, ['filepath', 'old_string', 'new_string', 'allow_multiple'])
    print(len(recs), 'samples', flush=True)
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
        await asyncio.gather(*[worker() for _ in range(a.workers)])
    print('done', dict(srv.stats), flush=True)
    await srv.close()

asyncio.run(main())
