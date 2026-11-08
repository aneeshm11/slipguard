"""CPU mock of vLLM /v1/completions (streaming) for harmony / mistral / xml-nothink formats (token-id or text prompts).
seed % 5 == 0 (harmony): an analysis message of 5,000 chunks without '<|end|>' (budget path); seed % 7 == 0: a call whose
JSON arguments are broken; else a valid edit_file call (S1 keys). usage: mock_server_ext.py <port> <fmt>"""
import asyncio
import json
import sys

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

PORT = int(sys.argv[1]); FMT = sys.argv[2]
app = FastAPI()
ARGS = {'file_path': 'a.py', 'new_string': 'x = "1"\n', 'old_string': 'x = 0\n'}


def args_text(bad=False):
    a = json.dumps(ARGS)
    return a.replace('\\n", "old_string"', '\\n`, "old_string"') if bad else a


def call(bad=False):
    if FMT == 'harmony':
        return ['<|start|>assistant', '<|channel|>commentary to=functions.edit_file <|constrain|>json<|message|>', args_text(bad)]
    if FMT == 'mistral':
        return ['[TOOL_CALLS]', 'edit_file', args_text(bad)]
    s = '<tool_call>\n<function=edit_file>\n'
    for k, v in ARGS.items():
        s += f'<parameter={k}>\n{v}\n</parameter>\n'
    return [s + '</function>\n</tool_call>']


@app.get('/v1/models')
async def models():
    return JSONResponse({'data': [{'id': 'mock', 'max_model_len': 32768}]})


@app.post('/v1/completions')
async def comp(req: Request):
    b = await req.json()
    seed = b.get('seed') or 0; mt = b['max_tokens']; prompt = b['prompt']
    cont = isinstance(prompt, list) and len(prompt) > 3 and prompt[-2:] == [200007, 200006] or (isinstance(prompt, list) and prompt[-1:] == [200006])
    stop = None
    if FMT == 'harmony':
        if cont:
            chunks = call()[1:]; stop = 200012
        elif seed % 5 == 0:
            chunks = ['<|channel|>analysis<|message|>'] + ['a '] * 5000
        else:
            chunks = ['<|channel|>analysis<|message|>', 'thinking', '<|end|>'] + call(bad=seed % 7 == 0); stop = 200012
    elif FMT == 'mistral':
        chunks = call(bad=seed % 7 == 0); stop = 2
    else:
        chunks = call(); stop = None
    chunks = chunks[:mt]

    async def gen():
        for i, c in enumerate(chunks):
            last = i == len(chunks) - 1
            fin = ('length' if len(chunks) == mt else 'stop') if last else None
            yield 'data: ' + json.dumps({'choices': [{'index': 0, 'text': c, 'finish_reason': fin, 'stop_reason': stop if last else None}]}) + '\n\n'
            if i % 200 == 0:
                await asyncio.sleep(0)
        yield 'data: ' + json.dumps({'choices': [], 'usage': {'completion_tokens': len(chunks)}}) + '\n\n'
        yield 'data: [DONE]\n\n'
    return StreamingResponse(gen(), media_type='text/event-stream')


uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='error')
