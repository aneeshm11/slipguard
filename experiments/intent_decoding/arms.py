"""P0-B decoder arms that need the model (shared by replay.py [inline, prefix pinned] and head2head_gen.py):
  retry   : retry-on-invalid x2 (resample the whole call, T, new seeds) -- strictly-invalid calls only
  greedy  : the call re-decoded at T=0 from the same prefix
  forbid  : streaming forbid-trigger logits rule (exact emulation): right after '<look-alike run>,' inside a string, every
            token that can begin a declared edit_file key is banned (logit_bias -100) for that one step; repeated (<=4)
  grammar : grammar-constrained decoding (exact emulation): longest grammatical prefix + the grammar's forced legal
            continuation, then free generation; repeated (<=6)
"""
from gemma_protocol import (TC_END, is_valid, first_slip_site, grammar_state, grammar_force, runtime_view)
from intent_decode import ids_of


def view(text, finished, schema):
    v = runtime_view(text, finished, schema)
    v['slip'] = (first_slip_site(text, schema, finished=finished) is not None) if finished else None
    return v


def banned_key_tokens(tok, keys):
    out = set()
    for tid in range(len(tok)):
        s = tok.decode([tid]).lstrip()
        if s and any(k.startswith(s) or s.startswith(k) for k in keys):
            out.add(tid)
    return sorted(out)


async def _gen(srv, prompt_ids, max_tokens, temperature, seed, extra=None):
    c = await srv.complete(prompt_ids, max_tokens=max_tokens, stop=[TC_END], temperature=temperature, top_p=0.95,
                           seed=seed, extra=extra, tag='arm')
    fin = c.get('finish_reason') == 'stop' and c.get('stop_reason') == TC_END
    return c['text'], fin, (c['_usage'].get('completion_tokens') or 0), c['_latency']


async def arm_retry(srv, tok, pid, head, schema, seed, temp=0.2, call_max=2048, n=2):
    tries = []
    for t in range(n):
        txt, fin, ntok, lat = await _gen(srv, pid + ids_of(tok, head), call_max, temp, seed * 1000 + 77 + t)
        call = head + txt
        tries.append({'text': call, 'finished': fin, 'tokens': ntok, 'latency': lat, **view(call, fin, schema)})
        if fin and is_valid(call, schema):
            break
    best = next((x for x in tries if x['strict_valid']), None)
    return {'tries': tries, 'final_text': best['text'] if best else None, 'delivered': 'repaired' if best else 'loud',
            'tokens': sum(x['tokens'] for x in tries), 'latency': sum(x['latency'] for x in tries)}


async def arm_greedy(srv, tok, pid, head, schema, call_max=2048):
    txt, fin, ntok, lat = await _gen(srv, pid + ids_of(tok, head), call_max, 0.0, 0)
    call = head + txt
    return {'final_text': call, 'finished': fin, 'tokens': ntok, 'latency': lat, **view(call, fin, schema)}


async def arm_forbid(srv, tok, pid, call, finished, schema, ban, seed, temp=0.2, call_max=2048):
    cur, fin = call, finished
    rounds = []
    for rd in range(4):
        site = first_slip_site(cur, schema, finished=fin)
        if site is None or site.kind != 'key':
            break
        cut = site.struct_pos + 1
        pre = cur[:cut]
        c1 = await srv.complete(pid + ids_of(tok, pre), max_tokens=1, temperature=temp, top_p=0.95, seed=seed + rd,
                                extra={'logit_bias': {str(t): -100 for t in ban}}, tag='arm')
        step = c1['text']
        txt, fin, ntok, lat = await _gen(srv, pid + ids_of(tok, pre + step), call_max, temp, seed + 100 + rd)
        rounds.append({'cut': cut, 'forced_step': step, 'tokens': ntok + 1, 'latency': lat + c1['_latency']})
        cur = pre + step + txt
    return {'final_text': cur, 'finished': fin, 'rounds': rounds, 'tokens': sum(x['tokens'] for x in rounds),
            'latency': sum(x['latency'] for x in rounds), **view(cur, fin, schema)}


async def arm_grammar(srv, tok, pid, call, finished, schema, seed, temp=0.2, call_max=2048):
    cur, fin = call, finished
    rounds = []
    for rd in range(6):
        v, st, info = grammar_state(cur, schema)
        if st == 'complete' and v == len(cur.rstrip()) and fin:
            break
        if st == 'complete':
            cur, fin = cur[:v], True
            break
        force = grammar_force(st, info)
        pre = cur[:v] + force
        txt, fin, ntok, lat = await _gen(srv, pid + ids_of(tok, pre), call_max, temp, seed + 200 + rd)
        rounds.append({'v': v, 'state': st, 'force': force, 'tokens': ntok, 'latency': lat})
        cur = pre + txt
    return {'final_text': cur, 'finished': fin, 'rounds': rounds, 'tokens': sum(x['tokens'] for x in rounds),
            'latency': sum(x['latency'] for x in rounds), **view(cur, fin, schema)}


async def arm_forbid2(srv, tok, pid, call, finished, schema, ban, seed, temp=0.2, call_max=2048, rounds_max=6):
    """Stricter forbid-trigger emulation: the ban is applied at the position where the declared key would START,
    i.e. after '<look-alike run>,' AND any whitespace, so the model cannot sidestep it with a newline.
    Repeated at every new trigger (<= rounds_max)."""
    import re as _re
    cur, fin = call, finished
    rounds = []
    for rd in range(rounds_max):
        site = first_slip_site(cur, schema, finished=fin)
        if site is None or site.kind != 'key':
            break
        m = _re.compile(r'[ \t\r\n]*').match(cur, site.struct_pos + 1)
        cut = m.end()                                  # start of the key name
        pre = cur[:cut]
        c1 = await srv.complete(pid + ids_of(tok, pre), max_tokens=1, temperature=temp, top_p=0.95, seed=seed + rd,
                                extra={'logit_bias': {str(t): -100 for t in ban}}, tag='arm')
        step = c1['text']
        txt, fin, ntok, lat = await _gen(srv, pid + ids_of(tok, pre + step), call_max, temp, seed + 300 + rd)
        rounds.append({'cut': cut, 'forced_step': step, 'tokens': ntok + 1, 'latency': lat + c1['_latency']})
        cur = pre + step + txt
    return {'final_text': cur, 'finished': fin, 'rounds': rounds, 'tokens': sum(x['tokens'] for x in rounds),
            'latency': sum(x['latency'] for x in rounds), **view(cur, fin, schema)}
