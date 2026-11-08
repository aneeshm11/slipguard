"""Workstream X runner, format-general (benchmark extension, prereg_ext.md): generate the next assistant turn of
pre-rendered prompts (text for HF-template formats, TOKEN IDS for harmony / mistral) and judge the first tool call.
Per-format: stop tokens (Qwen: <|im_end|>/<|endoftext|>; harmony: <|return|>/<|call|>/<|endoftext|>; mistral: </s>),
detokenisation (mistral: skip_special_tokens=True as the production server), thinking budget (Qwen think models:
'</think>'; harmony: the analysis message ends with '<|end|>' and is forced closed with '<|end|><|start|>assistant';
non-thinking models: none). Everything else as run_qwen.py (registered discovery runner).

One streamed /v1/completions request per job on the raw rendered prompt (special tokens kept, no server-side tool or
reasoning parser involved; the production parsers are applied offline by qwenproto.judge):
  * sampling: the context's logged temperature / top_p, top_k = 20 (Qwen model cards), per-context seed shared by all
    arms of the context (common random numbers);
  * stop: EOS only (<|im_end|>, <|endoftext|>), so a '</tool_call>' written inside the thought cannot cut the turn;
    max 7,168 new tokens (as workstream A);
  * thinking budget 4,096 tokens applied post hoc as in A (= vLLM's ThinkingTokenBudgetLogitsProcessor, which forces the
    reasoning-end token): if the thought exceeds 4,096 tokens (the stream is aborted once ~4,160 tokens pass without
    '</think>'), the thought is cut at 4,096 tokens, '</think>' is appended and the continuation is generated
    (<= 5,120 tokens, seed + 1);
  * leader-first prefix-cache scheduling (A): the first job of a context group (P0, or the single census job) is
    streamed first; the other arms are released when its first token arrives.
usage: run_qwen.py --prompts data/prompts_<mk>.jsonl --out out/gen_<mk>.jsonl --mk <model_key> --base URL --served NAME
"""
import argparse
import asyncio
import collections
import json
import os
import sys
import time

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qwenproto as qp  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--prompts', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--mk', required=True, choices=sorted(qp.MODELS))
ap.add_argument('--base', required=True); ap.add_argument('--served', required=True)
ap.add_argument('--conc', type=int, default=32); ap.add_argument('--ctx_conc', type=int, default=6)
ap.add_argument('--max_model_len', type=int, default=0, help='0 = read from /v1/models')
ap.add_argument('--top_k', type=int, default=20); ap.add_argument('--budget', type=int, default=4096)
ap.add_argument('--max_new', type=int, default=7168)
ap.add_argument('--sets', default='battery,census'); ap.add_argument('--arms', default='')
ap.add_argument('--limit_ctx', type=int, default=0, help='only the first N context groups (pilot)')
ap.add_argument('--skip_done_from', default='')
a = ap.parse_args()

FMT = qp.MODELS[a.mk]['fmt']
THINK = qp.thinking(a.mk)
SKIP_SPECIAL = qp.MODELS[a.mk].get('skip_special_tokens', False)
if FMT == 'harmony':
    import fmt_ext as fe
    STOP_IDS = [200002, 200012, 199999]  # <|return|>, <|call|>, <|endoftext|>
    def tok_count(t): return len(fe.harmony_encode(t))
    def tok_cut(t, n): return fe.harmony_decode(fe.harmony_encode(t)[:n])
elif FMT == 'mistral':
    STOP_IDS = [2]  # </s>
    def tok_count(t): return 0
    def tok_cut(t, n): return t
else:
    TOK = qp.hf_tok(a.mk)
    STOP_IDS = [TOK.convert_tokens_to_ids('<|im_end|>'), TOK.convert_tokens_to_ids('<|endoftext|>')]
    def tok_count(t): return len(TOK(t, add_special_tokens=False)['input_ids'])
    def tok_cut(t, n): return TOK.decode(TOK(t, add_special_tokens=False)['input_ids'][:n], skip_special_tokens=False)
THINK_END = '<|end|>' if FMT == 'harmony' else '</think>'
SETS = set(a.sets.split(',')); ARMS = set(a.arms.split(',')) if a.arms else None


def done_in(fn):
    ds = set()
    if fn and os.path.exists(fn):
        for line in open(fn):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('error') and not str(d['error']).startswith(('context_too_long', 'render:')):
                continue
            ds.add((d['id'], d['arm']))
    return ds


DONE = done_in(a.out)
for f in [x for x in a.skip_done_from.split(',') if x]:
    DONE |= done_in(f)
JOBS = []
TOOLS_BY_ID = {}
for line in open(a.prompts):
    j = json.loads(line)
    if j['set'] not in SETS or (ARMS and j['arm'] not in ARMS):
        continue
    if (j['id'], j['arm']) in DONE:
        continue
    JOBS.append(j)
groups = collections.OrderedDict()
for j in JOBS:
    groups.setdefault(j['id'], []).append(j)
if a.limit_ctx:
    groups = collections.OrderedDict(list(groups.items())[:a.limit_ctx])
NJ = sum(len(v) for v in groups.values())
print(f'[{time.strftime("%H:%M:%S")}] {a.mk} jobs todo {NJ} in {len(groups)} context groups (already done {len(DONE)})', flush=True)

def tools_for(job):
    return job['tools']


def body(prompt, max_tokens, temp, top_p, seed):
    return {'model': a.served, 'prompt': prompt, 'max_tokens': max_tokens, 'temperature': temp, 'top_p': top_p,
            'top_k': a.top_k, 'seed': seed, 'stop_token_ids': STOP_IDS, 'skip_special_tokens': SKIP_SPECIAL,
            'spaces_between_special_tokens': False, 'include_stop_str_in_output': False,
            'stream': True, 'stream_options': {'include_usage': True}}


async def stream(client, b, on_first=None, abort_after=None, tries=6):
    """-> dict(text, finish, usage, aborted). abort_after: stop reading (closing the stream aborts the request in vLLM)
    once that many chunks arrived and '</think>' has not appeared."""
    fired = [False]

    def fire():
        if not fired[0]:
            fired[0] = True
            if on_first:
                try:
                    on_first()
                except Exception:  # noqa: BLE001
                    pass
    for t in range(tries):
        text = []; fin = None; usage = None; n = 0; aborted = False; stop_reason = None
        try:
            async with client.stream('POST', a.base + '/completions', json=b, timeout=3600) as r:
                if r.status_code == 400:
                    msg = (await r.aread()).decode(errors='replace')[:500]; fire()
                    return {'error': msg}
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith('data: '):
                        continue
                    data = line[6:].strip()
                    if data == '[DONE]':
                        break
                    ch = json.loads(data)
                    if ch.get('error') or ch.get('object') == 'error':
                        raise RuntimeError('server error event: ' + json.dumps(ch)[:300])
                    if ch.get('usage'):
                        usage = ch['usage']
                    for c in ch.get('choices') or []:
                        fire()
                        if c.get('text'):
                            text.append(c['text']); n += 1
                        if c.get('finish_reason'):
                            fin = c['finish_reason']; stop_reason = c.get('stop_reason')
                    if abort_after and n > abort_after and n % 64 == 0 and THINK_END not in ''.join(text):
                        aborted = True
                        break
            if not aborted and fin is None:
                raise RuntimeError('stream ended without a finish_reason')
            fire()
            return {'text': ''.join(text), 'finish': 'budget_abort' if aborted else fin, 'usage': usage, 'aborted': aborted,
                    'stop_reason': stop_reason}
        except Exception as e:  # noqa: BLE001
            if t == tries - 1:
                fire()
                return {'error': repr(e)[:500]}
            await asyncio.sleep(5 * (t + 1))


def thought_span(gen):
    """character span of the thought inside the generated text: Qwen3 generates '<think>' itself; Qwen3.5's prompt
    ends with '<think>\\n' so the thought starts at 0; harmony: the analysis message."""
    if FMT == 'harmony':
        h = '<|channel|>analysis<|message|>'
        i = gen.find(h)
        if i < 0:
            return 0, 0, True
        st = i + len(h); j = gen.find('<|end|>', st)
        return st, (j if j >= 0 else len(gen)), j >= 0
    st = 0
    i = gen.find('<think>')
    if i >= 0 and gen[:i].strip() == '':
        st = i + len('<think>')
    j = gen.find('</think>', st)
    return st, (j if j >= 0 else len(gen)), j >= 0


STATS = collections.defaultdict(lambda: [0, 0, 0])
T0 = time.time(); NDONE = 0


async def run_job(client, sem, job, fo, room_of, on_first=None):
    global NDONE
    release = on_first if on_first is not None else (lambda: None)
    rec = {k: job.get(k) for k in ('id', 'arm', 'set', 'idx', 'task', 'temp', 'top_p', 'seed', 'n_prompt')}
    rec.update(model=a.mk, served=a.served, base=a.base, top_k=a.top_k, fmt=FMT,
               info={k: v for k, v in (job.get('info') or {}).items() if k != 'p1n_raw'})
    if job.get('error'):
        release(); rec['error'] = job['error']; fo.write(json.dumps(rec) + '\n'); fo.flush(); return
    room = room_of - job['n_prompt'] - 8
    if room < 600:
        release(); rec['error'] = 'context_too_long'; fo.write(json.dumps(rec) + '\n'); fo.flush(); return
    t1 = time.time()
    async with sem:
        P = job.get('prompt_ids') or job['prompt']
        r = await stream(client, body(P, min(a.max_new, room), job['temp'], job['top_p'], job['seed']),
                         on_first=release, abort_after=(a.budget + 64) if THINK else None)
        release()
        if 'error' in r:
            rec['error'] = 'gen:' + r['error']; fo.write(json.dumps(rec) + '\n'); fo.flush(); return
        gen = r['text']; rec['finish'] = r['finish']; rec['completion_tokens'] = (r.get('usage') or {}).get('completion_tokens')
        rec['stop_reason'] = r.get('stop_reason')
        st, en, closed = thought_span(gen) if THINK else (0, 0, True)
        n_th = tok_count(gen[st:en]) if THINK else 0
        rec['thought_tokens'] = n_th
        if THINK and (n_th > a.budget or (r['aborted'] and not closed)):
            # post-hoc thinking budget: cut at `budget` tokens, force the end of the thought, regenerate the continuation
            cut = tok_cut(gen[st:en], a.budget)
            prefix_gen = gen[:st] + cut + ('<|end|><|start|>assistant' if FMT == 'harmony' else '</think>')
            used = job['n_prompt'] + (len(fe.harmony_encode(prefix_gen)) if FMT == 'harmony' else qp.n_tokens(prefix_gen, a.mk))
            mt = min(5120, room_of - used - 8)
            rec['budget_forced'] = True
            if mt < 64:
                rec['error'] = 'no_room_after_budget'; fo.write(json.dumps(rec) + '\n'); fo.flush(); return
            P2 = (job['prompt_ids'] + fe.harmony_encode(prefix_gen)) if job.get('prompt_ids') and FMT == 'harmony' else (job['prompt'] + prefix_gen)
            r2 = await stream(client, body(P2, mt, job['temp'], job['top_p'], job['seed'] + 1))
            rec['stop_reason'] = r2.get('stop_reason')
            if 'error' in r2:
                rec['error'] = 'gen2:' + r2['error']; fo.write(json.dumps(rec) + '\n'); fo.flush(); return
            gen = prefix_gen + r2['text']; rec['finish2'] = r2['finish']
            rec['completion_tokens2'] = (r2.get('usage') or {}).get('completion_tokens')
    rec['wall_s'] = round(time.time() - t1, 1)
    rec['gen'] = gen
    try:
        sr = rec.get('stop_reason')
        rec['judge'] = qp.judge(gen, FMT, tools_for(job), a.mk, stop_token=sr if (FMT == 'harmony' and isinstance(sr, int)) else None)
    except Exception as e:  # noqa: BLE001
        rec['judge_error'] = repr(e)[:300]
    fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()
    j = rec.get('judge') or {}
    st_ = STATS[job['arm']]; st_[0] += 1
    if j.get('name') == 'edit_file':
        st_[1] += 1; st_[2] += int(bool(j.get('malformed')))
    NDONE += 1
    if NDONE % 25 == 0:
        el = time.time() - T0
        print(f'[{time.strftime("%H:%M:%S")}] done {NDONE}/{NJ} {NDONE / el * 3600:.0f} jobs/h eta {(NJ - NDONE) / max(1e-9, NDONE / el) / 3600:.2f}h | '
              + ' '.join(f'{k}:{v[2]}/{v[1]}/{v[0]}' for k, v in sorted(STATS.items())), flush=True)


async def run_group(client, sem, csem, jobs, fo, room_of):
    async with csem:
        jobs = sorted(jobs, key=lambda j: (j['arm'] not in ('P0', 'C0'), j['arm']))
        ev = asyncio.Event()
        lead = asyncio.create_task(run_job(client, sem, jobs[0], fo, room_of, on_first=ev.set))
        if len(jobs) > 1:
            try:
                await asyncio.wait_for(ev.wait(), timeout=3600)
            except asyncio.TimeoutError:
                pass
        rest = [asyncio.create_task(run_job(client, sem, j, fo, room_of)) for j in jobs[1:]]
        await asyncio.gather(lead, *rest)


async def main():
    limits = httpx.Limits(max_connections=a.conc + 8, max_keepalive_connections=a.conc + 8)
    async with httpx.AsyncClient(limits=limits) as client:
        room_of = a.max_model_len
        if not room_of:
            r = await client.get(a.base + '/models', timeout=30)
            room_of = int(r.json()['data'][0].get('max_model_len') or 32768)
        print('max_model_len', room_of, 'served', a.served, flush=True)
        sem = asyncio.Semaphore(a.conc); csem = asyncio.Semaphore(a.ctx_conc)
        with open(a.out, 'a') as fo:
            pending = set()
            for cid, js in groups.items():
                pending.add(asyncio.create_task(run_group(client, sem, csem, js, fo, room_of)))
                if len(pending) >= a.ctx_conc * 2:
                    _, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            if pending:
                await asyncio.wait(pending)
    print(f'finished {NDONE} in {(time.time() - T0) / 60:.1f} min', flush=True)

asyncio.run(main())
