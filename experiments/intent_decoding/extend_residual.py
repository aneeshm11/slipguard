"""(i++) post-hoc arm: apply the opt-in extension rules ('kwarg' = Python-kwargs drift `KEY=`, 'qkey' = JSON-mode
quoted-key slip `",\"KEY\":`) on top of 'closer' + 'opener' to every E1 replay record whose final (i+) / (i) / baseline
call is still census-malformed or strictly invalid.  Same prefix (context + own thought + <|tool_call>), same model.
The default deployed rules are unchanged; this measures how far the same rollback-and-force mechanism generalises.
"""
import argparse, asyncio, json, os, sys
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import TC_START, schema_from_tools, census_judge, is_valid, parse_strict, schema_problems
from intent_decode import Server, rollback_resume, ChannelPrior, ids_of
from replay_utils import fix_msgs

ap = argparse.ArgumentParser()
ap.add_argument('--replay', required=True)
ap.add_argument('--contexts', default=os.path.join(HERE, 'data/replay_first_edit.jsonl'))
ap.add_argument('--base', required=True)
ap.add_argument('--model', required=True)
ap.add_argument('--tok', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--conc', type=int, default=2)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tok)
PRIOR = ChannelPrior.from_log_slips('ft_edit')


def judge(text, finished, schema):
    ok, why, _ = census_judge(text, schema) if finished else (False, 'no_close', {})
    sp = parse_strict(text)
    probs = schema_problems(sp, schema) if sp.ok else ['struct:' + sp.error]
    return {'census_ok': ok, 'census_why': why, 'strict_valid': bool(sp.ok and not probs and finished), 'strict_probs': probs[:4]}


async def one(srv, c, r, fo, lock):
    schema = schema_from_tools(c['tools'])
    fin = r.get('i_plus') or r.get('i_nc') or {'text': r['call'], 'finished': r['finished']}
    p0 = tok.apply_chat_template(fix_msgs(c['messages']), tools=c['tools'], add_generation_prompt=True, tokenize=False,
                                 enable_thinking=bool(r['think']))
    prefix = p0 + (r.get('A_text') or '') + TC_START
    rec = {'id': r['id'], 'seed': r['seed'], 'sample': r.get('sample', 0), 'start_from': 'i_plus' if r.get('i_plus') else
           ('i_nc' if r.get('i_nc') else 'base')}
    try:
        rp = await rollback_resume(srv, tok, prefix, fin['text'], fin['finished'], schema, rule='nc', prior=PRIOR,
                                   rules=('closer', 'opener', 'kwarg', 'qkey'), max_tokens=2048, seed=r['seed'] * 100 + 31)
        rp['judge'] = judge(rp['text'], rp['finished'], schema)
        rec['i_pp'] = rp
        rec['status'] = 'ok'
    except Exception as e:
        rec['status'] = 'error'; rec['err'] = repr(e)[:300]
    async with lock:
        fo.write(json.dumps(rec) + '\n'); fo.flush()


async def main():
    recs = [json.loads(l) for l in open(a.replay)]
    todo = []
    for r in recs:
        if r.get('status') != 'call' or r.get('tool') != 'edit_file':
            continue
        fin = r.get('i_plus') or r.get('i_nc')
        j = fin['judge'] if fin else r['base']
        if not j['census_ok'] or not j['strict_valid']:
            todo.append(r)
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            d = json.loads(l)
            if d.get('status') == 'ok':
                done.add((d['id'], d['seed'], d.get('sample', 0)))
    todo = [r for r in todo if (r['id'], r['seed'], r.get('sample', 0)) not in done]
    need = {r['id'] for r in todo}
    ctx = {}
    for l in open(a.contexts):
        d = json.loads(l)
        if d['id'] in need:
            ctx[d['id']] = d
    print(len(todo), 'residual invalid records', flush=True)
    srv = Server(a.base, a.model, conc=a.conc)
    lock = asyncio.Lock()
    q = asyncio.Queue()
    for r in todo:
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
