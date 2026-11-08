"""Sanity check of the proxy's fixes on REAL agent contexts (main-track logs) right before an edit_file call:
same context sent to cfg A and cfg B (thinking on, budget 4096, T=0.2, as the harness does); compares
emitted/delivered edit validity and logs IPD events. Small n: a pipeline check, not the causal estimate."""
import asyncio
import os
import json
import random
import sys

import httpx

PROXY = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8420'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 30
CFGS = (sys.argv[3] if len(sys.argv) > 3 else 'base,ipd').split(',')
OUT = sys.argv[4] if len(sys.argv) > 4 else 'logs/test_ipd_real.jsonl'
random.seed(2)
ctxs = [json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/protocol/contexts.jsonl'))]
bad = [c for c in ctxs if not c['orig_ok']]
random.shuffle(bad)
ctxs = bad[:N]


async def main():
    sem = asyncio.Semaphore(int(os.environ.get('CONC', '8')))
    fo = open(OUT, 'a', buffering=1)
    async with httpx.AsyncClient(timeout=1800) as client:
        async def one(c, cfg):
            body = {'model': 'gemma-4-31b-it-qat-w4a16-ct', 'messages': c['messages'], 'tools': c['tools'],
                    'max_tokens': 8192, 'temperature': 0.2, 'top_p': 0.95,
                    'chat_template_kwargs': {'enable_thinking': True}, 'thinking_token_budget': 4096}
            async with sem:
                r = await client.post(f'{PROXY}/{cfg}/v1/chat/completions', json=body, headers={'X-E2E-Task': f'ipdtest-{cfg}:{c["id"]}'})
            j = r.json()
            m = j['choices'][0]['message'] if r.status_code == 200 else {}
            fo.write(json.dumps({'id': c['id'], 'cfg': cfg, 'status': r.status_code,
                                 'calls': [(t['function']['name'], t['function']['arguments'][:300]) for t in m.get('tool_calls') or []],
                                 'content': (m.get('content') or '')[:300]}) + '\n')
        await asyncio.gather(*[one(c, cfg) for c in ctxs for cfg in CFGS])


asyncio.run(main())
