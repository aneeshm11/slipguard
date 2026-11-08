"""Gemma-4 tool-protocol helpers shared by the injection experiment: rendering (log-faithful), raw-call construction,
judging generated calls with vLLM 0.19.1's own gemma4 argument parser.

The parser is vLLM's `_parse_gemma4_args`; its array helper is replaced in-process by the main track's hang fix
(/harness/work/scripts/serve_vllm.py::_patch_gemma4_array_parser; identical output otherwise), and every
parse runs under a wall-clock guard.
"""
import os  # added by the repo export (paths are env/config driven)
import json, re, signal, copy
import vllm.tool_parsers.gemma4_tool_parser as g

D = g.STRING_DELIM  # '<|"|>'
TOOL_CALL_RE = re.compile(r"<\|tool_call>call:([\w\-\.]+)\{(.*?)\}<tool_call\|>", re.DOTALL)  # vLLM extract_tool_calls regex
CLOSER = re.compile(r'(["`\\\']+)\s*,\s*(old_string|new_string|filepath|allow_multiple|content|command|start_line|end_line)\s*:')
EDIT_KEYS = {'filepath', 'old_string', 'new_string', 'allow_multiple'}
REQ = {'edit_file': ['filepath', 'old_string', 'new_string'], 'write_file': ['filepath', 'content'], 'read_file': ['filepath'],
       'run_command': ['command'], 'get_status': [], 'submit_patch': []}
OLD_TEMPLATE = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')   # produced the logs
NEW_TEMPLATE = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')  # current HF template
MISSING_ERR = ('Invoking `edit_file()` failed as the following mandatory input parameters are not present:\n{missing}\n'
               'You could retry calling this tool, but it is IMPORTANT for you to provide all the mandatory parameters.')
NUDGE_TRUNCATED_CALL = ('<competition-harness truncated-call retry message withheld in the public export (M9)>')  # harness text withheld (M9)


def _patched_array(arr_str, *, partial=False):
    items, i, n = [], 0, len(arr_str)
    while i < n:
        while i < n and arr_str[i] in (' ', ',', '\n', '\t'):
            i += 1
        if i >= n: break
        if arr_str[i:].startswith(D):
            i += len(D); end_pos = arr_str.find(D, i)
            if end_pos == -1: items.append(arr_str[i:]); break
            items.append(arr_str[i:end_pos]); i = end_pos + len(D)
        elif arr_str[i] == '{':
            depth, obj_start = 1, i + 1; i += 1
            while i < n and depth > 0:
                if arr_str[i:].startswith(D):
                    i += len(D); nd = arr_str.find(D, i); i = nd + len(D) if nd != -1 else n; continue
                if arr_str[i] == '{': depth += 1
                elif arr_str[i] == '}': depth -= 1
                i += 1
            items.append(g._parse_gemma4_args(arr_str[obj_start:i], partial=True) if depth > 0 else g._parse_gemma4_args(arr_str[obj_start:i - 1]))
        elif arr_str[i] == '[':
            depth, sub_start = 1, i + 1; i += 1
            while i < n and depth > 0:
                if arr_str[i] == '[': depth += 1
                elif arr_str[i] == ']': depth -= 1
                i += 1
            items.append(_patched_array(arr_str[sub_start:i], partial=True) if depth > 0 else _patched_array(arr_str[sub_start:i - 1]))
        else:
            val_start = i
            while i < n and arr_str[i] not in (',', ']'): i += 1
            if i == val_start: i += 1; continue
            if partial and i >= n: break
            items.append(g._parse_gemma4_value(arr_str[val_start:i]))
    return items


g._parse_gemma4_array = _patched_array


class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout()


def parse_args(args_str, timeout_s=5):
    """vLLM's _parse_gemma4_args with a wall-clock guard (main thread only)."""
    old = signal.signal(signal.SIGALRM, _alarm); signal.alarm(timeout_s)
    try:
        return g._parse_gemma4_args(args_str)
    except _Timeout:
        return {'__parse_timeout__': True}
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM, old)


def fmt_value(v):
    if v is None: return 'null'
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, str): return D + v + D
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, dict): return '{' + ','.join(f'{k}:{fmt_value(x)}' for k, x in v.items()) + '}'
    if isinstance(v, list): return '[' + ','.join(fmt_value(x) for x in v) + ']'
    return str(v)


def raw_args(args, order, slip_key=None, closer='`'):
    """The argument text a model emits for `args` in key order `order`; if slip_key is given, that string argument is
    closed with `closer` instead of the <|"|> delimiter (the dominant real slip)."""
    parts = []
    for k in order:
        if k not in args: continue
        v = args[k]
        if k == slip_key and isinstance(v, str):
            parts.append(f'{k}:{D}{v}{closer}')
        else:
            parts.append(f'{k}:{fmt_value(v)}')
    return ','.join(parts)


def canonical_call_text(name, args):
    """Schema order for edit_file (filepath, old_string, new_string, allow_multiple), rendered like the template."""
    order = ['filepath', 'old_string', 'new_string', 'allow_multiple'] + [k for k in args if k not in EDIT_KEYS]
    return '<|tool_call>call:' + name + '{' + ','.join(f'{k}:{fmt_value(args[k])}' for k in order if k in args) + '}<tool_call|>'


def to_template_messages(msgs):
    """Log messages -> what vLLM 0.19.1's chat path hands the template: tool-call arguments as dicts and string contents
    as OpenAI text parts (the template appends ' ' after the system text in that case; this reproduces logged
    prompt_tokens exactly)."""
    out = []
    for i, m in enumerate(msgs):
        m = copy.deepcopy(m)
        if m.get('tool_calls'):
            for t in m['tool_calls']:
                f = t['function']
                if isinstance(f.get('arguments'), str):
                    f['arguments'] = json.loads(f['arguments']) if f['arguments'] else {}
        if i == 0 and m.get('role') == 'system' and isinstance(m.get('content'), str):
            m['content'] = [{'type': 'text', 'text': m['content']}]
        out.append(m)
    return out


def judge(stage2_text, stopped_on_close, name_hint=None):
    """Judge the text generated after '<|tool_call>' exactly like vLLM's non-streaming extractor would see it."""
    full = '<|tool_call>' + stage2_text + ('<tool_call|>' if stopped_on_close else '')
    m = TOOL_CALL_RE.search(full)
    out = {'parsed': bool(m)}
    if not m:
        mm = re.match(r'<\|tool_call>\s*call[:\s]*([\w\-\.]+)', full)
        out['name'] = mm.group(1) if mm else None
        out['malformed'] = True; out['why'] = 'unparsed' + ('' if stopped_on_close else '_unclosed')
        out['flags'] = ['unparsed']
        return out
    name, astr = m.group(1), m.group(2)
    a = parse_args(astr)
    out['name'] = name
    flags = []
    if a.get('__parse_timeout__'): flags.append('parse_timeout')
    for k in REQ.get(name, []):
        if k not in a: flags.append('missing:' + k)
    if name == 'edit_file':
        for k in a:
            if k not in EDIT_KEYS: flags.append('extra_key')
    for k, v in a.items():
        if isinstance(v, str):
            if CLOSER.search(v): flags.append('leak_closer:' + k)
            if D in v or '<tool_call|>' in v or '<|tool_call>' in v: flags.append('special_tok:' + k)
    flags = sorted(set(flags))
    out['flags'] = flags; out['malformed'] = bool(flags); out['why'] = flags[0] if flags else 'ok'
    keys = list(a.keys()); out['keys'] = keys[:6]
    if name == 'edit_file':
        if 'new_string' in keys and ('old_string' not in keys or keys.index('new_string') < keys.index('old_string')): out['order'] = 'new_first'
        elif 'old_string' in keys: out['order'] = 'old_first'
        else: out['order'] = 'neither'
        cl = None
        for v in a.values():
            if isinstance(v, str):
                mm = CLOSER.search(v)
                if mm: cl = mm.group(1); break
        out['closer'] = cl
        out['fp'] = a.get('filepath') if isinstance(a.get('filepath'), str) else None
        ns = a.get('new_string') if isinstance(a.get('new_string'), str) else ''
        mm = CLOSER.search(ns)
        out['new_head'] = (ns[:mm.start()] if mm else ns)[:160]
        out['lit_backslash_n'] = ns.count('\\n')
    return out


def judge_decision(stage2_text, stop_str):
    """Judge an edit call cut right after its first string argument closed (decision-point stop on ',old_string:' or
    ',new_string:'). Correct closure => the text ends with <|"|>; anything else => look-alike closer slip, which vLLM would
    turn into a lost argument (the parser takes everything up to the next <|"|> into the first string)."""
    full = '<|tool_call>' + stage2_text
    mm = re.match(r'<\|tool_call>\s*call[:\s]*([\w\-\.]+)\{', full)
    name = mm.group(1) if mm else None
    out = {'parsed': False, 'decision_point': True, 'name': name, 'stop': stop_str}
    nxt = stop_str.strip(',:')
    # the string argument that just closed
    kk = re.findall(r'(\w+):' + re.escape(D), stage2_text)
    first_key = kk[-1] if kk else None
    body_ = re.sub(r'(,\s*\w+:(true|false|null|-?\d+(\.\d+)?))+\s*$', '', stage2_text)  # trailing bare-value args
    if body_.endswith(D):
        out.update({'malformed': False, 'why': 'ok', 'flags': [], 'order': 'new_first' if nxt == 'old_string' else 'old_first'})
    else:
        tail = re.search(r'(["`\\\']+)\s*$', body_)
        cl = tail.group(1) if tail else None
        out.update({'malformed': True, 'why': 'leak_closer:' + str(first_key), 'flags': ['leak_closer:' + str(first_key), 'missing:' + nxt],
                    'closer': cl, 'order': 'new_first' if nxt == 'old_string' else 'old_first'})
    fpm = re.search(r'filepath:' + re.escape(D) + r'(.*?)' + re.escape(D), stage2_text, re.S)
    out['fp'] = fpm.group(1) if fpm else None
    nm = re.search(r'new_string:' + re.escape(D) + r'(.*)', stage2_text, re.S)
    if nm:
        v = nm.group(1)
        if v.endswith(D): v = v[:-len(D)]
        out['new_head'] = v[:160]; out['lit_backslash_n'] = v.count('\\n')
    return out
