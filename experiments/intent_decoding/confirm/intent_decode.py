"""Intent-preserving decoding for Gemma-4 tool calls over ANY OpenAI-compatible /v1/completions server (no engine change).

Algorithm (i)  SLIP ROLLBACK/RESUME (decode time):
    generate the call; if it is strictly valid -> return it byte-identical (GUARD, model-free);
    else find the left-most slip site (look-alike closer run followed by protocol structure; gemma_protocol);
    choose the cut inside the run with the NOISY-CHANNEL rule
        score(k) = log P_model( run[:k] <|"|> <structural continuation> | context, call prefix )   [exact, cached]
                 + log P_channel( closer = run[k:] )                                           [closer prior]
    truncate there, append the true delimiter <|"|>, resume generation (one extra request); repeat (<= max_rounds).
Algorithm (ii) LIKELIHOOD-SCORED REPAIR (post hoc, text only):
    enumerate all minimal complete parses of the emitted text under the relaxed grammar (repair_candidates);
    re-render each canonically; score each by windowed cached teacher forcing (WCTF) under the serving model
    + log P_channel of its closers; accept the argmax iff its margin over the runner-up is >= tau, else ABSTAIN.

Scoring never uses prompt_logprobs on long prompts (vLLM 0.19.1 materialises an fp32 [chunk x 262k] log_softmax for
prompt logprobs, which OOM-crashed a shared server).  Instead every scored token is one cached max_tokens=1 request
whose next token is FORCED with allowed_token_ids: vLLM computes raw logprobs before logits processors, so the
returned logprob of the forced token is the exact model logprob (any rank).  Prompts are sent as token ids so the
server's prefix cache is reused across the window requests.
"""
from __future__ import annotations
import asyncio, json, math, os, time, collections
import httpx
from gemma_protocol import (D, TC_START, TC_END, first_slip_site, first_violation, repair_candidates, is_valid,
                            parse_strict, schema_problems)

MAX_PROMPT_LOGPROBS_TOKENS = 1024   # PI rule: never request prompt_logprobs on longer prompts (any server)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # prior data lives in ../data


class Server:
    def __init__(self, base, model, conc=16, timeout=1800, sampling_extra=None):
        self.base, self.model = base.rstrip('/'), model
        self.sampling_extra = dict(sampling_extra or {})   # e.g. {'top_k': 64}: applied to every SAMPLED request (T > 0)
        self.sem = asyncio.Semaphore(conc)
        self.client = httpx.AsyncClient(timeout=timeout, limits=httpx.Limits(max_connections=conc + 4))
        self.stats = collections.Counter()

    async def close(self):
        await self.client.aclose()

    async def complete(self, prompt, max_tokens, stop=None, temperature=0.2, top_p=0.95, seed=0, logprobs=None,
                       prompt_logprobs=None, tries=4, n=1, extra=None, tag='gen'):
        if prompt_logprobs is not None:
            n_tok = len(prompt) if isinstance(prompt, list) else len(prompt)   # chars >= tokens for a str prompt
            if n_tok > MAX_PROMPT_LOGPROBS_TOKENS:
                raise ValueError(f'prompt_logprobs refused on a {n_tok}-unit prompt (server OOM risk; PI rule)')
        body = {'model': self.model, 'prompt': prompt, 'max_tokens': max_tokens, 'temperature': temperature,
                'top_p': top_p, 'seed': seed, 'skip_special_tokens': False, 'spaces_between_special_tokens': False}
        if self.sampling_extra and temperature and temperature > 0:
            body.update(self.sampling_extra)
        if extra:
            body.update(extra)
        if n > 1:
            body['n'] = n
        if stop:
            body['stop'] = stop
        if logprobs is not None:
            body['logprobs'] = logprobs
        if prompt_logprobs is not None:
            body['prompt_logprobs'] = prompt_logprobs
        last = None
        for t in range(tries):
            try:
                async with self.sem:
                    t0 = time.time()
                    r = await self.client.post(self.base + '/completions', json=body)
                    dt = time.time() - t0
                if r.status_code == 400:
                    raise ValueError('400: ' + r.text[:300])
                r.raise_for_status()
                j = r.json()
                u = j.get('usage') or {}
                self.stats['requests'] += 1
                self.stats['req_' + tag] += 1
                self.stats['prompt_tokens'] += u.get('prompt_tokens') or 0
                self.stats['completion_tokens'] += u.get('completion_tokens') or 0
                self.stats['ctok_' + tag] += u.get('completion_tokens') or 0
                c = j['choices'][0]
                c['_usage'] = u
                c['_latency'] = dt
                if n > 1:
                    for x in j['choices']:
                        x['_latency'] = dt
                    c['_all'] = sorted(j['choices'], key=lambda x: x.get('index', 0))
                return c
            except ValueError:
                self.stats['errors'] += 1
                raise
            except Exception as e:
                last = e
                self.stats['errors'] += 1
                await asyncio.sleep(2 + 3 * t)
        raise RuntimeError(f'request failed: {last!r}')


class Pin:
    """Hold a prompt prefix resident in vLLM's prefix cache while follow-up requests run: a STREAMING request on the
    prefix is started, we wait for its first chunk (prefill done -> blocks computed and in use), run the body, then
    close the stream (vLLM aborts the request on disconnect).  vLLM v1 shares computed blocks of running requests,
    so every scoring / resume / arm request on the same prefix hits the cache instead of re-prefilling ~12k tokens."""
    def __init__(self, srv, prompt_ids, max_tokens=4096):
        self.srv, self.ids, self.max_tokens = srv, list(prompt_ids), max_tokens
        self._task = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()

    async def _run(self):
        body = {'model': self.srv.model, 'prompt': self.ids, 'max_tokens': self.max_tokens, 'temperature': 0.0,
                'stream': True, 'ignore_eos': True, 'skip_special_tokens': False}
        try:
            async with self.srv.client.stream('POST', self.srv.base + '/completions', json=body) as resp:
                async for _ in resp.aiter_lines():
                    self._ready.set()
                    if self._stop.is_set():
                        break
                    # keep the connection open (and the request running) until the body is done
                    if self._stop.is_set():
                        break
        except Exception:
            pass
        finally:
            self._ready.set()

    async def __aenter__(self):
        self.srv.stats['pins'] += 1
        self._task = asyncio.create_task(self._run())
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=600)
        except asyncio.TimeoutError:
            pass
        return self

    async def __aexit__(self, *exc):
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except BaseException:
                pass
        return False


# --------------------------------------------------------------------------------------------- closer channel prior
class ChannelPrior:
    """P_channel(closer string): how often the model writes a given look-alike run where the true delimiter belongs.
    Add-alpha smoothing over observed strings; unseen strings share alpha mass, geometrically down-weighted by length."""
    def __init__(self, counts, alpha=0.5, name='prior'):
        self.counts = dict(counts)
        self.alpha = alpha
        self.name = name
        self.N = sum(self.counts.values())
        self.den = self.N + alpha * (len(self.counts) + 1)

    def logp(self, closer):
        c = (closer or '').strip(' \t\r\n')
        if c in self.counts:
            return math.log((self.counts[c] + self.alpha) / self.den)
        return math.log(self.alpha / self.den) + max(0, len(c) - 1) * math.log(0.25)

    @classmethod
    def from_log_slips(cls, source='ft_edit', path=None, alpha=0.5):
        path = path or os.path.join(HERE, 'data/log_slips.jsonl')
        c = collections.Counter()
        for l in open(path):
            r = json.loads(l)
            base = 'gemma-4-31b' in r['model']
            if source == 'ft_edit' and (r['tool'] != 'edit_file' or base):
                continue
            if source == 'base_edit' and (r['tool'] != 'edit_file' or not base):
                continue
            c[r['closer_run']] += 1
        return cls(c, alpha, name=source)

    def to_json(self):
        return {'name': self.name, 'alpha': self.alpha, 'N': self.N, 'counts': self.counts}


class NoPrior:
    name = 'none'
    def logp(self, closer):
        return 0.0


# --------------------------------------------------------------------------------------------- exact cached scoring
def ids_of(tok, text):
    return tok.encode(text, add_special_tokens=False)


async def token_logprob(srv, prompt_ids, target_id):
    """exact log P(target | prompt_ids): one cached max_tokens=1 request with the next token forced (allowed_token_ids);
    vLLM 0.19.1 returns RAW logprobs computed before the allowed-token mask."""
    c = await srv.complete(list(prompt_ids), max_tokens=1, temperature=0.0, logprobs=1,
                           extra={'allowed_token_ids': [int(target_id)], 'return_tokens_as_token_ids': True}, tag='score')
    lp = c['logprobs']
    tokname = lp['tokens'][0]
    if tokname != f'token_id:{int(target_id)}':
        raise RuntimeError(f'forced token not sampled: {tokname} != {target_id}')
    return float(lp['token_logprobs'][0])


async def wctf_scores(srv, prefix_ids, cand_ids, K=12, to_end=False):
    """Windowed cached teacher forcing.  All candidates share the context (prefix_ids); the scored window of candidate j
    starts at the first token where candidates differ and ends K tokens into the shared token suffix (or at the end of
    the candidate if to_end).  Score differences equal full teacher-forced differences up to the (shared-text,
    differently-conditioned) remainder beyond the window."""
    toks = [list(prefix_ids) + list(c) for c in cand_ids]
    m = min(len(t) for t in toks)
    d = m
    for i in range(len(prefix_ids), m):
        if any(t[i] != toks[0][i] for t in toks):
            d = i
            break
    sfx = 0
    while sfx < m - d and all(t[-1 - sfx] == toks[0][-1 - sfx] for t in toks):
        sfx += 1
    jobs = []
    for j, t in enumerate(toks):
        end = len(t) if to_end else min(len(t), len(t) - sfx + K)
        for p in range(d, end):
            jobs.append((j, p))
    if not jobs:
        return [0.0] * len(toks), {'div_token': d, 'common_suffix_tokens': sfx, 'window': [0] * len(toks), 'requests': 0}
    t0 = time.time()
    first = await token_logprob(srv, toks[jobs[0][0]][:jobs[0][1]], toks[jobs[0][0]][jobs[0][1]])   # warm the cache
    rest = await asyncio.gather(*[token_logprob(srv, toks[j][:p], toks[j][p]) for j, p in jobs[1:]])
    res = [first] + list(rest)
    scores = [0.0] * len(toks)
    nwin = [0] * len(toks)
    per_tok = [[] for _ in toks]
    for (j, p), lp in zip(jobs, res):
        scores[j] += lp
        nwin[j] += 1
        per_tok[j].append(round(lp, 4))
    return scores, {'div_token': d - len(prefix_ids), 'common_suffix_tokens': sfx, 'window': nwin, 'requests': len(jobs),
                    'latency': time.time() - t0, 'per_token': per_tok}


def _continuation(site, schema_tool):
    """structural text that follows the true delimiter at a slip site (scored together with the cut)."""
    if site.kind == 'end':
        return '}' + TC_END
    ty = str(((schema_tool or {}).get('props', {}).get(site.next_key) or {}).get('type') or '').lower()
    return ',' + site.next_key + ':' + (D if ty == 'string' else '')


def closer_at(site, k):
    """closer string implied by cutting at the k-th cut position of a site (run remainder; gap is whitespace)."""
    return site.closer_for(site.cut_positions()[k])


async def cut_scores(srv, tok, prefix_ids, text, site, schema_tool):
    """exact local log-likelihood of every cut at a slip site: log P(run[:k] <|"|> continuation | context, call prefix)."""
    cps = site.cut_positions()
    cont = _continuation(site, schema_tool)
    cands = [ids_of(tok, text[:cp] + D + cont) for cp in cps]
    if len(cps) == 1:
        return cps, [0.0], {'requests': 0}
    lls, info = await wctf_scores(srv, prefix_ids, cands, to_end=True)
    return cps, lls, info


def pick_cut(lls, closers, rule, prior):
    if rule == 'max':
        return 0
    adj = [lls[k] + (prior.logp(closers[k]) if rule == 'nc' else 0.0) for k in range(len(lls))]
    return max(range(len(adj)), key=lambda k: (adj[k], -k))


async def choose_cut(srv, tok, prefix_ids, text, site, schema_tool, rule='nc', prior=None):
    cps = site.cut_positions()
    closers = [closer_at(site, k) for k in range(len(cps))]
    info = {'rule': rule, 'cands': cps, 'run': site.run, 'gap': site.gap, 'closers': closers}
    if rule == 'max' or len(cps) == 1:
        info.update(chosen=cps[0], k=0, requests=0, latency=0.0)
        return cps[0], info
    cps, lls, winfo = await cut_scores(srv, tok, prefix_ids, text, site, schema_tool)
    prior = prior or NoPrior()
    k = pick_cut(lls, closers, rule, prior)
    info.update(lls=[round(x, 4) for x in lls], prior=[round(prior.logp(c), 4) for c in closers], chosen=cps[k], k=k,
                k_lik=pick_cut(lls, closers, 'lik', prior), requests=winfo.get('requests', 0),
                latency=winfo.get('latency', 0.0))
    return cps[k], info


async def rollback_resume(srv, tok, prefix_text, text, finish, schema, *, rule='nc', prior=None, rules=('closer',),
                          max_rounds=4, max_tokens=2048, temperature=0.2, top_p=0.95, seed=0, prefix_ids=None):
    """Algorithm (i). prefix_text = rendered context + thought + '<|tool_call>'; `text` = generated call
    ('call:NAME{...' without <tool_call|>); `finish` = generation ended with <tool_call|>."""
    prefix_ids = prefix_ids if prefix_ids is not None else ids_of(tok, prefix_text)
    name = parse_strict(text).name
    sc_tool = schema.get(name) if name else None
    rounds = []
    cur, cur_finished = text, finish
    for r in range(max_rounds):
        site = first_violation(cur, schema, finished=cur_finished, rules=rules)
        if site is None:
            break
        force = D
        if site.kind in ('opener', 'kwarg'):
            cut = site.colon_end
            force = site.force
            cinfo = {'rule': site.kind, 'lead': site.lead, 'latency': 0.0, 'requests': 0}
        else:
            cut, cinfo = await choose_cut(srv, tok, prefix_ids, cur, site, sc_tool, rule=rule, prior=prior)
        new_prefix = cur[:cut] + force
        c = await srv.complete(list(prefix_ids) + ids_of(tok, new_prefix), max_tokens=max_tokens, stop=[TC_END],
                               temperature=temperature, top_p=top_p, seed=seed + 1000 * (r + 1), tag='resume')
        gen = c['text']
        discarded = cur[cut:]
        cur = new_prefix + gen
        cur_finished = (c.get('finish_reason') == 'stop' and c.get('stop_reason') == TC_END)
        rounds.append({'round': r, 'site_key': site.key, 'next_key': getattr(site, 'next_key', None), 'kind': site.kind,
                       'run': getattr(site, 'run', getattr(site, 'lead', None)), 'cut': cut, 'cut_choice': cinfo,
                       'discarded_chars': len(discarded), 'discarded': discarded[:200],
                       'gen_tokens': (c['_usage'].get('completion_tokens') or 0),
                       'latency': c['_latency'] + cinfo.get('latency', 0.0), 'finish': c.get('finish_reason')})
    return {'text': cur, 'finished': cur_finished, 'rounds': rounds, 'changed': cur != text,
            'valid': is_valid(cur, schema) and cur_finished}


async def lik_repair(srv, tok, prefix_text, text, finish, schema, *, tau=1.0, prior=None, max_cands=12, K=12,
                     prefix_ids=None):
    """Algorithm (ii). Never alters strictly valid calls. Records raw window LL and prior per candidate so that the
    decision can be recomputed offline for any tau / prior."""
    if is_valid(text, schema):          # GUARD: strictly valid calls are returned byte-identical
        return {'decision': 'identity', 'text': text, 'cands': []}
    cands = repair_candidates(text, schema, finished=finish)
    name = parse_strict(text).name
    if not cands:
        return {'decision': 'abstain_nocand', 'text': text, 'cands': []}
    cands = cands[:max_cands]
    texts = [c.text(name) for c in cands]
    prior = prior or NoPrior()
    pri = [sum(prior.logp(cl) for _, _, cl in c.cuts) for c in cands]
    t0 = time.time()
    if len(texts) == 1:
        lls, winfo = [0.0], {'requests': 0}
    else:
        prefix_ids = prefix_ids if prefix_ids is not None else ids_of(tok, prefix_text)
        lls, winfo = await wctf_scores(srv, prefix_ids, [ids_of(tok, t + TC_END) for t in texts], K=K)
    adj = [lls[i] + pri[i] for i in range(len(texts))]
    order = sorted(range(len(texts)), key=lambda i: -adj[i])
    best = order[0]
    margin = adj[best] - adj[order[1]] if len(order) > 1 else math.inf
    out = {'cands': [{'text': texts[i], 'll': lls[i], 'prior': pri[i], 'adj': adj[i],
                      'cuts': [(k, cp, cl) for k, cp, cl in cands[i].cuts]} for i in range(len(texts))],
           'best': best, 'margin': margin if margin != math.inf else 'inf', 'latency': time.time() - t0,
           'scorer': 'wctf_exact', 'prior_name': prior.name,
           'wctf': {k: v for k, v in winfo.items() if k != 'per_token'}}
    if margin >= tau:
        out.update(decision='repair', text=texts[best])
    else:
        out.update(decision='abstain_margin', text=text)
    return out


# --------------------------------------------------------------------------------------------- drop-in client API
async def generate_call(srv, tok, prompt_text, schema, *, prior=None, rules=('closer', 'opener'), max_tokens=2048,
                        temperature=0.2, top_p=0.95, seed=0, think_budget=0):
    """End-to-end drop-in for a client harness: prompt_text = rendered chat (generation prompt included).
    Generates (optional thinking) until the first complete tool call, applies algorithm (i) [+ opener rule],
    and returns {'call': text or None, 'valid': bool, 'audit': {...}}.  Strictly valid calls pass through untouched."""
    c = await srv.complete(prompt_text, max_tokens=think_budget + max_tokens, stop=[TC_END], temperature=temperature,
                           top_p=top_p, seed=seed)
    t = c['text']
    if TC_START not in t:
        return {'call': None, 'valid': False, 'text': t, 'audit': {'reason': 'no tool call'}}
    i = t.index(TC_START)
    pre, call = t[:i], t[i + len(TC_START):]
    fin = c.get('finish_reason') == 'stop' and c.get('stop_reason') == TC_END
    if is_valid(call, schema):
        return {'call': call, 'valid': True, 'pre': pre, 'audit': {'repaired': False}}
    r = await rollback_resume(srv, tok, prompt_text + pre + TC_START, call, fin, schema, rule='nc', prior=prior,
                              rules=rules, max_tokens=max_tokens, temperature=temperature, top_p=top_p, seed=seed)
    return {'call': r['text'], 'valid': r['valid'], 'pre': pre,
            'audit': {'repaired': r['changed'], 'original': call, 'rounds': r['rounds']}}
