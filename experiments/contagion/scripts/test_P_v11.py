"""CPU test of the v1.1 pool/meta builders (PI decision on P's observation masking) on a SYNTHETIC corpus derived from
the 20-context S1 test corpus (data/test_S1; main-track histories with S1 keys). Adds history_tool_status (from the
ADK status of each result), a split, and masked copies:
  M1: the most recent prior edit's result masked (+ its turn's reasoning nulled) -> must leave A1, A1k2, A2;
  M2: only the second most recent prior edit masked -> stays A1-eligible, leaves A1k2 / A2;
  ST: one copy whose most recent prior edit result TEXT says ok but history_tool_status says error -> leaves A1 (rule 1).
Checks validate_contexts token equality, build_contexts_P vs sample_pools_v2 agreement, rule-2 counts, verified subset,
and that v1.1 equals v1 on the unmodified contexts."""
import json, sys, os, copy, subprocess, collections
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/scripts'))
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion'); S = f'{D}/data/test_S1'; T = f'{D}/data/test_P_v11'
PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python')
import gemma_protocol as gp
from transformers import AutoTokenizer
os.makedirs(T, exist_ok=True)
MASK = '[This earlier tool output was removed to keep the conversation within the context limit.]'
man = json.load(open(f'{S}/manifest.json'))
man['corpus_id'] = 'TEST-P-v11'; man['harness']['responses']['masked_tool_output'] = MASK
man['harness']['observation_masking'] = {'placeholder': MASK, 'keep_recent_turns': 2}
gp.set_profile('S1', tools=man['tools'], responses=man['harness']['responses'])
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
tpl = open(man['render']['chat_template_path']).read()


def ntok(msgs, tools):
    s = tok.apply_chat_template(gp.to_template_messages(msgs), tools=tools, add_generation_prompt=True, tokenize=False, enable_thinking=True, chat_template=tpl)
    return len(tok(s, add_special_tokens=False)['input_ids'])


def status_of_adk(c):
    try:
        j = json.loads(c)
        return 'error' if (isinstance(j, dict) and ('error' in j or str(j.get('status', '')).lower() in ('error', 'failed'))) else 'ok'
    except Exception:
        return 'error' if str(c).lower().startswith('error') else 'ok'


def edit_idx(msgs):
    out = []
    for i, m in enumerate(msgs):
        for tc in m.get('tool_calls') or []:
            if tc['function']['name'] == 'edit_file':
                ti = next((j for j, x in enumerate(msgs) if x.get('role') == 'tool' and x.get('tool_call_id') == tc['id']), None)
                out.append((i, ti, tc['id']))
    return out


rows = [json.loads(l) for l in open(f'{S}/contexts.jsonl')]
out = []; expect = collections.Counter()
for n, d in enumerate(rows):
    msgs = d['messages']
    hts = {m['tool_call_id']: status_of_adk(m.get('content')) for m in msgs if m.get('role') == 'tool'}
    base = dict(d, history_tool_status=hts, split='verified' if n % 2 == 0 else 'swebench_test_ext')
    out.append(base)
    E = edit_idx(msgs)
    if E and E[-1][1] is not None:
        m1 = copy.deepcopy(base); m1['context_id'] += ':M1'
        ai, ti, _ = E[-1]; m1['messages'][ti]['content'] = MASK
        m1['messages'][ai]['reasoning_content'] = None; m1['messages'][ai].pop('reasoning', None)
        m1['prompt_tokens'] = ntok(m1['messages'], d['tools']); out.append(m1); expect['M1'] += 1
        st = copy.deepcopy(base); st['context_id'] += ':ST'; st['history_tool_status'][E[-1][2]] = 'error'; out.append(st); expect['ST'] += 1
    if len(E) >= 2 and E[-2][1] is not None:
        m2 = copy.deepcopy(base); m2['context_id'] += ':M2'
        ai, ti, _ = E[-2]; m2['messages'][ti]['content'] = MASK
        m2['messages'][ai]['reasoning_content'] = None; m2['messages'][ai].pop('reasoning', None)
        m2['prompt_tokens'] = ntok(m2['messages'], d['tools']); out.append(m2); expect['M2'] += 1
with open(f'{T}/contexts.jsonl', 'w') as f:
    for r in out: f.write(json.dumps(r) + '\n')
json.dump(man, open(f'{T}/manifest.json', 'w'), indent=1)
print('contexts', len(out), dict(expect))

v = subprocess.run([PY, f'{D}/scripts/validate_contexts.py', f'{T}/manifest.json', str(len(out))], capture_output=True, text=True, cwd=T)
vr = json.loads(v.stdout); print('validate PASS', vr['PASS'], {k: vr[k] for k in ('checked', 'token_match_declared', 'order_ok')})
assert vr['PASS'], v.stdout[-800:] + v.stderr[-800:]
b = subprocess.run([PY, f'{D}/scripts/build_contexts_P.py', f'{T}/manifest.json', f'{T}/meta.jsonl'], capture_output=True, text=True)
print(b.stdout.strip()[-400:]); assert b.returncode == 0, b.stderr[-1500:]
p = subprocess.run([PY, f'{D}/scripts/sample_pools_v2.py', f'{T}/manifest.json', '--out', f'{T}/pools'], capture_output=True, text=True)
assert p.returncode == 0, p.stderr[-1500:]
PM = json.load(open(f'{T}/pools/POOLS_MANIFEST.json'))['S1']
print('pools: eligible', PM['eligible'], '| before rule 2', PM['eligible_before_rule2'], '| rule-2 excluded', PM['rule2_excluded_masked_target'],
      '| verified_only', PM['verified_only'], '| counts', PM['counts'])
meta = {json.loads(l)['id']: json.loads(l) for l in open(f'{T}/meta.jsonl')}
pool = {k: {json.loads(l)['context_id'] for l in open(f'{T}/pools/S1_{k}.jsonl')} for k in ('A1', 'A2', 'B1') if os.path.exists(f'{T}/pools/S1_{k}.jsonl')}
assert all(os.path.isabs(m['template_path']) and os.path.exists(m['template_path']) for m in meta.values())
for cid, m in meta.items():
    if cid.endswith(':M1'): assert m['k_unmasked'] == 0 and cid not in pool['A1'], cid
    if cid.endswith(':M2'): assert m['k_unmasked'] == 1, cid
    if cid.endswith(':ST'): assert m['k_usable'] == 0 and cid not in pool['A1'], cid
# rule-2 accounting: every rule-1-eligible M1 state is a rule-2 exclusion for A1; M2 states with k_usable >= 2 for A1k2/A2
clean = {cid for cid, m in meta.items() if m['protocol_clean'] and (m['pt'] or 0) <= 24000}
exp_a1 = sum(1 for cid, m in meta.items() if cid in clean and m['k_usable'] >= 1 and m['k_unmasked'] < 1)
exp_a2 = sum(1 for cid, m in meta.items() if cid in clean and m['k_usable'] >= 4 and m['k_unmasked'] < 4)
assert PM['rule2_excluded_masked_target'].get('A1', 0) == exp_a1 and PM['rule2_excluded_masked_target'].get('A2', 0) == exp_a2, (exp_a1, exp_a2)
assert exp_a1 == sum(1 for cid in clean if cid.endswith(':M1') and meta[cid]['k_usable'] >= 1)
# verified subset
for k in pool:
    ver = [json.loads(l) for l in open(f'{T}/pools/verified_only/S1_{k}.jsonl')]
    assert all(r['split'] == 'verified' for r in ver) and len(ver) == sum(1 for l in open(f'{T}/pools/S1_{k}.jsonl') if json.loads(l)['split'] == 'verified')
# v1.1 == v1 on the unmodified contexts (k_usable / cleanliness), using the archived v1 builder on the original corpus
o = subprocess.run([PY, f'{D}/scripts/archive/build_contexts_P.v1.py', f'{S}/manifest.json', f'{T}/meta_v1.jsonl'], capture_output=True, text=True,
                   env=dict(os.environ, PYTHONPATH=f'{D}/scripts'))
assert o.returncode == 0, o.stderr[-800:]
v1 = {json.loads(l)['id']: json.loads(l) for l in open(f'{T}/meta_v1.jsonl')}
diff = [(cid, v1[cid]['k_usable'], meta[cid]['k_usable'], v1[cid]['protocol_clean'], meta[cid]['protocol_clean']) for cid in v1
        if (v1[cid]['k_usable'], v1[cid]['protocol_clean']) != (meta[cid]['k_usable'], meta[cid]['protocol_clean'])]
print('v1 vs v1.1 on unmodified contexts: differences', diff)
print('P v1.1 TEST PASSED')
