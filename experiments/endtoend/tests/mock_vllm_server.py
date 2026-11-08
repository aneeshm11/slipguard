"""Mock vLLM /v1/completions for offline tests of the proxy's live path: every generation answers with a short thought
and submit_patch; IPD confirmation requests get <|"|>; forced-token scoring requests return logprob -1.
Usage: mock_vllm_server.py <port> <model_dir>"""
import sys

from aiohttp import web
from transformers import AutoTokenizer

PORT, MD = int(sys.argv[1]), sys.argv[2]
tok = AutoTokenizer.from_pretrained(MD)
D_ID = tok.convert_tokens_to_ids('<|"|>')
EOS = tok.convert_tokens_to_ids('<|tool_response>')
SEEN = {'gen': 0, 'forced': 0, 'confirm': 0, 'prompt_logprobs': 0, 'seeds': []}


async def completions(request):
    b = await request.json()
    if b.get('prompt_logprobs') is not None:
        SEEN['prompt_logprobs'] += 1
    prompts = b['prompt'] if b['prompt'] and isinstance(b['prompt'][0], list) else [b['prompt']]
    out = []
    for i, ids in enumerate(prompts):
        if b.get('allowed_token_ids'):
            SEEN['forced'] += 1
            t = b['allowed_token_ids'][0]
            out.append({'index': i, 'text': tok.decode([t]), 'token_ids': [t], 'finish_reason': 'length', 'stop_reason': None,
                        'logprobs': {'tokens': [f'token_id:{t}'], 'token_logprobs': [-1.0], 'top_logprobs': [{f'token_id:{t}': -1.0}]}})
        elif b.get('max_tokens') == 1:
            SEEN['confirm'] += 1
            out.append({'index': i, 'text': '<|"|>', 'token_ids': [D_ID], 'finish_reason': 'length', 'stop_reason': None})
        else:
            SEEN['gen'] += 1
            SEEN['seeds'].append(b.get('seed'))
            text = tok.decode(ids, skip_special_tokens=False)
            cont = ('' if text.endswith('<|channel>thought\n') else '<|channel>thought\n') + 'mock<channel|>' \
                   '<|tool_call>call:submit_patch{}<tool_call|>'
            t = tok.encode(cont, add_special_tokens=False)[:max(1, b['max_tokens'] - 1)] + [EOS]
            out.append({'index': i, 'text': cont, 'token_ids': t, 'finish_reason': 'stop', 'stop_reason': EOS})
    return web.json_response({'choices': out, 'usage': {}})


async def seen(request):
    return web.json_response(SEEN)


app = web.Application(client_max_size=256 * 1024 ** 2)
app.router.add_post('/v1/completions', completions)
app.router.add_get('/seen', seen)
web.run_app(app, host='127.0.0.1', port=PORT, access_log=None, print=lambda *_: None)
