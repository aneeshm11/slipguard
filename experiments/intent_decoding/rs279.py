"""Gold-intent split from REAL logged slips (P0-B(c)): base-31B records of C's corpus with `intent_from_retry`
(the intended old_string recovered from a later clean retry with the same file path and the same new_string payload).
For each: exact logged prefix = June-template render of the logged context (thinking ON as logged) + the logged thought
+ '<|tool_call>' + the byte-exact raw call prefix up to (and including) the opener of the absorbed old_string.
Arms run from that prefix at the LOGGED temperature (greedy at T=0), prefix pinned in the cache:
  IPD (i) noisy-channel cut + resume, (i)-max, retry x2, greedy, forbid-trigger, grammar-CD.
T1 text-only and (ii) need the full emitted call, whose tail was lost at serving time; they are evaluated on an
ASSUMED remainder = retry old_string + <|"|>} (labelled 'assumed_tail'; tests only the cut decision).
Gold: filepath, new_string = payload before the look-alike closer, old_string = retry's old_string.
NOTE (selection): the retry match requires retry.new_string == payload-without-closer, so the true cut is the whole
look-alike run for every record here; only old_string recovery discriminates decoders that resume.
"""
import argparse, asyncio, json, lzma, os, sys, time
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import (D, TC_START, TC_END, schema_from_tools, is_valid, first_slip_site, parse_strict,
                            runtime_view, repair_candidates)
from intent_decode import Server, rollback_resume, lik_repair, ChannelPrior, ids_of, Pin
from replay_utils import render_prompt
import arms as ARM

CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')
CTX = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz')
ap = argparse.ArgumentParser()
ap.add_argument('--base', default='http://127.0.0.1:8302/v1')
ap.add_argument('--model', default='gemma-4-31b')
ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
ap.add_argument('--out', required=True)
ap.add_argument('--n', type=int, default=10000)
ap.add_argument('--conc', type=int, default=6)
ap.add_argument('--workers', type=int, default=3)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tok)
PRIOR = ChannelPrior.from_log_slips('ft_edit')
BAN = None


def gold_of(d):
    args = json.loads(d['arguments_json'])
    lab = d['labels']['absorbed'][0]
    host = args.get(lab['host_key']) or ''
    payload = host[:lab['offset']] if 'offset' in lab else host[:d['labels'].get('payload_chars_before_closer', 0)]
    return {'filepath': args.get('filepath'), 'new_string': payload, 'old_string': d['intent_from_retry']['old_string']}


def score(text, finished, schema, gold):
    v = runtime_view(text, finished, schema) if text is not None else {'accepted': False, 'strict_valid': False,
                                                                       'silent_corruption': False, 'census_ok': False}
    ok = bool(text is not None and finished and is_valid(text, schema))
    args = parse_strict(text).args() if ok else {}
    return {'strict_valid': ok, 'silent_corruption': v.get('silent_corruption'), 'census_ok': v.get('census_ok'),
            'exact_intent': ok and args.get('filepath') == gold['filepath'] and args.get('new_string') == gold['new_string']
            and args.get('old_string') == gold['old_string'],
            'new_exact': ok and args.get('new_string') == gold['new_string'],
            'old_exact': ok and args.get('old_string') == gold['old_string']}


async def one(srv, d, ctx, fo, lock):
    schema = schema_from_tools(ctx['tools'])
    gold = gold_of(d)
    T = float(d['temperature'])
    p0 = render_prompt(tok, ctx['messages'], ctx['tools'], True, 'june')
    th = d.get('reasoning_content') or ''
    A = '<|channel>thought\n' + th + ('' if th.endswith('\n') else '\n') + '<channel|>' if th else '<|channel>thought\n<channel|>'
    A += d.get('content') or ''
    prefix = p0 + A + TC_START
    pid = ids_of(tok, prefix)
    rawp = d['raw']['raw_prefix']
    call_prefix = rawp[len(TC_START):] if rawp.startswith(TC_START) else rawp
    rec = {'id': d['id'], 'run': d['run'], 'T': T, 'thought_truncated': len(th) >= 3990,
           'raw_prefix_exact': d['raw'].get('raw_prefix_exact'), 'closer': d['labels']['absorbed'][0].get('closer'),
           'gold_new_len': len(gold['new_string']), 'arms': {}}
    sk = abs(hash(d['id'])) % 100000
    try:
        site = first_slip_site(call_prefix, schema, finished=False)
        rec['site_found'] = site is not None
        async with Pin(srv, pid):
            async def run_i(rule):
                if site is None:
                    return
                ri = await rollback_resume(srv, tok, prefix, call_prefix, False, schema, rule=rule, prior=PRIOR,
                                           temperature=T, seed=sk, prefix_ids=pid)
                rec['arms']['i_' + rule] = {'text': ri['text'], **score(ri['text'], ri['finished'], schema, gold),
                                            'rounds': len(ri['rounds']),
                                            'k': ri['rounds'][0]['cut_choice'].get('k') if ri['rounds'] else None}

            async def run_retry():
                rt = await ARM.arm_retry(srv, tok, pid, '', schema, sk, temp=T)
                rec['arms']['retry_x2'] = {'text': rt['final_text'], **score(rt['final_text'], True, schema, gold)}

            async def run_greedy():
                g = await ARM.arm_greedy(srv, tok, pid, '', schema)
                rec['arms']['greedy'] = {'text': g['final_text'], **score(g['final_text'], g['finished'], schema, gold)}

            async def run_forbid():
                fb = await ARM.arm_forbid2(srv, tok, pid, call_prefix, False, schema, BAN, sk, temp=T)
                rec['arms']['forbid_strict'] = {'text': fb['final_text'], **score(fb['final_text'], fb['finished'], schema, gold)}

            async def run_grammar():
                gr = await ARM.arm_grammar(srv, tok, pid, call_prefix, False, schema, sk, temp=T)
                rec['arms']['grammar'] = {'text': gr['final_text'], **score(gr['final_text'], gr['finished'], schema, gold)}

            async def run_text_only():
                # assumed-tail variants for text-only decoders
                full = call_prefix + gold['old_string'] + D + '}'
                cands = repair_candidates(full, schema, finished=True)
                t1 = None
                for c in cands:
                    if all(s_ is not None and cp == s_.cut_positions()[0] for (k, cp, cl), s_ in zip(c.cuts, c.sites)):
                        t1 = c.text('edit_file'); break
                rec['arms']['T1_assumed_tail'] = {'text': t1, **score(t1, True, schema, gold)}
                rii = await lik_repair(srv, tok, prefix, full, True, schema, tau=0.0, prior=PRIOR, prefix_ids=pid)
                txt = rii.get('text') if rii.get('decision') == 'repair' else None
                rec['arms']['ii_assumed_tail'] = {'text': txt, 'margin': rii.get('margin'), **score(txt, True, schema, gold)}

            await asyncio.gather(run_i('nc'), run_i('max'), run_retry(), run_greedy(), run_forbid(), run_grammar(),
                                 run_text_only())
        rec['status'] = 'ok'
    except Exception as e:
        rec['status'] = 'error'; rec['err'] = repr(e)[:300]
    async with lock:
        fo.write(json.dumps(rec) + '\n'); fo.flush()


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
            if x.get('status') == 'ok':
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
    print(len(recs), 'real slips with retry-derived intent (base)', flush=True)
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
