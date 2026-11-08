"""CPU end-to-end test of the S1 profile on a SYNTHETIC P corpus built from 20 main-track contexts (edit_file keys
renamed filepath -> file_path, allow_multiple dropped; a different, verbatim harness error format)."""
import json, sys, os, copy, subprocess
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/scripts'))
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); T = f'{D}/data/test_S1'
import gemma_protocol as gp, variants as V
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
meta = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
ids = [x.strip() for x in open(f'{D}/data/ids_gate300.txt')][:20]
def conv_tools(tools):
    out = copy.deepcopy(tools)
    for t in out:
        f = t['function']
        if f['name'] == 'edit_file':
            f['parameters'] = {'type': 'object', 'properties': {'file_path': {'type': 'string'}, 'old_string': {'type': 'string'}, 'new_string': {'type': 'string'}},
                               'required': ['file_path', 'old_string', 'new_string']}
    return out
def conv_msgs(msgs):
    out = copy.deepcopy(msgs)
    for m in out:
        for tc in m.get('tool_calls') or []:
            if tc['function']['name'] == 'edit_file':
                a = json.loads(tc['function']['arguments']); b = {}
                for k, v in a.items():
                    if k == 'allow_multiple': continue
                    b['file_path' if k == 'filepath' else k] = v
                tc['function']['arguments'] = json.dumps(b)
    return out
tpl = gp.OLD_TEMPLATE
man = {'corpus_id': 'TEST-S1-synthetic', 'tool_profile': 'S1', 'model': {}, 'server': {},
       'render': {'chat_template_path': tpl, 'chat_template_md5': '', 'chat_template_kwargs': {'enable_thinking': True}, 'system_content_form': 'parts', 'tool_call_arguments_form': 'json_string'},
       'sampling': {'temperature': 0.2, 'top_p': 0.95}, 'tools': None,
       'harness': {'edit_tool': {'name': 'edit_file', 'path_key': 'file_path', 'old_key': 'old_string', 'new_key': 'new_string'},
                   'responses': {'missing_required': 'Error: missing required argument(s): {missing}', 'edit_not_found': 'Error: old_string not found in file.',
                                 'unparsed_call': 'Your previous tool call could not be parsed. Emit one well-formed tool call.'}},
       'files': {'contexts': 'contexts.jsonl', 'outcomes': 'outcomes.jsonl'}}
with open(f'{T}/contexts.jsonl', 'w') as f:
    for i, cid in enumerate(ids):
        msgs, tools = V.load_context(meta[cid]); tools_s1 = conv_tools(tools); msgs_s1 = conv_msgs(msgs)
        if man['tools'] is None: man['tools'] = tools_s1
        s = tok.apply_chat_template(gp.to_template_messages(msgs_s1), tools=tools_s1, add_generation_prompt=True, tokenize=False, enable_thinking=True, chat_template=open(tpl).read())
        f.write(json.dumps({'context_id': f'S1test:{i}', 'task_id': meta[cid]['task'].split('#')[0], 'attempt_id': meta[cid]['task'], 'request_index': i,
                            'messages': msgs_s1, 'tools_ref': 'inline', 'tools': tools_s1, 'prompt_tokens': len(tok(s, add_special_tokens=False)['input_ids'])}) + '\n')
json.dump(man, open(f'{T}/manifest.json', 'w'), indent=1)
PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python')
print(subprocess.run([PY, f'{D}/scripts/validate_contexts.py', f'{T}/manifest.json', '20'], capture_output=True, text=True).stdout[-400:])
print(subprocess.run([PY, f'{D}/scripts/build_contexts_P.py', f'{T}/manifest.json', f'{T}/meta_S1.jsonl'], capture_output=True, text=True).stdout[-300:])
gp.set_profile('S1', tools=man['tools'], responses=man['harness']['responses'])
ms = [json.loads(l) for l in open(f'{T}/meta_S1.jsonl')]
m = next(x for x in ms if x['protocol_clean'] and x['k_usable'] >= 1); ctx = V.load_context(m)
for pw, k in (('P0', 0), ('P1', 1), ('P5', 1), ('P6', 1), ('P9', 1), ('P8a', 1), ('P8b', 1), ('P4', 1)):
    p, info = V.build_prompt(tok, m, pw, k, ctx=ctx)
    tail = p[p.rfind('call:edit_file{'):][:220] if pw != 'P5' else p[-180:]
    print(pw, '| missing:', info.get('missing'), '| actions:', [(a['how'], a['why']) for a in info.get('quarantine_actions', [])], '|', repr(tail[:200]))
    if pw == 'P1': assert 'Error: missing required argument(s): old_string' in p and 'file_path:' in p and 'filepath:' not in p[p.rfind('call:edit_file{'):]
    if pw == 'P8a':
        vm, _, inf = V.make_variant(ctx[0], m['prior'], 'P1', 1)
        q, _ = V.quarantine_renderer().quarantine_messages(vm, ctx[1], raw_by_call_id=inf['raw_by_id'])
        pr = m['prior'][-1]; orig = json.loads(ctx[0][pr['ai']]['tool_calls'][0]['function']['arguments']); rec = json.loads(q[pr['ai']]['tool_calls'][0]['function']['arguments'])
        print('   P8a recovered == original S1 args:', rec == orig)
j_ok = gp.judge('call:edit_file{file_path:<|"|>a.py<|"|>,new_string:<|"|>x = 2<|"|>,old_string:<|"|>x = 1<|"|>}', True)
j_slip = gp.judge('call:edit_file{file_path:<|"|>a.py<|"|>,new_string:<|"|>x = 2`,old_string:<|"|>x = 1<|"|>}', True)
j_key = gp.judge('call:edit_file{filepath:<|"|>a.py<|"|>,new_string:<|"|>x = 2<|"|>,old_string:<|"|>x = 1<|"|>}', True)
print('judge S1 valid:', j_ok['malformed'], j_ok.get('is_edit'), j_ok['order'], '| slip:', j_slip['flags'], '| wrong key:', j_key['flags'])
assert not j_ok['malformed'] and j_slip['malformed'] and 'missing:old_string' in j_slip['flags'] and 'missing:file_path' in j_key['flags'] and 'extra_key' in j_key['flags']
print('S1 SYNTHETIC TEST PASSED')
