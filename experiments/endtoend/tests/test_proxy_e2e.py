"""In-process integration test of the WHOLE proxy request path (engine_chat: logging, quarantine, rendering,
generation, IPD scoring requests, parsing, response shape) against a scripted mock vLLM /v1/completions server.
Multi-turn requests with tool messages and a malformed historical call, for cfgs base and full."""
import os  # added by the repo export (paths are env/config driven)
import asyncio
import json
import sys
import types
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'proxy'))
import e2e_proxy as ep  # noqa: E402
import gemma_protocol as gp  # noqa: E402

MD = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-12b-it-qat-w4a16-ct')
D = gp.D
EOS = '<|tool_response>'
SLIP = f'<|channel>thought\nok<channel|><|tool_call>call:edit_file{{filepath:{D}a.py{D},new_string:{D}y = 2`,old_string:{D}y = 1{D}}}<tool_call|>'
LIT = f'<|channel>thought\nok<channel|><|tool_call>call:edit_file{{filepath:{D}a.py{D},new_string:{D}s = "``,old_string:"{D},old_string:{D}y = 1{D}}}<tool_call|>'
LIT_ARGS = {'filepath': 'a.py', 'new_string': 's = "``,old_string:"', 'old_string': 'y = 1'}
seen = {'completions': 0, 'forced': 0, 'confirm': 0, 'prompt_logprobs': 0}
n_ok = 0


def check(c, m):
    global n_ok
    assert c, m
    n_ok += 1


def make_backend(tok):
    async def completions(request):
        b = await request.json()
        if b.get('prompt_logprobs') is not None:
            seen['prompt_logprobs'] += 1
        prompts = b['prompt'] if b['prompt'] and isinstance(b['prompt'][0], list) else [b['prompt']]
        choices = []
        for i, ids in enumerate(prompts):
            text = tok.decode(ids, skip_special_tokens=False)
            if b.get('allowed_token_ids'):
                seen['forced'] += 1
                t = b['allowed_token_ids'][0]
                choices.append({'index': i, 'text': tok.decode([t]), 'token_ids': [t], 'finish_reason': 'length',
                                'stop_reason': None, 'logprobs': {'tokens': [f'token_id:{t}'], 'token_logprobs': [-1.0],
                                                                  'top_logprobs': [{f'token_id:{t}': -1.0}]}})
                continue
            if b.get('max_tokens') == 1:
                seen['confirm'] += 1
                choices.append({'index': i, 'text': D, 'token_ids': [tok.convert_tokens_to_ids(D)], 'finish_reason': 'length', 'stop_reason': None})
                continue
            seen['completions'] += 1
            gen = text[text.rfind('<|turn>model\n') + len('<|turn>model\n'):]
            script = LIT if 'LITERAL' in text else SLIP
            gen = gen[len('<|channel>thought\n'):] if gen.startswith('<|channel>thought\n') and not script.startswith(gen) else gen
            full = script + EOS
            if full.startswith(gen):
                cont = full[len(gen):]
            elif gen.endswith(f'y = 2{D}'):  # verify-then-repair cut new_string before the backtick: continue
                cont = f',old_string:{D}y = 1{D}}}<tool_call|>' + EOS
            else:
                cont = 'thought\nok<channel|><|tool_call>call:read_file{filepath:<|"|>a.py<|"|>}<tool_call|>' + EOS
            out, fr, sr, stopped = [], 'length', None, False
            for t in tok.encode(cont, add_special_tokens=False):
                if len(out) >= b['max_tokens']:
                    break
                out.append(t)
                if tok.decode([t]) == EOS:
                    fr, sr = 'stop', t
                    break
                txt = tok.decode(out, skip_special_tokens=False)
                hit = [s for s in (b.get('stop') or []) if s in txt]
                if hit:
                    s0 = min(hit, key=lambda s: txt.index(s) + len(s))
                    choices.append({'index': i, 'text': txt[:txt.index(s0) + len(s0)], 'token_ids': out, 'finish_reason': 'stop', 'stop_reason': s0})
                    stopped = True
                    break
            if not stopped:
                txt = tok.decode([t for t in out if tok.decode([t]) != EOS], skip_special_tokens=False)
                choices.append({'index': i, 'text': txt, 'token_ids': out, 'finish_reason': fr, 'stop_reason': sr})
        return web.json_response({'choices': choices, 'usage': {}})
    app = web.Application()
    app.router.add_post('/v1/completions', completions)
    return app


TOOLS = [{'type': 'function', 'function': {'name': 'edit_file', 'description': 'Edit.', 'parameters': {'type': 'object', 'properties': {
    'filepath': {'type': 'string'}, 'old_string': {'type': 'string'}, 'new_string': {'type': 'string'}, 'allow_multiple': {'type': 'boolean'}},
    'required': ['filepath', 'old_string', 'new_string']}}},
         {'type': 'function', 'function': {'name': 'read_file', 'description': 'Read.', 'parameters': {'type': 'object', 'properties': {
             'filepath': {'type': 'string'}}, 'required': ['filepath']}}}]


async def main():
    import tempfile
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MD)
    backend = TestServer(make_backend(tok))
    await backend.start_server()
    logdir = tempfile.mkdtemp(dir=str(Path(__file__).resolve().parents[1] / 'tmp'))
    args = types.SimpleNamespace(backend=str(backend.make_url('/v1')), served='m', model_dir=MD,
                                 configs=str(Path(__file__).resolve().parents[1] / 'proxy/configs.json'), logdir=logdir,
                                 max_backend_conc=8, cpu_workers=2, call_timeout=60.0, max_interventions=8, budget_slack=64,
                                 prior=str(Path(__file__).resolve().parents[1] / 'configs/channel_prior.json'), prior_source='ft_edit')
    proxy = ep.Proxy(args)
    app = web.Application()
    app.on_startup.append(proxy.start)
    app.on_cleanup.append(proxy.stop)
    app.router.add_post('/{cfg}/v1/chat/completions', proxy.chat)
    client = TestClient(TestServer(app))
    await client.start_server()
    bad_args = json.dumps({'filepath': 'a.py', 'new_string': 'x`,old_string:'})
    turn1 = [{'role': 'system', 'content': 'sys'}, {'role': 'user', 'content': 'fix a.py'}]
    turn3 = turn1 + [
        {'role': 'assistant', 'content': None, 'reasoning': 'r', 'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'read_file', 'arguments': json.dumps({'filepath': 'a.py'})}}]},
        {'role': 'tool', 'tool_call_id': 'c1', 'content': json.dumps({'status': 'ok', 'content': 'y = 1'})},
        {'role': 'assistant', 'content': None, 'reasoning': 'r2', 'tool_calls': [{'id': 'c2', 'type': 'function', 'function': {'name': 'edit_file', 'arguments': bad_args}}]},
        {'role': 'tool', 'tool_call_id': 'c2', 'content': json.dumps({'status': 'error', 'error_type': 'TypeError', 'error_message': 'missing old_string'})}]
    for cfg in ('base', 'fullp'):
        for msgs in (turn1, turn3):
            body = {'model': 'x', 'messages': msgs, 'tools': TOOLS, 'max_completion_tokens': 512, 'temperature': 0.2,
                    'top_p': 0.95, 'chat_template_kwargs': {'enable_thinking': True}, 'thinking_token_budget': 64}
            r = await client.post(f'/{cfg}/v1/chat/completions', json=body)
            j = await r.json()
            check(r.status == 200, f'{cfg} n_msgs={len(msgs)} status {r.status} {str(j)[:300]}')
            calls = j['choices'][0]['message']['tool_calls']
            check(len(calls) == 1, f'{cfg} one call {calls}')
            a = json.loads(calls[0]['function']['arguments'])
            if cfg == 'fullp' and calls[0]['function']['name'] == 'edit_file':
                check(a == {'filepath': 'a.py', 'new_string': 'y = 2', 'old_string': 'y = 1'}, f'full repaired {a}')
            if cfg == 'base' and calls[0]['function']['name'] == 'edit_file':
                check('old_string' not in a, f'base keeps the slip {a}')
    # P1 through the real HTTP path: a VALID call whose string literally contains '``,old_string:' is delivered
    # byte-identical (no repair, no post-hoc rewrite) and is not quarantined when it comes back in the history
    lit_turn = [{'role': 'system', 'content': 'sys'}, {'role': 'user', 'content': 'LITERAL edit please'}]
    body = {'model': 'x', 'messages': lit_turn, 'tools': TOOLS, 'max_completion_tokens': 512, 'temperature': 0.2,
            'top_p': 0.95, 'chat_template_kwargs': {'enable_thinking': True}, 'thinking_token_budget': 64}
    r = await client.post('/fullp/v1/chat/completions', json=body)
    jl = await r.json()
    tl = jl['choices'][0]['message']['tool_calls']
    check(r.status == 200 and len(tl) == 1 and json.loads(tl[0]['function']['arguments']) == LIT_ARGS, f'literal delivered exactly {tl}')
    lit_turn2 = lit_turn + [{'role': 'assistant', 'content': None, 'reasoning': 'ok', 'tool_calls': tl},
                            {'role': 'tool', 'tool_call_id': tl[0]['id'], 'content': json.dumps({'status': 'ok', 'message': 'edited'})}]
    r = await client.post('/fullp/v1/chat/completions', json={**body, 'messages': lit_turn2})
    check(r.status == 200, 'literal follow-up 200')
    recs = {c: [json.loads(l) for l in open(Path(logdir) / f'proxy_{c}.jsonl')] for c in ('base', 'fullp')}
    lr, lr2 = recs['fullp'][2], recs['fullp'][3]
    check(not lr['events'] and lr['raw'] == LIT and lr['ipd']['strict_valid'] == 1 and lr['calls'][0]['strict_valid']
          and not lr['calls'][0]['ok_emitted'] and not lr['calls'][0].get('posthoc_repaired'),
          f"literal: no IPD event, raw identical, criterion flags it but guard keeps it {lr['events']} {lr.get('ipd')}")
    check(lr2.get('quarantine') == [], f"strictly valid literal not quarantined later {lr2.get('quarantine')}")
    check(all(r['status'] == 200 for c in recs for r in recs[c]), 'all logged 200')
    check(recs['fullp'][1].get('quarantine') and recs['fullp'][1]['quarantine'][0]['how'] == 'sanitized', f"quarantine {recs['fullp'][1].get('quarantine')}")
    tr = recs['base'][1]['tool_results']
    check([t[:3] for t in tr] == [['edit_file', 'error', 'TypeError']] and len(tr[0][3]) == 16, f'tool_results {tr}')
    check(recs['base'][1]['hist'] == [['read_file', 0], ['edit_file', 1]], f"hist {recs['base'][1]['hist']}")
    check(any(e['ev'] == 'ipd_repair' for r in recs['fullp'] for e in r['events']), 'ipd repair logged')
    check(seen['prompt_logprobs'] == 0 and seen['forced'] > 0 and seen['confirm'] == 0, f'request kinds {seen}')
    rr = [e for r in recs['fullp'] for e in r['events'] if e['ev'] == 'ipd_repair']
    check(rr and rr[0]['kind'] == 'key' and rr[0]['in'] == 'new_string' and rr[0]['how'] == 'noisy_channel' and rr[0]['cut_k'] == 0,
          f'verify-then-repair event {rr[:1]}')
    # ---- branch-at-onset replay (closed loop): recorded prefix replayed, onset delivered malformed, live after it
    await client.close()
    seen_bodies = []
    D2 = gp.D
    raw_slip = f'filepath:{D2}a.py{D2},new_string:{D2}y = 2`,old_string:{D2}y = 1{D2}'
    plan = {'branches': {'t1': {'task': 't1', 'b': 1, 'branch_id': 'unit:t1', 'onset': 'injected', 'onset_call_id': 'e1',
             'onset_args': {'filepath': 'a.py', 'new_string': 'y = 2`,old_string:'}, 'onset_raw_args': raw_slip,
             'responses': [
                 {'raw': '<|channel>thought\nread<channel|><|tool_call>call:read_file{filepath:<|"|>a.py<|"|>}<tool_call|>',
                  'calls': [{'id': 'r1', 'name': 'read_file', 'args': {'filepath': 'a.py'}, 'ok_emitted': True}],
                  'raw_args': {'r1': 'filepath:<|"|>a.py<|"|>'}, 'usage': {'prompt_tokens': 111, 'completion_tokens': 22},
                  'tool_results': [], 'n_msgs': 2, 'finish': 'stop'},
                 {'raw': '<|channel>thought\nedit<channel|><|tool_call>call:edit_file{filepath:<|"|>a.py<|"|>,new_string:<|"|>y = 2<|"|>,old_string:<|"|>y = 1<|"|>}<tool_call|>',
                  'calls': [{'id': 'e1', 'name': 'edit_file', 'args': {'filepath': 'a.py', 'new_string': 'y = 2', 'old_string': 'y = 1'}, 'ok_emitted': True}],
                  'raw_args': {}, 'usage': {'prompt_tokens': 150, 'completion_tokens': 30},
                  'tool_results': [['read_file', 'ok', None, gp.tool_output_hash(json.dumps({'status': 'ok', 'content': 'y = 1'}))]],
                  'n_msgs': 4, 'finish': 'stop'}]}}}
    plan_path = Path(logdir) / 'plan.json'
    plan_path.write_text(json.dumps(plan))
    args.replay_plan = str(plan_path)
    args.logdir = logdir + '/replay'
    proxy2 = ep.Proxy(args)
    app2 = web.Application()
    app2.on_startup.append(proxy2.start)
    app2.on_cleanup.append(proxy2.stop)
    app2.router.add_post('/{cfg}/v1/chat/completions', proxy2.chat)
    client2 = TestClient(TestServer(app2))
    await client2.start_server()
    hdr = {'X-E2E-Task': 'bt/fullp:t1'}
    base_body = {'model': 'x', 'tools': TOOLS, 'max_completion_tokens': 256, 'temperature': 0.2,
                 'chat_template_kwargs': {'enable_thinking': True}, 'thinking_token_budget': 64}
    m0 = [{'role': 'system', 'content': 'sys'}, {'role': 'user', 'content': 'fix a.py'}]
    r = await client2.post('/fullp/v1/chat/completions', json={**base_body, 'messages': m0}, headers=hdr)
    j0 = await r.json()
    check(r.status == 200 and j0['choices'][0]['message']['tool_calls'][0]['id'] == 'r1' and j0['usage']['prompt_tokens'] == 111,
          f'replayed response 0 {j0}')
    m1 = m0 + [{'role': 'assistant', 'content': None, 'reasoning': 'read', 'tool_calls': j0['choices'][0]['message']['tool_calls']},
               {'role': 'tool', 'tool_call_id': 'r1', 'content': json.dumps({'status': 'ok', 'content': 'y = 1'})}]
    r = await client2.post('/fullp/v1/chat/completions', json={**base_body, 'messages': m1}, headers=hdr)
    j1 = await r.json()
    tc = j1['choices'][0]['message']['tool_calls'][0]
    check(tc['id'] == 'e1' and json.loads(tc['function']['arguments']) == plan['branches']['t1']['onset_args'], f'onset delivered malformed {tc}')
    m2 = m1 + [{'role': 'assistant', 'content': None, 'reasoning': 'edit', 'tool_calls': [tc]},
               {'role': 'tool', 'tool_call_id': 'e1', 'content': json.dumps({'error': 'Invoking `edit_file()` failed as the following mandatory input parameters are not present:\nold_string'})}]
    r = await client2.post('/fullp/v1/chat/completions', json={**base_body, 'messages': m2}, headers=hdr)
    j2 = await r.json()
    check(r.status == 200, f'live after onset {j2}')
    recs2 = [json.loads(l) for l in open(Path(logdir) / 'replay' / 'proxy_fullp.jsonl')]
    check([x.get('replayed', False) for x in recs2] == [True, True, False], f"replayed flags {[x.get('replayed') for x in recs2]}")
    check(all(x['replay']['fidelity'] == 'ok' for x in recs2[:2]), f"fidelity {[x.get('replay') for x in recs2[:2]]}")
    check(recs2[2]['quarantine'] and recs2[2]['quarantine'][0]['how'] == 'recovered', f"quarantine after onset {recs2[2].get('quarantine')}")
    check(recs2[2]['tool_results'][0][1:3] == ['error', 'MissingParameters'], f"ADK error classified {recs2[2]['tool_results']}")
    check(recs2[2]['branch']['seed'] is not None, 'common seed set on the live request')
    # fidelity mismatch is detected (different tool output)
    proxy2.req_index.clear()
    r = await client2.post('/fullp/v1/chat/completions', json={**base_body, 'messages': m0}, headers={'X-E2E-Task': 'bt2/fullp:t1'})
    m1b = m1[:-1] + [{'role': 'tool', 'tool_call_id': 'r1', 'content': json.dumps({'status': 'ok', 'content': 'DIFFERENT'})}]
    r = await client2.post('/fullp/v1/chat/completions', json={**base_body, 'messages': m1b}, headers={'X-E2E-Task': 'bt2/fullp:t1'})
    recs3 = [json.loads(l) for l in open(Path(logdir) / 'replay' / 'proxy_fullp.jsonl')]
    check(recs3[-1]['replay']['fidelity'] == 'mismatch', f"mismatch detected {recs3[-1]['replay']}")
    await client2.close()
    await backend.close()
    print(f'ALL {n_ok} CHECKS PASSED', seen)


asyncio.run(main())
