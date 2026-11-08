"""PREREG_v2.4 injected-slip repair battery -- GPU RUNNER (sha256 logged in PROGRESS.md before any data).

Per state (v24/battery_inputs.jsonl, built by build_battery.py):
  prefix  = P's exact prompt (manifest template, system as parts; token count re-verified == logged prompt_tokens)
            + the logged raw text before the call + '<|tool_call>'                       [the call head; pinned in cache]
  slipped = the logged call text up to the closing <|"|> of new_string, that delimiter replaced by the stratum's closer
  LIVE    : the 31B continues `slipped` (thinking already closed in the teacher-forced prefix), P's sampling
            T=1.0 / top_p 0.95 / top_k 64, stop '<tool_call|>', one seed per state  ->  emission = slipped + continuation
  arms (B's frozen code, confirm/ copies: gemma_protocol b8dac830, intent_decode bda60a08, arms 5a521ae8):
    IPD (i+)   : rollback_resume(emission) -- strictly valid -> unchanged (guard); else noisy-channel cut + frozen
                 closer prior, closer+opener rules, true delimiter forced, resumed (<= 4 rounds); T=1.0, same seed
    grammar-CD : arm_grammar(emission) (longest grammatical prefix + forced legal continuation, <= 6 rounds), T=1.0
    retry x2   : only if the emission is strictly invalid: arm_retry from the call head (whole call resampled, T=1.0,
                 new seeds derived from the state seed), else the emission is delivered
    greedy     : arm_greedy from the call head (T=0)
    lenient / fail-loud / T1 are text-only and computed by analyze_battery.py from the emission.
usage: run_battery.py --out <jsonl> [--base URL] [--conc 22 --workers 10] [--n N] [--mock]
"""
import argparse, asyncio, copy, hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(B, 'confirm'))           # frozen copies only
from transformers import AutoTokenizer  # noqa: E402
from gemma_protocol import TC_START, TC_END, schema_from_tools, is_valid  # noqa: E402
from intent_decode import Server, rollback_resume, ChannelPrior, ids_of, Pin  # noqa: E402
import arms as ARM  # noqa: E402

CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
TOKP = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')
ap = argparse.ArgumentParser()
ap.add_argument('--inputs', default=os.path.join(HERE, 'battery_inputs.jsonl'))
ap.add_argument('--out', required=True)
ap.add_argument('--base', default='http://127.0.0.1:8302/v1')
ap.add_argument('--model', default='gemma-4-31b')
ap.add_argument('--conc', type=int, default=22)
ap.add_argument('--workers', type=int, default=10)
ap.add_argument('--n', type=int, default=600)
ap.add_argument('--call_max', type=int, default=4096)
ap.add_argument('--mock', action='store_true', help='CPU dry run against an in-process echo backend (no model)')
a = ap.parse_args()

MAN = json.load(open(os.path.join(CORPUS, 'manifest.json')))
TOOLS = MAN['tools']
SCHEMA = schema_from_tools(TOOLS)
TPL = open(os.path.join(CORPUS, MAN['render']['chat_template_path'])).read()
KW = MAN['render'].get('chat_template_kwargs', {'enable_thinking': True})
SAMP = MAN['sampling']
TEMP, TOP_P, TOP_K = float(SAMP['temperature']), float(SAMP['top_p']), SAMP.get('top_k')
assert (TEMP, TOP_P, TOP_K) == (1.0, 0.95, 64), (TEMP, TOP_P, TOP_K)   # PREREG_v2.4: P's sampling
tok = AutoTokenizer.from_pretrained(TOKP)
_pj = json.load(open(os.path.join(B, 'confirm', 'prior_ft_edit.json')))
PRIOR = ChannelPrior(_pj['counts'], _pj.get('alpha', 0.5), name='ft_edit_frozen')


def render(c):
    msgs = []
    for i, m in enumerate(c['messages']):
        m = copy.deepcopy(m)
        for t in m.get('tool_calls') or []:
            f = t['function']
            if isinstance(f.get('arguments'), str):
                f['arguments'] = json.loads(f['arguments']) if f['arguments'] else {}
        if i == 0 and m.get('role') == 'system' and isinstance(m.get('content'), str):
            m['content'] = [{'type': 'text', 'text': m['content']}]
        msgs.append(m)
    return tok.apply_chat_template(msgs, tools=TOOLS, add_generation_prompt=True, tokenize=False, chat_template=TPL, **KW)


class _Skip(Exception):
    pass


def fin_of(c):
    return c.get('finish_reason') == 'stop' and c.get('stop_reason') == TC_END


async def one(srv, x, c, fo, lock):
    rec = {k: x[k] for k in ('context_id', 'episode_id', 'turn_index', 'repo', 'split', 'accepted_rank', 'stratum', 'closer', 'seed')}
    t0 = time.time()
    try:
        p0 = render(c)
        n0 = len(ids_of(tok, p0))
        if n0 != c['prompt_tokens']:
            rec.update(status='render_mismatch', render_tokens=n0)
            raise _Skip()
        head_text = p0 + x['pre_call_text'] + TC_START
        pid = ids_of(tok, head_text)
        slipped = x['slipped_call_prefix']
        s = int(x['seed'])
        async with Pin(srv, pid):
            lv = await srv.complete(pid + ids_of(tok, slipped), max_tokens=a.call_max, stop=[TC_END], temperature=TEMP,
                                    top_p=TOP_P, seed=s, tag='live')
            em, fin = slipped + lv['text'], fin_of(lv)
            rec['live'] = {'continuation': lv['text'], 'finished': fin, 'finish_reason': lv.get('finish_reason'),
                           'tokens': lv['_usage'].get('completion_tokens'), 'latency': lv['_latency']}
            valid = bool(fin and is_valid(em, SCHEMA))
            rec['emission_strictly_valid'] = valid
            arms = {}

            async def ipd():
                t1 = time.time()
                if valid:
                    arms['IPD'] = {'text': em, 'finished': fin, 'changed': False, 'rounds': 0, 'tokens': 0, 'latency': 0.0}
                    return
                r = await rollback_resume(srv, tok, head_text, em, fin, SCHEMA, rule='nc', prior=PRIOR,
                                          rules=('closer', 'opener'), max_tokens=a.call_max, temperature=TEMP,
                                          top_p=TOP_P, seed=s, prefix_ids=pid)
                arms['IPD'] = {'text': r['text'], 'finished': r['finished'], 'changed': r['changed'],
                               'rounds': len(r['rounds']), 'cut_choice': [z['cut_choice'] for z in r['rounds']],
                               'tokens': sum(z.get('gen_tokens') or 0 for z in r['rounds']),
                               'score_requests': sum((z['cut_choice'] or {}).get('requests', 0) for z in r['rounds']),
                               'latency': time.time() - t1}

            async def put(name, coro):
                t1 = time.time()
                arms[name] = await coro
                arms[name]['wall'] = time.time() - t1
            jobs = [ipd(), put('grammar_CD', ARM.arm_grammar(srv, tok, pid, em, fin, SCHEMA, s, temp=TEMP, call_max=a.call_max)),
                    put('greedy', ARM.arm_greedy(srv, tok, pid, '', SCHEMA, call_max=a.call_max))]
            if not valid:
                jobs.append(put('retry_x2', ARM.arm_retry(srv, tok, pid, '', SCHEMA, s, temp=TEMP, call_max=a.call_max)))
            await asyncio.gather(*jobs)
        rec.update(status='ok', emission=em, arms=arms, wall=time.time() - t0)
    except _Skip:
        pass
    except Exception as e:
        rec.update(status='error', err=repr(e)[:400])
    async with lock:
        fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()


async def main():
    xs = [json.loads(l) for l in open(a.inputs)][:a.n]
    want = {x['context_id'] for x in xs}
    ctx = {}
    for l in open(os.path.join(CORPUS, 'contexts.jsonl')):
        d = json.loads(l)
        if d['context_id'] in want:
            ctx[d['context_id']] = d
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            d = json.loads(l)
            if d.get('status') in ('ok', 'render_mismatch'):
                done.add(d['context_id'])
    todo = [x for x in xs if x['context_id'] not in done]
    base = a.base
    runner = None
    if a.mock:
        sys.path.insert(0, HERE)
        import mock_backend
        runner, base = await mock_backend.start(tok)
    print(f'{len(todo)} states to run ({len(done)} done); base {base}; T={TEMP} top_p={TOP_P} top_k={TOP_K} call_max={a.call_max}', flush=True)
    srv = Server(base, a.model, conc=a.conc, sampling_extra={'top_k': int(TOP_K)})
    lock = asyncio.Lock(); q = asyncio.Queue()
    for x in todo:
        q.put_nowait(x)
    with open(a.out, 'a') as fo:
        async def worker():
            while True:
                try:
                    x = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(srv, x, ctx[x['context_id']], fo, lock)
        await asyncio.gather(*[worker() for _ in range(a.workers)])
    print('done', dict(srv.stats), flush=True)
    await srv.close()
    if runner is not None:
        await runner.cleanup()

asyncio.run(main())
