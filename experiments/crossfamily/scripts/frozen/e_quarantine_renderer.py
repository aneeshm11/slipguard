"""FROZEN shipped quarantine renderer (workstream E) — single source of truth.

Used by the E protocol proxy (cfgs `quar`, `fullp` = quarantine + IPD) and importable by other workstreams
(A: P8a = shipped quarantine, recovered; P8b = shipped quarantine, sanitized). Pure Python, no dependencies.

API
  quarantine_messages(messages, tools, raw_by_call_id=None, canonical=False) -> (messages_out, actions)
    messages        OpenAI chat messages; assistant `tool_calls[].function.arguments` as JSON strings (or dicts),
                    tool messages with string content (the harness's JSON results).
    tools           the OpenAI tool declarations sent to the model.
    raw_by_call_id  {tool_call_id: raw argument text exactly as the model emitted it, i.e. the text between
                    'call:NAME{' and '}<tool_call|>'}. With it, a malformed call's intended arguments are recovered
                    (look-alike closer before ',<declared key>:', no-visible-closer, trailing closer) -> P8a.
                    Without it (or if recovery does not yield a valid call) the call is SANITIZED: undeclared keys
                    dropped, leaked '<closer>,<key>:...' tails and special tokens cut -> P8b.
    canonical       re-order arguments to schema order (False for `fullp`; the order patch is a separate ablation).
  Malformed (SYNTHESIS §5, all tools): unknown tool, required key missing, unknown key, leaked '<closer>,<key>:' in a
  string value, or a special token in a value. Valid historical calls are returned unchanged (canonical=False).
  The tool response of a quarantined call becomes a structured `MalformedToolCall` error (if the call had succeeded:
  the original result + a `protocol_warning`). Returned messages are deep copies; actions = [{id, tool, why, how}].

Render the returned messages with your usual chat-template path (arguments as dicts, as vLLM 0.19.1 does).
Self-test: python quarantine_renderer.py --selftest
"""
from __future__ import annotations

import copy
import json

D = '<|"|>'
SPECIALS = ['<|"|>', '<|tool_call>', '<tool_call|>', '<|tool_response>', '<tool_response|>', '<|channel>',
            '<channel|>', '<|turn>', '<turn|>', '<|tool>', '<tool|>', '<|think|>']
# look-alike closers, longest first
CLOSERS = ['"""', "\'\'\'", '```', '\\"', '`', '"', "\'"]


def _leak(value: str, keys) -> tuple[str, str] | None:
    """`<closer>,<key>:` inside a string value (or a value that ENDS with `,<key>:`, the no-visible-closer
    slip) -> (closer, key)."""
    for k in keys:
        pat = ',' + k + ':'
        j = value.find(pat)
        while j >= 0:
            for c in CLOSERS:
                if value[:j].endswith(c):
                    return c, k
            if j + len(pat) == len(value):  # value ends with ',key:' (delimiter consumed as closer)
                return '', k
            j = value.find(pat, j + 1)
    return None


def classify_args(name: str, args, schemas: dict) -> dict:
    """Malformed criterion (SYNTHESIS §5, all tools): unknown tool, required key missing, unknown key,
    leaked `<closer>,<declared key>:` in a string value, or a special token inside a value."""
    sch = schemas.get(name)
    if sch is None:
        return {'ok': False, 'why': ['unknown_tool']}
    if not isinstance(args, dict):
        return {'ok': False, 'why': ['non_dict_args']}
    props, req = sch['properties'], sch['required']
    why = []
    missing = [k for k in req if k not in args]
    unknown = [k for k in args if k not in props]
    if missing:
        why.append('missing:' + ','.join(missing))
    if unknown:
        why.append('unknown_key')
    leak = None
    for k, v in args.items():
        if isinstance(v, str):
            lk = _leak(v, [p for p in props if p != k])
            if lk and leak is None:
                leak = {'in': k, 'closer': lk[0], 'key': lk[1]}
            if any(s in v for s in SPECIALS):
                why.append('special_token')
    if leak:
        why.append('leak')
    return {'ok': not why, 'why': why, 'leak': leak, 'missing': missing, 'unknown': unknown}


def tool_schemas(tools: list[dict] | None) -> dict[str, dict]:
    out = {}
    for t in tools or []:
        f = t.get('function', t)
        p = f.get('parameters') or {}
        out[f['name']] = {'properties': dict(p.get('properties') or {}), 'required': list(p.get('required') or [])}
    return out


def reorder_args(args: dict, props: dict) -> dict:
    """Schema order first, unknown keys after (stable)."""
    if not isinstance(args, dict):
        return args
    out = {k: args[k] for k in props if k in args}
    out.update({k: v for k, v in args.items() if k not in out})
    return out


def intent_parse_args(args_str: str, props: dict) -> dict:
    """Parse a raw `key:value,...` argument string like vLLM, except that a string value also ends at a
    look-alike closer immediately followed by `,<declared unseen key>:` or by the end of the arguments."""
    out, i, n = {}, 0, len(args_str)
    while i < n:
        while i < n and args_str[i] in ' ,\n\t':
            i += 1
        if i >= n:
            break
        k0 = i
        while i < n and args_str[i] != ':':
            i += 1
        if i >= n:
            break
        key = args_str[k0:i].strip()
        i += 1
        while i < n and args_str[i] in ' \n\t':
            i += 1
        if args_str.startswith(D, i):
            vs = i + len(D)
            best = None
            e = args_str.find(D, vs)
            cands = [] if e < 0 else [(e, e + len(D))]
            for k in props:
                if k == key or k in out:
                    continue
                for c in CLOSERS:
                    pat = c + ',' + k + ':'
                    j = args_str.find(pat, vs)
                    if j >= 0:
                        cands.append((j, j + len(c)))
                j = args_str.find(',' + k + ':' + D, vs)  # no visible closer (delimiter consumed)
                if j >= 0:
                    cands.append((j, j))
            for c in CLOSERS:  # closer at the very end of the args string
                if args_str.endswith(c) and n - len(c) >= vs:
                    cands.append((n - len(c), n))
            if cands:
                best = min(cands)
                out[key] = args_str[vs:best[0]]
                i = best[1]
            else:
                out[key] = args_str[vs:]
                break
        else:
            v0 = i
            while i < n and args_str[i] not in ',}]':
                i += 1
            raw = args_str[v0:i].strip()
            out[key] = True if raw == 'true' else False if raw == 'false' else (None if raw.lower() in ('null', 'none') else _num(raw))
    return out


def _num(s):
    try:
        return float(s) if '.' in s else int(s)
    except ValueError:
        return s


def sanitize_args(args: dict, props: dict) -> dict:
    """Unrecoverable call: keep declared keys only and cut leaked tails from string values."""
    out = {}
    for k, v in (args or {}).items():
        if k not in props:
            continue
        if isinstance(v, str):
            lk = _leak(v, [p for p in props if p != k])
            if lk:
                c, kk = lk
                j = v.find(c + ',' + kk + ':') if c else v.rfind(',' + kk + ':')
                v = v[:j] if j >= 0 else v
            for s in SPECIALS:
                v = v.replace(s, '')
        out[k] = v
    return out


def quarantine_history(messages: list[dict], schemas: dict, raw_store: dict, canonical: bool) -> tuple[list[dict], list[dict]]:
    """Re-render malformed historical tool calls canonically (recovered intent if the raw emission is known,
    else a sanitized version) and annotate their tool responses. Valid calls are untouched (except ordering
    when `canonical`). Returns (new_messages, actions)."""
    msgs = copy.deepcopy(messages)
    actions = []
    fix_resp = {}
    for m in msgs:
        if m.get('role') != 'assistant' or not m.get('tool_calls'):
            continue
        for tc in m['tool_calls']:
            f = tc.get('function') or {}
            name = f.get('name')
            a = f.get('arguments')
            try:
                args = json.loads(a) if isinstance(a, str) else (a or {})
            except Exception:  # noqa: BLE001
                args = None
            cls = classify_args(name, args, schemas)
            props = schemas.get(name, {}).get('properties', {})
            if cls['ok']:
                if canonical and isinstance(args, dict):
                    f['arguments'] = json.dumps(reorder_args(args, props), ensure_ascii=False)
                continue
            if name not in schemas:
                continue  # hallucinated tool: leave as is (the harness already answered with an error)
            raw = raw_store.get(tc.get('id'))
            new, how = None, None
            if raw is not None:
                rec = intent_parse_args(raw['args_str'], props)
                if classify_args(name, rec, schemas)['ok']:
                    new, how = rec, 'recovered'
            if new is None:
                new, how = sanitize_args(args if isinstance(args, dict) else {}, props), 'sanitized'
            if canonical:
                new = reorder_args(new, props)
            f['arguments'] = json.dumps(new, ensure_ascii=False)
            fix_resp[tc.get('id')] = (name, cls, how)
            actions.append({'id': tc.get('id'), 'tool': name, 'why': cls['why'], 'how': how})
    for m in msgs:
        if m.get('role') == 'tool' and m.get('tool_call_id') in fix_resp:
            name, cls, how = fix_resp[m['tool_call_id']]
            body = m.get('content')
            text = body if isinstance(body, str) else ''.join(p.get('text', '') for p in (body or []) if isinstance(p, dict))
            try:
                obj = json.loads(text)
            except Exception:  # noqa: BLE001
                obj = None
            what = ('a string argument was closed with a look-alike character instead of the string delimiter'
                    if cls.get('leak') else 'its arguments were malformed (' + ';'.join(cls['why']) + ')')
            shown = ('The call is shown above in corrected form; re-issue it if the change is still needed.'
                     if how == 'recovered' else
                     'The call is shown above with the corrupted text removed, so required arguments may be missing; '
                     're-issue it with all required arguments if the change is still needed.')
            if isinstance(obj, dict) and obj.get('status') == 'ok':
                obj['protocol_warning'] = (f'This {name} call was emitted malformed ({what}); it was executed with '
                                           'the corrupted arguments, check the result.')
                m['content'] = json.dumps(obj, ensure_ascii=False)
            else:
                orig = (obj.get('error_message') or obj.get('error') or '') if isinstance(obj, dict) else text
                m['content'] = json.dumps({
                    'status': 'error', 'error_type': 'MalformedToolCall',
                    'error_message': f'This {name} call was not executed as intended: {what}. {shown}',
                    'original_error': str(orig)[:300]}, ensure_ascii=False)
    return msgs, actions


def quarantine_messages(messages, tools, raw_by_call_id=None, canonical=False):
    """Public API (see module docstring)."""
    raw_store = {cid: {'args_str': raw} for cid, raw in (raw_by_call_id or {}).items()}
    return quarantine_history(messages, tool_schemas(tools), raw_store, canonical)


def _selftest():
    edit = {'type': 'function', 'function': {'name': 'edit_file', 'description': 'Edit.', 'parameters': {
        'type': 'object', 'properties': {'filepath': {'type': 'string'}, 'old_string': {'type': 'string'},
                                         'new_string': {'type': 'string'}, 'allow_multiple': {'type': 'boolean'}},
        'required': ['filepath', 'old_string', 'new_string']}}}
    # P1-style slip: new_string closed with a backtick; vLLM 0.19.1 swallows old_string into new_string
    raw = 'filepath:' + D + 'a.py' + D + ',new_string:' + D + 'y = 2\n`,old_string:' + D + 'y = 1\n' + D
    parsed = {'filepath': 'a.py', 'new_string': 'y = 2\n`,old_string:'}
    msgs = [{'role': 'user', 'content': 'fix'},
            {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {
                'name': 'edit_file', 'arguments': json.dumps(parsed)}}]},
            {'role': 'tool', 'tool_call_id': 'c1', 'content': json.dumps({'error': 'Invoking `edit_file()` failed as the '
             'following mandatory input parameters are not present:\nold_string'})}]
    a, act_a = quarantine_messages(msgs, [edit], {'c1': raw})
    b, act_b = quarantine_messages(msgs, [edit])
    ra, rb = json.loads(a[1]['tool_calls'][0]['function']['arguments']), json.loads(b[1]['tool_calls'][0]['function']['arguments'])
    assert act_a[0]['how'] == 'recovered' and ra == {'filepath': 'a.py', 'new_string': 'y = 2\n', 'old_string': 'y = 1\n'}, ra
    assert act_b[0]['how'] == 'sanitized' and rb == {'filepath': 'a.py', 'new_string': 'y = 2\n'}, rb
    assert json.loads(a[2]['content'])['error_type'] == 'MalformedToolCall'
    assert quarantine_messages(a, [edit])[1] == [], 'idempotent on the quarantined history'
    print('P8a (recovered):', json.dumps(ra), '|', json.loads(a[2]['content'])['error_message'])
    print('P8b (sanitized):', json.dumps(rb), '|', json.loads(b[2]['content'])['error_message'])
    print('SELFTEST OK')


if __name__ == '__main__':
    import sys
    if '--selftest' in sys.argv:
        _selftest()
