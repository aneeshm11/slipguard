"""Gemma-4 tool-protocol utilities for the end-to-end proxy (workstream E).

Everything here is pure (no I/O) so it can be unit-tested and reused by the analysis scripts:
  * vLLM-faithful prompt rendering (message conversion exactly as vLLM 0.19.1 does it for this template),
  * a canonical-order variant of the official chat template (schema order instead of dictsort),
  * call extraction / malformed-call classification (same criterion as SYNTHESIS §5, generalised to all tools),
  * intent-preserving repair of look-alike-closer slips (minimal version of workstream B's idea),
  * history quarantine (re-render malformed historical calls canonically + annotate their tool responses).
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
import sys as _sys
from pathlib import Path as _Path

# the shipped quarantine (and the classification it relies on) lives in ONE frozen file shared with other workstreams
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / 'export'))
from quarantine_renderer import (_leak, _num, classify_args, intent_parse_args, quarantine_history,  # noqa: E402,F401
                                 reorder_args, sanitize_args, tool_schemas)

D = '<|"|>'
TC_START, TC_END = '<|tool_call>', '<tool_call|>'
CH_START, CH_END = '<|channel>', '<channel|>'
TR_START = '<|tool_response>'
SPECIALS = ['<|"|>', '<|tool_call>', '<tool_call|>', '<|tool_response>', '<tool_response|>', '<|channel>',
            '<channel|>', '<|turn>', '<turn|>', '<|tool>', '<tool|>', '<|think|>']
# look-alike closers, longest first (so '"""' wins over '"' when both are suffixes)
CLOSERS = ['"""', "'''", '```', '\\"', '`', '"', "'"]
CALL_RE = re.compile(r'<\|tool_call>call:([\w\-\.]+)\{(.*?)\}<tool_call\|>', re.DOTALL)  # == vLLM gemma4 parser

# ----------------------------------------------------------------------------------------------
# chat template
# ----------------------------------------------------------------------------------------------
_PROPS_LOOP = "{%- for key, value in properties | dictsort -%}"
_ARGS_LOOP = "{%- for key, value in function['arguments'] | dictsort -%}"


_VOLATILE = [(re.compile(r'\b\d+(?:\.\d+)?\s*(?:s|sec|seconds|ms)\b'), '<T>'),        # durations
             (re.compile(r'0x[0-9a-fA-F]{6,}'), '<ADDR>'),                                  # object addresses
             (re.compile(r'/tmp/[^\s"\']*|/var/tmp/[^\s"\']*'), '<TMP>'),                # temp paths
             (re.compile(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?'), '<TS>'),  # timestamps
             (re.compile(r'"(?:time_seconds_remaining|agent_elapsed_seconds|tool_calls_remaining|tool_calls_used)":\s*[\d.]+'), '<BUDGET>'),
             (re.compile(r'"budget_warning":\s*"[^"]*"'), '<BUDGETW>')]


def tool_output_hash(content) -> str:
    """Hash of a tool result with volatile parts (durations, addresses, temp paths, timestamps, budget counters)
    normalised: replay fidelity check of the branch-at-onset mode."""
    import hashlib
    txt = content if isinstance(content, str) else json.dumps(content, sort_keys=True, default=str)
    for rx, rep in _VOLATILE:
        txt = rx.sub(rep, txt)
    return hashlib.sha1(txt.encode('utf-8', 'replace')).hexdigest()[:16]


def canonical_template(tpl: str) -> str:
    """Official template with tool-declaration properties and historical call arguments rendered in the
    order given (schema order) instead of alphabetical dictsort. Nothing else changes."""
    assert tpl.count(_PROPS_LOOP) == 1 and tpl.count(_ARGS_LOOP) == 1, 'template layout changed'
    return (tpl.replace(_PROPS_LOOP, "{%- for key, value in properties | items -%}")
               .replace(_ARGS_LOOP, "{%- for key, value in function['arguments'] | items -%}"))


def to_conversation(messages: list[dict]) -> list[dict]:
    """OpenAI chat messages -> the conversation vLLM 0.19.1 hands to this template
    (content format 'openai' as detected by the server: every content becomes a list of text parts;
    only `reasoning` (not `reasoning_content`) is read from assistant messages; tool-call arguments
    JSON strings are parsed into dicts; empty tool_calls lists are dropped)."""
    conv = []
    for m in messages:
        role = m['role']
        content = m.get('content')
        if content is None:
            parts = []
        elif isinstance(content, str):
            parts = [{'type': 'text', 'text': content}]
        else:
            parts = []
            for p in content:
                if isinstance(p, str):
                    parts.append({'type': 'text', 'text': p})
                elif p.get('type') in ('text', 'input_text', 'output_text', 'refusal', 'thinking'):
                    t = p.get('text', p.get(p.get('type')))
                    if t is not None:
                        parts.append({'type': 'text', 'text': t})
        msg = {'role': role, 'content': parts}
        if role == 'assistant':
            if m.get('tool_calls') is not None:
                msg['tool_calls'] = copy.deepcopy(list(m['tool_calls']))
            r = m.get('reasoning')
            if r is not None:
                msg['reasoning'] = r
                msg['reasoning_content'] = r
        elif role == 'tool':
            if 'tool_call_id' in m:
                msg['tool_call_id'] = m['tool_call_id']
        if isinstance(m.get('name'), str):
            msg['name'] = m['name']
        conv.append(msg)
    for msg in conv:  # vLLM _postprocess_messages
        if msg['role'] == 'assistant' and 'tool_calls' in msg:
            tcs = msg['tool_calls']
            if not isinstance(tcs, list):
                continue
            if not tcs:
                msg.pop('tool_calls')
                continue
            for item in tcs:
                a = item['function'].get('arguments')
                if a:
                    if not isinstance(a, (dict, list)):
                        item['function']['arguments'] = json.loads(a)
                else:
                    item['function']['arguments'] = {}
    return conv


def open_call_state(text: str):
    """State of the last *open* tool call in generated (non-thinking) text, or None.
    Returns dict(name, done_keys, str_key, str_start) where str_key is the key whose <|"|> string value
    is currently open (None if not inside a string)."""
    i = text.rfind(TC_START)
    if i < 0 or text.find(TC_END, i) >= 0:
        return None
    body_start = i + len(TC_START)
    m = re.match(r'call:([\w\-\.]+)\{', text[body_start:])
    if not m:
        return None
    s = text
    j = body_start + m.end()
    n = len(s)
    done = []
    while j < n:
        while j < n and s[j] in ' ,\n\t':
            j += 1
        if j >= n:
            break
        k0 = j
        while j < n and s[j] != ':':
            if s.startswith(D, j) or s[j] in '{}[]':
                return {'name': m.group(1), 'done_keys': done, 'str_key': None, 'str_start': None, 'garbled': True}
            j += 1
        if j >= n:
            break
        key = s[k0:j].strip()
        j += 1
        while j < n and s[j] in ' \n\t':
            j += 1
        if j >= n:
            break
        if s.startswith(D, j):
            vs = j + len(D)
            e = s.find(D, vs)
            if e < 0:
                return {'name': m.group(1), 'done_keys': done, 'str_key': key, 'str_start': vs, 'garbled': False}
            done.append(key)
            j = e + len(D)
        elif s[j] in '{[':
            depth, j = 1, j + 1
            while j < n and depth:
                if s.startswith(D, j):
                    e = s.find(D, j + len(D))
                    if e < 0:
                        return {'name': m.group(1), 'done_keys': done, 'str_key': None, 'str_start': None,
                                'garbled': False, 'in_nested': True}
                    j = e + len(D)
                    continue
                depth += {'{': 1, '[': 1, '}': -1, ']': -1}.get(s[j], 0)
                j += 1
            if depth:
                return {'name': m.group(1), 'done_keys': done, 'str_key': None, 'str_start': None, 'in_nested': True}
            done.append(key)
        else:
            while j < n and s[j] not in ',}]':
                j += 1
            done.append(key)
    return {'name': m.group(1), 'done_keys': done, 'str_key': None, 'str_start': None, 'garbled': False}


LOOKALIKE = set('`"\'\\')   # look-alike closer characters (same set as workstream B)
STOP_CLOSERS = ['`', '"', "'", '\\']   # minimal: a stop on the LAST run char also catches longer runs
STOP_GAPS = ['', '\n']


def ipd_stop_strings(schemas: dict) -> list[str]:
    """Decode-time stop strings that fire when a string value may have been closed by a look-alike character:
    `<closer>[gap],<key>:` for keys of multi-parameter tools, and `<closer>[gap]}<tool_call|>`.
    No stop for the no-visible-closer slip (`code,key:`): that text also ends every VALID argument
    (`<|"|>,key:`), so it would cost a round trip per argument; those are repaired post hoc."""
    keys = sorted({k for s in schemas.values() if len(s['properties']) > 1 for k in s['properties']})
    stops = [c + g + ',' + k + ':' for c in STOP_CLOSERS for g in STOP_GAPS for k in keys]
    stops += [c + g + '}' + TC_END for c in STOP_CLOSERS for g in STOP_GAPS]
    return list(dict.fromkeys(stops))


@dataclass
class Slip:
    kind: str            # 'key' (closer + ',key:') or 'end' (closer + '}<tool_call|>')
    tool: str
    in_key: str          # string argument whose closer slipped
    next_key: str | None
    next_type: str | None
    content_start: int   # absolute index of the first content char of that string
    run_start: int       # absolute start of the look-alike run
    run: str
    gap: str
    struct_pos: int      # absolute index of ',' (kind key) or '}' (kind end)

    def cuts(self) -> list[int]:
        """candidate positions for the true delimiter (content = text[content_start:cut]); B's cut_positions."""
        return [self.run_start + k for k in range(len(self.run) + len(self.gap) + 1)]


def detect_slip(text: str, schemas: dict) -> Slip | None:
    """Called when an IPD stop fired (text = generated text up to and including the stop string).
    Returns the slip site if the stop sits inside an UNTERMINATED string argument of an open call and is
    followed by a declared, not-yet-emitted key of that tool (or by the end of the call); else None."""
    if text.endswith('}' + TC_END):
        kind, struct_pos, nk = 'end', len(text) - len('}' + TC_END), None
    else:
        mk = re.search(r',([A-Za-z_][\w\-\.]*):$', text)
        if not mk:
            return None
        kind, struct_pos, nk = 'key', mk.start(), mk.group(1)
    pre = text[:struct_pos]
    st = open_call_state(pre)
    if not st or not st.get('str_key') or st.get('garbled'):
        return None
    sch = schemas.get(st['name'])
    if sch is None:
        return None
    props = sch['properties']
    if kind == 'key' and (nk not in props or nk == st['str_key'] or nk in st['done_keys']):
        return None
    j = len(pre)
    while j > st['str_start'] and pre[j - 1] in ' \t\r\n':
        j -= 1
    gap = pre[j:]
    k = j
    while k > st['str_start'] and pre[k - 1] in LOOKALIKE:
        k -= 1
    run = pre[k:j]
    if not run:
        return None
    nt = None
    if nk is not None:
        nt = str((props.get(nk) or {}).get('type') or '').lower() or None
    return Slip(kind, st['name'], st['str_key'], nk, nt, st['str_start'], k, run, gap, struct_pos)


def opener_ok(tok_text: str, next_type: str | None) -> bool:
    """Does the model's next token open a value of the declared type (B's _value_opener_ok, token level)?"""
    if tok_text == D:
        return next_type in (None, 'string')
    x = tok_text.lstrip(' ')
    if not x or next_type == 'string':
        return False
    if next_type == 'boolean':
        return x[0] in 'tf'
    if next_type in ('integer', 'number'):
        return x[0] in '-0123456789'
    if next_type == 'array':
        return x[0] == '['
    if next_type == 'object':
        return x[0] == '{'
    return x[0] in 'tfn-0123456789[{'


class ChannelPrior:
    """Pinned copy of workstream B's intent_decode.ChannelPrior: P_channel(closer string) from logged slips,
    add-alpha smoothing; unseen strings share alpha mass, geometrically down-weighted by length."""
    def __init__(self, counts, alpha=0.5):
        import math
        self._log = math.log
        self.counts = dict(counts)
        self.alpha = alpha
        self.den = sum(self.counts.values()) + alpha * (len(self.counts) + 1)

    def logp(self, closer):
        c = (closer or '').strip(' \t\r\n')
        if c in self.counts:
            return self._log((self.counts[c] + self.alpha) / self.den)
        return self._log(self.alpha / self.den) + max(0, len(c) - 1) * self._log(0.25)


def apply_cut(text: str, slip: Slip, cut: int) -> str:
    """Insert the true delimiter at `cut`; drop the rest of the closer run/gap; keep the model's structure."""
    return text[:cut] + D + text[slip.struct_pos:]


@dataclass
class Repair:
    text: str
    kind: str
    closer: str
    key: str | None
    in_key: str | None
    tool: str
    done: bool = False  # call already complete after the repair


def ipd_repair(gen: str, schemas: dict) -> Repair | None:
    """Deterministic variant (whole run = closer; used only by unit tests / as a fallback when the probe fails)."""
    sl = detect_slip(gen, schemas)
    if sl is None:
        return None
    return Repair(apply_cut(gen, sl, sl.run_start), 'last_arg' if sl.kind == 'end' else 'closer',
                  sl.run + sl.gap, sl.next_key, sl.in_key, sl.tool, sl.kind == 'end')


def _think_spans(text: str):
    spans, i = [], 0
    while True:
        a = text.find(CH_START, i)
        if a < 0:
            return spans
        b = text.find(CH_END, a)
        spans.append((a, len(text) if b < 0 else b))
        if b < 0:
            return spans
        i = b + len(CH_END)


def find_opener_site(text: str, schemas: dict):
    """First 'opener drift' in the tool calls of generated text (outside thinking): a declared argument whose separator
    is not ':' (e.g. Python/JSON 'key=') or a declared STRING argument whose value does not open with <|"|>
    (a Python triple quote, a JSON quote, bare text). Returns {'call_pos','tool','key','cut','lead','sep','is_str'} or None.
    The repair rolls back to `cut` (right after the key) and forces ':' (+ <|"|> for strings) - workstream B's
    opener rule (i+), extended to separator drift."""
    spans = _think_spans(text)
    pos = 0
    while True:
        p = text.find(TC_START, pos)
        if p < 0:
            return None
        pos = p + len(TC_START)
        if any(a <= p < b for a, b in spans):
            continue
        m = re.match(r'call:([\w\-\.]+)\{', text[pos:])
        if not m or m.group(1) not in schemas:
            continue
        name, props = m.group(1), schemas[m.group(1)]['properties']
        j, n = pos + m.end(), len(text)
        while j < n:
            while j < n and text[j] in ' ,\n\t\r':
                j += 1
            if j >= n or text[j] == '}':
                break
            km = re.match(r'[A-Za-z_][\w\-\.]*', text[j:])
            if not km:
                break
            key, k2 = km.group(0), j + km.end()
            s2 = k2
            while s2 < n and text[s2] in ' \t':
                s2 += 1
            if s2 >= n or text[s2] not in ':=':
                break
            sep, v = text[s2], s2 + 1
            while v < n and text[v] in ' \t\n\r':
                v += 1
            spec = props.get(key)
            is_str = str((spec or {}).get('type') or '').lower() == 'string'
            if spec is not None and (sep == '=' or (is_str and not text.startswith(D, v))):
                return {'call_pos': p, 'tool': name, 'key': key, 'cut': k2, 'lead': text[v:v + 8], 'sep': sep, 'is_str': is_str}
            if text.startswith(D, v):
                e = text.find(D, v + len(D))
                if e < 0:
                    break
                j = e + len(D)
            elif v < n and text[v] in '{[':
                depth, j = 1, v + 1
                while j < n and depth:
                    if text.startswith(D, j):
                        e = text.find(D, j + len(D))
                        j = n if e < 0 else e + len(D)
                        continue
                    depth += {'{': 1, '[': 1, '}': -1, ']': -1}.get(text[j], 0)
                    j += 1
            else:
                while v < n and text[v] not in ',}':
                    v += 1
                j = v


