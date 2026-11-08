"""Parity of the proxy's engine mode with vLLM's own /v1/chat/completions on real agent contexts.
(1) prompt rendering: usage.prompt_tokens equal for every context;
(2) generation+parsing: at temperature 0 (no thinking budget), engine-mode 'base' and passthrough 'pass'
    return the same reasoning / content / tool calls (modulo batch nondeterminism)."""
import asyncio
import json
import random
import sys

import httpx

import os
PROXY = os.environ.get('PROXY', 'http://127.0.0.1:8420')
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
NGEN = int(sys.argv[2]) if len(sys.argv) > 2 else 12
random.seed(1)
ctxs = [json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/protocol/contexts.jsonl'))]
random.shuffle(ctxs)
ctxs = ctxs[:N]


async def call(client, cfg, c, max_tokens, think, temp=0.0):
    body = {'model': 'gemma-4-31b-it-qat-w4a16-ct', 'messages': c['messages'], 'tools': c['tools'],
            'max_tokens': max_tokens, 'temperature': temp, 'seed': 0,
            'chat_template_kwargs': {'enable_thinking': think}}
    r = await client.post(f'{PROXY}/{cfg}/v1/chat/completions', json=body, timeout=900)
    return r.status_code, r.json()


async def main():
    sem = asyncio.Semaphore(int(os.environ.get('CONC', '8')))
    res = {'prompt_equal': 0, 'prompt_diff': [], 'gen_same': 0, 'gen_diff': []}
    async with httpx.AsyncClient() as client:
        async def one(i, c):
            async with sem:
                think = bool(i % 2)
                s1, a = await call(client, 'pass', c, 1, think)
                s2, b = await call(client, 'base', c, 1, think)
                if s1 != 200 or s2 != 200:
                    res['prompt_diff'].append((c['id'], s1, s2, str(a)[:200], str(b)[:200]))
                    return
                pa, pb = a['usage']['prompt_tokens'], b['usage']['prompt_tokens']
                if pa == pb:
                    res['prompt_equal'] += 1
                else:
                    res['prompt_diff'].append((c['id'], pa, pb))
                if i < NGEN:
                    _, a = await call(client, 'pass', c, 1500, False)
                    _, b = await call(client, 'base', c, 1500, False)
                    ma, mb = a['choices'][0]['message'], b['choices'][0]['message']
                    ka = (ma.get('content'), [(t['function']['name'], t['function']['arguments']) for t in ma.get('tool_calls') or []])
                    kb = (mb.get('content'), [(t['function']['name'], t['function']['arguments']) for t in mb.get('tool_calls') or []])
                    if ka == kb and a['usage']['completion_tokens'] == b['usage']['completion_tokens']:
                        res['gen_same'] += 1
                    else:
                        res['gen_diff'].append({'id': c['id'], 'pass': str(ka)[:300], 'base': str(kb)[:300],
                                                'ct': (a['usage']['completion_tokens'], b['usage']['completion_tokens'])})
        await asyncio.gather(*[one(i, c) for i, c in enumerate(ctxs)])
    print(json.dumps({'n': len(ctxs), 'prompt_equal': res['prompt_equal'], 'prompt_diff': res['prompt_diff'][:10],
                      'gen_n': min(NGEN, len(ctxs)), 'gen_same': res['gen_same'], 'gen_diff': res['gen_diff'][:5]}, indent=1))


asyncio.run(main())
