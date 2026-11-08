"""Offline unit tests for proxy/gemma_protocol.py (no server needed)."""
import os  # added by the repo export (paths are env/config driven)
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'proxy'))
import gemma_protocol as gp  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402
from vllm.tool_parsers.gemma4_tool_parser import _parse_gemma4_args  # noqa: E402

MD = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')
tok = AutoTokenizer.from_pretrained(MD)
TPL = Path(MD, 'chat_template.jinja').read_text()
CAN = gp.canonical_template(TPL)
D = gp.D

EDIT = {'type': 'function', 'function': {'name': 'edit_file', 'description': 'Edit.', 'parameters': {
    'type': 'object', 'properties': {'filepath': {'type': 'string'}, 'old_string': {'type': 'string'},
                                     'new_string': {'type': 'string'}, 'allow_multiple': {'default': False, 'type': 'boolean'}},
    'required': ['filepath', 'old_string', 'new_string']}}}
WRITE = {'type': 'function', 'function': {'name': 'write_file', 'description': 'Write.', 'parameters': {
    'type': 'object', 'properties': {'filepath': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['filepath', 'content']}}}
TOOLS = [EDIT, WRITE]
SCH = gp.tool_schemas(TOOLS)

n_ok = 0


def check(cond, msg):
    global n_ok
    assert cond, msg
    n_ok += 1


# 1. canonical template: declaration + history order
msgs = [{'role': 'system', 'content': 'sys'}, {'role': 'user', 'content': 'fix it'},
        {'role': 'assistant', 'content': None, 'reasoning': 'think',
         'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'edit_file', 'arguments': json.dumps(
             {'filepath': 'a.py', 'old_string': 'x = 1', 'new_string': 'x = 2'})}}]},
        {'role': 'tool', 'tool_call_id': 'c1', 'content': '{"status": "ok"}'}]
conv = gp.to_conversation(msgs)
off = tok.apply_chat_template(conv, tools=TOOLS, add_generation_prompt=True, tokenize=False, chat_template=TPL, enable_thinking=True)
can = tok.apply_chat_template(gp.to_conversation(msgs), tools=TOOLS, add_generation_prompt=True, tokenize=False, chat_template=CAN, enable_thinking=True)
check(off.index('new_string:{') < off.index('old_string:{'), 'official declaration is alphabetical')
check(can.index('old_string:{') < can.index('new_string:{'), 'canonical declaration in schema order')
check('filepath:<|"|>a.py<|"|>,new_string:' in off, 'official history dictsorted')
check('filepath:<|"|>a.py<|"|>,old_string:<|"|>x = 1<|"|>,new_string:' in can, 'canonical history in given order')
check(off.replace('new_string', 'X').count('X') == can.replace('new_string', 'X').count('X'), 'same content')
check(len(off) == len(can), 'only order differs')
check('<|channel>thought\nthink\n<channel|>' in off, 'reasoning rendered from `reasoning`')
check(off.endswith('<|channel>thought\n'), 'after tool response with thinking: prompt opens thought channel')
check('sys <|tool>' in off, "openai content format: system text + ' ' before declarations")

# 2. classification
check(gp.classify_args('edit_file', {'filepath': 'a', 'old_string': 'b', 'new_string': 'c'}, SCH)['ok'], 'valid edit')
c = gp.classify_args('edit_file', {'filepath': 'a', 'new_string': 'code`,old_string:'}, SCH)
check(not c['ok'] and c['leak']['closer'] == '`' and 'missing:old_string' in c['why'], 'lost old_string w/ backtick leak')
c = gp.classify_args('edit_file', {'filepath': 'a', 'new_string': 'code,old_string:', 'x': 1}, SCH)
check(not c['ok'] and c['leak']['closer'] == '' and 'unknown_key' in c['why'], 'no-closer leak + junk key')
check(gp.classify_args('edit_file', {'filepath': 'a', 'old_string': 'def f(a, filepath: str):', 'new_string': 'c'}, SCH)['ok'],
      'type-annotated param named like a key is not a leak')

# 3. verify-then-repair primitives (workstream B's guard + site finder, vendored byte-identical)
import hashlib  # noqa: E402
import re as _re  # noqa: E402
import subprocess  # noqa: E402
VB = Path(gp.__file__).resolve().parent / 'vendor_b_gemma_protocol.py'
want = _re.search(r'sha256: ([0-9a-f]{64})', (VB.parent / 'VENDOR_B.txt').read_text()).group(1)
check(hashlib.sha256(VB.read_bytes()).hexdigest() == want, 'vendored B library matches its recorded sha256')
live = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/gemma_protocol.py'))
print('  (info) B live library', 'identical to vendored copy' if live.read_bytes() == VB.read_bytes() else 'CHANGED since vendoring')
BS = gp.b_schema(SCH)
check(BS == gp.b_schema_from_tools(TOOLS), 'B schema from tool_schemas == from the tools list')
valid = f'call:edit_file{{filepath:{D}a.py{D},old_string:{D}x`{D},new_string:{D}y{D}}}'
check(gp.strictly_valid(valid, BS), 'valid call (content ending in a backtick) passes the strict guard')
# adversarial VALID literals (the class B's QuoteStorm test found the old decode-time IPD changing): strictly valid,
# no plan; the malformed criterion still flags the first one (a known false positive) -> every fix sits behind the guard
lit1 = f'call:edit_file{{filepath:{D}a.py{D},new_string:{D}s = "``,old_string:"{D},old_string:{D}y{D}}}'
lit2 = f"call:edit_file{{filepath:{D}a.py{D},old_string:{D}x{D},new_string:{D}s = '`,allow_multiple:true'{D}}}"
for lit in (lit1, lit2):
    check(gp.strictly_valid(lit, BS), 'adversarial literal is strictly valid')
    plan, aud = gp.ipd_scan(gp.TC_START + lit + gp.TC_END, BS)
    check(plan is None and aud['strict_valid'] == 1, f'no repair plan for a valid literal {aud}')
check(not gp.classify_args('edit_file', _parse_gemma4_args(lit1[len('call:edit_file{'):-1]), SCH)['ok'],
      'SYNTHESIS criterion flags lit1 (false positive the guard protects against)')
# whitespace variants of the closer slip: B's site finder accepts [ws] ',' [ws] KEY [ws] ':'
for sep in [',', ', ', ' ,', ',\n', ', \n    ', '\n, ']:
    call = f'call:edit_file{{filepath:{D}a.py{D},old_string:{D}dirs = P()`{sep}new_string:{D}dirs = Q(){D}}}'
    plan, aud = gp.ipd_scan(gp.TC_START + call + gp.TC_END, BS)
    st = plan and plan['site']
    check(st is not None and st.kind == 'key' and st.key == 'old_string' and st.next_key == 'new_string' and st.run == '`',
          f'whitespace variant {sep!r}: site found {st}')
    rec = gp.intent_parse_args(call[len('call:edit_file{'):-1], SCH['edit_file']['properties'])
    check(rec == {'filepath': 'a.py', 'old_string': 'dirs = P()', 'new_string': 'dirs = Q()'}, f'post-hoc parse {sep!r}: {rec}')
# B's gate example (out/v3_r31_on_june.jsonl ctx-311005d2c5), as generated
gate = (f'call:edit_file{{filepath:{D}repro.py{D}, old_string:{D}dirs = PlatformDirs()`, new_string:{D}'
        f'dirs = PlatformDirs(appname="myapp", appauthor="myauthor")`}}')
plan, aud = gp.ipd_scan(gp.TC_START + gate + gp.TC_END, BS)
check(plan['site'].key == 'old_string' and plan['site'].next_key == 'new_string' and plan['site'].run == '`'
      and plan['site'].gap == '' and plan['site'].cut_positions() == [plan['site'].run_start, plan['site'].run_start + 1]
      and plan['site'].run_start == 81, f'gate site == B reference (pos 81, cuts [81, 82]) {plan["site"]}')
check(_parse_gemma4_args(gate[len('call:edit_file{'):-1]).get('new_string') is None, 'vLLM loses new_string on the gate call')
# content region == vLLM 0.19.1's reasoning parser split
t = 'pre<|channel>thought\nx <|tool_call>call:a{}<tool_call|><channel|>ans<|tool_call>call:b{}<tool_call|>'
check(gp.content_start(t) == t.index('ans') and [c['text'] for c in gp.answer_calls(t)] == ['call:b{}'], 'content region')
check(gp.content_start('<|channel>thought\nnever closed <|tool_call>call:a{}') is None, 'unclosed thought: no content, no calls')
check(gp.content_start('<|tool_call>call:a{}<tool_call|>') == 0, 'no channel tags: everything is content')
two = f'<|tool_call>{valid}<tool_call|><|tool_call>call:edit_file{{filepath:{D}a'
cs = gp.answer_calls(two)
check(len(cs) == 2 and cs[0]['finished'] and not cs[1]['finished'], 'finished / unfinished calls')
# mirrors of B's intent_decode helpers == B's own functions (B's module run in a clean subprocess, read-only)
probe = r"""
import json, sys
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding'))
import gemma_protocol as G, intent_decode as I
sch = G.schema_from_tools(json.loads(sys.argv[1]))
out = []
for call in json.loads(sys.argv[2]):
    st = G.first_violation(call, sch, finished=True, rules=('closer', 'opener'))
    if st is None or st.kind not in ('key', 'end'):
        out.append(None); continue
    n = len(st.cut_positions())
    lls = [-(1.0 + 0.5 * k) for k in range(n)]
    pr = I.ChannelPrior({'`': 320, '"': 58, '\\"': 69}, 0.5)
    out.append({'cont': I._continuation(st, sch['edit_file']), 'closers': [I.closer_at(st, k) for k in range(n)],
                'nc': I.pick_cut(lls, [I.closer_at(st, k) for k in range(n)], 'nc', pr),
                'lik': I.pick_cut(lls, [I.closer_at(st, k) for k in range(n)], 'lik', pr), 'prior': [pr.logp(I.closer_at(st, k)) for k in range(n)]})
print(json.dumps(out))
"""
calls = [gate, f'call:edit_file{{filepath:{D}a.py{D},new_string:{D}y = `x``,old_string:{D}y{D}}}',
         f'call:edit_file{{filepath:{D}a.py{D},old_string:{D}x{D},new_string:{D}y\\"}}',
         f'call:edit_file{{filepath:{D}a.py{D},new_string:{D}q"`,allow_multiple:true,old_string:{D}z{D}}}']
res = subprocess.run([sys.executable, '-I', '-c', probe, json.dumps(TOOLS), json.dumps(calls)], capture_output=True, text=True)
theirs = json.loads(res.stdout.strip().splitlines()[-1]) if res.returncode == 0 else None
check(theirs is not None, f'B probe ran: {res.stderr[-400:]}')
pr = gp.ChannelPrior({'`': 320, '"': 58, '\\"': 69}, 0.5)
for call, th in zip(calls, theirs):
    st = gp.BG.first_violation(call, BS, finished=True, rules=gp.IPD_RULES)
    n = len(st.cut_positions())
    lls = [-(1.0 + 0.5 * k) for k in range(n)]
    mine = {'cont': gp.continuation(st, BS['edit_file']), 'closers': [gp.closer_at(st, k) for k in range(n)],
            'nc': gp.pick_cut(lls, [gp.closer_at(st, k) for k in range(n)], 'nc', pr),
            'lik': gp.pick_cut(lls, [gp.closer_at(st, k) for k in range(n)], 'lik', pr), 'prior': [pr.logp(gp.closer_at(st, k)) for k in range(n)]}
    check(mine == th, f'mirror == B for {call[-40:]!r}: {mine} vs {th}')
check(gp.ipd_stop_strings(SCH) == [], 'no decode-time stop strings (verify-then-repair)')

# 4. intent parse of raw slipped calls; vLLM parse loses old_string
raw = f'filepath:{D}a.py{D},new_string:{D}y = 2\n`,old_string:{D}y = 1\n{D}'
check('old_string' not in _parse_gemma4_args(raw), 'vLLM swallows old_string')
rec = gp.intent_parse_args(raw, SCH['edit_file']['properties'])
check(rec == {'filepath': 'a.py', 'new_string': 'y = 2\n', 'old_string': 'y = 1\n'}, f'intent parse recovers: {rec}')
raw2 = f'filepath:{D}a.py{D},new_string:{D}y = 2,old_string:{D}y = 1{D}'
rec = gp.intent_parse_args(raw2, SCH['edit_file']['properties'])
check(rec == {'filepath': 'a.py', 'new_string': 'y = 2', 'old_string': 'y = 1'}, f'no-closer recovered: {rec}')
raw3 = f'filepath:{D}a.py{D},old_string:{D}x{D},new_string:{D}y`'
rec = gp.intent_parse_args(raw3, SCH['edit_file']['properties'])
check(rec['new_string'] == 'y', 'trailing closer at end')

# 5. quarantine: malformed historical call re-rendered with recovered args; response annotated
bad_args = _parse_gemma4_args(raw)
hist = [{'role': 'user', 'content': 'go'},
        {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'b1', 'type': 'function', 'function': {
            'name': 'edit_file', 'arguments': json.dumps(bad_args)}}]},
        {'role': 'tool', 'tool_call_id': 'b1', 'content': json.dumps({'status': 'error', 'error_type': 'TypeError', 'error_message': 'missing old_string'})},
        {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'g1', 'type': 'function', 'function': {
            'name': 'edit_file', 'arguments': json.dumps({'new_string': 'b', 'filepath': 'f', 'old_string': 'a'})}}]},
        {'role': 'tool', 'tool_call_id': 'g1', 'content': '{"status": "ok"}'}]
q, acts = gp.quarantine_history(hist, SCH, {'b1': {'name': 'edit_file', 'args_str': raw}}, canonical=True)
check(len(acts) == 1 and acts[0]['how'] == 'recovered', f'one recovered action {acts}')
check(json.loads(q[1]['tool_calls'][0]['function']['arguments']) == {'filepath': 'a.py', 'old_string': 'y = 1\n', 'new_string': 'y = 2\n'}, 'recovered args')
check(list(json.loads(q[1]['tool_calls'][0]['function']['arguments'])) == ['filepath', 'old_string', 'new_string'], 'schema order')
check(json.loads(q[2]['content'])['error_type'] == 'MalformedToolCall', 'response annotated')
check(list(json.loads(q[3]['tool_calls'][0]['function']['arguments'])) == ['filepath', 'old_string', 'new_string'], 'valid call reordered')
check(q[4]['content'] == '{"status": "ok"}', 'valid response untouched')
q2, acts2 = gp.quarantine_history(hist, SCH, {}, canonical=False)
check(acts2[0]['how'] == 'sanitized' and 'old_string' not in json.loads(q2[1]['tool_calls'][0]['function']['arguments']), 'sanitized w/o raw')
r2 = tok.apply_chat_template(gp.to_conversation(q2), tools=TOOLS, add_generation_prompt=True, tokenize=False, chat_template=TPL, enable_thinking=True)
check('`,old_string:' not in r2, 'no leaked closer pattern in rendered quarantined history')
# 5b. quarantine never touches a call vouched strictly valid, even if the criterion flags it (lit1)
lit_args = _parse_gemma4_args(lit1[len('call:edit_file{'):-1])
vh = [{'role': 'user', 'content': 'go'},
      {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'v1', 'type': 'function', 'function': {
          'name': 'edit_file', 'arguments': json.dumps(lit_args)}}]},
      {'role': 'tool', 'tool_call_id': 'v1', 'content': json.dumps({'status': 'ok'})}]
check(gp.quarantine_history(vh, SCH, {}, False)[1] != [], 'without the guard the literal would be quarantined')
qv, av = gp.quarantine_history(vh, SCH, {}, False, strictly_valid_ids={'v1'})
check(av == [] and qv == vh, 'strictly valid history call untouched')

# 6. opener drift sites (analysis helper used by the failure log; the request path uses B's first_violation)
TQ = '"' * 3
op1 = f'<|tool_call>call:edit_file{{filepath:{D}a.py{D},new_string="x = 1",old_string:{D}y{D}}}<tool_call|>'
st = gp.find_opener_site(op1, SCH)
check(st and st['key'] == 'new_string' and st['sep'] == '=' and op1[:st['cut']].endswith('new_string'), f'= drift {st}')
op2 = f'<|tool_call>call:edit_file{{filepath:{D}a.py{D},old_string:{TQ}doc{TQ},new_string:{D}y{D}}}<tool_call|>'
st = gp.find_opener_site(op2, SCH)
check(st and st['key'] == 'old_string' and st['sep'] == ':' and st['lead'].startswith(TQ), f'triple-quote opener {st}')
check(gp.find_opener_site(valid, SCH) is None, 'no opener site in a valid call')
think = f'<|channel>thought\n<|tool_call>call:edit_file{{new_string="x"}}<tool_call|><channel|>' + valid
check(gp.find_opener_site(think, SCH) is None, 'calls inside thinking ignored')
check(gp.find_opener_site(f'<|tool_call>call:edit_file{{filepath:a.py,old_string:{D}x{D},new_string:{D}y{D}}}<tool_call|>', SCH)['key'] == 'filepath',
      'bare string value is a site (the generate() guard decides by the official parser)')
# 7. (the vLLM 0.19.1 array-parser hang-trigger checks are withheld from the public copy; the proxy's _install_array_hang_patch is exercised privately -- release_hygiene B4)
print(f'ALL {n_ok} CHECKS PASSED')
