"""In-process ECHO backend for the PREREG_v2.4 CPU dry run (plumbing only; no model, no outcome).
/v1/completions:
  stream=True (prefix pin)       -> a few SSE chunks, then [DONE]
  allowed_token_ids (scoring)    -> the forced token with logprob -0.5
  prompt ending at '<|tool_call>' -> a fixed valid edit_file call (retry / greedy from the call head)
  anything else                  -> ',old_string:<|"|>MOCK_OLD<|"|>}' (continues inside a call; a slip pattern after an
                                    injected closer, a valid tail after a forced delimiter)"""
import asyncio, json
from aiohttp import web

FULL = 'call:edit_file{file_path:<|"|>mock.py<|"|>,new_string:<|"|>MOCK_NEW<|"|>,old_string:<|"|>MOCK_OLD<|"|>}'
TAIL = ',old_string:<|"|>MOCK_OLD<|"|>}'


async def start(tok, port=0):
    async def completions(request):
        b = await request.json()
        prompt = b['prompt']
        ids = prompt if isinstance(prompt, list) else tok.encode(prompt, add_special_tokens=False)
        if b.get('stream'):
            resp = web.StreamResponse(headers={'Content-Type': 'text/event-stream'})
            await resp.prepare(request)
            try:
                for _ in range(20):
                    await resp.write(b'data: {"choices": [{"text": "x"}]}\n\n')
                    await asyncio.sleep(0.05)
                await resp.write(b'data: [DONE]\n\n')
            except Exception:          # the pin closes its stream early (expected)
                pass
            return resp
        if b.get('allowed_token_ids'):
            t = int(b['allowed_token_ids'][0])
            return web.json_response({'choices': [{'text': tok.decode([t]), 'finish_reason': 'length',
                                                   'logprobs': {'tokens': [f'token_id:{t}'], 'token_logprobs': [-0.5]}}],
                                      'usage': {'prompt_tokens': len(ids), 'completion_tokens': 1}})
        tail = tok.decode(ids[-8:])
        text = FULL if tail.endswith('<|tool_call>') else TAIL
        n = len(tok.encode(text, add_special_tokens=False))
        return web.json_response({'choices': [{'index': 0, 'text': text, 'finish_reason': 'stop', 'stop_reason': '<tool_call|>'}],
                                  'usage': {'prompt_tokens': len(ids), 'completion_tokens': n}})

    app = web.Application(client_max_size=512 * 1024 ** 2)
    app.router.add_post('/v1/completions', completions)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', port)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f'http://127.0.0.1:{port}/v1'
