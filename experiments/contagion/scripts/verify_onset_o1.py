"""PREREG_v2.3 O1 construction checks (CPU; P's corpus and C's library-faithful pipeline only, no audited path):
 (1) every historical tool result of the 600 S1_B1 states: run_onset.adk_result_content(c) == the REAL google-adk 1.36.1
     serializer applied to the dict ADK builds for a text-returning tool, _safe_json_serialize({'result': c});
 (2) on N states: the tool-response segments of A's O1 render == those of C's library-faithful pipeline
     (experiments/conformance/history/pipeline.py: genai Content -> google-adk LiteLlm -> litellm 1.104 HTTP body ->
     vLLM 0.19.1 preprocessing -> July template), byte for byte;
 (3) manipulation strength: share of tool results containing \\" natively (O0) vs in O1; O1 prompt token growth.
usage: verify_onset_o1.py <out.json> [N=6]"""
import sys, os, json, re, collections
sys.dont_write_bytecode = True
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
os.makedirs(f'{D}/data/onset/tmp', exist_ok=True)
os.environ['TMPDIR'] = f'{D}/data/onset/tmp'
sys.path.insert(0, f'{D}/scripts')
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/history'))
import pipeline as CP                                  # C's library-faithful pipeline (read-only)
from google.genai import types
from google.adk.models.lite_llm import _safe_json_serialize
import gemma_protocol as gp, variants as V, run_onset as RO
from transformers import AutoTokenizer
N = int(sys.argv[2]) if len(sys.argv) > 2 else 6
man = json.load(open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json')))
gp.set_profile(man['tool_profile'], tools=man['tools'], responses=man['harness'].get('responses'))
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
b1 = [json.loads(l)['context_id'] for l in open(f'{D}/data/confirmatory/pools/S1_B1.jsonl')][:600]
S = set(b1); META = {}
for l in open(f'{D}/data/confirmatory/meta_S1.jsonl'):
    m = json.loads(l)
    if m['id'] in S: META[m['id']] = m
res = {'states': len(b1), 'adk_serializer_equal': 0, 'adk_serializer_total': 0, 'native_dq_escape': 0, 'o1_dq_escape': 0,
       'pipeline_check': [], 'tokens': {}}
SEG = re.compile(r'<\|tool_response>.*?<tool_response\|>', re.S)


def to_genai(msgs):
    contents, system, names, pend = [], None, {}, []
    def flush():
        if pend: contents.append(types.Content(role='user', parts=list(pend))); pend.clear()
    for m in msgs:
        r = m['role']
        if r == 'system': system = m['content'] if isinstance(m['content'], str) else ''.join(p.get('text', '') for p in m['content']); continue
        if r == 'tool':
            pend.append(types.Part(function_response=types.FunctionResponse(id=m['tool_call_id'], name=names.get(m['tool_call_id'], 'unknown'),
                                                                            response={'result': m['content']})))
            continue
        flush()
        if r == 'user':
            contents.append(types.Content(role='user', parts=[types.Part(text=m['content'])]))
        else:
            parts = []
            if m.get('content'): parts.append(types.Part(text=m['content']))
            for tc in m.get('tool_calls') or []:
                f = tc['function']; a = json.loads(f['arguments']) if isinstance(f['arguments'], str) else f['arguments']
                names[tc['id']] = f['name']
                parts.append(types.Part(function_call=types.FunctionCall(id=tc['id'], name=f['name'], args=a)))
            contents.append(types.Content(role='model', parts=parts))
    flush()
    return system, contents


growth = []
for n, cid in enumerate(b1):
    m = META[cid]; msgs, tools = V.load_context(m)
    for x in msgs:
        if x['role'] == 'tool':
            c = x['content']; res['adk_serializer_total'] += 1
            res['adk_serializer_equal'] += RO.adk_result_content(c) == _safe_json_serialize({'result': c})
            res['native_dq_escape'] += '\\"' in c; res['o1_dq_escape'] += '\\"' in RO.adk_result_content(c)
    p0, _ = RO.build_prompt(tok, m, 'O0', 0, ctx=(msgs, tools)); p1, _ = RO.build_prompt(tok, m, 'O1', 0, ctx=(msgs, tools))
    n0 = len(tok(p0, add_special_tokens=False)['input_ids']); n1 = len(tok(p1, add_special_tokens=False)['input_ids'])
    growth.append((n0, n1, n0 == m['pt']))
    if n < N:
        system, contents = to_genai(msgs)
        c = CP.adk_forward(contents, system_instruction=system, model=CP.HARNESS_MODEL)
        if not c['ok']: res['pipeline_check'].append({'id': cid, 'error': c['error'][:300]}); continue
        v = CP.vllm_render(c['body'], 'july')
        if not v['ok']: res['pipeline_check'].append({'id': cid, 'error': str(v.get('error'))[:300]}); continue
        a_seg, c_seg = SEG.findall(p1), SEG.findall(v['prompt'])
        body = json.loads(c['body']); wire_tool = [x['content'] for x in body['messages'] if x.get('role') == 'tool']
        mine_tool = [x['content'] for x in RO.o1_messages(msgs) if x['role'] == 'tool']
        res['pipeline_check'].append({'id': cid, 'tool_results': len(mine_tool), 'wire_content_identical': wire_tool == mine_tool,
                                      'rendered_segments_identical': a_seg == c_seg, 'n_segments': [len(a_seg), len(c_seg)],
                                      'first_diff': None if a_seg == c_seg else next(((i, a[:200], b[:200]) for i, (a, b) in enumerate(zip(a_seg, c_seg)) if a != b), 'count differs')})
res['tokens'] = {'O0_matches_logged_prompt_tokens': sum(g[2] for g in growth), 'O0_mean': sum(g[0] for g in growth) / len(growth),
                 'O1_mean': sum(g[1] for g in growth) / len(growth), 'O1_max': max(g[1] for g in growth),
                 'O1_over_32160 (room < 600)': sum(1 for g in growth if g[1] > 32768 - 608)}
json.dump(res, open(sys.argv[1], 'w'), indent=1, default=str)
print(json.dumps(res, indent=1, default=str)[:3000])
