"""Protocol proxy: OpenAI-compatible chat-completions endpoint between an agent harness and a vLLM server.

Routes: /<cfg>/v1/chat/completions, /<cfg>/v1/models (cfg names from --configs JSON).
Modes per cfg:
  passthrough  forward to backend /v1/chat/completions (drops thinking_token_budget, which our servers
               reject because they run without --reasoning-config).
  engine       render the prompt here (vLLM-faithful), generate over backend /v1/completions with token
               ids, emulate vLLM's ThinkingTokenBudget logits processor, parse with vLLM's own gemma4
               reasoning + tool parsers, and return a vLLM-shaped chat.completion. Optional fixes:
                 canonical_order  tool declarations + historical calls rendered in schema order
                 quarantine       malformed historical calls re-rendered canonically, responses annotated
                 ipd              intent-preserving decoding = VERIFY-THEN-REPAIR (workstream B's reference
                                  algorithm (i+), its strict guard and site finder vendored byte-identical):
                                  the turn is generated uninterrupted; every call that is STRICTLY valid is
                                  delivered byte-identical; the first call that is not, and has a repairable
                                  site (closer slip / drifted string opener, declared keys only), is rolled
                                  back to that site, the true delimiter inserted (cut chosen by B's
                                  noisy-channel rule) and generation resumed (+ guarded post-hoc fallback).
NEVER uses prompt_logprobs (PI rule: vLLM 0.19.1 allocates fp32 [prompt x vocab]; it OOM-crashed a server).
Every request is logged (raw generation, interventions, delivered calls) to <logdir>/proxy_<cfg>.jsonl.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import aiohttp
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemma_protocol as gp  # noqa: E402

MAX_LEN = 32768


def _install_array_hang_patch():
    """vLLM 0.19.1's _parse_gemma4_array can loop forever on some malformed arrays (no progress on a bare value).
    Same fix as workstream A (contagion/scripts/gemma_protocol.py::_patched_array): skip a non-advancing character."""
    import vllm.tool_parsers.gemma4_tool_parser as g
    if getattr(g, '_e2e_array_patch', False):
        return
    D_ = g.STRING_DELIM

    def _patched_array(arr_str, *, partial=False):
        items, i, n = [], 0, len(arr_str)
        while i < n:
            while i < n and arr_str[i] in (' ', ',', '\n', '\t'):
                i += 1
            if i >= n:
                break
            if arr_str[i:].startswith(D_):
                i += len(D_)
                end_pos = arr_str.find(D_, i)
                if end_pos == -1:
                    items.append(arr_str[i:])
                    break
                items.append(arr_str[i:end_pos])
                i = end_pos + len(D_)
            elif arr_str[i] == '{':
                depth, obj_start = 1, i + 1
                i += 1
                while i < n and depth > 0:
                    if arr_str[i:].startswith(D_):
                        i += len(D_)
                        nd = arr_str.find(D_, i)
                        i = nd + len(D_) if nd != -1 else n
                        continue
                    if arr_str[i] == '{':
                        depth += 1
                    elif arr_str[i] == '}':
                        depth -= 1
                    i += 1
                items.append(g._parse_gemma4_args(arr_str[obj_start:i], partial=True) if depth > 0
                             else g._parse_gemma4_args(arr_str[obj_start:i - 1]))
            elif arr_str[i] == '[':
                depth, sub_start = 1, i + 1
                i += 1
                while i < n and depth > 0:
                    if arr_str[i] == '[':
                        depth += 1
                    elif arr_str[i] == ']':
                        depth -= 1
                    i += 1
                items.append(_patched_array(arr_str[sub_start:i], partial=True) if depth > 0
                             else _patched_array(arr_str[sub_start:i - 1]))
            else:
                val_start = i
                while i < n and arr_str[i] not in (',', ']'):
                    i += 1
                if i == val_start:  # the fix: no progress -> skip one character
                    i += 1
                    continue
                if partial and i >= n:
                    break
                items.append(g._parse_gemma4_value(arr_str[val_start:i]))
        return items

    g._parse_gemma4_array = _patched_array
    g._e2e_array_patch = True


class Engine:
    def __init__(self, model_dir: str):
        _install_array_hang_patch()
        from transformers import AutoTokenizer
        from vllm.reasoning.gemma4_reasoning_parser import Gemma4ReasoningParser
        from vllm.tool_parsers.gemma4_tool_parser import Gemma4ToolParser
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.tpl_official = Path(model_dir, 'chat_template.jinja').read_text()
        self.tpl_canonical = gp.canonical_template(self.tpl_official)
        self.rparser = Gemma4ReasoningParser(self.tok)  # non-streaming extract_* are stateless
        self.tparser = Gemma4ToolParser(self.tok)
        gc = json.loads(Path(model_dir, 'generation_config.json').read_text())
        eos = gc.get('eos_token_id')
        self.eos_ids = set(eos if isinstance(eos, list) else [eos])  # vLLM drops the stop token from the text
        self.ch_start = self.tok.convert_tokens_to_ids(gp.CH_START)
        self.ch_end = self.tok.convert_tokens_to_ids(gp.CH_END)
        self.d_id = self.tok.convert_tokens_to_ids(gp.D)

    def render_ids(self, conv, tools, kwargs, canonical: bool):
        text = self.tok.apply_chat_template(conv, tools=tools, add_generation_prompt=True, tokenize=False,
                                            chat_template=self.tpl_canonical if canonical else self.tpl_official,
                                            **kwargs)
        return text, self.tok.encode(text, add_special_tokens=False)

    def decode(self, ids):
        return self.tok.decode(ids, skip_special_tokens=False)

    def encode(self, text):
        return self.tok.encode(text, add_special_tokens=False)

    def resync(self, ids, text):
        """Token ids whose decoding is exactly `text`, reusing the longest exact prefix of `ids`."""
        lo, hi = 0, len(ids)
        while lo < hi:  # largest k with decode(ids[:k]) a prefix of text
            mid = (lo + hi + 1) // 2
            if text.startswith(self.decode(ids[:mid])):
                lo = mid
            else:
                hi = mid - 1
        head = self.decode(ids[:lo])
        return ids[:lo] + (self.encode(text[len(head):]) if len(text) > len(head) else [])

    def parse(self, text):
        reasoning, content = self.rparser.extract_reasoning(text, None)
        info = self.tparser.extract_tool_calls(content if content is not None else '', None)
        calls = []
        if info.tools_called:
            for tc in info.tool_calls:
                calls.append({'name': tc.function.name, 'arguments': tc.function.arguments})
            content = info.content
            if content and content.strip() == '':
                content = None
        return reasoning, content, calls


async def nc_cut(engine, prompt_ids, gen_ids, text, cstart, site, btool, lp_fn, prior):
    """Workstream B's choose_cut (rule 'nc'), mirrored: cut candidates = site.cut_positions() (B's, capped), score of
    cut k = exact log P(call[:cut_k] <|"|> continuation | context) by windowed cached teacher forcing to the end of the
    candidate (B's cut_scores / wctf_scores(to_end=True)), plus the closer prior log P_channel(closer_at(site, k));
    argmax with ties to the earliest cut. Returns (k, info); k = 0 (whole run, B's 'max') if scoring is unavailable."""
    cps = site.cut_positions()
    closers = [gp.closer_at(site, k) for k in range(len(cps))]
    info = {'cands': len(cps), 'closers': closers}
    if len(cps) == 1:
        return 0, {**info, 'how': 'single_cut'}
    if lp_fn is None:
        return 0, {**info, 'how': 'whole_run(no_scorer)'}
    cont = gp.continuation(site, btool)
    cands = [await asyncio.to_thread(engine.resync, gen_ids, text[:cstart + cp] + gp.D + cont) for cp in cps]
    m = min(len(c) for c in cands)
    d = next((i for i in range(m) if any(c[i] != cands[0][i] for c in cands)), m)
    jobs = [(j, p) for j, c in enumerate(cands) for p in range(d, len(c))]
    res = await asyncio.gather(*[lp_fn(prompt_ids + cands[j][:p], cands[j][p]) for j, p in jobs])
    if any(r is None for r in res):
        return 0, {**info, 'how': 'whole_run(scoring_failed)'}
    lls = [0.0] * len(cands)
    for (j, _), lp in zip(jobs, res):
        lls[j] += lp
    k = gp.pick_cut(lls, closers, 'nc', prior)
    return k, {**info, 'how': 'noisy_channel', 'k_lik': gp.pick_cut(lls, closers, 'lik', prior),
               'lls': [round(x, 3) for x in lls],
               'prior': [round(prior.logp(c), 3) if prior is not None else 0.0 for c in closers], 'n_scored': len(jobs)}


def _budget_state(engine, prompt_ids, gen_ids):
    """(in_think, think_count, thought_done) after prompt+gen, as the ThinkingTokenBudget processor tracks it."""
    ls = max((i for i, t in enumerate(prompt_ids) if t == engine.ch_start), default=-1)
    le = max((i for i, t in enumerate(prompt_ids) if t == engine.ch_end), default=-1)
    it = ls > le
    tc = len(prompt_ids) - (ls + 1) if it else 0
    td = False
    for t in gen_ids:
        if it:
            if t == engine.ch_end:
                it, tc, td = False, 0, True
            else:
                tc += 1
        elif t == engine.ch_start:
            it, tc = True, 0
    return it, tc, td


async def generate(engine, prompt_ids, *, max_total, budget, user_stops, schemas, backend_fn, ipd_stops=(),
                   budget_slack=1536, max_interventions=8, confirm_fn=None, lp_fn=None, prior=None, opener=False,
                   ipd=None, bschema=None, rules=None, max_rounds=gp.IPD_MAX_ROUNDS):
    """Segmented generation with thinking-budget emulation and intent-preserving decoding.
    backend_fn(prompt_ids, max_tokens, stops) -> (status, choice) with choice = vLLM completions choice
    (text, token_ids, finish_reason, stop_reason).

    Intent-preserving decoding (ipd) = VERIFY-THEN-REPAIR, workstream B's reference algorithm (i+)
    (intent_decode.rollback_resume): generation is never interrupted for IPD. When the turn ends (EOS, a user stop
    string, or the length cap), every tool call in vLLM's content region is checked with B's strict guard
    (gemma_protocol.is_valid: strict structural parse + schema). Strictly valid calls are never altered (byte
    identity, no extra request). For the FIRST call that is not strictly valid and has a repairable site
    (B's first_violation over `rules`, default closer + opener; whitespace around ',' and ':' tolerated; sites inside
    arguments not declared in the schema are excluded) the text is truncated at the site and the true delimiter is
    inserted -- closer sites: cut inside the look-alike run by B's noisy-channel rule (lp_fn = exact forced-token
    log-probabilities, prior = closer channel prior); opener sites: right after 'KEY:' -- and generation resumes.
    <= max_rounds repairs per call (B: 4) and <= max_interventions per turn.
    lp_fn(prompt_ids, target_id) -> exact log P(target | prompt) (forced max_tokens=1) or None.
    ipd_stops / confirm_fn / opener: accepted for backward compatibility; ipd defaults to (opener or ipd_stops)."""
    if ipd is None:
        ipd = bool(opener) or bool(ipd_stops)
    rules = tuple(rules or gp.IPD_RULES)
    if ipd and bschema is None:
        bschema = gp.b_schema(schemas)
    # ---- thinking state of the prompt (as vLLM's ThinkingTokenBudget logits processor initialises it)
    ch_s, ch_e = engine.ch_start, engine.ch_end
    ls = max((i for i, t in enumerate(prompt_ids) if t == ch_s), default=-1)
    le = max((i for i, t in enumerate(prompt_ids) if t == ch_e), default=-1)
    in_think = ls > le
    think_count = len(prompt_ids) - (ls + 1) if in_think else 0
    budget = int(budget) if budget is not None else None
    gen_ids: list[int] = []
    events, segs = [], []
    finish, stop_reason = None, None
    n_sampled, n_interv = 0, 0
    thought_done = False
    rounds: dict[int, int] = {}
    audit = None
    # One backend request per segment; the thinking budget is enforced post hoc: if the sampled thinking
    # exceeds the budget, the tokens after the budget-th thinking token are discarded, <channel|> is forced
    # and generation resumes (identical in distribution to the logits processor, which never intervenes
    # before the budget is reached). Segments end early only at budget overflow (and user stop strings).
    while True:  # outer loop: re-entered after an IPD rollback
        while True:
            remaining = max_total - len(gen_ids)
            if remaining <= 0:
                finish = 'length'
                break
            if budget is not None and in_think and think_count >= budget:
                gen_ids.append(ch_e)
                in_think, think_count, thought_done = False, 0, True
                events.append({'ev': 'budget_forced_end', 'at': len(gen_ids), 'discarded': 0})
                continue
            seg_max = remaining
            if budget is not None and (in_think or not thought_done):
                left = budget - think_count if in_think else budget
                seg_max = min(remaining, max(left, 0) + budget_slack)  # bounds the discarded overflow
            status, ch = await backend_fn(prompt_ids + gen_ids, seg_max, list(user_stops))
            if status != 200:
                return {'error': (status, ch)}
            ids = list(ch.get('token_ids') or [])
            seg_text = ch.get('text') or ''
            fr, sr = ch.get('finish_reason'), ch.get('stop_reason')
            n_sampled += len(ids)
            segs.append({'n': len(ids), 'fr': fr, 'sr': sr if not isinstance(sr, str) else sr[-24:], 'max': seg_max})
            # walk the new tokens through the budget state machine
            it, tc, cut_at, td = in_think, think_count, None, thought_done
            for j, t in enumerate(ids):
                if it:
                    if t == ch_e:
                        it, tc, td = False, 0, True
                    else:
                        tc += 1
                        if budget is not None and tc >= budget:
                            cut_at = j + 1
                            break
                elif t == ch_s:
                    it, tc = True, 0
            if cut_at is not None:
                gen_ids += ids[:cut_at] + [ch_e]
                in_think, think_count, thought_done = False, 0, True
                events.append({'ev': 'budget_forced_end', 'at': len(gen_ids), 'discarded': len(ids) - cut_at})
                continue
            prev_text = engine.decode(gen_ids) if (isinstance(sr, str) and fr == 'stop') else None
            gen_ids += ids
            in_think, think_count, thought_done = it, tc, td
            if fr == 'stop' and isinstance(sr, str) and sr in user_stops:
                gen_ids = await asyncio.to_thread(engine.resync, gen_ids, prev_text + seg_text[:-len(sr)])
                finish, stop_reason = 'stop', sr
                break
            if fr == 'length' and len(gen_ids) < max_total:
                continue  # segment cap (budget slack) reached without overflow: keep going
            finish, stop_reason = fr, sr
            break
        # ---- verify-then-repair at the end of the turn (EOS, user stop string or length cap)
        if ipd and finish in ('stop', 'length'):
            tids = gen_ids[:-1] if (finish == 'stop' and not isinstance(stop_reason, str) and gen_ids
                                    and gen_ids[-1] in engine.eos_ids) else gen_ids
            text = engine.decode(tids)
            plan, audit = await asyncio.to_thread(gp.ipd_scan, text, bschema, rules, dict(rounds), max_rounds)
            if plan is not None and n_interv < max_interventions:
                site, cstart = plan['site'], plan['cstart']
                btool = bschema.get(plan['tool'])
                ev = {'ev': 'ipd_repair', 'kind': site.kind, 'tool': plan['tool'], 'call_index': plan['index'],
                      'round': rounds.get(plan['pos'], 0), 'in': site.key, 'finished_call': plan['finished']}
                if site.kind in ('opener', 'kwarg'):
                    cut, force = cstart + site.colon_end, site.force
                    ev.update({'key': site.key, 'lead': site.lead, 'how': 'rollback_resume'})
                else:
                    k, cinfo = await nc_cut(engine, prompt_ids, gen_ids, text, cstart, site, btool, lp_fn, prior)
                    cut, force = cstart + site.cut_positions()[k], gp.D
                    ev.update({'key': site.next_key, 'run': site.run, 'gap': site.gap, 'closer': gp.closer_at(site, k),
                               'cut_k': k, **cinfo})
                ev.update({'discarded_chars': len(text) - cut, 'ctx': text[max(cstart, cut - 160):cut + 40]})
                gen_ids = await asyncio.to_thread(engine.resync, gen_ids, text[:cut] + force)
                in_think, think_count, thought_done = _budget_state(engine, prompt_ids, gen_ids)
                rounds[plan['pos']] = rounds.get(plan['pos'], 0) + 1
                n_interv += 1
                events.append(ev)
                finish, stop_reason = None, None
                continue
        break
    return {'gen_ids': gen_ids, 'events': events, 'segs': segs, 'finish': finish, 'stop_reason': stop_reason,
            'n_sampled': n_sampled, 'n_interv': n_interv, 'ipd_audit': audit}


class Proxy:
    def __init__(self, args):
        self.args = args
        self.cfgs = json.loads(Path(args.configs).read_text())
        self.engine = Engine(args.model_dir)
        self.pool = ThreadPoolExecutor(max_workers=args.cpu_workers)
        self.sem = asyncio.Semaphore(args.max_backend_conc)
        self.raw_store: dict[str, dict] = {}  # tool_call id -> raw emission (for quarantine)
        self.last_nmsgs: dict[str, int] = {}  # task -> n_msgs of its last tool-bearing request (compaction detection)
        self.replay = {}  # branch-at-onset plan: task id -> recorded prefix (see analysis/build_branch_plan.py)
        if getattr(args, 'replay_plan', None):
            self.replay = json.loads(Path(args.replay_plan).read_text())['branches']
        self.req_index: dict[str, int] = {}  # session key -> index of the current request (replay position)
        Path(args.logdir).mkdir(parents=True, exist_ok=True)
        self.logs = {c: open(Path(args.logdir) / f'proxy_{c}.jsonl', 'a', buffering=1) for c in self.cfgs}
        self.session: aiohttp.ClientSession | None = None
        self.stats = {c: {'requests': 0, 'errors': 0, 'interventions': 0} for c in self.cfgs}
        pr = json.loads(Path(args.prior).read_text())
        self.prior = gp.ChannelPrior(pr['priors'][args.prior_source], pr.get('alpha', 0.5))

    async def start(self, app):
        conn = aiohttp.TCPConnector(limit=0, force_close=True)  # fresh connection per call (vLLM keep-alive stall)
        self.session = aiohttp.ClientSession(connector=conn, timeout=aiohttp.ClientTimeout(total=None))

    async def stop(self, app):
        await self.session.close()

    async def cpu(self, fn, *a, **kw):
        return await asyncio.get_running_loop().run_in_executor(self.pool, lambda: fn(*a, **kw))

    # -------------------------------------------------------------------------------------- backend
    async def backend(self, path, body, timeout):
        last = None
        for attempt in range(3):
            try:
                async with self.sem:
                    async with self.session.post(self.args.backend + path, json=body,
                                                 timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                        txt = await r.text()
                        if r.status >= 500:
                            last = (r.status, txt)
                            await asyncio.sleep(2 + 3 * attempt)
                            continue
                        return r.status, txt
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                last = (504, json.dumps({'error': {'message': f'backend {type(e).__name__}', 'type': 'timeout'}}))
                await asyncio.sleep(2 + 3 * attempt)
        return last

    # -------------------------------------------------------------------------------------- handlers
    async def models(self, request):
        return web.json_response({'object': 'list', 'data': [
            {'id': m, 'object': 'model', 'owned_by': 'e2e-proxy'} for m in (self.args.served, 'gemma-4-31b-it-qat-w4a16-ct')]})

    async def chat(self, request):
        cfg_name = request.match_info.get('cfg', 'base')
        if cfg_name not in self.cfgs:
            return web.json_response({'error': {'message': f'unknown cfg {cfg_name}'}}, status=404)
        cfg = self.cfgs[cfg_name]
        body = await request.json()
        task = request.headers.get('X-E2E-Task', '')
        t0 = time.time()
        rid = uuid.uuid4().hex[:16]
        self.stats[cfg_name]['requests'] += 1
        rec = {'t': t0, 'rid': rid, 'cfg': cfg_name, 'task': task, 'n_msgs': len(body.get('messages') or []),
               'n_tools': len(body.get('tools') or [])}
        # compaction events: ADK's summarisation call carries no tools; an applied compaction shows as the session's
        # agent history shrinking between consecutive tool-bearing requests
        if rec['n_tools'] == 0:
            rec['compaction_call'] = True
        elif task:
            prev = self.last_nmsgs.get(task)
            if prev is not None and rec['n_msgs'] < prev:
                rec['compaction_applied'] = {'n_msgs_before': prev, 'n_msgs_after': rec['n_msgs']}
            self.last_nmsgs[task] = rec['n_msgs']
        try:
            if cfg.get('mode') == 'passthrough':
                status, out = await self.passthrough(body, rec)
            else:
                status, out = await self.engine_chat(body, cfg, rec)
        except Exception as e:  # noqa: BLE001
            import traceback
            rec['exception'] = traceback.format_exc()[-3000:]
            status, out = 500, {'error': {'message': f'proxy error: {e!r}', 'type': 'proxy_error'}}
        rec['status'] = status
        rec['latency_s'] = round(time.time() - t0, 3)
        if status != 200:
            self.stats[cfg_name]['errors'] += 1
        self.logs[cfg_name].write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')
        if isinstance(out, str):
            return web.Response(text=out, status=status, content_type='application/json')
        if body.get('stream') and status == 200:
            return await self.as_sse(request, out)
        return web.json_response(out, status=status, dumps=lambda o: json.dumps(o, ensure_ascii=False))

    async def as_sse(self, request, out):
        resp = web.StreamResponse(headers={'Content-Type': 'text/event-stream'})
        await resp.prepare(request)
        ch = out['choices'][0]
        msg = ch['message']
        delta = {'role': 'assistant', 'content': msg.get('content'), 'reasoning': msg.get('reasoning')}
        if msg.get('tool_calls'):
            delta['tool_calls'] = [{**tc, 'index': i} for i, tc in enumerate(msg['tool_calls'])]
        chunk = {'id': out['id'], 'object': 'chat.completion.chunk', 'created': out['created'], 'model': out['model'],
                 'choices': [{'index': 0, 'delta': delta, 'finish_reason': ch['finish_reason']}], 'usage': out['usage']}
        await resp.write(('data: ' + json.dumps(chunk, ensure_ascii=False) + '\n\n').encode())
        await resp.write(b'data: [DONE]\n\n')
        await resp.write_eof()
        return resp

    async def passthrough(self, body, rec):
        body = dict(body)
        if 'thinking_token_budget' in body:
            rec['dropped_thinking_token_budget'] = body.pop('thinking_token_budget')
        if body.pop('prompt_logprobs', None) is not None:  # PI rule: prompt_logprobs can OOM the shared servers
            rec['dropped_prompt_logprobs'] = True
        body['model'] = self.args.served
        status, txt = await self.backend('/chat/completions', body, self.args.call_timeout)
        rec['raw_response'] = txt[:20000]
        return status, txt

    # -------------------------------------------------------------------------------------- engine mode
    async def engine_chat(self, body, cfg, rec):
        msgs = body.get('messages') or []
        tools = body.get('tools') or None
        schemas = gp.tool_schemas(tools)
        ctk = dict(body.get('chat_template_kwargs') or {})
        budget = body.get('thinking_token_budget')
        canonical = bool(cfg.get('canonical_order'))
        rec.update({'budget': budget, 'enable_thinking': ctk.get('enable_thinking'),
                    'temperature': body.get('temperature'), 'max_tokens': body.get('max_tokens') or body.get('max_completion_tokens')})
        if len(msgs) <= 2:
            rec['request'] = {k: v for k, v in body.items() if k != 'stream'}  # first call of a session: full request
        elif msgs:
            lm = msgs[-1]
            rec['last_msg'] = {'role': lm.get('role'), 'content': str(lm.get('content'))[:1500]}
        # history as the CLIENT sent it (before any quarantine): malformed historical calls, in order
        hist = []
        for m in msgs:
            if m.get('role') == 'assistant' and m.get('tool_calls'):
                for tc in m['tool_calls']:
                    f = tc.get('function') or {}
                    try:
                        aa = json.loads(f.get('arguments')) if isinstance(f.get('arguments'), str) else f.get('arguments')
                    except Exception:  # noqa: BLE001
                        aa = None
                    hist.append([f.get('name'), int(not gp.classify_args(f.get('name'), aa, schemas)['ok'])])
        rec['hist'] = hist
        # tool results that arrived since the model's last turn: [tool, status, error_type] (for time-to-first-valid-
        # edit, wasted calls, protocol errors); plus the harness nudge text if the last message is a user nudge
        last_a = max((i for i, m in enumerate(msgs) if m.get('role') == 'assistant'), default=-1)
        names = {}
        if last_a >= 0:
            for tc in msgs[last_a].get('tool_calls') or []:
                names[tc.get('id')] = (tc.get('function') or {}).get('name')
        trs = []
        for m in msgs[last_a + 1:]:
            if m.get('role') == 'tool':
                tcontent = m.get('content')
                txt = tcontent if isinstance(tcontent, str) else ''.join(
                    pt.get('text', '') for pt in (tcontent or []) if isinstance(pt, dict))
                st, et = None, None
                try:
                    o = json.loads(txt)
                    if isinstance(o, dict):
                        st, et = o.get('status'), o.get('error_type')
                        if st is None and 'error' in o:  # ADK's own argument validation: {"error": "Invoking `x()` failed ..."}
                            em = str(o.get('error'))
                            st = 'error'
                            et = ('MissingParameters' if 'mandatory input parameters' in em else
                                  'UnexpectedArgument' if 'unexpected keyword' in em else 'ADKToolError')
                except Exception:  # noqa: BLE001
                    st = 'unparsed'
                trs.append([names.get(m.get('tool_call_id')), st, et, gp.tool_output_hash(txt)])
            elif m.get('role') == 'user' and last_a >= 0:
                rec['user_after_turn'] = str(m.get('content'))[:200]
        rec['tool_results'] = trs
        # ---- branch-at-onset: replay the recorded prefix of a base episode (closed loop: the harness re-executes)
        skey = rec.get('task', '')
        br = self.replay.get(skey.split(':')[-1]) if (self.replay and skey) else None
        if br is None and skey and getattr(self.args, 'seed_salt', None):
            # common random numbers across arms (population runs): seed = f(salt, task, request index in the session)
            i = self.req_index[skey] = self.req_index.get(skey, -1) + 1
            seed = int(hashlib.sha1(f"{self.args.seed_salt}:{skey.split(':')[-1]}:{i}".encode()).hexdigest()[:8], 16) & 0x7FFFFFFF
            body = {**body, 'seed': seed}
            rec['crn'] = {'i': i, 'seed': seed}
        if br is not None:
            i = self.req_index[skey] = self.req_index.get(skey, -1) + 1
            rec['branch'] = {'i': i, 'b': br['b'], 'onset': br['onset'], 'branch_id': br['branch_id']}
            if i <= br['b']:
                return await self.replay_response(body, rec, br, i, trs)
            seed = int(hashlib.sha1(f"{br['branch_id']}:{i}".encode()).hexdigest()[:8], 16) & 0x7FFFFFFF
            body = {**body, 'seed': seed}  # common random numbers across the four arms of a branch
            rec['branch']['seed'] = seed
        bschema = gp.b_schema_from_tools(tools) if tools else {}
        if cfg.get('quarantine') and tools:
            sv_ids = self._strictly_valid_history_ids(msgs, bschema)
            msgs, actions = gp.quarantine_history(msgs, schemas, self.raw_store, canonical, strictly_valid_ids=sv_ids)
            rec['quarantine'] = actions
        elif canonical and tools:
            msgs = self._reorder_only(msgs, schemas)
        try:
            conv = gp.to_conversation(msgs)
        except json.JSONDecodeError as e:
            return 400, {'error': {'message': f'invalid tool call arguments JSON in history: {e}', 'type': 'BadRequestError'}}
        tools_r = [t if isinstance(t, dict) else dict(t) for t in tools] if tools else None
        prompt_text, prompt_ids = await self.cpu(self.engine.render_ids, conv, tools_r, ctk, canonical)
        rec['prompt_tokens'] = len(prompt_ids)
        rec['prompt_sha'] = hashlib.sha1(prompt_text.encode()).hexdigest()[:16]
        if len(prompt_ids) >= MAX_LEN:
            return 400, {'error': {'message': f"Input length ({len(prompt_ids)}) exceeds model's maximum context length ({MAX_LEN}).",
                                   'type': 'BadRequestError', 'code': 400}}
        req_max = body.get('max_completion_tokens') or body.get('max_tokens')
        max_total = MAX_LEN - len(prompt_ids) if req_max is None else min(int(req_max), MAX_LEN - len(prompt_ids))
        samp = {k: body[k] for k in ('temperature', 'top_p', 'top_k', 'min_p', 'seed', 'presence_penalty',
                                     'frequency_penalty', 'repetition_penalty') if body.get(k) is not None}
        user_stops = body.get('stop') or []
        if isinstance(user_stops, str):
            user_stops = [user_stops]
        ipd = bool(cfg.get('ipd')) and bool(tools)

        async def backend_fn(ids, seg_max, stops):
            req = {'model': self.args.served, 'prompt': ids, 'max_tokens': seg_max, 'skip_special_tokens': False,
                   'include_stop_str_in_output': True, 'return_token_ids': True, 'stop': stops, **samp}
            status, txt = await self.backend('/completions', req, self.args.call_timeout)
            if status != 200:
                return status, txt
            return 200, json.loads(txt)['choices'][0]

        async def lp_fn(ids, target):
            # PI rule: generation logprobs of a FORCED next token on a cached prefix (raw logprob, any rank);
            # never prompt_logprobs
            req = {'model': self.args.served, 'prompt': ids, 'max_tokens': 1, 'temperature': 0.0, 'logprobs': 1,
                   'allowed_token_ids': [int(target)], 'skip_special_tokens': False, 'return_tokens_as_token_ids': True}
            status, txt = await self.backend('/completions', req, self.args.call_timeout)
            try:
                lp = json.loads(txt)['choices'][0]['logprobs']
                if status != 200 or lp['tokens'][0] != f'token_id:{int(target)}':
                    return None
                return float(lp['token_logprobs'][0])
            except Exception:  # noqa: BLE001
                return None

        g = await generate(self.engine, prompt_ids, max_total=max_total, budget=budget, user_stops=user_stops,
                           schemas=schemas, backend_fn=backend_fn, budget_slack=self.args.budget_slack,
                           max_interventions=self.args.max_interventions,
                           lp_fn=lp_fn if cfg.get('ipd_rule', 'nc') == 'nc' else None, prior=self.prior,
                           ipd=ipd, bschema=bschema, rules=cfg.get('ipd_rules') or gp.IPD_RULES)
        if 'error' in g:
            rec['backend_error'] = str(g['error'][1])[:2000]
            return g['error']
        gen_ids, events, segs = g['gen_ids'], g['events'], g['segs']
        finish, stop_reason, n_sampled, n_interv = g['finish'], g['stop_reason'], g['n_sampled'], g['n_interv']
        self.stats[rec['cfg']]['interventions'] += n_interv
        text_ids = gen_ids
        if finish == 'stop' and not isinstance(stop_reason, str) and gen_ids and gen_ids[-1] in self.engine.eos_ids:
            text_ids = gen_ids[:-1]  # like vLLM: the EOS/stop token is not part of the output text
        text = self.engine.decode(text_ids)
        reasoning, content, calls = await self.cpu(self.engine.parse, text)
        # ---- post-hoc intent repair: fallback for calls that are still NOT strictly valid after verify-then-repair
        # (B's guard first: a strictly valid call is delivered byte-identical even if the malformed criterion flags it)
        cs = gp.content_start(text)
        raw_calls = gp.CALL_RE.findall(text[cs:]) if cs is not None else []  # == vLLM's tool parser input
        delivered, call_meta = [], []
        for idx, c in enumerate(calls):
            args = json.loads(c['arguments'])
            cls = gp.classify_args(c['name'], args, schemas)
            meta = {'name': c['name'], 'ok_emitted': cls['ok'], 'why': cls['why'], 'leak': cls.get('leak')}
            raw_args = raw_calls[idx][1] if (idx < len(raw_calls) and raw_calls[idx][0] == c['name']) else None
            strict_ok = raw_args is not None and gp.strictly_valid(f"call:{c['name']}{{{raw_args}}}", bschema)
            meta['strict_valid'] = strict_ok
            if not cls['ok'] and ipd and not strict_ok and c['name'] in schemas and raw_args is not None:
                rec_args = gp.intent_parse_args(raw_args, schemas[c['name']]['properties'])
                if gp.classify_args(c['name'], rec_args, schemas)['ok']:
                    args = rec_args
                    c = {'name': c['name'], 'arguments': json.dumps(args, ensure_ascii=False)}
                    meta['posthoc_repaired'] = True
                    events.append({'ev': 'posthoc_repair', 'tool': c['name'], 'why': cls['why']})
            tcid = f'chatcmpl-tool-{uuid.uuid4().hex[:16]}'
            if raw_args is not None:
                self.raw_store[tcid] = {'name': c['name'], 'args_str': raw_args}
            meta['ok_delivered'] = gp.classify_args(c['name'], args, schemas)['ok']
            meta['id'] = tcid
            meta['args'] = args
            call_meta.append(meta)
            delivered.append({'id': tcid, 'type': 'function', 'function': {'name': c['name'], 'arguments': c['arguments']}})
        n_open = text.count(gp.TC_START)
        rec.update({'gen_tokens': len(gen_ids), 'sampled_tokens': n_sampled, 'segments': segs, 'events': events,
                    'finish': finish, 'stop_reason': stop_reason, 'raw': text, 'calls': call_meta,
                    'unparsed_tool_call': n_open > len(calls), 'n_tool_call_tags': n_open})
        if ipd:
            rec['ipd'] = g.get('ipd_audit')
        msg = {'role': 'assistant', 'content': content, 'refusal': None, 'annotations': None, 'audio': None,
               'function_call': None, 'tool_calls': delivered, 'reasoning': reasoning}
        fin = 'tool_calls' if delivered else (finish or 'stop')
        out = {'id': f'chatcmpl-{uuid.uuid4().hex[:16]}', 'object': 'chat.completion', 'created': int(time.time()),
               'model': body.get('model') or self.args.served,
               'choices': [{'index': 0, 'message': msg, 'logprobs': None, 'finish_reason': fin,
                            'stop_reason': stop_reason, 'token_ids': None}],
               'service_tier': None, 'system_fingerprint': None,
               'usage': {'prompt_tokens': len(prompt_ids), 'total_tokens': len(prompt_ids) + len(gen_ids),
                         'completion_tokens': len(gen_ids), 'prompt_tokens_details': None},
               'prompt_logprobs': None, 'prompt_token_ids': None, 'kv_transfer_params': None}
        return 200, out

    async def replay_response(self, body, rec, br, i, trs):
        """Return recorded response i of the branch's source episode (i <= b). At i == b the onset edit call is
        delivered malformed: as recorded (natural slip) or with workstream A's P1 corruption (injected)."""
        r = br['responses'][i]
        # fidelity: the re-executed tool results must match the recording (status/error_type/normalised hash)
        exp = r.get('tool_results') or []
        mism = []
        if len(exp) != len(trs):
            mism.append(f'n_results {len(trs)} != {len(exp)}')
        for k, (a, b) in enumerate(zip(trs, exp)):
            if a[:3] != b[:3] or (len(a) > 3 and len(b) > 3 and a[3] != b[3]):
                mism.append({'k': k, 'got': a, 'exp': b})
        if r.get('n_msgs') is not None and rec['n_msgs'] != r['n_msgs']:
            mism.append(f"n_msgs {rec['n_msgs']} != {r['n_msgs']}")
        rec['replay'] = {'fidelity': 'ok' if not mism else 'mismatch', 'mismatch': mism[:5]}
        reasoning, content, _ = await self.cpu(self.engine.parse, r['raw'])
        delivered, metas = [], []
        for c in r['calls']:
            args, ok = c['args'], c.get('ok_emitted', True)
            if r.get('raw_args', {}).get(c['id']) is not None:
                self.raw_store[c['id']] = {'name': c['name'], 'args_str': r['raw_args'][c['id']]}
            if i == br['b'] and c['id'] == br['onset_call_id']:
                args, ok = br['onset_args'], False
                self.raw_store[c['id']] = {'name': c['name'], 'args_str': br['onset_raw_args']}
            delivered.append({'id': c['id'], 'type': 'function',
                              'function': {'name': c['name'], 'arguments': json.dumps(args, ensure_ascii=False)}})
            metas.append({'name': c['name'], 'id': c['id'], 'ok_emitted': ok, 'ok_delivered': ok, 'args': args,
                          'replayed': True, 'onset': i == br['b'] and c['id'] == br['onset_call_id']})
        u = r.get('usage') or {}
        pt, ct = int(u.get('prompt_tokens') or 0), int(u.get('completion_tokens') or 0)
        rec.update({'replayed': True, 'raw': r['raw'], 'calls': metas, 'gen_tokens': ct, 'prompt_tokens': pt,
                    'finish': r.get('finish'), 'events': []})
        msg = {'role': 'assistant', 'content': content, 'refusal': None, 'annotations': None, 'audio': None,
               'function_call': None, 'tool_calls': delivered, 'reasoning': reasoning}
        out = {'id': f'chatcmpl-{uuid.uuid4().hex[:16]}', 'object': 'chat.completion', 'created': int(time.time()),
               'model': body.get('model') or self.args.served,
               'choices': [{'index': 0, 'message': msg, 'logprobs': None,
                            'finish_reason': 'tool_calls' if delivered else (r.get('finish') or 'stop'),
                            'stop_reason': None, 'token_ids': None}],
               'service_tier': None, 'system_fingerprint': None,
               'usage': {'prompt_tokens': pt, 'total_tokens': pt + ct, 'completion_tokens': ct, 'prompt_tokens_details': None},
               'prompt_logprobs': None, 'prompt_token_ids': None, 'kv_transfer_params': None}
        return 200, out

    def _strictly_valid_history_ids(self, msgs, bschema):
        """tool-call ids in the history whose raw emission (as generated through this proxy) passes B's guard."""
        out = set()
        for m in msgs:
            if m.get('role') == 'assistant' and m.get('tool_calls'):
                for tc in m['tool_calls']:
                    raw = self.raw_store.get(tc.get('id'))
                    if raw is not None and raw.get('args_str') is not None and gp.strictly_valid(
                            f"call:{raw.get('name') or (tc.get('function') or {}).get('name')}{{{raw['args_str']}}}", bschema):
                        out.add(tc.get('id'))
        return out

    @staticmethod
    def _reorder_only(msgs, schemas):
        import copy
        msgs = copy.deepcopy(msgs)
        for m in msgs:
            if m.get('role') == 'assistant' and m.get('tool_calls'):
                for tc in m['tool_calls']:
                    f = tc.get('function') or {}
                    a = f.get('arguments')
                    try:
                        args = json.loads(a) if isinstance(a, str) else a
                    except Exception:  # noqa: BLE001
                        continue
                    if isinstance(args, dict) and f.get('name') in schemas:
                        f['arguments'] = json.dumps(gp.reorder_args(args, schemas[f['name']]['properties']), ensure_ascii=False)
        return msgs

    async def health(self, request):
        return web.json_response({'ok': True, 'stats': self.stats, 'raw_store': len(self.raw_store)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8420)
    ap.add_argument('--backend', default='http://127.0.0.1:8302/v1')
    ap.add_argument('--served', default='gemma-4-31b')
    ap.add_argument('--model-dir', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
    ap.add_argument('--configs', default=str(Path(__file__).resolve().parent / 'configs.json'))
    ap.add_argument('--logdir', required=True)
    ap.add_argument('--max-backend-conc', type=int, default=24)
    ap.add_argument('--cpu-workers', type=int, default=6)
    ap.add_argument('--call-timeout', type=float, default=900.0)
    ap.add_argument('--max-interventions', type=int, default=8)
    ap.add_argument('--budget-slack', type=int, default=1536)
    ap.add_argument('--prior', default=str(Path(__file__).resolve().parents[1] / 'configs/channel_prior.json'))
    ap.add_argument('--prior-source', default='ft_edit', help='B default for gate replays')
    ap.add_argument('--replay-plan', default=None, help='branch-at-onset plan JSON (record-and-replay branch mode)')
    ap.add_argument('--seed-salt', default=None, help='common per-request seeds across arms: sha1(salt:task:i)')
    args = ap.parse_args()
    proxy = Proxy(args)
    app = web.Application(client_max_size=256 * 1024 ** 2)
    app.on_startup.append(proxy.start)
    app.on_cleanup.append(proxy.stop)
    app.router.add_post('/{cfg}/v1/chat/completions', proxy.chat)
    app.router.add_get('/{cfg}/v1/models', proxy.models)
    app.router.add_get('/health', proxy.health)
    web.run_app(app, host=args.host, port=args.port, access_log=None, print=lambda *_: None)


if __name__ == '__main__':
    main()
