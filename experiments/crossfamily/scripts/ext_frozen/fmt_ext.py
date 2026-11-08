"""Workstream X benchmark extension: tool-call formats beyond hermes JSON / qwen3_coder XML.

  harmony (gpt-oss-20b): '<|start|>assistant<|channel|>commentary to=functions.NAME <|constrain|>json<|message|>{JSON}<|call|>'
           rendering = vLLM 0.19.1's chat path for GPT-OSS (system + developer messages via harmony_utils,
           parse_chat_inputs_to_harmony_messages, render_for_completion -> token ids; conversation start date pinned);
           production parser = vLLM OpenAIToolParser on the output token ids (a call whose arguments are not JSON is
           still DELIVERED with the raw argument text).
  mistral (Devstral-Small-2, tokenizer v13): '[TOOL_CALLS]NAME[ARGS]{JSON}'; rendering = vLLM 0.19.1's Mistral chat path
           (maybe_serialize_tool_calls, truncate_tool_call_ids, validate_request_params, MistralTokenizer
           .apply_chat_template -> token ids); production parser = vLLM MistralToolParser (>= v11: arguments are not
           validated -> a call with non-JSON arguments is DELIVERED) on the server's detokenised text
           (skip_special_tokens=True keeps [TOOL_CALLS], drops [ARGS]).
Everything here is imported lazily by qwenproto's dispatch (render / parse_nonstream / judge / call_text / slip_text).
"""
import copy
import json
import os

os.environ.setdefault('TIKTOKEN_RS_CACHE_DIR', os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/data/tiktoken_cache'))
HARMONY_START_DATE = '2026-11-04'   # pinned (vLLM otherwise uses today's date: VLLM_SYSTEM_START_DATE)
_C = {}


def _ccr(messages=None, tools=None):
    from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
    return ChatCompletionRequest.model_validate({'model': 'm', 'messages': copy.deepcopy(messages) if messages else [{'role': 'user', 'content': 'x'}],
                                                 'tools': copy.deepcopy(tools) if tools else None})


# ------------------------------------------------------------------------------------------------ harmony
def harmony_enc():
    if 'henc' not in _C:
        from vllm.entrypoints.openai.parser.harmony_utils import get_encoding
        _C['henc'] = get_encoding()
    return _C['henc']


def harmony_render_ids(messages, tools):
    from vllm.entrypoints.openai.parser.harmony_utils import (get_developer_message, get_system_message,
                                                              parse_chat_inputs_to_harmony_messages, render_for_completion)
    import vllm.tokenizers.mistral as _mt
    req = _ccr(messages, tools)
    _mt.maybe_serialize_tool_calls(req)  # as vLLM's _make_request_with_harmony does
    msgs = [get_system_message(reasoning_effort=req.reasoning_effort, start_date=HARMONY_START_DATE, browser_description=None,
                               python_description=None, with_custom_tools=req.tools is not None)]
    if req.tools:
        msgs.append(get_developer_message(tools=req.tools))
    msgs.extend(parse_chat_inputs_to_harmony_messages(req.messages))
    return list(render_for_completion(msgs))


def harmony_decode(ids):
    return harmony_enc().decode(ids)


def harmony_encode(text):
    return harmony_enc().encode(text, allowed_special='all')


def harmony_history_call(name, args_text):
    """how vLLM's harmony path renders an assistant tool call of the history (recipient in the header, content type
    'json'; verified on rendered prompts)"""
    return '<|start|>assistant to=functions.' + name + '<|channel|>commentary json<|message|>' + args_text + '<|call|>'


def harmony_emit_call(name, args_text):
    """the call as gpt-oss emits it (after the prompt's '<|start|>assistant')"""
    return '<|channel|>commentary to=functions.' + name + ' <|constrain|>json<|message|>' + args_text + '<|call|>'


def harmony_parse(gen_text, tools, mk, stop_token=None):
    """vLLM OpenAIToolParser on the output token ids -> {'tools_called', 'calls': [{name, args_text}], 'content', ...}"""
    from vllm.tool_parsers.openai_tool_parser import OpenAIToolParser
    from vllm.entrypoints.openai.parser.harmony_utils import parse_output_into_messages
    import qwenproto as qp
    ids = harmony_encode(gen_text)
    if stop_token is not None and (not ids or ids[-1] != stop_token):
        ids = ids + [stop_token]
    req = _ccr(None, tools)
    key = ('oaitp', mk)
    if key not in _C:
        _C[key] = OpenAIToolParser(qp.vllm_tok(mk), req.tools)
    try:
        info = _C[key].extract_tool_calls('', req, token_ids=ids)
    except Exception as e:  # noqa: BLE001  (harmony parse error -> the server would fail the request)
        return {'tools_called': False, 'calls': [], 'content': None, 'exception': repr(e)[:200], 'reasoning': None}
    try:
        p = parse_output_into_messages(ids)
        reasoning = ''.join(m.content[0].text for m in p.messages if m.channel == 'analysis' and m.content)
    except Exception:  # noqa: BLE001
        reasoning = None
    calls = [{'name': tc.function.name, 'args_text': tc.function.arguments} for tc in (info.tool_calls or [])]
    return {'tools_called': bool(info.tools_called), 'calls': calls, 'content': info.content, 'reasoning': reasoning}


# ------------------------------------------------------------------------------------------------ mistral
def mistral_tok(mk):
    key = ('mtok', mk)
    if key not in _C:
        import qwenproto as qp
        from vllm.tokenizers.mistral import MistralTokenizer
        _C[key] = MistralTokenizer.from_pretrained(qp.MODELS[mk]['dir'])
    return _C[key]


def strip_reasoning(messages):
    """Devstral-Small-2's v13 tokenizer has no think tokens: mistral_common rejects assistant messages that carry
    reasoning_content ('think tokens are not available'), i.e. vLLM answers HTTP 400 for every request of a history
    with thoughts. The harness must drop them; X does so for this model (documented adaptation)."""
    out = copy.deepcopy(messages)
    for m in out:
        if m.get('role') == 'assistant':
            m.pop('reasoning_content', None); m.pop('reasoning', None)
    return out


def mistral_render_ids(messages, tools, mk, strip_thoughts=True):
    import vllm.tokenizers.mistral as _mt
    from vllm.renderers.mistral import safe_apply_chat_template
    req = _ccr(strip_reasoning(messages) if strip_thoughts else messages, tools)
    _mt.maybe_serialize_tool_calls(req); _mt.truncate_tool_call_ids(req); _mt.validate_request_params(req)
    tool_dicts = None if req.tools is None else [t.model_dump() for t in req.tools]
    # mistral_common rejects add_generation_prompt after a final assistant message (HTTP 400 in vLLM); a history that
    # ends with an assistant text turn (arm P5 when the removed call was the last turn) is rendered with
    # continue_final_message=True, i.e. the model continues that assistant turn (documented format adaptation)
    last_asst = (req.messages[-1].get('role') if isinstance(req.messages[-1], dict) else getattr(req.messages[-1], 'role', None)) == 'assistant'
    ids = safe_apply_chat_template(mistral_tok(mk), req.messages, tools=tool_dicts, add_generation_prompt=not last_asst,
                                   continue_final_message=last_asst, tokenize=True)
    return list(ids)


def mistral_decode(ids, mk, skip_special_tokens=False):
    return mistral_tok(mk).decode(ids, skip_special_tokens=skip_special_tokens)


def mistral_history_call(name, args_text):
    return '[TOOL_CALLS]' + name + '[ARGS]' + args_text


def mistral_emit_call(name, args_text, server_text=True):
    """the call as the server's detokeniser shows it (skip_special_tokens=True drops [ARGS], keeps [TOOL_CALLS])"""
    return '[TOOL_CALLS]' + name + ('' if server_text else '[ARGS]') + args_text


def mistral_parse(gen_text, tools, mk):
    from vllm.tool_parsers.mistral_tool_parser import MistralToolParser
    req = _ccr(None, tools)
    key = ('mtp', mk)
    if key not in _C:
        _C[key] = MistralToolParser(mistral_tok(mk), req.tools)
    p = _C[key]
    try:
        info = p.extract_tool_calls(gen_text, req)
    except Exception as e:  # noqa: BLE001
        return {'tools_called': False, 'calls': [], 'content': gen_text, 'exception': repr(e)[:200]}
    calls = [{'name': tc.function.name, 'args_text': tc.function.arguments} for tc in (info.tool_calls or [])] if info.tools_called else []
    return {'tools_called': bool(info.tools_called), 'calls': calls, 'content': info.content}


# ------------------------------------------------------------------------------------------------ shared
def args_dict(args_text):
    try:
        a = json.loads(args_text)
        return a if isinstance(a, dict) else {'__not_object__': args_text}
    except Exception:
        return {'__unparseable_args__': args_text}
