"""NO-NUDGE client: a minimal ReAct loop with native Gemma tool calling through the protocol proxy.

Same task setup, tools (the 9 swegemma tools, executed in the same Docker sandbox), system prompt, initial
prompt, tool declarations and sampling as the official harness run, and the same Phase-2 verification; but:
  * no continuation nudges: a response without a tool call ENDS the episode (as in clients that do not route
    around failures, e.g. a raw tool call the parser could not read);
  * no error-recovery prompts and no ADK machinery (no ToolErrorPlugin wording, no LLM compaction); tool errors are
    returned as the tools' own JSON results; context is bounded by observation masking (when the last request used
    > --mask-tokens tokens, all but the last --mask-keep tool outputs are replaced by a fixed placeholder).
Plugged into swegemma's Evaluator by replacing _run_agent_sandbox, so container setup, patch extraction and
verification are the official code paths.

Usage: nonudge_client.py --cfg base --tasks @file --out runs/X --system configs/client_system.txt
                         --tools configs/client_tools.json [--concurrency 8]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'harness'))
import common  # noqa: E402
import run_harness  # noqa: E402,F401  (per-container serialised exec)
import yaml  # noqa: E402
from adk_eval_core.tracing import SessionTrace  # noqa: E402
from swegemma.harness.agent_runner import (  # noqa: E402
    build_agent_prompt, build_workspace_tree_command)
from swegemma.harness.container_setup import (  # noqa: E402
    extract_snapshot, install_editable_package, install_test_dependencies, setup_baseline_commit,
    setup_container_wheels, setup_git_exclude, setup_workspace_test_config)
from swegemma.sandbox import sandbox_exec, sandbox_start, sandbox_stop  # noqa: E402

MASK = '{"status": "ok", "note": "[earlier tool output omitted to fit the context window]"}'
TOOL_NAMES = ['run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch',
              'get_code_neighbors', 'search_similar_code', 'get_code_subgraph']


class Client:
    def __init__(self, a):
        self.a = a
        self.system = Path(a.system).read_text()
        self.tools = json.loads(Path(a.tools).read_text())
        sampling = yaml.safe_load((Path(a.sub) / 'configs/sampling.yaml').read_text())
        self.samp = {'temperature': sampling['temperature'], 'top_p': sampling['top_p'],
                     'max_tokens': sampling['max_output_tokens']}
        tb = (sampling.get('thinking_config') or {}).get('thinking_budget', 0)
        self.extra = {'chat_template_kwargs': {'enable_thinking': tb > 0}}
        if tb > 0:
            self.extra['thinking_token_budget'] = tb
        self.url = f'{a.proxy}/{a.cfg}/v1/chat/completions'
        self.alias = common.declared_model(a.sub)
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(1800.0))
        self.log = open(Path(a.out) / 'client_calls.jsonl', 'a', buffering=1)

    @staticmethod
    def mask(messages, keep):
        """Observation masking (no LLM, no nudge): replace all but the last `keep` tool outputs by a placeholder and
        drop the reasoning of all but the last `keep` assistant turns (the template re-renders past thinking)."""
        tool_idx = [i for i, m in enumerate(messages) if m.get('role') == 'tool']
        n = 0
        for i in tool_idx[:-keep] if keep > 0 else tool_idx:
            if messages[i]['content'] != MASK:
                messages[i] = {**messages[i], 'content': MASK}
                n += 1
        asst = [i for i, m in enumerate(messages) if m.get('role') == 'assistant']
        for i in asst[:-keep] if keep > 0 else asst:
            if messages[i].get('reasoning'):
                messages[i] = {**messages[i], 'reasoning': None, 'reasoning_content': None}
                n += 1
        return n

    async def llm(self, attempt, messages):
        body = {'model': self.alias, 'messages': messages, 'tools': self.tools, **self.samp, **self.extra}
        for k in range(6):
            try:
                r = await self.http.post(self.url, json=body, headers={'X-E2E-Task': attempt})
                if r.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(2 * 2 ** k)
                    continue
                return r.status_code, r.json()
            except httpx.HTTPError:
                await asyncio.sleep(2 * 2 ** k)
        return 599, {'error': 'backend unavailable'}

    async def run(self, docker, config, task, snapshot_path, *, base_snapshot_path=None, patch_path=None,
                  context=None, **_):
        attempt = f'{Path(self.a.out).name}/nonudge-{self.a.cfg}:{task.instance_id}'
        common.CUR_TASK.set(attempt)
        sid = await sandbox_start(docker)
        trace = SessionTrace()
        agent_patch, agent_error, end = '', None, None
        stats = {'llm_calls': 0, 'tool_calls': 0, 'malformed_delivered': 0, 'unknown_tool': 0, 'masked_outputs': 0}
        last_pt = 0
        try:
            await asyncio.to_thread(setup_container_wheels, docker, sid, config)
            await asyncio.to_thread(extract_snapshot, docker, sid, snapshot_path, patch_path=patch_path,
                                    base_snapshot_path=base_snapshot_path)
            await asyncio.to_thread(setup_git_exclude, docker, sid)
            await asyncio.to_thread(install_editable_package, docker, sid)
            await asyncio.to_thread(install_test_dependencies, docker, sid, task.repo, config=config)
            await asyncio.to_thread(setup_workspace_test_config, docker, sid, repo=task.repo)
            await asyncio.to_thread(setup_baseline_commit, docker, sid, 'baseline')
            tree = await sandbox_exec(docker, sid, build_workspace_tree_command())
            context.docker, context.container_id = docker, sid
            tools = context.create_tools()
            prompt = build_agent_prompt(task=task, config=config, workspace_tree=tree.stdout.strip() if tree.exit_code == 0 else '',
                                        enable_sandbox_testing=True, declared_tools=set(TOOL_NAMES))
            messages = [{'role': 'system', 'content': self.system}, {'role': 'user', 'content': prompt}]
            context.start_agent_session()
            t0 = time.time()
            b = config.budget
            while True:
                if b.turns is not None and stats['llm_calls'] >= b.turns:
                    end = 'turn_budget'
                    break
                if b.tool_calls is not None and context.tool_calls_used >= b.tool_calls:
                    end = 'tool_budget'
                    break
                if b.time_minutes is not None and time.time() - t0 > b.time_minutes * 60:
                    end = 'time_budget'
                    break
                if last_pt > self.a.mask_tokens:
                    stats['masked_outputs'] += self.mask(messages, self.a.mask_keep)
                st, resp = await self.llm(attempt, messages)
                if st == 400 and 'maximum context length' in str(resp):
                    stats['masked_outputs'] += self.mask(messages, 1)  # one aggressive retry, then give up
                    st, resp = await self.llm(attempt, messages)
                    if st == 400 and 'maximum context length' in str(resp):
                        end, agent_error = 'context_overflow', f'context overflow: {str(resp)[:200]}'
                        break
                stats['llm_calls'] += 1
                if st != 200:
                    end = f'llm_error_{st}'
                    agent_error = f'LLM error {st}: {str(resp)[:300]}'
                    break
                last_pt = (resp.get('usage') or {}).get('total_tokens') or 0
                ch = resp['choices'][0]
                msg = ch['message']
                tcs = msg.get('tool_calls') or []
                amsg = {'role': 'assistant', 'content': msg.get('content'), 'reasoning': msg.get('reasoning'),
                        'reasoning_content': msg.get('reasoning')}
                if tcs:
                    amsg['tool_calls'] = [{'id': t['id'], 'type': 'function', 'function': t['function']} for t in tcs]
                messages.append(amsg)
                if not tcs:
                    end = 'no_tool_call_' + str(ch.get('finish_reason'))  # NO nudge: the episode ends here
                    break
                for t in tcs:
                    name = t['function']['name']
                    try:
                        args = json.loads(t['function']['arguments'] or '{}')
                    except Exception:  # noqa: BLE001
                        args = None
                    fn = tools.get(name)
                    if fn is None:
                        stats['unknown_tool'] += 1
                        out = json.dumps({'status': 'error', 'error_type': 'UnknownTool', 'error_message': f'unknown tool {name}'})
                    elif not isinstance(args, dict):
                        out = json.dumps({'status': 'error', 'error_type': 'ValueError', 'error_message': 'arguments are not a JSON object'})
                    else:
                        try:
                            out = await asyncio.to_thread(fn, **args)
                            if not isinstance(out, str):
                                out = json.dumps(out, default=str)
                        except TypeError as e:
                            stats['malformed_delivered'] += 1
                            out = json.dumps({'status': 'error', 'error_type': 'TypeError', 'error_message': str(e)[:500]})
                        except Exception as e:  # noqa: BLE001
                            out = json.dumps({'status': 'error', 'error_type': type(e).__name__, 'error_message': str(e)[:500]})
                    stats['tool_calls'] += 1
                    messages.append({'role': 'tool', 'tool_call_id': t['id'], 'content': out})
                if context.patch_submitted:
                    end = 'submitted'
                    break
            context.stop_agent_session()
            agent_patch = context.submitted_patch or ''
            from swegemma.harness.verification import strip_protected_files_from_patch
            if not context.patch_submitted:
                await sandbox_exec(docker, sid, 'cd /workspace && git add -N .')
                d = await sandbox_exec(docker, sid, 'cd /workspace && (git diff --binary _swegemma_baseline 2>/dev/null || git diff --binary HEAD)')
                agent_patch = d.stdout or ''
                if not agent_patch.strip() and not agent_error:
                    agent_error = 'Agent completed execution without calling submit_patch.'
            if agent_patch.strip():
                agent_patch = strip_protected_files_from_patch(agent_patch, extra_protected_paths=list(getattr(task, 'test_files', None) or ()))
        except Exception as e:  # noqa: BLE001
            logging.exception('client error %s', task.instance_id)
            agent_error = f'Sandbox execution error: {e}'
            end = end or 'exception'
        finally:
            await sandbox_stop(docker, sid)
        context.llm_calls_used = stats['llm_calls']  # read by Evaluator for the result record
        self.log.write(json.dumps({'task': attempt, 'end': end, **stats, 'tool_calls_ctx': context.tool_calls_used,
                                   'submitted': bool(context.patch_submitted), 'agent_s': round(context.agent_elapsed_seconds or 0, 1),
                                   'n_msgs': len(messages) if 'messages' in dir() else 0}) + '\n')
        try:  # transcript for analysis
            (Path(self.a.out) / 'transcripts').mkdir(exist_ok=True)
            (Path(self.a.out) / 'transcripts' / f'{task.instance_id}.json').write_text(json.dumps(messages[1:], ensure_ascii=False))
        except Exception:  # noqa: BLE001
            pass
        return agent_patch, agent_error, trace


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cfg', required=True)
    ap.add_argument('--proxy', default='http://127.0.0.1:8420')
    ap.add_argument('--tasks', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--sub', default=str(common.E2E / 'subs/sample_noadapter'))
    ap.add_argument('--system', default=str(common.E2E / 'configs/client_system.txt'))
    ap.add_argument('--tools', default=str(common.E2E / 'configs/client_tools.json'))
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--mask-tokens', type=int, default=24000, help='observation masking threshold (prompt+completion tokens)')
    ap.add_argument('--mask-keep', type=int, default=6, help='most recent tool outputs kept unmasked')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    import os
    os.environ['E2E_RUN'] = out.name
    logging.basicConfig(level=logging.WARNING, filename=str(out / 'client.log'))
    for name in ('httpx', 'httpcore'):
        logging.getLogger(name).setLevel(logging.ERROR)
    from adk_submission import ModelRegistry
    from swegemma.evaluate import Evaluator
    ids = Path(a.tasks[1:]).read_text().split() if a.tasks.startswith('@') else a.tasks.split(',')
    done = set()
    if (out / 'per_task.jsonl').exists():
        done = {json.loads(l)['id'] for l in open(out / 'per_task.jsonl')}
    ids = [i for i in ids if i not in done]
    sub = Path(a.sub)
    ev_raw = yaml.safe_load((sub / 'eval_config.yaml').read_text()) or {}
    budget = ev_raw.get('evaluation', ev_raw)
    common.install_wheel_routing()
    cfg = common.base_config(out, ModelRegistry(), sub_dir=sub, task_ids=ids, concurrency=a.concurrency, budget=budget)
    (out / 'run_cfg.json').write_text(json.dumps({'client': 'nonudge', 'cfg': a.cfg, 'proxy': a.proxy, 'budget': budget,
                                                  'concurrency': a.concurrency, 'tasks': ids, 'started': time.time(),
                                                  'tag': out.name, 'model_alias': common.declared_model(sub)}))
    client = Client(a)
    ev = Evaluator(cfg)

    async def run_sandbox(task, snapshot_path, task_index, total_tasks, slot_id=None, dashboard=None, context=None,
                          base_snapshot_path=None, patch_path=None):
        return await client.run(ev.docker, cfg, task, snapshot_path, base_snapshot_path=base_snapshot_path,
                                patch_path=patch_path, context=context)

    ev._run_agent_sandbox = run_sandbox
    orig_eval = ev.evaluate_task

    async def evaluate_task(task, *args, **kw):
        t0 = time.time()
        res = await orig_eval(task, *args, **kw)
        rec = {'id': task.instance_id, 'cfg': a.cfg, 'client': 'nonudge', 'resolved': bool(res.resolved),
               'error': (res.error or '')[:500], 'patch_chars': len(res.agent_patch or ''), 'tool_calls': res.tool_calls,
               'llm_calls': res.total_llm_calls, 'wall_s': round(time.time() - t0, 1), 'test_exit': res.test_exit_code,
               'patch': (res.agent_patch or '')[:100000]}
        with open(out / 'per_task.jsonl', 'a') as f:
            f.write(json.dumps(rec) + '\n')
        print(f"{time.strftime('%H:%M:%S')} nonudge:{a.cfg}:{task.instance_id} resolved={rec['resolved']} "
              f"calls={rec['tool_calls']} llm={rec['llm_calls']} wall={rec['wall_s']}s", flush=True)
        return res

    ev.evaluate_task = evaluate_task
    res = await ev.run()
    print(f'DONE nonudge {a.cfg} resolved {sum(r.resolved for r in res.task_results)}/{len(res.task_results)}', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
