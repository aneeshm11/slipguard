"""Gemma-4 tool-protocol utilities for the end-to-end proxy (workstream E).

Everything here is pure (no I/O) so it can be unit-tested and reused by the analysis scripts:
  * vLLM-faithful prompt rendering (message conversion exactly as vLLM 0.19.1 does it for this template),
  * a canonical-order variant of the official chat template (schema order instead of dictsort),
  * call extraction / malformed-call classification (same criterion as SYNTHESIS §5, generalised to all tools),
  * intent-preserving decoding primitives: workstream B's strict guard + site finder (vendored byte-identical) and
    exact mirrors of B's cut-choice helpers (verify-then-repair; the loop itself lives in e2e_proxy.generate),
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

# ----------------------------------------------------------------------------------------------
# intent-preserving decoding = VERIFY-THEN-REPAIR (workstream B's reference algorithm (i+))
# ----------------------------------------------------------------------------------------------
# B's reference library, vendored byte-identical (proxy/vendor_b_gemma_protocol.py, provenance in VENDOR_B.txt).
# Loaded under a private module name so that it never clashes with this module's name ('gemma_protocol').
def _load_vendor_b():
    import importlib.util
    path = _Path(__file__).resolve().parent / 'vendor_b_gemma_protocol.py'
    name = 'e2e_vendor_b_gemma_protocol'
    if name in _sys.modules:
        return _sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    _sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


BG = _load_vendor_b()
IPD_RULES = ('closer', 'opener')   # B's (i+): look-alike closer slips + drifted string openers (replay.py, generate_call)
IPD_MAX_ROUNDS = 4                 # B's rollback_resume default (rounds per call)


def ipd_stop_strings(schemas: dict) -> list[str]:
    """DEPRECATED (kept for API compatibility): verify-then-repair needs no decode-time stop strings."""
    return []


def b_schema_from_tools(tools) -> dict:
    """B's schema format ({name: {'props': {key: {'type', 'nullable'}}, 'required': [...]}}) from OpenAI tools."""
    return BG.schema_from_tools([t if isinstance(t, dict) else dict(t) for t in (tools or [])])


def b_schema(schemas: dict) -> dict:
    """B's schema format from this module's tool_schemas() output (exact: same properties dicts and required lists)."""
    return BG.schema_from_tools([{'function': {'name': n, 'parameters': {'properties': s['properties'],
                                                                           'required': s['required']}}}
                                 for n, s in (schemas or {}).items()])


def content_start(text: str):
    """Index where vLLM 0.19.1's Gemma4ReasoningParser content begins (its tool parser only sees the content):
    no channel tags -> 0; else after the first <channel|> that follows the first <|channel> (if any); None if the
    thought channel is never closed (no content, no tool calls)."""
    if CH_START not in text and CH_END not in text:
        return 0
    i = text.find(CH_START)
    base = i + len(CH_START) if i >= 0 else 0
    j = text.find(CH_END, base)
    return None if j < 0 else j + len(CH_END)


def answer_calls(text: str) -> list[dict]:
    """Every '<|tool_call>' in the content region, in order: {'pos' (index of <|tool_call>), 'cstart' (index of the
    call text 'call:NAME{...'), 'text' (call text without wrappers, B's format), 'finished' (closed by <tool_call|>)}.
    A call ends at the first <tool_call|> after it, or (unfinished) at the next <|tool_call> / end of text."""
    cs = content_start(text)
    if cs is None:
        return []
    out, i = [], cs
    while True:
        p = text.find(TC_START, i)
        if p < 0:
            return out
        c0 = p + len(TC_START)
        e = text.find(TC_END, c0)
        nxt = text.find(TC_START, c0)
        if e >= 0 and (nxt < 0 or e < nxt):
            out.append({'pos': p, 'cstart': c0, 'text': text[c0:e], 'finished': True})
            i = e + len(TC_END)
        else:
            end = nxt if nxt >= 0 else len(text)
            out.append({'pos': p, 'cstart': c0, 'text': text[c0:end], 'finished': False})
            i = end
            if nxt < 0:
                return out


def strictly_valid(call_text: str, bschema: dict) -> bool:
    """B's GUARD (gemma_protocol.is_valid): strict structural parse + schema (known tool, declared keys, no
    duplicates, required keys, types). Strictly valid calls are never altered by any fix in this proxy."""
    return BG.is_valid(call_text, bschema)


def ipd_scan(text: str, bschema: dict, rules=IPD_RULES, rounds=None, max_rounds=IPD_MAX_ROUNDS):
    """Verify every call of the generated text; return (plan, audit). plan = the first call that is NOT strictly valid
    and has a repairable site (B's first_violation = left-most violation among `rules`; whitespace-tolerant), with the
    site restricted to arguments DECLARED in the tool schema; None if nothing is repairable."""
    audit = {'calls': 0, 'strict_valid': 0, 'invalid': 0, 'no_site': 0, 'site_in_undeclared_key': 0,
             'rounds_exhausted': 0}
    plan = None
    for ci, c in enumerate(answer_calls(text)):
        audit['calls'] += 1
        if strictly_valid(c['text'], bschema):
            audit['strict_valid'] += 1
            continue
        audit['invalid'] += 1
        if plan is not None:
            continue
        if rounds is not None and rounds.get(c['pos'], 0) >= max_rounds:
            audit['rounds_exhausted'] += 1
            continue
        site = BG.first_violation(c['text'], bschema, finished=c['finished'], rules=tuple(rules))
        if site is None:
            audit['no_site'] += 1
            continue
        m = BG._NAME_RE.match(c['text'])
        tool = m.group(1) if m else None
        if getattr(site, 'key', None) not in (bschema.get(tool) or {}).get('props', {}):
            audit['site_in_undeclared_key'] += 1
            continue
        plan = {**c, 'index': ci, 'tool': tool, 'site': site}
    return plan, audit


# exact mirrors of workstream B's intent_decode.py helpers (tests/test_protocol.py checks them against B's module)
def continuation(site, schema_tool) -> str:
    """== intent_decode._continuation: structural text scored after the inserted delimiter."""
    if site.kind == 'end':
        return '}' + TC_END
    ty = str(((schema_tool or {}).get('props', {}).get(site.next_key) or {}).get('type') or '').lower()
    return ',' + site.next_key + ':' + (D if ty == 'string' else '')


def closer_at(site, k) -> str:
    """== intent_decode.closer_at."""
    return site.run[k:] if k <= len(site.run) else ''


def pick_cut(lls, closers, rule, prior) -> int:
    """== intent_decode.pick_cut ('nc' = local LL + closer prior, 'lik' = LL only, 'max' = whole run); ties -> earliest."""
    if rule == 'max':
        return 0
    adj = [lls[k] + (prior.logp(closers[k]) if (rule == 'nc' and prior is not None) else 0.0) for k in range(len(lls))]
    return max(range(len(adj)), key=lambda k: (adj[k], -k))


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


# ----------------------------------------------------------------------------------------------
# analysis-only helpers (failure log); not used on the request path
# ----------------------------------------------------------------------------------------------
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


