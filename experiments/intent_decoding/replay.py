"""Real-context replay: baseline vs (i) slip rollback/resume vs (ii) likelihood-scored repair.

For every (context, seed): render the logged history with its tool declarations (thinking ON or OFF),
stage A: generate until the model opens a tool call (<|tool_call>), stage B: generate the call until <tool_call|>.
The baseline call is then (i) passed through rollback/resume (paired: same initial sample) and
(ii) scored post hoc. Natural tool choice (no forcing); edit_file calls are the primary population.
"""
import argparse, asyncio, json, os, sys, time, math, random
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import (D, TC_START, TC_END, schema_from_tools, is_valid, first_slip_site, census_judge, parse_strict,
                            schema_problems, repair_candidates, first_opener_site)
from intent_decode import Server, rollback_resume, lik_repair, ChannelPrior, ids_of, Pin
import arms as ARM
from replay_utils import fix_msgs, render_prompt, with_exemplar

ap = argparse.ArgumentParser()
ap.add_argument('--base', default='http://127.0.0.1:8302/v1')
ap.add_argument('--model', default='gemma-4-31b')
ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
ap.add_argument('--contexts', default=os.path.join(HERE, 'data/replay_first_edit.jsonl'))
ap.add_argument('--out', required=True)
ap.add_argument('--think', type=int, default=1)
ap.add_argument('--n', type=int, default=100000)
ap.add_argument('--skip', type=int, default=0)
ap.add_argument('--seeds', default='0')
ap.add_argument('--conc', type=int, default=24)
ap.add_argument('--temp', type=float, default=0.2)
ap.add_argument('--top_p', type=float, default=0.95)
ap.add_argument('--think_budget', type=int, default=4096)
ap.add_argument('--call_max', type=int, default=2048)
ap.add_argument('--no_lik', action='store_true')
ap.add_argument('--force_edit', action='store_true', help='skip natural tool choice; force call:edit_file{')
ap.add_argument('--k', type=int, default=1, help='samples per context (n>1 shares the prefill)')
ap.add_argument('--prior', default='ft_edit', help='closer channel prior source: ft_edit | base_edit | none')
ap.add_argument('--template', default=None, choices=[None, 'june', 'july'], help='chat template (None = tokenizer default)')
ap.add_argument('--exemplar', action='store_true', help='arm 11: insert one synthetic clean edit_file exchange')
ap.add_argument('--h2h', default='greedy,retry,forbid,grammar', help='inline head-to-head arms (empty = none)')
ap.add_argument('--no_pin', action='store_true')
ap.add_argument('--workers', type=int, default=0, help='contexts in flight (default = conc); pins <= workers*k')
a = ap.parse_args()

tok = AutoTokenizer.from_pretrained(a.tok)
PRIOR = ChannelPrior.from_log_slips(a.prior) if a.prior != 'none' else None
H2H = [x for x in a.h2h.split(',') if x]
BAN = None


def render(c):
    msgs = with_exemplar(c['messages']) if a.exemplar else c['messages']
    return render_prompt(tok, msgs, c['tools'], a.think, a.template)


def judge(text, finished, schema):
    ok, why, args = census_judge(text, schema) if finished else (False, 'no_close', {})
    sp = parse_strict(text)
    probs = schema_problems(sp, schema) if sp.ok else ['struct:' + sp.error]
    return {'census_ok': ok, 'census_why': why, 'strict_valid': bool(sp.ok and not probs and finished),
            'strict_probs': probs[:4]}


async def write(fo, lock, rec):
    async with lock:
        fo.write(json.dumps(rec) + '\n'); fo.flush()


async def one(srv, c, seed, fo, lock):
    schema = schema_from_tools(c['tools'])
    try:
        p0 = render(c)
        samples = []
        if a.force_edit and not a.think:
            samples.append({'A_text': '', 'call': None, 'finished': None, 'A_finish': 'forced', 'k': 0})
        else:
            R = await srv.complete(p0, max_tokens=a.think_budget + a.call_max, stop=[TC_END], temperature=a.temp,
                                   top_p=a.top_p, seed=seed, n=a.k)
            for k, ch in enumerate(R.get('_all') or [R]):
                t = ch['text']
                fin = ch.get('finish_reason') == 'stop' and ch.get('stop_reason') == TC_END
                if TC_START in t:
                    i = t.index(TC_START)
                    samples.append({'A_text': t[:i], 'call': t[i + len(TC_START):], 'finished': fin,
                                    'A_finish': ch.get('finish_reason'), 'k': k, 'gen_tokens_total': None})
                else:
                    samples.append({'A_text': None, 'tail': t[-300:], 'A_finish': ch.get('finish_reason'), 'k': k})
        await asyncio.gather(*[process(srv, c, schema, p0, smp, seed, fo, lock) for smp in samples])
    except Exception as e:
        await write(fo, lock, {'id': c['id'], 'task': c.get('task'), 'seed': seed, 'think': a.think, 'model': a.model,
                               'status': 'error', 'err': repr(e)[:500]})


async def process(srv, c, schema, p0, smp, seed, fo, lock):
    rec = {'id': c['id'], 'task': c.get('task'), 'seed': seed, 'sample': smp['k'], 'think': a.think, 'model': a.model, 'template': a.template or 'default', 'exemplar': bool(a.exemplar),
           'A_finish': smp.get('A_finish')}
    t_start = time.time()
    try:
        if smp.get('A_text') is None:
            rec['status'] = 'no_call'; rec['A_tail'] = smp.get('tail')
            await write(fo, lock, rec); return
        rec['A_text'] = smp['A_text']
        prefix = p0 + smp['A_text'] + TC_START
        sk = seed * 100 + smp['k']
        text, finished = smp['call'], smp['finished']
        nat_tool = None
        if text is not None:
            sp = parse_strict(text)
            nat_tool = sp.name if sp.name else (text.split('{')[0][:40])
        rec['natural_tool'] = nat_tool
        B = {'_usage': {}, '_latency': None}
        if nat_tool != 'edit_file':
            # census of the natural non-edit call, then force an edit_file call in the same state (as order_replay)
            if text is not None:
                st = first_slip_site(text, schema, finished=finished)
                rec['natural_call'] = {'text': text[:4000], 'finished': finished, 'judge': judge(text, finished, schema),
                                       'site': None if st is None else {'key': st.key, 'next_key': st.next_key,
                                                                         'run': st.run, 'kind': st.kind}}
            H = 'call:edit_file{'
            B = await srv.complete(prefix + H, max_tokens=a.call_max, stop=[TC_END], temperature=a.temp, top_p=a.top_p,
                                   seed=sk)
            text = H + B['text']
            finished = B.get('finish_reason') == 'stop' and B.get('stop_reason') == TC_END
            sp = parse_strict(text)
            rec['forced'] = True
        else:
            rec['forced'] = False
        rec.update(status='call', tool=(sp.name if sp.name else text[:40]), call=text, finished=finished,
                   B_tokens=B['_usage'].get('completion_tokens'), B_latency=B['_latency'])
        rec['base'] = judge(text, finished, schema)
        site = first_slip_site(text, schema, finished=finished)
        rec['site'] = None if site is None else {'key': site.key, 'next_key': site.next_key, 'kind': site.kind,
                                                 'run': site.run, 'gap': site.gap, 'pos': site.run_start}
        prefix_ids = ids_of(tok, prefix)
        head = 'call:edit_file{' if rec['forced'] else ''
        pin = Pin(srv, prefix_ids) if not a.no_pin else None
        if pin:
            await pin.__aenter__()
        try:
            async def chain_i():
                # (i) rollback/resume, noisy-channel cut rule (and the zero-cost 'max' rule when its first cut differs)
                if site is not None:
                    ri = await rollback_resume(srv, tok, prefix, text, finished, schema, rule='nc', prior=PRIOR,
                                               max_tokens=a.call_max, temperature=a.temp, top_p=a.top_p, seed=sk,
                                               prefix_ids=prefix_ids)
                    ri['judge'] = judge(ri['text'], ri['finished'], schema)
                    rec['i_nc'] = ri
                    r0 = ri['rounds'][0]
                    if r0['cut'] != site.run_start:
                        rm = await rollback_resume(srv, tok, prefix, text, finished, schema, rule='max',
                                                   max_tokens=a.call_max, temperature=a.temp, top_p=a.top_p, seed=sk,
                                                   prefix_ids=prefix_ids)
                        rm['judge'] = judge(rm['text'], rm['finished'], schema)
                        rec['i_max'] = rm
                    else:
                        rec['i_max'] = 'same'
                # (i+) extension: closer + opener rules, applied to whatever (i) left strictly invalid
                start = rec['i_nc'] if site is not None else {'text': text, 'finished': finished}
                if not is_valid(start['text'], schema) and first_opener_site(start['text'], schema) is not None:
                    rp = await rollback_resume(srv, tok, prefix, start['text'], start['finished'], schema, rule='nc',
                                               prior=PRIOR, rules=('closer', 'opener'), max_tokens=a.call_max,
                                               temperature=a.temp, top_p=a.top_p, seed=sk + 7, prefix_ids=prefix_ids)
                    rp['judge'] = judge(rp['text'], rp['finished'], schema)
                    rec['i_plus'] = rp

            async def do_ii():
                # (ii) likelihood-scored repair of the emitted text (strictly-invalid finished calls only; tau offline)
                if not a.no_lik and not rec['base']['strict_valid'] and finished:
                    rii = await lik_repair(srv, tok, prefix, text, finished, schema, tau=0.0, prior=PRIOR,
                                           prefix_ids=prefix_ids)
                    if rii.get('text') is not None:
                        rii['judge'] = judge(rii['text'], True, schema)
                    rec['ii'] = rii

            hh = {}

            async def put(name, coro):
                hh[name] = await coro

            jobs = []
            if 'greedy' in H2H:
                jobs.append(put('greedy', ARM.arm_greedy(srv, tok, prefix_ids, head, schema, call_max=a.call_max)))
            if 'retry' in H2H and not rec['base']['strict_valid']:
                jobs.append(put('retry', ARM.arm_retry(srv, tok, prefix_ids, head, schema, sk, temp=a.temp, call_max=a.call_max)))
            if 'forbid' in H2H and site is not None:
                jobs.append(put('forbid', ARM.arm_forbid(srv, tok, prefix_ids, text, finished, schema, BAN, sk, temp=a.temp,
                                                         call_max=a.call_max)))
            if 'grammar' in H2H and not rec['base']['strict_valid']:
                jobs.append(put('grammar', ARM.arm_grammar(srv, tok, prefix_ids, text, finished, schema, sk, temp=a.temp,
                                                           call_max=a.call_max)))
            await asyncio.gather(chain_i(), do_ii(), *jobs)
            rec['h2h'] = hh
        finally:
            if pin:
                await pin.__aexit__(None, None, None)
        rec['wall'] = time.time() - t_start
    except Exception as e:
        rec['status'] = 'error'; rec['err'] = repr(e)[:500]
    await write(fo, lock, rec)


async def main():
    cs = []
    with open(a.contexts) as f:
        for i, l in enumerate(f):
            if i < a.skip:
                continue
            if len(cs) >= a.n:
                break
            cs.append(json.loads(l))
    seeds = [int(s) for s in a.seeds.split(',')]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try:
                d = json.loads(l)
            except Exception:
                continue
            if d.get('status') != 'error':
                done.add((d['id'], d['seed']))
    global BAN
    if 'forbid' in H2H:
        BAN = ARM.banned_key_tokens(tok, ['filepath', 'old_string', 'new_string', 'allow_multiple'])
        print('forbid-trigger banned tokens:', len(BAN), flush=True)
    srv = Server(a.base, a.model, conc=a.conc)
    lock = asyncio.Lock()
    todo = [(c, s) for c in cs for s in seeds if (c['id'], s) not in done]
    print(f'{len(todo)} jobs ({len(done)} done)', flush=True)
    t0 = time.time()
    with open(a.out, 'a') as fo:
        # bounded fan-out so that rendering does not get far ahead of the server
        q = asyncio.Queue()
        for job in todo:
            q.put_nowait(job)

        async def worker():
            while True:
                try:
                    c, s = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(srv, c, s, fo, lock)

        await asyncio.gather(*[worker() for _ in range(a.workers or a.conc)])
    print('done in %.0fs' % (time.time() - t0), dict(srv.stats), flush=True)
    await srv.close()

asyncio.run(main())
