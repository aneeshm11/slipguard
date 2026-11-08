import os, sys, json, copy, types as pytypes, logging
os.environ.setdefault("HF_HOME", os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "cache/hf")); os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1"); os.environ.setdefault("VLLM_LOGGING_LEVEL", "ERROR")
from transformers import AutoTokenizer
from vllm.entrypoints.chat_utils import parse_chat_messages
from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
from vllm.renderers.hf import resolve_chat_template_content_format, safe_apply_chat_template
from vllm.renderers.params import merge_kwargs
META = {}
for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')):
    m = json.loads(l); META[m['id']] = m
ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt'))]
ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
def load(m):
    with open(f"{ROOT}/{m['run']}/{m['file']}", 'rb') as f:
        f.seek(m['off']); d = json.loads(f.readline()); f.seek(m['tools_off']); tools = json.loads(f.readline())['tools']
    return d, tools
d, tools = load(META[ids[0]])
msgs = d['messages']
# reasoning fields
import collections
cnt = collections.Counter()
for i in ids[:100]:
    dd, _ = load(META[i])
    for x in dd['messages']:
        if x['role'] == 'assistant':
            cnt['asst'] += 1; cnt['rc_nonnull'] += x.get('reasoning_content') is not None; cnt['r_nonnull'] += x.get('reasoning') is not None
            cnt['content_nonnull'] += bool(x.get('content'))
        if x['role'] == 'user': cnt['user'] += 1; cnt['user_list'] += isinstance(x.get('content'), list)
        if x['role'] == 'system': cnt['sys_list'] += isinstance(x.get('content'), list)
print('field stats over 100 gate contexts:', dict(cnt))
print('extra_body:', d.get('extra_body'), 'temp', d.get('temperature'), 'top_p', d.get('top_p'), 'max_tokens', d.get('max_tokens'))
for mk in ['Qwen3.5-9B']:
    tok = AutoTokenizer.from_pretrained(fos.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), '{mk}'))
    mc = pytypes.SimpleNamespace(multimodal_config=None, hf_config=pytypes.SimpleNamespace(model_type='qwen3'), trust_remote_code=False,
                                 allowed_local_media_path='', allowed_media_domains=None, media_io_kwargs=None)
    body = {'model': 'x', 'messages': copy.deepcopy(msgs), 'tools': tools, 'chat_template_kwargs': {'enable_thinking': True}}
    req = ChatCompletionRequest.model_validate(body)
    tool_dicts = [t.model_dump() for t in req.tools]
    default_kwargs = merge_kwargs({}, dict(tools=tool_dicts, tokenize=False))
    cp = req.build_chat_params(None, 'auto').with_defaults(default_kwargs, default_media_io_kwargs=None, default_mm_processor_kwargs=None)
    cf = resolve_chat_template_content_format(chat_template=cp.chat_template, tools=cp.chat_template_kwargs.get('tools'), given_format=cp.chat_template_content_format, tokenizer=tok, model_config=mc)
    conv, _, _ = parse_chat_messages(req.messages, mc, content_format=cf)
    kw = cp.get_apply_chat_template_kwargs()
    p = safe_apply_chat_template(mc, tok, copy.deepcopy(conv), **kw)
    try:
        direct = tok.apply_chat_template(copy.deepcopy(msgs), tools=tools, tokenize=False, add_generation_prompt=True, enable_thinking=True)
    except Exception as e:
        direct = 'ERR ' + repr(e)[:100]
    print('=====', mk, 'content_format', cf, 'kw', {k: v for k, v in kw.items() if k not in ('tools', 'chat_template')})
    print('n_tokens vllm-path', len(tok(p, add_special_tokens=False)['input_ids']), 'direct', len(tok(direct, add_special_tokens=False)['input_ids']), 'same', p == direct, 'logged gemma pt', d['prompt_tokens'])
    print('conv[2] keys', list(conv[2].keys()), 'args type', type(conv[2]['tool_calls'][0]['function']['arguments']))
    print('conv[1] content type', type(conv[1]['content']), repr(conv[1]['content'])[:200])
    print(p[:1500]); print('.....'); print(p[-3000:])
