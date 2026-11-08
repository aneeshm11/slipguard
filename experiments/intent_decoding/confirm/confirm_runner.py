"""FROZEN confirmatory runner (workstream B, PREREG_v2 §3.2: C12-C16) for workstream P's public corpus.
Pool B1 (first-edit states, stratum S1; S2 = separate stratum), Gemma-4-31B-QAT, thinking ON, P's sampling.
For every pool state, in rank order:
  1. render the logged messages EXACTLY as P's server did (manifest template + kwargs; system content as text parts
     when the manifest says so; tool-call arguments as dicts) and require token-count equality with `prompt_tokens`
     (else the state is recorded as render_mismatch and skipped, never silently replaced);
  2. base decoding with P's sampling (temperature, top_p, top_k from the manifest); thinking budget emulated exactly:
     thought generated up to `thinking_token_budget` tokens (stop at '<channel|>'), '<channel|>' forced if exhausted,
     then the answer/tool call up to the manifest max_tokens;
  3. the natural next call is recorded; if it is not the edit tool, an edit call is forced in the same state
     (same procedure as the discovery runs; forced samples are flagged);
  4. arms on the SAME baseline sample, prefix pinned: IPD (i+) [noisy-channel cut, frozen closer prior, closer+opener
     rules], retry x2 (P's sampling), greedy (T=0), grammar-CD (exact emulation; P's sampling). T1 text-only and the
     lenient / fail-loud policies are computed offline by confirm_analyze.py.
Never opens an outcomes file.  usage:
  confirm_runner.py --pools_dir <.../confirmatory/pools> [--stratum S1] [--pool B1] --out <jsonl> [--n 600]
"""
import argparse, asyncio, copy, hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                     # frozen copies only
from transformers import AutoTokenizer
from gemma_protocol import (D, TC_START, TC_END, schema_from_tools, is_valid, first_slip_site, census_judge, parse_strict,
                            schema_problems)
from intent_decode import Server, rollback_resume, ChannelPrior, ids_of, Pin
import arms as ARM

CONTAGION = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser()
ap.add_argument('--pools_dir', required=True)
ap.add_argument('--stratum', default='S1')
ap.add_argument('--pool', default='B1')
ap.add_argument('--base', default='http://127.0.0.1:8302/v1')
ap.add_argument('--model', default='gemma-4-31b')
ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
ap.add_argument('--out', required=True)
ap.add_argument('--n', type=int, default=600)
ap.add_argument('--conc', type=int, default=16)
ap.add_argument('--workers', type=int, default=8)
a = ap.parse_args()

PM = json.load(open(os.path.join(a.pools_dir, 'POOLS_MANIFEST.json')))
SM = PM[a.stratum]
man_path = SM['corpus_manifest'] if os.path.isabs(SM['corpus_manifest']) else os.path.join(CONTAGION, SM['corpus_manifest'])
MAN = json.load(open(man_path))
BASE_DIR = os.path.dirname(os.path.abspath(man_path))
ctx_file = MAN['files']['contexts']
ctx_file = ctx_file if os.path.isabs(ctx_file) else os.path.join(BASE_DIR, ctx_file)
assert 'outcome' not in os.path.basename(ctx_file).lower(), 'refusing to read an outcomes file'
TPL = open(MAN['render']['chat_template_path']).read()
KW = MAN['render'].get('chat_template_kwargs', {'enable_thinking': True})
PARTS = MAN['render'].get('system_content_form', 'parts') == 'parts'
SAMP = MAN.get('sampling', {})
TEMP = float(SAMP.get('temperature', 1.0))
TOP_P = float(SAMP.get('top_p', 0.95))
TOP_K = SAMP.get('top_k')
MAX_TOK = int(SAMP.get('max_tokens') or 8192)
BUDGET = SAMP.get('thinking_token_budget')
EDIT = (MAN.get('harness') or {}).get('edit_tool', {}).get('name', 'edit_file')
tok = AutoTokenizer.from_pretrained(a.tok)
_pj = json.load(open(os.path.join(HERE, 'prior_ft_edit.json')))
PRIOR = ChannelPrior(_pj['counts'], _pj.get('alpha', 0.5), name='ft_edit_frozen')


def to_template_messages(msgs, parts):
    """vLLM 0.19.1 chat path: tool-call arguments -> dicts; string system content -> text parts (if declared)."""
    out = []
    for i, m in enumerate(msgs):
        m = copy.deepcopy(m)
        for t in m.get('tool_calls') or []:
            f = t['function']
            if isinstance(f.get('arguments'), str):
                try:
                    f['arguments'] = json.loads(f['arguments']) if f['arguments'] else {}
                except Exception:
                    f['arguments'] = {}
        if i == 0 and m.get('role') == 'system' and isinstance(m.get('content'), str) and parts:
            m['content'] = [{'type': 'text', 'text': m['content']}]
        out.append(m)
    return out


def render(c, tools):
    """-> (prompt, n_tokens, form_used) ; tries the declared system form first, then the other one."""
    for parts in (PARTS, not PARTS):
        s = tok.apply_chat_template(to_template_messages(c['messages'], parts), tools=tools, add_generation_prompt=True,
                                    tokenize=False, chat_template=c.get('_template_text') or TPL, **KW)
        n = len(tok(s, add_special_tokens=False)['input_ids'])
        if n == c.get('prompt_tokens'):
            return s, n, ('parts' if parts else 'string')
    return s, n, None


def judge(text, finished, schema):
    ok, why, _ = census_judge(text, schema) if finished else (False, 'no_close', {})
    sp = parse_strict(text)
    probs = schema_problems(sp, schema) if sp.ok else ['struct:' + sp.error]
    return {'census_ok': ok, 'census_why': why, 'strict_valid': bool(sp.ok and not probs and finished), 'strict_probs': probs[:4]}


async def stage_a(srv, p0, seed):
    """base decoding up to the end of the first tool call; thinking budget emulated."""
    used = 0
    pre = ''
    if BUDGET and p0.endswith('<|channel>thought\n'):
        c1 = await srv.complete(p0, max_tokens=int(BUDGET), stop=['<channel|>'], temperature=TEMP, top_p=TOP_P, seed=seed, tag='think')
        used = c1['_usage'].get('completion_tokens') or 0
        pre = c1['text'] + '<channel|>'
        budget_hit = c1.get('finish_reason') == 'length'
    else:
        budget_hit = None
    c2 = await srv.complete(p0 + pre, max_tokens=max(256, MAX_TOK - used), stop=[TC_END], temperature=TEMP, top_p=TOP_P,
                            seed=seed + 1, tag='answer')
    t = pre + c2['text']
    fin = c2.get('finish_reason') == 'stop' and c2.get('stop_reason') == TC_END
    return t, fin, budget_hit


async def one(srv, row, c, fo, lock):
    rec = {k: row.get(k) for k in ('context_id', 'episode_id', 'task_id', 'repo', 'turn_index', 'rank', 'half', 'rank_hash')}
    rec.update(stratum=a.stratum, pool=a.pool, edit_tool=EDIT, temperature=TEMP, top_p=TOP_P, top_k=TOP_K)
    t0 = time.time()
    try:
        tools = c.get('tools') or MAN['tools']
        schema = schema_from_tools(tools)
        p0, ntok, form = render(c, tools)
        rec['render_tokens'] = ntok; rec['logged_prompt_tokens'] = c.get('prompt_tokens'); rec['system_form'] = form
        if form is None:
            rec['status'] = 'render_mismatch'
            async with lock:
                fo.write(json.dumps(rec) + '\n'); fo.flush()
            return
        seed = int(hashlib.sha256(('B|' + str(row.get('context_id'))).encode()).hexdigest()[:8], 16)
        t, fin, budget_hit = await stage_a(srv, p0, seed)
        rec['budget_hit'] = budget_hit
        if TC_START not in t:
            rec.update(status='no_call', A_tail=t[-300:])
            async with lock:
                fo.write(json.dumps(rec) + '\n'); fo.flush()
            return
        i = t.index(TC_START)
        rec['A_text'] = t[:i]
        call = t[i + len(TC_START):]
        prefix = p0 + t[:i] + TC_START
        sp = parse_strict(call)
        nat = sp.name if sp.name else call.split('{')[0][:40]
        rec['natural_tool'] = nat
        head = ''
        if nat != EDIT:
            rec['natural_call'] = {'text': call[:4000], 'finished': fin, 'judge': judge(call, fin, schema)}
            head = 'call:' + EDIT + '{'
            cc = await srv.complete(prefix + head, max_tokens=2048, stop=[TC_END], temperature=TEMP, top_p=TOP_P,
                                    seed=seed + 2, tag='forced')
            call = head + cc['text']
            fin = cc.get('finish_reason') == 'stop' and cc.get('stop_reason') == TC_END
            rec['forced'] = True
        else:
            rec['forced'] = False
        rec.update(status='call', call=call, finished=fin, base=judge(call, fin, schema))
        site = first_slip_site(call, schema, finished=fin)
        rec['site'] = None if site is None else {'key': site.key, 'next_key': site.next_key, 'kind': site.kind,
                                                 'run': site.run, 'gap': site.gap, 'pos': site.run_start}
        pid = ids_of(tok, prefix)
        arms = {}
        async with Pin(srv, pid):
            async def ipd():
                if is_valid(call, schema):
                    arms['IPD'] = {'text': call, 'finished': fin, 'changed': False, 'rounds': 0}
                    return
                r = await rollback_resume(srv, tok, prefix, call, fin, schema, rule='nc', prior=PRIOR,
                                          rules=('closer', 'opener'), temperature=TEMP, top_p=TOP_P, seed=seed + 10,
                                          prefix_ids=pid)
                arms['IPD'] = {'text': r['text'], 'finished': r['finished'], 'changed': r['changed'],
                               'rounds': len(r['rounds']), 'cut_choice': [x['cut_choice'] for x in r['rounds']]}

            async def put(name, coro):
                arms[name] = await coro
            jobs = [ipd(), put('greedy', ARM.arm_greedy(srv, tok, pid, head, schema))]
            if not rec['base']['strict_valid']:
                jobs.append(put('retry_x2', ARM.arm_retry(srv, tok, pid, head, schema, seed % 100000, temp=TEMP)))
                jobs.append(put('grammar_CD', ARM.arm_grammar(srv, tok, pid, call, fin, schema, seed % 100000, temp=TEMP)))
            await asyncio.gather(*jobs)
        rec['arms'] = arms
        rec['wall'] = time.time() - t0
    except Exception as e:
        rec['status'] = 'error'; rec['err'] = repr(e)[:400]
    async with lock:
        fo.write(json.dumps(rec) + '\n'); fo.flush()


async def main():
    rows = [json.loads(l) for l in open(os.path.join(a.pools_dir, f'{a.stratum}_{a.pool}.jsonl'))]
    rows.sort(key=lambda r: r.get('rank', 0))
    rows = rows[:a.n]
    want = {r['context_id'] for r in rows}
    ctx = {}
    with open(ctx_file) as f:
        for l in f:
            d = json.loads(l)
            if d.get('context_id') in want:
                if d.get('template'):
                    d['_template_text'] = open(d['template']).read() if os.path.exists(str(d['template'])) else None
                ctx[d['context_id']] = d
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            x = json.loads(l)
            if x.get('status') in ('call', 'no_call', 'render_mismatch'):
                done.add(x['context_id'])
    rows = [r for r in rows if r['context_id'] not in done and r['context_id'] in ctx]
    print(f'{len(rows)} states to run ({len(done)} done); manifest {man_path}; T={TEMP} top_p={TOP_P} top_k={TOP_K} '
          f'budget={BUDGET} max_tokens={MAX_TOK} edit_tool={EDIT}', flush=True)
    srv = Server(a.base, a.model, conc=a.conc, sampling_extra=({'top_k': int(TOP_K)} if TOP_K else None))
    lock = asyncio.Lock()
    q = asyncio.Queue()
    for r in rows:
        q.put_nowait(r)
    with open(a.out, 'a') as fo:
        async def worker():
            while True:
                try:
                    r = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(srv, r, ctx[r['context_id']], fo, lock)
        await asyncio.gather(*[worker() for _ in range(a.workers)])
    print('done', dict(srv.stats), flush=True)
    await srv.close()

asyncio.run(main())
