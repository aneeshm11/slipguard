"""CPU-only mock of vLLM's OpenAI /v1/completions streaming endpoint for an end-to-end test of run_qwen.py.
Behaviour by seed: seed % 5 == 0 -> a 5,000-chunk thought with no '</think>' (tests the post-hoc thinking budget);
seed % 7 == 0 -> a malformed call; else a short thought + a valid edit_file call. A prompt that ends with '</think>'
(budget continuation) gets a valid call. usage: mock_server.py <port> <fmt hermes|xml>"""
import asyncio
import json
import sys

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

PORT = int(sys.argv[1]); FMT = sys.argv[2]
app = FastAPI()
ARGS = {'filepath': 'a.py', 'new_string': 'x = "1"\n', 'old_string': 'x = 0\n'}


def call(bad=False):
    if FMT == 'hermes':
        a = json.dumps(ARGS)
        if bad:
            a = a.replace('\\n", "old_string"', '\\n`, "old_string"')
        return '<tool_call>\n{"name": "edit_file", "arguments": ' + a + '}\n</tool_call>'
    s = '<tool_call>\n<function=edit_file>\n'
    for k, v in ARGS.items():
        s += f'<parameter={k}>\n{v}' + ('`,old_string:' if bad and k == 'new_string' else '') + '\n</parameter>\n'
    return s + '</function>\n</tool_call>'


@app.get('/v1/models')
async def models():
    return JSONResponse({'data': [{'id': 'mock', 'max_model_len': 32768}]})


@app.post('/v1/completions')
async def comp(req: Request):
    b = await req.json()
    prompt = b['prompt']; seed = b.get('seed') or 0; mt = b['max_tokens']
    pre = '<think>\n' if FMT == 'hermes' else ''
    if prompt.endswith('</think>'):
        chunks = ['\n\n'] + [call()]
    elif seed % 5 == 0:
        chunks = [pre] + ['a '] * 5000
    elif seed % 7 == 0:
        chunks = [pre, 'thinking ', 'more', '\n</think>\n\n', call(bad=True)]
    else:
        chunks = [pre, 'thinking ', 'more', '\n</think>\n\n', call()]
    chunks = chunks[:mt]

    async def gen():
        for i, c in enumerate(chunks):
            fin = 'length' if (i == len(chunks) - 1 and len(chunks) == mt) else ('stop' if i == len(chunks) - 1 else None)
            yield 'data: ' + json.dumps({'choices': [{'index': 0, 'text': c, 'finish_reason': fin}]}) + '\n\n'
            if i % 200 == 0:
                await asyncio.sleep(0)
        yield 'data: ' + json.dumps({'choices': [], 'usage': {'completion_tokens': len(chunks)}}) + '\n\n'
        yield 'data: [DONE]\n\n'
    return StreamingResponse(gen(), media_type='text/event-stream')


uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='error')
