"""Run the official swegemma 0.2.11 harness (Evaluator, ADK agent, Docker sandbox, Phase-2 verification)
against the protocol proxy. The harness code is unchanged except for: (1) the model registry points the
declared alias at the proxy (<proxy>/<cfg>/v1), (2) a header X-E2E-Task tags each LLM call with its attempt
id (for log joins), (3) sync tools run in a thread pool so concurrent tasks do not block each other
(tool calls within one task are serialised per container, as on Kaggle), (4) rootless-docker CPU-quota patch
(common.py).

Usage: run_harness.py --cfg base --tasks @file --out runs/X [--concurrency 8] [--sub subs/sample_noadapter]
"""
from __future__ import annotations

import argparse
import asyncio
import contextvars
import json
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import swegemma.sandbox.docker as sd  # noqa: E402
import yaml  # noqa: E402
from google.adk.models import lite_llm  # noqa: E402

CUR = common.CUR_TASK
_locks: dict[str, threading.Lock] = {}
_glock = threading.Lock()
_orig_exec = sd.ContainerManager.exec


def _serial_exec(self, container_id, command, *, timeout=None):
    with _glock:
        lk = _locks.setdefault(container_id, threading.Lock())
    with lk:
        return _orig_exec(self, container_id, command, timeout=timeout)


sd.ContainerManager.exec = _serial_exec


def install_llm_hook(log_path: Path):
    orig = lite_llm.LiteLLMClient.acompletion
    f = open(log_path, 'a', buffering=1)

    async def acompletion(self, model, messages, tools, **kwargs):
        tid = CUR.get()
        kwargs['extra_headers'] = {**(kwargs.get('extra_headers') or {}), 'X-E2E-Task': tid}
        t0 = time.time()
        err = None
        try:
            resp = await orig(self, model, messages, tools, **kwargs)
            return resp
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:300]
            raise
        finally:
            rec = {'task': tid, 't': t0, 's': round(time.time() - t0, 2), 'n_msgs': len(messages),
                   'n_tools': len(tools or []), 'err': err, 'extra_body': kwargs.get('extra_body'),
                   'max_tokens': kwargs.get('max_tokens') or kwargs.get('max_completion_tokens'),
                   'temperature': kwargs.get('temperature')}
            try:
                f.write(json.dumps(rec, default=str) + '\n')
            except Exception:  # noqa: BLE001
                pass

    lite_llm.LiteLLMClient.acompletion = acompletion


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cfg', required=True)
    ap.add_argument('--proxy', default='http://127.0.0.1:8420')
    ap.add_argument('--tasks', required=True, help='comma list or @file')
    ap.add_argument('--out', required=True)
    ap.add_argument('--sub', default=str(common.E2E / 'subs/sample_noadapter'))
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--tool-workers', type=int, default=64)
    ap.add_argument('--no-wheel-routing', action='store_true', help='use the single wheels dir (E2E_WHEELS)')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    os.environ['E2E_RUN'] = out.name  # container label: stop/clean one run without touching others
    logging.basicConfig(level=logging.WARNING, filename=str(out / 'harness.log'))
    for name in ('LiteLLM', 'litellm', 'httpx', 'httpcore', 'openai', 'opentelemetry'):
        logging.getLogger(name).setLevel(logging.ERROR)
    import swegemma.harness.agent_runner as agent_runner
    from google.adk.agents.run_config import RunConfig, ToolThreadPoolConfig
    agent_runner.RunConfig = lambda **kw: RunConfig(**kw, tool_thread_pool_config=ToolThreadPoolConfig(max_workers=a.tool_workers))
    install_llm_hook(out / 'llm_calls.jsonl')
    from swegemma.evaluate import Evaluator

    ids = Path(a.tasks[1:]).read_text().split() if a.tasks.startswith('@') else a.tasks.split(',')
    done = set()
    if (out / 'per_task.jsonl').exists():
        done = {json.loads(l)['id'] for l in open(out / 'per_task.jsonl')}
    ids = [i for i in ids if i not in done]
    sub = Path(a.sub)
    ev_raw = yaml.safe_load((sub / 'eval_config.yaml').read_text()) or {}
    budget = ev_raw.get('evaluation', ev_raw)
    if not a.no_wheel_routing:
        common.install_wheel_routing()
    alias = common.declared_model(sub)
    models = common.make_models(f'{a.proxy}/{a.cfg}/v1', alias)
    cfg = common.base_config(out, models, sub_dir=sub, task_ids=ids, concurrency=a.concurrency, budget=budget)
    (out / 'run_cfg.json').write_text(json.dumps({'cfg': a.cfg, 'proxy': a.proxy, 'sub': str(sub), 'budget': budget,
                                                  'concurrency': a.concurrency, 'tasks': ids, 'started': time.time(),
                                                  'model_alias': alias, 'wheel_routing': not a.no_wheel_routing,
                                                  'tag': out.name}))
    evaluator = Evaluator(cfg)
    orig_eval = evaluator.evaluate_task

    async def evaluate_task(task, *args, **kw):
        attempt_id = f'{out.name}/{a.cfg}:{task.instance_id}'
        CUR.set(attempt_id)
        t0 = time.time()
        res = await orig_eval(task, *args, **kw)
        ctx = kw.get('context')
        rec = {'id': task.instance_id, 'cfg': a.cfg, 'attempt': attempt_id, 'resolved': bool(res.resolved),
               'error': (res.error or '')[:500], 'patch_chars': len(res.agent_patch or ''),
               'tool_calls': res.tool_calls, 'llm_calls': res.total_llm_calls,
               'agent_s': round(getattr(ctx, 'agent_elapsed_seconds', 0.0) or 0.0, 1) if ctx else None,
               'submitted': bool(getattr(ctx, 'patch_submitted', False)) if ctx else None,
               'wall_s': round(time.time() - t0, 1), 'test_exit': res.test_exit_code, 'patch': (res.agent_patch or '')[:100000]}
        tail = (res.test_output or '')[-3000:]
        for k in ('failed', 'passed', 'error', 'skipped'):
            mm = re.findall(rf'(\d+) {k}', tail)
            rec[f'n_{k}'] = int(mm[-1]) if mm else 0
        with open(out / 'per_task.jsonl', 'a') as f:
            f.write(json.dumps(rec) + '\n')
        print(f"{time.strftime('%H:%M:%S')} {attempt_id} resolved={rec['resolved']} calls={rec['tool_calls']} "
              f"llm={rec['llm_calls']} wall={rec['wall_s']}s err={rec['error'][:80]!r}", flush=True)
        return res

    evaluator.evaluate_task = evaluate_task
    t0 = time.time()
    res = await evaluator.run()
    k = sum(r.resolved for r in res.task_results)
    print(f'DONE {a.cfg} resolved {k}/{len(res.task_results)} in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
