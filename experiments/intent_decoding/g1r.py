"""G1R: NATURAL closures with known intent at real slip-prone states (P0-B gold split, scalable).
For each base-31B record of C's corpus with retry-derived intent (229): exact logged prefix (June template + logged
thought + '<|tool_call>') + the byte-exact call prefix up to the END OF THE INTENDED PAYLOAD (gold new_string), then
k samples of the model's own continuation at the logged temperature: the model decides naturally how to close the
string (true delimiter or a look-alike slip) and continues the call.  Gold: filepath, new_string = payload,
old_string = the later clean retry's old_string.  Every sample (slip or not) is passed through the decoders:
IPD (i+), (i)-max, T1 text-only (on the REAL emitted tail), (ii) tau, retry x2, greedy, forbid-trigger (strict),
grammar-CD; valid samples measure false repairs (must be 0) and the model's own intent accuracy.
"""
import argparse, asyncio, json, lzma, os, sys
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import (D, TC_START, TC_END, schema_from_tools, is_valid, first_slip_site, parse_strict,
                            runtime_view, repair_candidates, census_judge, schema_problems)
from intent_decode import Server, rollback_resume, lik_repair, ChannelPrior, ids_of, Pin
from replay_utils import render_prompt
import arms as ARM
CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')
CTX = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz')


def gold_of(d):
    args = json.loads(d['arguments_json'])
    lab = d['labels']['absorbed'][0]
    host = args.get(lab['host_key']) or ''
    return {'filepath': args.get('filepath'), 'new_string': host[:lab['offset']],
            'old_string': d['intent_from_retry']['old_string']}


def score(text, finished, schema, gold):
    v = runtime_view(text, finished, schema) if text is not None else {'silent_corruption': False, 'census_ok': False}
    ok = bool(text is not None and finished and is_valid(text, schema))
    args = parse_strict(text).args() if ok else {}
    return {'strict_valid': ok, 'silent_corruption': v.get('silent_corruption'), 'census_ok': v.get('census_ok'),
            'exact_intent': ok and args.get('filepath') == gold['filepath'] and args.get('new_string') == gold['new_string']
            and args.get('old_string') == gold['old_string'],
            'new_exact': ok and args.get('new_string') == gold['new_string'],
            'old_exact': ok and args.get('old_string') == gold['old_string']}

ap = argparse.ArgumentParser()
ap.add_argument('--base', default='http://127.0.0.1:8302/v1')
ap.add_argument('--model', default='gemma-4-31b')
ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
ap.add_argument('--out', required=True)
ap.add_argument('--k', type=int, default=4)
ap.add_argument('--n', type=int, default=10000)
ap.add_argument('--conc', type=int, default=8)
ap.add_argument('--workers', type=int, default=3)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tok)
PRIOR = ChannelPrior.from_log_slips('ft_edit')
BAN = None


def judge(text, finished, schema):
    ok, why, _ = census_judge(text, schema) if finished else (False, 'no_close', {})
    sp = parse_strict(text)
    probs = schema_problems(sp, schema) if sp.ok else ['struct:' + sp.error]
    return {'census_ok': ok, 'census_why': why, 'strict_valid': bool(sp.ok and not probs and finished)}


async def one(srv, d, ctx, fo, lock):
    schema = schema_from_tools(ctx['tools'])
    gold = gold_of(d)
    T = float(d['temperature'])
    p0 = render_prompt(tok, ctx['messages'], ctx['tools'], True, 'june')
    th = d.get('reasoning_content') or ''
    A = ('<|channel>thought\n' + th + ('' if th.endswith('\n') else '\n') + '<channel|>') if th else '<|channel>thought\n<channel|>'
    A += d.get('content') or ''
    prefix = p0 + A + TC_START
    pid = ids_of(tok, prefix)
    rawp = d['raw']['raw_prefix']
    call_prefix = rawp[len(TC_START):] if rawp.startswith(TC_START) else rawp
    site = first_slip_site(call_prefix, schema, finished=False)
    base_rec = {'id': d['id'], 'run': d['run'], 'T': T, 'thought_truncated': len(th) >= 3990}
    if site is None:
        async with lock:
            fo.write(json.dumps({**base_rec, 'status': 'no_site'}) + '\n'); fo.flush()
        return
    forced = call_prefix[:site.content_start + d['labels']['absorbed'][0]['offset']]   # up to the end of the gold payload
    sk0 = abs(hash(d['id'])) % 100000
    try:
        async with Pin(srv, pid):
            c = await srv.complete(pid + ids_of(tok, forced), max_tokens=2048, stop=[TC_END], temperature=T, top_p=0.95,
                                   seed=sk0, n=a.k, tag='sample')
            samples = c.get('_all') or [c]

            async def process(j, ch):
                text = forced + ch['text']
                fin = ch.get('finish_reason') == 'stop' and ch.get('stop_reason') == TC_END
                rec = {**base_rec, 'sample': j, 'call': text, 'finished': fin, 'base': judge(text, fin, schema),
                       'base_score': score(text, fin, schema, gold), 'arms': {}}
                st = first_slip_site(text, schema, finished=fin)
                rec['slip'] = st is not None
                rec['slip_run'] = st.run if st is not None else None
                sk = sk0 * 10 + j

                async def run_i(rule, rules):
                    ri = await rollback_resume(srv, tok, prefix, text, fin, schema, rule=rule, prior=PRIOR, rules=rules,
                                               temperature=T, seed=sk, prefix_ids=pid)
                    return {'text': ri['text'], 'finished': ri['finished'], 'changed': ri['changed'],
                            **score(ri['text'], ri['finished'], schema, gold)}

                async def put(name, coro):
                    rec['arms'][name] = await coro

                async def run_ii():
                    if rec['base']['strict_valid']:
                        return {'text': text, 'changed': False, **score(text, fin, schema, gold)}
                    rii = await lik_repair(srv, tok, prefix, text, fin, schema, tau=0.0, prior=PRIOR, prefix_ids=pid)
                    out = {'margin': rii.get('margin'), 'decision': rii.get('decision'),
                           'cands': [{'text': x['text'], 'll': x['ll'], 'prior': x['prior']} for x in rii.get('cands', [])]}
                    return out

                async def run_retry():
                    if rec['base']['strict_valid']:
                        return {'text': text, **score(text, fin, schema, gold)}
                    rt = await ARM.arm_retry(srv, tok, pid, '', schema, sk, temp=T)
                    last = rt['tries'][-1]
                    return {'text': rt['final_text'], 'last_text': last['text'], 'last_finished': last['finished'],
                            **score(rt['final_text'], True, schema, gold)}

                async def run_greedy():
                    g = await ARM.arm_greedy(srv, tok, pid, '', schema)
                    return {'text': g['final_text'], 'finished': g['finished'], **score(g['final_text'], g['finished'], schema, gold)}

                async def run_forbid():
                    if st is None:
                        return {'text': text, 'finished': fin, **score(text, fin, schema, gold)}
                    fb = await ARM.arm_forbid2(srv, tok, pid, text, fin, schema, BAN, sk, temp=T)
                    return {'text': fb['final_text'], 'finished': fb['finished'], **score(fb['final_text'], fb['finished'], schema, gold)}

                async def run_grammar():
                    if rec['base']['strict_valid']:
                        return {'text': text, 'finished': fin, **score(text, fin, schema, gold)}
                    gr = await ARM.arm_grammar(srv, tok, pid, text, fin, schema, sk, temp=T)
                    return {'text': gr['final_text'], 'finished': gr['finished'], **score(gr['final_text'], gr['finished'], schema, gold)}

                jobs = [put('IPD', run_i('nc', ('closer', 'opener'))), put('i_max', run_i('max', ('closer',))),
                        put('ii', run_ii()), put('retry_x2', run_retry()), put('greedy', run_greedy()),
                        put('forbid_strict', run_forbid()), put('grammar', run_grammar())]
                await asyncio.gather(*jobs)
                rec['status'] = 'ok'
                async with lock:
                    fo.write(json.dumps(rec) + '\n'); fo.flush()

            await asyncio.gather(*[process(j, ch) for j, ch in enumerate(samples)])
    except Exception as e:
        async with lock:
            fo.write(json.dumps({**base_rec, 'status': 'error', 'err': repr(e)[:300]}) + '\n'); fo.flush()


async def main():
    global BAN
    recs = []
    for l in open(CORPUS):
        d = json.loads(l)
        if d.get('intent_from_retry') and d['model_family'] == 'base' and d.get('run_status') == 'ok':
            recs.append(d)
    recs = recs[:a.n]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            x = json.loads(l)
            if x.get('status') in ('ok', 'no_site'):
                done.add(x['id'])
    recs = [d for d in recs if d['id'] not in done]
    need = {d['context_ref'] for d in recs}
    ctx = {}
    with lzma.open(CTX, 'rt') as f:
        for l in f:
            c = json.loads(l)
            if c['context_ref'] in need:
                ctx[c['context_ref']] = c
    recs = [d for d in recs if d['context_ref'] in ctx]
    BAN = ARM.banned_key_tokens(tok, ['filepath', 'old_string', 'new_string', 'allow_multiple'])
    print(len(recs), 'states x', a.k, 'samples', flush=True)
    srv = Server(a.base, a.model, conc=a.conc)
    lock = asyncio.Lock()
    q = asyncio.Queue()
    for d in recs:
        q.put_nowait(d)
    with open(a.out, 'a') as fo:
        async def worker():
            while True:
                try:
                    d = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(srv, d, ctx[d['context_ref']], fo, lock)
        await asyncio.gather(*[worker() for _ in range(a.workers)])
    print('done', dict(srv.stats), flush=True)
    await srv.close()

asyncio.run(main())
