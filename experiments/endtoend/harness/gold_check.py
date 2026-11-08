"""Gradability check in OUR Docker sandbox: run the official Phase-2 verification (Container B) with the
gold patch (and optionally with an empty patch) for each task. Output: <out>/gold.jsonl."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402,F401  (env + docker patch)
from adk_eval_core.tracing import SessionTrace  # noqa: E402
from adk_submission import ModelRegistry  # noqa: E402
from swegemma.deduplication import resolve_task_snapshot_paths  # noqa: E402
from swegemma.evaluate import Evaluator  # noqa: E402
from swegemma.harness.verification import verify_task  # noqa: E402
from swegemma.models import load_tasks  # noqa: E402


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--empty', action='store_true', help='also verify an empty patch (should fail)')
    ap.add_argument('--tasks', default='')
    ap.add_argument('--no-wheel-routing', action='store_true')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks(common.COMP / 'tasks.jsonl')
    if not a.no_wheel_routing:
        common.install_wheel_routing()
    if a.tasks:
        keep = set(a.tasks.split(','))
        tasks = [t for t in tasks if t.instance_id in keep]
    done = set()
    fp = out / 'gold.jsonl'
    if fp.exists():
        done = {(json.loads(l)['id'], json.loads(l)['kind']) for l in open(fp)}
    cfg = common.base_config(out, ModelRegistry(), sub_dir=common.COMP / 'sample_submission', task_ids=[t.instance_id for t in tasks],
                             concurrency=a.concurrency, budget={})
    ev = Evaluator(cfg)
    sem = asyncio.Semaphore(a.concurrency)
    f = open(fp, 'a', buffering=1)

    async def one(task, kind):
        if (task.instance_id, kind) in done:
            return
        async with sem:
            common.CUR_TASK.set(task.instance_id)
            sp, bsp, pp = resolve_task_snapshot_paths(cfg.snapshots_dir, task.instance_id, task.repo)
            t0 = time.time()
            try:
                res = await verify_task(ev.docker, cfg, task, sp, base_snapshot_path=bsp, patch_path=pp,
                                        agent_patch=task.patch if kind == 'gold' else '', agent_error=None,
                                        trace=SessionTrace(), start_time=time.perf_counter())
                rec = {'id': task.instance_id, 'kind': kind, 'resolved': bool(res.resolved), 'exit': res.test_exit_code,
                       'error': (res.error or '')[:500], 'tail': (res.test_output or '')[-1500:], 's': round(time.time() - t0, 1)}
            except Exception as e:  # noqa: BLE001
                rec = {'id': task.instance_id, 'kind': kind, 'resolved': False, 'exit': None, 'error': repr(e)[:500],
                       'tail': '', 's': round(time.time() - t0, 1)}
            f.write(json.dumps(rec) + '\n')
            print(rec['id'], kind, rec['resolved'], rec['s'], flush=True)

    kinds = ['gold'] + (['empty'] if a.empty else [])
    await asyncio.gather(*[one(t, k) for t in tasks for k in kinds])
    try:
        ev.docker.cleanup_all()
    except Exception:  # noqa: BLE001
        pass


if __name__ == '__main__':
    asyncio.run(main())
