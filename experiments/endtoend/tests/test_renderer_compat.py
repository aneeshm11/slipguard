"""Backward compatibility of the shipped quarantine renderer for workstream A (P8a recovered / P8b sanitized):
old renderer (sha 13e28567..., archive/candidate_0c2a5278/export) vs current export/quarantine_renderer.py on A's own
P1 construction (contagion/scripts/variants.py: the first of new_string/old_string in emitted order closed by a
look-alike instead of <|"|>; vLLM 0.19.1's parse goes into the history; ADK's missing-parameter error, or the
FileEditError when the parse kept an old_string), over B's QuoteStorm payloads (quote/backtick-rich gold-patch hunks
+ adversarial literals; data/quotestorm.jsonl, read-only), both key orders, closers ` and ".
Reports exact-equality counts; any difference is listed (expected only where the content itself contains a
whitespace-variant pattern such as "`, old_string:")."""
import os  # added by the repo export (paths are env/config driven)
import importlib.util
import json
import sys
from pathlib import Path

E = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(E / 'proxy'))
import e2e_proxy as ep  # noqa: E402  (installs the vLLM array-hang patch used by A as well)
ep._install_array_hang_patch()
from vllm.tool_parsers.gemma4_tool_parser import _parse_gemma4_args  # noqa: E402

D = '<|"|>'
MISSING_ERR = ('Invoking `edit_file()` failed as the following mandatory input parameters are not present:\n{missing}\n'
               'You could retry calling this tool, but it is IMPORTANT for you to provide all the mandatory parameters.')
FILE_EDIT_ERR = {'status': 'error', 'error_type': 'FileEditError', 'error_message':
                 "Failed to replace: old_string not found. Ensure you're not escaping content incorrectly and check whitespace, indentation, and context."}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


old = load('qr_old', E / 'archive/candidate_0c2a5278/export/quarantine_renderer.py')
new = load('qr_new', E / 'export/quarantine_renderer.py')
EDIT = {'type': 'function', 'function': {'name': 'edit_file', 'description': 'Edit.', 'parameters': {'type': 'object', 'properties': {
    'filepath': {'type': 'string'}, 'old_string': {'type': 'string'}, 'new_string': {'type': 'string'},
    'allow_multiple': {'type': 'boolean'}}, 'required': ['filepath', 'old_string', 'new_string']}}}


def fmt_value(v):  # == contagion/scripts/gemma_protocol.py::fmt_value
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return D + v + D
    if isinstance(v, (int, float)):
        return str(v)
    return str(v)


def raw_args(args, order, slip_key, closer):  # == contagion/scripts/gemma_protocol.py::raw_args
    parts = []
    for k in order:
        v = args[k]
        parts.append(f'{k}:{D}{v}{closer}' if (k == slip_key and isinstance(v, str)) else f'{k}:{fmt_value(v)}')
    return ','.join(parts)


pay = [json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/data/quotestorm.jsonl'))]
n = same_a = same_b = 0
diffs = []
import collections
by_src = collections.Counter()
for p in pay:
    for order in (['filepath', 'new_string', 'old_string'], ['filepath', 'old_string', 'new_string']):
        args = {'filepath': p['filepath'], 'new_string': p['new'], 'old_string': p['old']}
        for closer in ('`', '"'):
            sk = next(k for k in order if k in ('new_string', 'old_string'))
            raw = raw_args(args, order, sk, closer)
            parsed = _parse_gemma4_args(raw)
            missing = [x for x in ('filepath', 'old_string', 'new_string') if x not in parsed]
            resp = json.dumps({'error': MISSING_ERR.format(missing='\n'.join(missing))}) if missing else json.dumps(FILE_EDIT_ERR)
            msgs = [{'role': 'user', 'content': 'go'},
                    {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'p1', 'type': 'function', 'function': {
                        'name': 'edit_file', 'arguments': json.dumps(parsed, ensure_ascii=False)}}]},
                    {'role': 'tool', 'tool_call_id': 'p1', 'content': resp}]
            n += 1
            a_old, a_new = old.quarantine_messages(msgs, [EDIT], {'p1': raw}), new.quarantine_messages(msgs, [EDIT], {'p1': raw})
            b_old, b_new = old.quarantine_messages(msgs, [EDIT]), new.quarantine_messages(msgs, [EDIT])
            same_a += a_old == a_new
            same_b += b_old == b_new
            grp = 'adversarial' if str(p.get('src', '')).startswith('adversarial') else 'natural'
            by_src[f'{grp}_cases'] += 1
            by_src[f'{grp}_P8a_diff'] += a_old != a_new
            by_src[f'{grp}_P8b_diff'] += b_old != b_new
            if (a_old != a_new or b_old != b_new) and len(diffs) < 10:
                diffs.append({'src': p.get('src'), 'order': order[1], 'closer': closer, 'P8a_same': a_old == a_new,
                              'P8b_same': b_old == b_new, 'content_tail': (args[sk])[-80:],
                              'P8a_old': a_old[0][1]['tool_calls'][0]['function']['arguments'][:200],
                              'P8a_new': a_new[0][1]['tool_calls'][0]['function']['arguments'][:200]})
out = {'cases': n, 'P8a_identical': same_a, 'P8b_identical': same_b, 'by_source': dict(by_src), 'examples_of_differences': diffs,
       'old_sha_prefix': '13e285673b70aa9a', 'payload_source': 'experiments/intent_decoding/data/quotestorm.jsonl'}
(E / 'acceptance/renderer_compat_A.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(json.dumps({k: v for k, v in out.items() if k != 'examples_of_differences'}), '| differences shown:', len(diffs))
for d in diffs[:4]:
    print('  ', json.dumps(d, ensure_ascii=False)[:600])
