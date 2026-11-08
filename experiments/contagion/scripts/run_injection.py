"""Causal injection runner: generate the next turn of real agent contexts under counterfactual histories.

Two-stage generation over /v1/completions on the raw rendered prompt (skip_special_tokens=False):
  stage 1  the model thinks (its own <|channel>thought ...) until it opens a tool call (stop on token <|tool_call>=48)
           or ends the turn (EOS: <turn|>, <|tool_response>, <eos>). max 4200 tokens ~ the harness thinking budget 4096;
           if the budget is hit inside the thought, '<channel|>' is forced (as vLLM's ThinkingTokenBudgetLogitsProcessor
           does) and the model continues (stage 1b, <=1024 tokens).
  stage 2  if a call was opened, it continues naturally until <tool_call|> (=49) or EOS/length; the call is judged
           with vLLM 0.19.1's own parser.
Sampling: the context's logged temperature/top_p (server default top_k from generation_config); per-context seeds
shared by all arms (common random numbers).
usage: run_injection.py --plan plan.jsonl --out results.jsonl [--base URL --model NAME --conc N --template old|new]
plan line: {"id": ctx_id, "pathway": "P1", "k": 1}
"""
import argparse, asyncio, json, os, sys, time, hashlib, collections, random
import httpx
sys.path.insert(0, os.path.dirname(__file__))
from transformers import AutoTokenizer
import variants as V
import gemma_protocol as gp

ap = argparse.ArgumentParser()
ap.add_argument('--plan', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--meta', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl'))
ap.add_argument('--base', default='http://127.0.0.1:8300/v1'); ap.add_argument('--model', default='gemma-4-31b')
ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
ap.add_argument('--template', default='old'); ap.add_argument('--conc', type=int, default=24)
ap.add_argument('--max_model_len', type=int, default=32768); ap.add_argument('--limit', type=int, default=0)
ap.add_argument('--temp', type=float, default=None, help='override the logged temperature')
ap.add_argument('--twostage', action='store_true')
ap.add_argument('--no_leader', action='store_true', help='disable leader-first prefix-cache scheduling')
ap.add_argument('--ctx_conc', type=int, default=0, help='contexts in flight in leader mode (default conc//6+1); keep '
                'ctx_conc x ~10.5K prompt tokens below the server KV capacity')
ap.add_argument('--decision_stop', action='store_true', help='stop an edit call right after its first string argument closes '
                '(stop strings ,old_string: / ,new_string:) -> judges the dominant slip with ~half the decode tokens')
ap.add_argument('--reverse', action='store_true', help='process the plan in reverse order (work stealing)')
ap.add_argument('--blind', action='store_true', help='never print outcome counts (pre-registered / held-out arms)')
ap.add_argument('--manifest', default='', help='workstream-P corpus manifest (CONTEXT_SCHEMA.md): sets the tool profile, harness texts, system form')
ap.add_argument('--seed_offset', type=int, default=0, help='added to every per-context seed (test-retest with new seeds)')
ap.add_argument('--skip_done_from', default='', help='comma-separated result files of other runners; their done jobs are skipped (re-read every 60 s)')
a = ap.parse_args()
if a.decision_stop:
    # Disabled 2026-11-04 10:16 UTC: the stop string ',new_string:' fires at the filepath->new_string boundary (filepath is
    # emitted first), so the judged closer is always filepath's; cross-check on 663 full-judged edits: sensitivity 0/30
    # (out/xcheck_decision_judge_A2.json). The full vLLM-parse judge is the only measurement used in this experiment.
    sys.exit('--decision_stop is disabled (unsound decision point); see out/xcheck_decision_judge_A2.json')

tok = AutoTokenizer.from_pretrained(a.tok)
if a.manifest:
    _man = json.load(open(a.manifest))
    gp.set_profile(_man['tool_profile'], tools=_man['tools'], responses=_man['harness'].get('responses'))
    gp.PROFILE['system_as_parts'] = (_man['render'].get('system_content_form', 'parts') == 'parts')
    print('profile', gp.PROFILE['name'], '| edit tool', gp.PROFILE['edit_tool'], '| keys', gp.PROFILE['path_key'], gp.PROFILE['old_key'], gp.PROFILE['new_key'], flush=True)
META = {}
for l in open(a.meta):
    m = json.loads(l); META[m['id']] = m
plan = [json.loads(l) for l in open(a.plan)]
if a.limit: plan = plan[:a.limit]
done = set()
if os.path.exists(a.out):
    for l in open(a.out):
        try:
            d = json.loads(l)
            if d.get('error') and not str(d['error']).startswith(('context_too_long', 'render:')): continue  # transient: retry
            done.add((d['id'], d['pathway'], d['k']))
        except Exception: pass
def done_in(files):
    ds = set()
    for fn in files:
        if not fn or not os.path.exists(fn): continue
        for l in open(fn):
            try:
                d = json.loads(l)
                if d.get('error') and not str(d['error']).startswith(('context_too_long', 'render:')): continue
                ds.add((d['id'], d['pathway'], d['k']))
            except Exception: pass
    return ds


OTHER = [x for x in a.skip_done_from.split(',') if x]
OTHER_DONE = done_in(OTHER); OTHER_T = time.time()
jobs = [p for p in plan if (p['id'], p['pathway'], p['k']) not in done and (p['id'], p['pathway'], p['k']) not in OTHER_DONE]
if a.reverse: jobs = jobs[::-1]
print(f'plan {len(plan)} done {len(done)} todo {len(jobs)}', flush=True)

CTX = collections.OrderedDict()


def get_ctx(cid):
    if cid in CTX:
        CTX.move_to_end(cid); return CTX[cid]
    c = V.load_context(META[cid]); CTX[cid] = c
    while len(CTX) > 64: CTX.popitem(last=False)
    return c


def seed_of(cid):
    return (int(hashlib.md5(cid.encode()).hexdigest()[:8], 16) + a.seed_offset) % (2 ** 31 - 8)


async def post(client, body, tries=6):
    for t in range(tries):
        try:
            r = await client.post(a.base + '/completions', json=body, timeout=1800)
            if r.status_code == 400:
                return {'error': r.text[:500]}
            r.raise_for_status(); return r.json()
        except Exception as e:
            if t == tries - 1: return {'error': repr(e)[:500]}
            await asyncio.sleep(5 * (t + 1))


async def post_stream(client, body_, on_first, tries=6):
    """Streaming completion; on_first() fires when the first token arrives (= prefill done, prompt blocks cached and
    pinned while this request keeps generating). Returns the same shape as the non-streaming response."""
    b = dict(body_); b['stream'] = True; b['stream_options'] = {'include_usage': True}
    fired = [False]

    def fire():
        if not fired[0]:
            fired[0] = True
            try: on_first()
            except Exception: pass
    for t in range(tries):
        try:
            text = []; fin = None; stop = None; usage = None
            async with client.stream('POST', a.base + '/completions', json=b, timeout=1800) as r:
                if r.status_code == 400:
                    msg = (await r.aread()).decode(errors='replace')[:500]; fire(); return {'error': msg}
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith('data: '): continue
                    data = line[6:].strip()
                    if data == '[DONE]': break
                    ch = json.loads(data)
                    if ch.get('usage'): usage = ch['usage']
                    for c in ch.get('choices') or []:
                        fire()
                        text.append(c.get('text') or '')
                        if c.get('finish_reason'): fin = c['finish_reason']; stop = c.get('stop_reason')
            fire()
            return {'choices': [{'text': ''.join(text), 'finish_reason': fin, 'stop_reason': stop}],
                    'usage': usage or {'completion_tokens': None}}
        except Exception as e:
            if t == tries - 1: fire(); return {'error': repr(e)[:500]}
            await asyncio.sleep(5 * (t + 1))


DECISION_STOPS = [',old_string:', ',new_string:']


def body(prompt, max_tokens, temp, top_p, seed, stop_ids):
    b = {'model': a.model, 'prompt': prompt, 'max_tokens': max_tokens, 'temperature': temp, 'top_p': top_p, 'seed': seed,
         'stop_token_ids': stop_ids, 'skip_special_tokens': False, 'spaces_between_special_tokens': False,
         'include_stop_str_in_output': False}
    if a.decision_stop and 49 in stop_ids:
        b['stop'] = DECISION_STOPS
    return b


def thought_span(prompt, text):
    """(start, end) character span of the model's own thought inside `text` (end = index of '<channel|>' or len)."""
    if prompt.endswith('<|channel>thought\n'):
        st = 0
    else:
        i = text.find('<|channel>')
        if i < 0: return None
        st = i
    j = text.find('<channel|>', st)
    return (st, j if j >= 0 else len(text))


async def finish_call(client, prefix, temp, top_p, seed, rec):
    """Continue after an opened '<|tool_call>' and judge the call."""
    used = len(tok(prefix, add_special_tokens=False)['input_ids'])
    mt = min(4096, a.max_model_len - used - 8)
    if mt < 64:
        rec['error'] = 'no_room_call'; return False
    r2 = await post(client, body(prefix + '<|tool_call>', mt, temp, top_p, seed, [49]))
    if 'error' in r2:
        rec['error'] = 'call:' + r2['error']; return False
    c2 = r2['choices'][0]; t2 = c2['text']; closed = (c2.get('stop_reason') == 49)
    if t2.endswith('<tool_call|>'): t2 = t2[:-len('<tool_call|>')]; closed = True
    rec['s2_finish'] = c2.get('finish_reason'); rec['s2_stop'] = c2.get('stop_reason'); rec['s2_text'] = t2
    rec['judge'] = gp.judge(t2, closed)
    return True


async def one_stage(client, prompt, room, temp, top_p, s0, rec, on_first=None):
    """One request: think + open + complete the first call (stop at <tool_call|>); the 4096-token thinking budget is
    applied post hoc (thought truncated at 4096 tokens, '<channel|>' forced, continuation regenerated)."""
    if on_first is not None:
        r = await post_stream(client, body(prompt, min(7168, room), temp, top_p, s0, [49]), on_first)
    else:
        r = await post(client, body(prompt, min(7168, room), temp, top_p, s0, [49]))
    if 'error' in r:
        rec['error'] = 'gen:' + r['error']; return False
    c = r['choices'][0]; text = c['text']
    rec['s1_finish'] = c.get('finish_reason'); rec['s1_stop'] = c.get('stop_reason'); rec['s1_tokens'] = r['usage']['completion_tokens']
    span = thought_span(prompt, text)
    th_tokens = len(tok(text[span[0]:span[1]], add_special_tokens=False)['input_ids']) if span else 0
    rec['thought_tokens'] = th_tokens
    if span and th_tokens > 4096:
        ids = tok(text[span[0]:span[1]], add_special_tokens=False)['input_ids'][:4096]
        prefix = prompt + text[:span[0]] + tok.decode(ids, skip_special_tokens=False) + '<channel|>'
        rec['budget_forced'] = True
        r1b = await post(client, body(prefix, min(1024, max(64, a.max_model_len - len(tok(prefix, add_special_tokens=False)['input_ids']) - 4200)), temp, top_p, s0 + 1, [48]))
        if 'error' in r1b:
            rec['error'] = 'stage1b:' + r1b['error']; return False
        c1b = r1b['choices'][0]; rec['s1b_text'] = c1b['text'][-2000:]
        rec['s1_text'] = text[:span[0]] + tok.decode(ids, skip_special_tokens=False) + '<channel|>' + c1b['text']
        if c1b.get('stop_reason') == 48:
            rec['opened_call'] = True
            return await finish_call(client, prefix + c1b['text'], temp, top_p, s0 + 2, rec)
        rec['opened_call'] = False; return True
    if a.decision_stop and c.get('finish_reason') == 'stop' and c.get('stop_reason') in DECISION_STOPS and '<|tool_call>' not in text:
        # decision stop string appeared inside the thought: continue without stopping there (up to 3 times)
        for _ in range(3):
            text = text + c['stop_reason']
            r = await post(client, body(prompt + text, min(7168, room - len(tok(text, add_special_tokens=False)['input_ids'])), temp, top_p, s0 + 3, [49]))
            if 'error' in r:
                rec['error'] = 'gen_cont:' + r['error']; return False
            c = r['choices'][0]; text = text + c['text']
            if not (c.get('finish_reason') == 'stop' and c.get('stop_reason') in DECISION_STOPS and '<|tool_call>' not in text): break
        rec['s1_finish'] = c.get('finish_reason'); rec['s1_stop'] = c.get('stop_reason')
    i = text.find('<|tool_call>')
    if i < 0:
        rec['s1_text'] = text; rec['opened_call'] = False; return True
    if a.decision_stop and c.get('finish_reason') == 'stop' and c.get('stop_reason') in DECISION_STOPS:
        rec['s1_text'] = text[:i]; rec['opened_call'] = True
        t2 = text[i + len('<|tool_call>'):]
        rec['s2_text'] = t2; rec['s2_finish'] = 'decision_stop'
        rec['judge'] = gp.judge_decision(t2, c.get('stop_reason'))
        return True
    rec['s1_text'] = text[:i]; rec['opened_call'] = True
    t2 = text[i + len('<|tool_call>'):]
    closed = (c.get('stop_reason') == 49)
    if t2.endswith('<tool_call|>'): t2 = t2[:-len('<tool_call|>')]; closed = True
    rec['s2_text'] = t2; rec['s2_finish'] = c.get('finish_reason')
    rec['judge'] = gp.judge(t2, closed)
    return True


async def two_stage(client, prompt, room, temp, top_p, s0, rec):
    r1 = await post(client, body(prompt, min(4200, room - 300), temp, top_p, s0, [48]))
    if 'error' in r1:
        rec['error'] = 'stage1:' + r1['error']; return False
    c1 = r1['choices'][0]; t1 = c1['text']; rec['s1_finish'] = c1.get('finish_reason'); rec['s1_stop'] = c1.get('stop_reason')
    rec['s1_tokens'] = r1['usage']['completion_tokens']
    opened = (c1.get('stop_reason') == 48)
    prefix = prompt + t1
    if not opened and c1.get('finish_reason') == 'length':
        starts_in_thought = prompt.endswith('<|channel>thought\n')
        open_thought = (t1.rfind('<|channel>') > t1.rfind('<channel|>')) or (starts_in_thought and '<channel|>' not in t1)
        rec['budget_forced'] = bool(open_thought)
        if open_thought:
            prefix = prefix + '<channel|>'
            r1b = await post(client, body(prefix, min(1024, max(64, room - rec['s1_tokens'] - 64)), temp, top_p, s0 + 1, [48]))
            if 'error' in r1b:
                rec['error'] = 'stage1b:' + r1b['error']; return False
            c1b = r1b['choices'][0]; t1b = c1b['text']; prefix = prefix + t1b
            rec['s1b_finish'] = c1b.get('finish_reason'); rec['s1b_text'] = t1b[-2000:]
            opened = (c1b.get('stop_reason') == 48)
    rec['s1_text'] = t1
    rec['opened_call'] = bool(opened)
    if opened:
        return await finish_call(client, prefix, temp, top_p, s0 + 2, rec)
    return True


STATS = collections.defaultdict(lambda: [0, 0, 0])  # arm -> [n, edit, malformed_edit]
T0 = time.time(); NDONE = 0


async def run_job(client, sem, job, fo, on_first=None):
    global NDONE, OTHER_DONE, OTHER_T
    release = on_first if on_first is not None else (lambda: None)
    if OTHER:
        if time.time() - OTHER_T > 60:
            OTHER_DONE = done_in(OTHER); OTHER_T = time.time()
        if (job['id'], job['pathway'], job['k']) in OTHER_DONE: release(); return
    meta = META[job['id']]
    temp = a.temp if a.temp is not None else (meta['temp'] if meta['temp'] is not None else 0.2)
    top_p = meta['top_p'] if meta['top_p'] is not None else 0.95
    s0 = seed_of(job['id'])
    async with sem:
        try:
            prompt, info = V.build_prompt(tok, meta, job['pathway'], job['k'], which=a.template, ctx=get_ctx(job['id']))
        except Exception as e:
            release(); fo.write(json.dumps({**job, 'error': 'render:' + repr(e)[:300]}) + '\n'); fo.flush(); return
        n_prompt = len(tok(prompt, add_special_tokens=False)['input_ids'])
        room = a.max_model_len - n_prompt - 8
        rec = {**job, 'template': a.template, 'model': a.model, 'server': a.base, 'temp': temp, 'top_p': top_p, 'seed': s0, 'n_prompt': n_prompt,
               'p1_missing': info.get('missing')}
        if room < 600:
            release(); rec['error'] = 'context_too_long'; fo.write(json.dumps(rec) + '\n'); fo.flush(); return
        if a.twostage:
            release(); ok = await two_stage(client, prompt, room, temp, top_p, s0, rec)
        else:
            ok = await one_stage(client, prompt, room, temp, top_p, s0, rec, on_first=on_first)
        release()
        if not ok:
            fo.write(json.dumps(rec) + '\n'); fo.flush(); return
        fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()
    arm = f"{job['pathway']}k{job['k']}"
    st = STATS[arm]; st[0] += 1
    j = rec.get('judge') or {}
    if j.get('is_edit', j.get('name') == 'edit_file'):
        st[1] += 1; st[2] += int(bool(j.get('malformed')))
    NDONE += 1
    if NDONE % 50 == 0:
        el = time.time() - T0
        msg = f'[{time.strftime("%H:%M:%S")}] done {NDONE}/{len(jobs)} rate {NDONE / el:.2f}/s eta {(len(jobs) - NDONE) / max(1e-9, NDONE / el) / 3600:.2f}h'
        if not a.blind: msg += ' | ' + ' '.join(f'{k}:{v[2]}/{v[1]}/{v[0]}' for k, v in sorted(STATS.items()))
        print(msg, flush=True)


async def run_context(client, sem, csem, cjobs, fo):
    """Leader first (P0 if present): its prompt blocks are computed once and stay pinned while it generates; the other
    arms of the same context are released when the leader's first token arrives and reuse the shared prefix."""
    async with csem:
        cjobs = sorted(cjobs, key=lambda j: (j['pathway'] != 'P0', j['k']))
        ev = asyncio.Event()
        lead = asyncio.create_task(run_job(client, sem, cjobs[0], fo, on_first=ev.set))
        try:
            await asyncio.wait_for(ev.wait(), timeout=2400)
        except asyncio.TimeoutError:
            pass
        rest = [asyncio.create_task(run_job(client, sem, j, fo)) for j in cjobs[1:]]
        await asyncio.gather(lead, *rest)


async def main_leader():
    sem = asyncio.Semaphore(a.conc)
    ncx = a.ctx_conc if a.ctx_conc > 0 else max(1, a.conc // 6 + 1)
    csem = asyncio.Semaphore(ncx)
    limits = httpx.Limits(max_connections=a.conc + 8, max_keepalive_connections=a.conc + 8)
    by_ctx = collections.OrderedDict()
    for j in jobs: by_ctx.setdefault((j.get('tier', ''), j['id']), []).append(j)  # tiers run in plan order
    async with httpx.AsyncClient(limits=limits) as client:
        with open(a.out, 'a') as fo:
            pending = set()
            for cid, cj in by_ctx.items():
                pending.add(asyncio.create_task(run_context(client, sem, csem, cj, fo)))
                if len(pending) >= ncx * 2:
                    _, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            if pending: await asyncio.wait(pending)
    print('finished', NDONE, 'in %.1f min' % ((time.time() - T0) / 60), flush=True)


async def main():
    sem = asyncio.Semaphore(a.conc)
    limits = httpx.Limits(max_connections=a.conc + 8, max_keepalive_connections=a.conc + 8)
    async with httpx.AsyncClient(limits=limits) as client:
        with open(a.out, 'a') as fo:
            # bounded task fan-out keeps arms of the same context adjacent in time (prefix-cache reuse)
            pending = set(); it = iter(jobs)
            for job in it:
                pending.add(asyncio.create_task(run_job(client, sem, job, fo)))
                if len(pending) >= a.conc * 2:
                    done_, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            if pending: await asyncio.wait(pending)
    print('finished', NDONE, 'in %.1f min' % ((time.time() - T0) / 60), flush=True)

asyncio.run(main() if (a.no_leader or a.twostage) else main_leader())
