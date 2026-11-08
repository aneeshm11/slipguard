"""qwenproto — Qwen-family tool-call protocol helpers for workstream X (cross-family / cross-format replication).

Formats
  hermes  (Qwen3-8B, Qwen3-32B-FP8): <tool_call>\n{"name": N, "arguments": {...}}\n</tool_call>   JSON, ESCAPED strings
  xml     (Qwen3.5-9B, qwen3_coder): <tool_call>\n<function=N>\n<parameter=k>\nVALUE\n</parameter>\n...</function>\n</tool_call>
          raw (escape-free) values, named asymmetric tags

Contents
  * render(): the prompt vLLM 0.19.1's chat path builds for an OpenAI-format request (ChatCompletionRequest ->
    resolve content format -> parse_chat_messages (tool-call arguments JSON string -> dict, text parts joined) ->
    the model's own HF chat template), i.e. what a Qwen server would see for the logged harness request.
  * serializers that reproduce the templates' call rendering byte-for-byte (checked in smoke tests), and native
    single-closer slip constructors (the closing delimiter of one string argument replaced by a look-alike).
  * production parsers: vLLM 0.19.1 Hermes2ProToolParser / Qwen3CoderToolParser / Qwen3XMLToolParser, non-streaming
    and token-delta streaming (Qwen tokenizer), plus the Qwen3 reasoning split (vLLM Qwen3ReasoningParser semantics).
  * strict reference parsers (fail loud): JSON with no duplicate keys / non-finite numbers / control characters, exact
    XML structure with no structural tag inside a value; both followed by a schema check.
  * judge(): the single malformed definition used by X (workstream A's rules, generalised to the format):
    unparsed (call opened but the production parser returns no call), missing required key, unknown key (edit_file),
    look-alike closer + ',<declared key>:' leak (A's regex), JSON-style closer + '"<edit key>":' leak, XML tag fragment
    inside a value, special token inside a value, non-object arguments, non-string edit argument.
"""
import copy
import json
import logging
import os
import re
import types as pytypes

os.environ.setdefault("HF_HOME", os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "cache/hf"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("VLLM_LOGGING_LEVEL", "ERROR")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

MD = os.environ.get('TRANSCRIPTLAB_MODELS', 'models/')
MODELS = {
    'qwen3-8b': {'dir': MD + 'Qwen3-8B', 'fmt': 'hermes', 'model_type': 'qwen3'},
    'qwen3-32b': {'dir': MD + 'Qwen3-32B-FP8', 'fmt': 'hermes', 'model_type': 'qwen3'},
    'qwen3.5-9b': {'dir': MD + 'Qwen3.5-9B', 'fmt': 'xml', 'model_type': 'qwen3_5'},
    'qwen3.8-27b': {'dir': MD + 'Qwen3.8-27B-FP8', 'fmt': 'xml', 'model_type': 'qwen3_5', 'xml_variant': 'tojson_nonstr'},
    # benchmark extension (prereg_ext.md)
    'qwen3-coder-30b': {'dir': MD + 'Qwen3-Coder-30B-A3B-Instruct-FP8', 'fmt': 'xml', 'model_type': 'qwen3_moe', 'thinking': False},
    'gpt-oss-20b': {'dir': MD + 'gpt-oss-20b', 'fmt': 'harmony', 'model_type': 'gpt_oss', 'ids_prompt': True},
    'devstral-24b': {'dir': MD + 'Devstral-Small-2-24B-Instruct-2512', 'fmt': 'mistral', 'model_type': 'mistral3', 'thinking': False,
                     'ids_prompt': True, 'skip_special_tokens': True},
}


def thinking(mk):
    return MODELS[mk].get('thinking', True)
FMT_TOKENIZER = {'hermes': 'qwen3-8b', 'xml': 'qwen3.5-9b', 'harmony': 'gpt-oss-20b', 'mistral': 'devstral-24b'}  # format-level (CPU) analyses

REQ = {'edit_file': ['filepath', 'old_string', 'new_string'], 'write_file': ['filepath', 'content'], 'read_file': ['filepath'],
       'run_command': ['command'], 'get_status': [], 'submit_patch': []}
EDIT_KEYS = {'filepath', 'old_string', 'new_string', 'allow_multiple'}
EDIT_STR_KEYS = ('filepath', 'old_string', 'new_string')
# workstream A's leak regex (look-alike closer, comma, declared key, colon; Gemma-native spelling) -- verbatim
CLOSER = re.compile(r'(["`\\\']+)\s*,\s*(old_string|new_string|filepath|allow_multiple|content|command|start_line|end_line)\s*:')
# JSON-native spelling of the same leak (closer, comma, QUOTED edit key, colon); restricted to edit keys (rare in code)
CLOSER_JSON = re.compile(r'(["`\\\']+)\s*,\s*\\?"(old_string|new_string|filepath|allow_multiple)\\?"\s*:')
TAG_FRAGS = ('</parameter>', '<parameter=', '</function>', '<function=')
QWEN_SPECIALS = ('<tool_call>', '</tool_call>', '<|im_end|>', '<|im_start|>', '<|endoftext|>', '<think>', '</think>',
                 '<tool_response>', '</tool_response>')
GEMMA_SPECIALS = ('<|"|>', '<|tool_call>', '<tool_call|>', '<|tool_response>', '<tool_response|>', '<|channel>', '<channel|>',
                  '<|turn>', '<turn|>')
NUDGE_GENERIC = ('Please continue your work using the available tools, or call submit_patch when '
                 'you have completed and verified your changes.')  # swegemma agent_runner: turn ended without a tool call
MISSING_ERR = ('Invoking `edit_file()` failed as the following mandatory input parameters are not present:\n{missing}\n'
               'You could retry calling this tool, but it is IMPORTANT for you to provide all the mandatory parameters.')
NOT_FOUND = {'status': 'error', 'error_type': 'FileEditError', 'error_message':
             "Failed to replace: old_string not found. Ensure you're not escaping content incorrectly and check whitespace, indentation, and context."}

_T = {}


def _quiet():
    for name in list(logging.root.manager.loggerDict):
        if name.startswith('vllm') or name.startswith('transformers'):
            logging.getLogger(name).setLevel(logging.CRITICAL)


def hf_tok(mk):
    """HF tokenizer of model key mk (used by the renderer and for token counting)."""
    k = ('hf', mk)
    if k not in _T:
        from transformers import AutoTokenizer
        _T[k] = AutoTokenizer.from_pretrained(MODELS[mk]['dir'])
    return _T[k]


def vllm_tok(mk):
    """vLLM's tokenizer wrapper (what the tool parsers receive in the server)."""
    k = ('vllm', mk)
    if k not in _T:
        from vllm.tokenizers import get_tokenizer
        _T[k] = get_tokenizer(MODELS[mk]['dir'])
        _quiet()
    return _T[k]


def _stub_model_config(mk):
    # text-only requests: parse_chat_messages reads only multimodal_config; resolve_chat_template reads hf_config.model_type
    return pytypes.SimpleNamespace(multimodal_config=None, hf_config=pytypes.SimpleNamespace(model_type=MODELS[mk]['model_type']),
                                   trust_remote_code=False, allowed_local_media_path='', allowed_media_domains=None,
                                   media_io_kwargs=None)


def render(messages, tools, mk, enable_thinking=True):
    """Prompt string exactly as vLLM 0.19.1's /v1/chat/completions path renders it with the model's own template."""
    from vllm.entrypoints.chat_utils import parse_chat_messages
    from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
    from vllm.renderers.hf import resolve_chat_template_content_format, safe_apply_chat_template
    from vllm.renderers.params import merge_kwargs
    tok = hf_tok(mk); mc = _stub_model_config(mk)
    body = {'model': 'm', 'messages': copy.deepcopy(messages), 'tools': copy.deepcopy(tools),
            'chat_template_kwargs': {'enable_thinking': enable_thinking}}
    req = ChatCompletionRequest.model_validate(body)
    tool_dicts = None if req.tools is None else [t.model_dump() for t in req.tools]
    default_kwargs = merge_kwargs({}, dict(tools=tool_dicts, tokenize=False))
    cp = req.build_chat_params(None, 'auto').with_defaults(default_kwargs, default_media_io_kwargs=None,
                                                          default_mm_processor_kwargs=None)
    cf = resolve_chat_template_content_format(chat_template=cp.chat_template, tools=cp.chat_template_kwargs.get('tools'),
                                              given_format=cp.chat_template_content_format, tokenizer=tok, model_config=mc)
    conv, _, _ = parse_chat_messages(req.messages, mc, content_format=cf)
    kw = cp.get_apply_chat_template_kwargs()
    _quiet()
    return safe_apply_chat_template(mc, tok, copy.deepcopy(conv), **kw)


def render_any(messages, tools, mk, enable_thinking=True):
    """-> (prompt_text, prompt_ids). HF-template formats return text (ids None); harmony / mistral are rendered to
    token ids by vLLM 0.19.1's own paths and are sent as token-id prompts (text = a readable decode)."""
    fmt = MODELS[mk]['fmt']
    if fmt == 'harmony':
        import fmt_ext as fe
        ids = fe.harmony_render_ids(messages, tools)
        return fe.harmony_decode(ids), ids
    if fmt == 'mistral':
        import fmt_ext as fe
        ids = fe.mistral_render_ids(messages, tools, mk)
        return fe.mistral_decode(ids, mk), ids
    return render(messages, tools, mk, enable_thinking), None


def n_tokens(text, mk):
    return len(hf_tok(mk)(text, add_special_tokens=False)['input_ids'])


# ----------------------------------------------------------------------------------------------------------------
# serializers (byte-identical to the templates' rendering of a call; verified by smoke tests)
# ----------------------------------------------------------------------------------------------------------------
def _jd(x):
    return json.dumps(x, ensure_ascii=False)  # transformers' tojson filter == json.dumps(ensure_ascii=False)


def hermes_args_text(args, order=None, slip_key=None, closer='`', mode='sub'):
    """JSON text of the arguments object in key order `order`. With slip_key, that string argument's closing quote is
    replaced by `closer` (mode 'sub'), dropped (mode 'omit'), or an internal '"' is left unescaped ('unesc')."""
    order = order or list(args)
    parts = []
    for k in order:
        if k not in args:
            continue
        v = _jd(args[k])
        if k == slip_key and isinstance(args[k], str):
            if mode == 'sub':
                v = v[:-1] + closer
            elif mode == 'omit':
                v = v[:-1]
            elif mode == 'unesc':
                j = v.find('\\"', 1)
                if j < 0:
                    return None
                v = v[:j] + v[j + 1:]
        parts.append(_jd(k) + ': ' + v)
    return '{' + ', '.join(parts) + '}'


def hermes_call_text(name, args_text):
    return '<tool_call>\n{"name": "' + name + '", "arguments": ' + args_text + '}\n</tool_call>'


def xml_value(v, variant=None):
    """Qwen3.5 template: mappings / non-string sequences -> tojson, everything else -> Jinja |string (= str()).
    variant 'tojson_nonstr' (Qwen3.8 template): strings raw, everything else tojson."""
    if variant == 'tojson_nonstr' and not isinstance(v, str):
        return _jd(v)
    if isinstance(v, (dict, list, tuple)):
        return _jd(v)
    if v is True:
        return 'True'
    if v is False:
        return 'False'
    if v is None:
        return 'None'
    return str(v)


def xml_call_text(name, args, order=None, slip_key=None, closer='`', mode='sub', variant=None):
    """Template rendering of one call; with slip_key, that parameter's closing '\\n</parameter>' is replaced by `closer`
    (mode 'sub'), or the next parameter's opener drifts to '<KEY>' with no closer at all ('opener')."""
    order = order or list(args)
    s = '<tool_call>\n<function=' + name + '>\n'
    keys = [k for k in order if k in args]
    for i, k in enumerate(keys):
        val = xml_value(args[k], variant)
        if k == slip_key and mode == 'sub':
            s += '<parameter=' + k + '>\n' + val + closer + '\n'
        elif k == slip_key and mode == 'tagname':
            s += '<parameter=' + k + '>\n' + val + '\n</' + k + '>\n'
        elif mode == 'opener' and i > 0 and keys[i - 1] == slip_key:
            s += '<' + k + '>\n' + val + '\n</' + k + '>\n'
        elif k == slip_key and mode == 'opener':
            s += '<parameter=' + k + '>\n' + val + '\n'
        else:
            s += '<parameter=' + k + '>\n' + val + '\n</parameter>\n'
    return s + '</function>\n</tool_call>'


def call_text(fmt, name, args, order=None, variant=None, form='history'):
    """the call as the template renders it in history (form 'history') or as the model emits it (form 'emit')"""
    if fmt == 'hermes':
        return hermes_call_text(name, hermes_args_text(args, order))
    if fmt == 'xml':
        return xml_call_text(name, args, order, variant=variant)
    import fmt_ext as fe
    at = hermes_args_text(args, order)
    if fmt == 'harmony':
        return fe.harmony_history_call(name, at) if form == 'history' else fe.harmony_emit_call(name, at)
    if fmt == 'mistral':
        return fe.mistral_history_call(name, at) if form == 'history' else fe.mistral_emit_call(name, at)
    raise ValueError(fmt)


def slip_text(fmt, name, args, order, slip_key, closer='`', mode='sub', variant=None):
    """the native single-closer slip as the model would emit it (JSON-argument formats: the slipped string's closing
    quote replaced; XML: the closing '\\n</parameter>' replaced)"""
    if fmt == 'xml':
        return xml_call_text(name, args, order, slip_key, closer, mode, variant)
    t = hermes_args_text(args, order, slip_key, closer, mode)
    if t is None:
        return None
    if fmt == 'hermes':
        return hermes_call_text(name, t)
    import fmt_ext as fe
    if fmt == 'harmony':
        return fe.harmony_emit_call(name, t)
    if fmt == 'mistral':
        return fe.mistral_emit_call(name, t)
    raise ValueError(fmt)


# ----------------------------------------------------------------------------------------------------------------
# production parsers (vLLM 0.19.1)
# ----------------------------------------------------------------------------------------------------------------
_P = {}


def ccr(tools, think=True):
    from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
    kw = dict(model='m', messages=[{'role': 'user', 'content': 'x'}], tools=tools or None, tool_choice='auto',
              chat_template_kwargs={'enable_thinking': think})
    return ChatCompletionRequest(**kw)


def parser_cls(path):
    if path == 'hermes':
        from vllm.tool_parsers.hermes_tool_parser import Hermes2ProToolParser as C
    elif path == 'qwen3_coder':
        from vllm.tool_parsers.qwen3coder_tool_parser import Qwen3CoderToolParser as C
    elif path == 'qwen3_xml':
        from vllm.tool_parsers.qwen3xml_tool_parser import Qwen3XMLToolParser as C
    else:
        raise ValueError(path)
    return C


PROD_PARSER = {'hermes': 'hermes', 'xml': 'qwen3_coder', 'harmony': 'openai', 'mistral': 'mistral'}


def _args_obj(s):
    try:
        return json.loads(s)
    except Exception:
        return {'__unparseable_args__': s}


def parse_nonstream(text, path, tools, mk=None, stop_token=None):
    """vLLM extract_tool_calls -> {'tools_called', 'calls': [{'name','args'}], 'content'}"""
    if path in ('openai', 'mistral'):
        import fmt_ext as fe
        mk = mk or FMT_TOKENIZER['harmony' if path == 'openai' else 'mistral']
        r = fe.harmony_parse(text, tools, mk, stop_token) if path == 'openai' else fe.mistral_parse(text, tools, mk)
        r['calls'] = [{'name': c['name'], 'args': fe.args_dict(c['args_text']), 'args_text': c['args_text']} for c in r['calls']]
        return r
    mk = mk or FMT_TOKENIZER['hermes' if path == 'hermes' else 'xml']
    key = ('ns', path, mk)
    req = ccr(tools)
    if key not in _P:
        _P[key] = parser_cls(path)(vllm_tok(mk), req.tools) if _accepts_tools(path) else parser_cls(path)(vllm_tok(mk))
    p = _P[key]
    try:
        info = p.extract_tool_calls(text, req)
    except Exception as e:  # noqa: BLE001  (the server would return HTTP 500)
        return {'tools_called': False, 'calls': [], 'content': text, 'exception': repr(e)[:200]}
    calls = [{'name': tc.function.name, 'args': _args_obj(tc.function.arguments)} for tc in (info.tool_calls or [])] if info.tools_called else []
    return {'tools_called': bool(info.tools_called), 'calls': calls, 'content': info.content}


def _accepts_tools(path):
    import inspect
    return 'tools' in inspect.signature(parser_cls(path).__init__).parameters


def token_deltas(text, mk):
    """Incremental detokenisation (special tokens kept), like vLLM's detokenizer: (delta_text, token_id) per token."""
    tok = vllm_tok(mk)
    ids = tok.encode(text, add_special_tokens=False)
    out = []; prev = ''
    for k in range(len(ids)):
        lo = max(0, k - 6)
        base = tok.decode(ids[lo:k], skip_special_tokens=False) if k > lo else ''
        cur = tok.decode(ids[lo:k + 1], skip_special_tokens=False)
        if cur.endswith('\ufffd'):
            out.append(('', ids[k])); continue
        if cur.startswith(base):
            out.append((cur[len(base):], ids[k]))
        else:  # rare: re-decode the full prefix
            full = tok.decode(ids[:k + 1], skip_special_tokens=False)
            out.append((full[len(prev):], ids[k]))
        prev = prev + out[-1][0]
    # repair pending replacement chars: make the concatenation equal the full decode
    full = tok.decode(ids, skip_special_tokens=False)
    if ''.join(d for d, _ in out) != full:
        out = []; prev = ''
        for k in range(len(ids)):
            cur = tok.decode(ids[:k + 1], skip_special_tokens=False)
            if cur.endswith('\ufffd'):
                out.append(('', ids[k])); continue
            out.append((cur[len(prev):], ids[k])); prev = cur
    return out


def parse_stream(text, path, tools, mk=None):
    """vLLM extract_tool_calls_streaming fed one token per delta; arguments are concatenated as a client would."""
    mk = mk or FMT_TOKENIZER['hermes' if path == 'hermes' else 'xml']
    req = ccr(tools)
    p = parser_cls(path)(vllm_tok(mk), req.tools) if _accepts_tools(path) else parser_cls(path)(vllm_tok(mk))
    acc = {}; content = []
    prev_text, prev_ids = '', []
    err = None
    for dt, tid in token_deltas(text, mk):
        cur_text = prev_text + dt; cur_ids = prev_ids + [tid]
        try:
            dm = p.extract_tool_calls_streaming(prev_text, cur_text, dt, prev_ids, cur_ids, [tid], req)
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:200]; dm = None
        if dm is not None:
            if dm.content:
                content.append(dm.content)
            for tc in dm.tool_calls or []:
                slot = acc.setdefault(tc.index, {'name': None, 'args': ''})
                fn = tc.function
                if fn is not None:
                    name = fn.get('name') if isinstance(fn, dict) else fn.name
                    a = fn.get('arguments') if isinstance(fn, dict) else fn.arguments
                    if name:
                        slot['name'] = name
                    if a:
                        slot['args'] += a
        prev_text, prev_ids = cur_text, cur_ids
    calls = [{'name': s['name'], 'args': _args_obj(s['args'] or '{}'), 'args_text': s['args']} for _, s in sorted(acc.items())]
    return {'tools_called': bool(calls), 'calls': calls, 'content': ''.join(content) or None, 'exception': err}


def split_reasoning(gen_text):
    """vLLM 0.19.1 Qwen3ReasoningParser.extract_reasoning (thinking enabled): strip a generated <think>; no </think> ->
    everything is reasoning (content None)."""
    a, s, b = gen_text.partition('<think>')
    t = b if s else a
    if '</think>' not in t:
        return t, None
    r, _, c = t.partition('</think>')
    return r, (c or None)


# ----------------------------------------------------------------------------------------------------------------
# strict reference parsers (fail loud; never return altered content)
# ----------------------------------------------------------------------------------------------------------------
class StrictError(Exception):
    def __init__(self, code, pos=None):
        super().__init__(code); self.code = code; self.pos = pos


def _no_dup(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise StrictError('DUPLICATE_KEY')
        d[k] = v
    return d


def _no_const(c):
    raise StrictError('NONFINITE_NUMBER')


def _schema_check(name, args, tools):
    decl = {t['function']['name']: t['function'] for t in (tools or []) if t.get('type') == 'function'}
    if name not in decl:
        raise StrictError('UNKNOWN_TOOL')
    params = decl[name].get('parameters') or {}
    props = params.get('properties') or {}
    for k in params.get('required') or []:
        if k not in args:
            raise StrictError('MISSING_REQUIRED:' + k)
    for k, v in args.items():
        if k not in props:
            raise StrictError('UNKNOWN_KEY')
        ty = props[k].get('type'); nullable = props[k].get('nullable')
        if v is None and nullable:
            continue
        ok = {'string': isinstance(v, str), 'integer': isinstance(v, int) and not isinstance(v, bool),
              'number': isinstance(v, (int, float)) and not isinstance(v, bool), 'boolean': isinstance(v, bool),
              'array': isinstance(v, list), 'object': isinstance(v, dict)}.get(ty, True)
        if not ok:
            raise StrictError('TYPE:' + k)


def strict_hermes(content, tools):
    """content = text after </think>. Accepts optional leading text, then one or more blocks
    '<tool_call>\\n' JSON '\\n</tool_call>' separated by whitespace; JSON strict (no dup keys, no NaN/Infinity, no raw
    control characters), object with exactly 'name' (declared tool) and 'arguments' (object passing the schema)."""
    i = content.find('<tool_call>')
    if i < 0:
        raise StrictError('NO_CALL')
    rest = content[i:]; calls = []
    while rest.strip():
        if not rest.startswith('<tool_call>\n'):
            raise StrictError('BAD_OPEN')
        j = rest.find('\n</tool_call>')
        if j < 0:
            raise StrictError('UNTERMINATED')
        body = rest[len('<tool_call>\n'):j]
        try:
            obj = json.loads(body, object_pairs_hook=_no_dup, parse_constant=_no_const)
        except StrictError:
            raise
        except json.JSONDecodeError as e:
            raise StrictError('JSON:' + e.msg, e.pos)
        if not isinstance(obj, dict) or set(obj) != {'name', 'arguments'} or not isinstance(obj['name'], str):
            raise StrictError('BAD_SHAPE')
        if not isinstance(obj['arguments'], dict):
            raise StrictError('ARGS_NOT_OBJECT')
        _schema_check(obj['name'], obj['arguments'], tools)
        calls.append({'name': obj['name'], 'args': obj['arguments']})
        rest = rest[j + len('\n</tool_call>'):].lstrip()
    return calls


_XML_TAGS = ('<parameter=', '</parameter>', '<function=', '</function>', '<tool_call>', '</tool_call>')


def _xml_convert(v, ty):
    if ty in (None, 'string'):
        return v
    if ty == 'boolean':
        if v.lower() in ('true', 'false'):
            return v.lower() == 'true'
        raise StrictError('TYPE_BOOL')
    if ty == 'integer':
        if re.fullmatch(r'-?\d+', v):
            return int(v)
        raise StrictError('TYPE_INT')
    if ty == 'number':
        try:
            return float(v)
        except ValueError:
            raise StrictError('TYPE_NUM')
    if ty in ('array', 'object'):
        try:
            return json.loads(v)
        except Exception:
            raise StrictError('TYPE_JSON')
    return v


def strict_xml(content, tools):
    """Exact qwen3_coder structure: '<tool_call>\\n<function=N>\\n' ('<parameter=K>\\nV\\n</parameter>\\n')*
    '</function>\\n</tool_call>'; no structural tag inside a value (no escaping exists), unique keys, schema check."""
    decl = {t['function']['name']: t['function'] for t in (tools or []) if t.get('type') == 'function'}
    i = content.find('<tool_call>')
    if i < 0:
        raise StrictError('NO_CALL')
    rest = content[i:]; calls = []
    while rest.strip():
        m = re.match(r'<tool_call>\n<function=([^>\n]+)>\n', rest)
        if not m:
            raise StrictError('BAD_OPEN')
        name = m.group(1); pos = m.end(); args = {}
        props = ((decl.get(name) or {}).get('parameters') or {}).get('properties') or {}
        while True:
            if rest.startswith('</function>\n</tool_call>', pos):
                pos += len('</function>\n</tool_call>'); break
            pm = re.compile(r'<parameter=([^>\n]+)>\n').match(rest, pos)
            if not pm:
                raise StrictError('EXPECTED_PARAM_OR_END', pos)
            k = pm.group(1); vstart = pm.end()
            j = rest.find('\n</parameter>\n', vstart)
            if j < 0:
                raise StrictError('UNTERMINATED_PARAM', vstart)
            v = rest[vstart:j]
            if any(t in v for t in _XML_TAGS):
                raise StrictError('TAG_IN_VALUE', vstart)
            if k in args:
                raise StrictError('DUPLICATE_KEY')
            args[k] = _xml_convert(v, (props.get(k) or {}).get('type'))
            pos = j + len('\n</parameter>\n')
        _schema_check(name, args, tools)
        calls.append({'name': name, 'args': args})
        rest = rest[pos:].lstrip()
    return calls


def strict_parse(content, fmt, tools):
    try:
        calls = (strict_hermes if fmt == 'hermes' else strict_xml)(content, tools)
        return {'ok': True, 'calls': calls}
    except StrictError as e:
        return {'ok': False, 'code': e.code, 'pos': e.pos}


# ----------------------------------------------------------------------------------------------------------------
# tool-schema profiles (v2, added 2026-11-04 ~14:50 UTC for workstream P's contexts). The registered discovery judge
# is the special case prof=None (main-track schema S0: edit_file(filepath, old_string, new_string, allow_multiple),
# module constants REQ / EDIT_KEYS / CLOSER / CLOSER_JSON), which is left byte-for-byte unchanged. Other schemas
# (S1: edit_file(file_path, old_string, new_string); S2: str_replace_editor(command, path, old_str, new_str, ...)) derive
# required keys, the edit tool's declared keys and the leak regexes from the declared tools.
# ----------------------------------------------------------------------------------------------------------------
class Profile:
    def __init__(self, name, edit_tool, path, old, new, req_by_tool, edit_keys, decl_keys, edit_command=None):
        self.name, self.edit_tool, self.path, self.old, self.new = name, edit_tool, path, old, new
        self.edit_command = edit_command  # S2: only command == 'str_replace' calls of the tool are edit calls
        self.req_by_tool = req_by_tool; self.edit_keys = set(edit_keys); self.str_keys = (path, old, new)
        ks = '|'.join(re.escape(k) for k in sorted(decl_keys, key=len, reverse=True))
        eks = '|'.join(re.escape(k) for k in sorted(self.edit_keys, key=len, reverse=True))
        self.closer = re.compile(r'(["`\\\']+)\s*,\s*(' + ks + r')\s*:')
        self.closer_json = re.compile(r'(["`\\\']+)\s*,\s*\\?"(' + eks + r')\\?"\s*:')

    def __repr__(self):
        return f'Profile({self.name}: {self.edit_tool}({self.path}, {self.old}, {self.new}))'


def _decl(tools):
    return {t['function']['name']: t['function'] for t in (tools or []) if t.get('type') == 'function'}


def profile_from_tools(tools):
    """-> None for the registered main-track schema (S0), else a derived Profile (S1 / S2 / generic)."""
    d = _decl(tools)
    props = lambda n: ((d.get(n) or {}).get('parameters') or {}).get('properties') or {}  # noqa: E731
    if 'edit_file' in d and 'filepath' in props('edit_file') and 'old_string' in props('edit_file'):
        return None
    req = {n: list((f.get('parameters') or {}).get('required') or []) for n, f in d.items()}
    allk = set(k for n in d for k in props(n))
    if 'edit_file' in d and 'file_path' in props('edit_file'):
        return Profile('S1', 'edit_file', 'file_path', 'old_string', 'new_string', req, props('edit_file'), allk)
    if 'str_replace_editor' in d:
        return Profile('S2', 'str_replace_editor', 'path', 'old_str', 'new_str', req, props('str_replace_editor'), allk,
                       edit_command='str_replace')
    for n in d:  # generic: a tool declaring an old/new string pair
        pr = props(n)
        for o, nw in (('old_string', 'new_string'), ('old_str', 'new_str'), ('oldString', 'newString')):
            if o in pr and nw in pr:
                path = next((k for k in ('file_path', 'filepath', 'path', 'filePath') if k in pr), None)
                return Profile('generic', n, path, o, nw, req, pr, allk)
    raise ValueError('no edit tool found in the declared tools')


# ----------------------------------------------------------------------------------------------------------------
# judge
# ----------------------------------------------------------------------------------------------------------------
def loose_name(content, fmt):
    if fmt == 'hermes':
        m = re.search(r'"name"\s*:\s*"([\w\-\.]+)"', content)
    else:
        m = re.search(r'<function=([\w\-\.]+)', content)
    return m.group(1) if m else None


def is_edit_call(name, args, prof=None, raw=None):
    """edit-call predicate: name == the edit tool (S2: and command == 'str_replace'; for an unparsed call the raw text
    is searched for the command value)"""
    if prof is None:
        return name == 'edit_file'
    if name != prof.edit_tool:
        return False
    if prof.edit_command is None:
        return True
    if isinstance(args, dict):
        return args.get('command') == prof.edit_command
    return bool(raw) and bool(re.search(r'"command"\s*:\s*"' + prof.edit_command + r'"|<parameter=command>\s*' + prof.edit_command, raw))


def call_flags(name, args, prof=None):
    """Malformed flags of one returned call (one definition; see module docstring). gemma_flags = A's subset.
    prof=None: the registered main-track constants; a Profile: the same rules with schema-derived keys."""
    flags = []
    if not isinstance(args, dict) or '__unparseable_args__' in args:
        return ['args_not_object'], ['args_not_object']
    req = REQ if prof is None else prof.req_by_tool
    edit_tool = 'edit_file' if prof is None else prof.edit_tool
    edit_keys = EDIT_KEYS if prof is None else prof.edit_keys
    str_keys = EDIT_STR_KEYS if prof is None else prof.str_keys
    closer = CLOSER if prof is None else prof.closer
    closer_json = CLOSER_JSON if prof is None else prof.closer_json
    for k in req.get(name, []):
        if k not in args:
            flags.append('missing:' + k)
    if name == edit_tool:
        for k in args:
            if k not in edit_keys:
                flags.append('extra_key')
        for k in str_keys:
            if k in args and not isinstance(args[k], str):
                flags.append('type:' + k)
    for k, v in args.items():
        if isinstance(v, str):
            if closer.search(v):
                flags.append('leak_closer:' + k)
            if closer_json.search(v):
                flags.append('leak_json:' + k)
            if any(t in v for t in TAG_FRAGS):
                flags.append('leak_tag:' + k)
            if any(t in v for t in QWEN_SPECIALS + GEMMA_SPECIALS):
                flags.append('special_tok:' + k)
    flags = sorted(set(flags))
    gem = [f for f in flags if f.startswith(('missing:', 'extra_key', 'leak_closer:', 'special_tok:'))]
    return flags, gem


def edit_fields(args, prof=None):
    """order / file path / old and new strings (always reported under the keys 'fp', 'new_string', 'old_string')"""
    out = {}
    if not isinstance(args, dict):
        return out
    P, O, N = ('filepath', 'old_string', 'new_string') if prof is None else (prof.path, prof.old, prof.new)
    keys = list(args.keys())
    if N in keys and (O not in keys or keys.index(N) < keys.index(O)):
        out['order'] = 'new_first'
    elif O in keys:
        out['order'] = 'old_first'
    else:
        out['order'] = 'neither'
    out['fp'] = args.get(P) if isinstance(args.get(P), str) else None
    for k, kk in (('new_string', N), ('old_string', O)):
        v = args.get(kk)
        out[k] = v if isinstance(v, str) else None
    cl = None
    closer = CLOSER if prof is None else prof.closer
    closer_json = CLOSER_JSON if prof is None else prof.closer_json
    for v in args.values():
        if isinstance(v, str):
            mm = closer.search(v) or closer_json.search(v)
            if mm:
                cl = mm.group(1); break
    out['closer'] = cl
    out['keys'] = keys[:8]
    return out


def strict_json_args(name, args_text, tools):
    """strict reference for JSON-argument formats (harmony, mistral): strict JSON object + schema"""
    try:
        a = json.loads(args_text, object_pairs_hook=_no_dup, parse_constant=_no_const)
        if not isinstance(a, dict):
            raise StrictError('ARGS_NOT_OBJECT')
        _schema_check(name, a, tools)
        return {'ok': True}
    except StrictError as e:
        return {'ok': False, 'code': e.code}
    except json.JSONDecodeError as e:
        return {'ok': False, 'code': 'JSON:' + e.msg}


def judge_ext(gen_text, fmt, tools, mk=None, prof='auto', stop_token=None):
    """judge for harmony (gpt-oss) and mistral (Devstral) generations with the format's vLLM 0.19.1 parser. A call
    delivered with non-JSON arguments (both parsers deliver it) is malformed ('args_not_object'; the client cannot
    execute it) and flagged delivered_invalid."""
    if prof == 'auto':
        prof = profile_from_tools(tools)
    edit_tool = 'edit_file' if prof is None else prof.edit_tool
    if fmt == 'harmony':
        opened = 'to=functions.' in gen_text
        mm = re.search(r'to=functions\.([\w\-\.]+)', gen_text)
        prod = parse_nonstream(gen_text, 'openai', tools, mk, stop_token)
        out = {'closed_think': ('<|channel|>analysis' not in gen_text) or ('<|end|>' in gen_text)}
    else:
        opened = '[TOOL_CALLS]' in gen_text
        mm = re.search(r'\[TOOL_CALLS\]([\w\-\.]+)', gen_text)
        prod = parse_nonstream(gen_text, 'mistral', tools, mk)
        out = {'closed_think': True}
    out['opened_call'] = opened; out['tools_called'] = prod['tools_called']; out['n_calls'] = len(prod['calls'])
    if prod.get('exception'):
        out['parser_exception'] = prod['exception']
    if not prod['calls']:
        if opened:
            out.update(name=mm.group(1) if mm else None, malformed=True, flags=['unparsed'], gemma_flags=['unparsed'], why='unparsed',
                       strict_ok=False, strict_code='UNPARSED')
            i = gen_text.find('to=functions.') if fmt == 'harmony' else gen_text.find('[TOOL_CALLS]')
            out['raw_call'] = gen_text[max(0, i - 40):][:20000]
        else:
            out.update(name=None, malformed=False, flags=[], gemma_flags=[], why='no_call', strict_ok=False, strict_code='NO_CALL')
        out['is_edit'] = is_edit_call(out['name'], None, prof, out.get('raw_call'))
        return out
    first = prod['calls'][0]; name, args = first['name'], first['args']
    out['delivered_invalid'] = '__unparseable_args__' in args or '__not_object__' in args
    if out['delivered_invalid']:
        args = {'__unparseable_args__': first.get('args_text')}
        out['raw_call'] = (first.get('args_text') or '')[:20000]
    flags, gem = call_flags(name, args, prof)
    st = strict_json_args(name, first.get('args_text') or '', tools)
    out.update(name=name, malformed=bool(flags), flags=flags, gemma_flags=gem, why=flags[0] if flags else 'ok',
               strict_ok=st['ok'], strict_code=st.get('code'))
    out['all_calls_ok'] = all(not call_flags(cc['name'], cc['args'], prof)[0] for cc in prod['calls'])
    out['is_edit'] = is_edit_call(name, args if not out['delivered_invalid'] else None, prof, first.get('args_text'))
    if out['is_edit'] and not out['delivered_invalid']:
        out.update(edit_fields(args, prof))
    return out


def judge(gen_text, fmt, tools, mk=None, prof='auto', lenient_reasoning=False, stop_token=None):
    """Judge one generated assistant turn (raw text after the prompt, special tokens kept) as the production stack sees
    it: Qwen3 reasoning split, then the format's vLLM 0.19.1 parser on the content; the FIRST call is judged.
    prof: 'auto' (derive from the declared tools; the main-track schema gives None = the registered constants), None,
    or a Profile. lenient_reasoning=True: a '<tool_call>' inside an UNCLOSED thought ends the reasoning (vLLM 0.31
    Qwen3 engine semantics) instead of the whole output being reasoning (vLLM 0.19.1); sensitivity analysis only.
    With prof resolving to None and lenient_reasoning=False the output equals the registered discovery judge."""
    if fmt in ('harmony', 'mistral'):
        return judge_ext(gen_text, fmt, tools, mk, prof, stop_token)
    if prof == 'auto':
        prof = profile_from_tools(tools)
    edit_tool = 'edit_file' if prof is None else prof.edit_tool
    if mk is not None and not thinking(mk):  # non-thinking model (e.g. Qwen3-Coder): no reasoning parser in production
        reasoning, content = None, gen_text
    else:
        reasoning, content = split_reasoning(gen_text)
    out = {'closed_think': content is not None or '</think>' in gen_text}
    swallowed = content is None and '<tool_call>' in (reasoning or '')
    if swallowed:
        out['call_in_unclosed_reasoning'] = True
        if lenient_reasoning:
            content = reasoning[reasoning.index('<tool_call>'):]
    c = content or ''
    opened = ('<tool_call>' in c) or (fmt == 'xml' and '<function=' in c)
    out['opened_call'] = opened
    path = PROD_PARSER[fmt]
    prod = parse_nonstream(c, path, tools, mk) if c else {'tools_called': False, 'calls': [], 'content': None}
    out['tools_called'] = prod['tools_called']; out['n_calls'] = len(prod['calls'])
    if prod.get('exception'):
        out['parser_exception'] = prod['exception']
    st = strict_parse(c, fmt, tools) if opened else {'ok': False, 'code': 'NO_CALL'}
    out['strict_ok'] = st['ok']; out['strict_code'] = st.get('code')
    if not prod['calls']:
        if opened:
            out.update(name=loose_name(c, fmt), malformed=True, flags=['unparsed'], gemma_flags=['unparsed'], why='unparsed')
            out['raw_call'] = c[c.find('<tool_call>') if '<tool_call>' in c else c.find('<function='):][:20000]
        else:
            out.update(name=None, malformed=False, flags=[], gemma_flags=[], why='no_call')
        out['is_edit'] = is_edit_call(out['name'], None, prof, out.get('raw_call'))
        return out
    first = prod['calls'][0]
    name, args = first['name'], first['args']
    flags, gem = call_flags(name, args, prof)
    out.update(name=name, malformed=bool(flags), flags=flags, gemma_flags=gem, why=flags[0] if flags else 'ok')
    out['all_calls_ok'] = all(not call_flags(cc['name'], cc['args'], prof)[0] for cc in prod['calls'])
    out['is_edit'] = is_edit_call(name, args, prof)
    if out['is_edit']:
        out.update(edit_fields(args, prof))
    return out
