"""CPU format analysis for the extension formats (harmony / gpt-oss; mistral v13 / Devstral-Small-2) on the same 1,598
located real Gemma slip payloads as format_cpu.py: the JSON-argument slip variants (J_bt backtick closer, J_real the real
look-alike closer, J_omit closer omitted, J_unesc first escaped inner quote left unescaped) wrapped in each format's
emitted call syntax and passed to the format's production vLLM 0.19.1 parser (OpenAIToolParser on token ids /
MistralToolParser on the server's detokenised text).
Outcomes: loud (no call), exact, delivered_invalid (a call whose arguments are not JSON reaches the client), silent_*.
For delivered_invalid calls the HISTORY re-render is recorded: harmony re-renders the raw argument text verbatim;
mistral_common re-serialises it as a JSON string (double-encoded).
Valid controls: the intended calls in each format -> exact.
usage: format_ext_cpu.py out_dir [limit=0]"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qwenproto as qp  # noqa: E402
import fmt_ext as fe  # noqa: E402
from format_cpu import CASES, classify, locate, wilson  # noqa: E402

MK = {'harmony': 'gpt-oss-20b', 'mistral': 'devstral-24b'}


def outcome(fmt, text, case, host, nk, X):
    tools = case['tools']; it = case['intended'][0]
    stop = fe.harmony_encode('<|call|>')[0] if fmt == 'harmony' else None
    r = qp.parse_nonstream(text, qp.PROD_PARSER[fmt], tools, MK[fmt], stop) if fmt == 'harmony' else qp.parse_nonstream(text, 'mistral', tools, MK[fmt])
    calls = r.get('calls') or []
    if r.get('exception') and not calls:
        return 'error', None
    if calls and ('__unparseable_args__' in calls[0]['args'] or '__not_object__' in calls[0]['args']):
        return 'delivered_invalid', calls[0]
    return classify([{'name': c['name'], 'args': c['args']} for c in calls], it, host, nk, X), (calls[0] if calls else None)


def main():
    od = sys.argv[1]; limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    os.makedirs(od, exist_ok=True)
    slips = [json.loads(line) for line in open(CASES)]
    slips = [d for d in slips if d.get('subfamily') in ('slip_reassembled_sampled_old', 'slip_reassembled_retry_intent')]
    if limit:
        slips = slips[:limit]
    tab = collections.defaultdict(collections.Counter); valid = collections.Counter(); hist = collections.Counter(); n_loc = 0
    for case in slips:
        loc = locate(case)
        if loc is None:
            continue
        n_loc += 1
        host, X, nk = loc; it = case['intended'][0]; args = it['arguments']; order = list(args)
        for fmt in ('harmony', 'mistral'):
            for v, kw in (('J_bt', dict(closer='`')), ('J_real', dict(closer=X)), ('J_omit', dict(mode='omit')), ('J_unesc', dict(mode='unesc'))):
                if v == 'J_real' and X.startswith('"'):
                    tab[(fmt, v)]['benign_in_json'] += 1; continue
                t = qp.slip_text(fmt, 'edit_file', args, order, host, **kw)
                if t is None:
                    tab[(fmt, v)]['na'] += 1; continue
                cls, call = outcome(fmt, t, case, host, nk, X)
                tab[(fmt, v)][cls] += 1
                if cls == 'delivered_invalid' and v == 'J_bt':
                    # history re-render of the delivered call (assistant message with the raw argument string)
                    msgs = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'u'},
                            {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call00001', 'type': 'function', 'function': {'name': 'edit_file', 'arguments': call['args_text']}}]},
                            {'role': 'tool', 'tool_call_id': 'call00001', 'content': 'error'}]
                    try:
                        txt, ids = qp.render_any(msgs, case['tools'], MK[fmt])
                        if fmt == 'harmony':
                            hist[(fmt, 'raw_args_verbatim_in_history')] += int(call['args_text'] in txt)
                        else:
                            hist[(fmt, 'raw_args_verbatim_in_history')] += int(call['args_text'] in txt)
                            hist[(fmt, 'double_encoded_json_string_in_history')] += int(json.dumps(call['args_text'], ensure_ascii=False) in txt)
                        hist[(fmt, 'rendered')] += 1
                    except Exception as e:  # noqa: BLE001
                        hist[(fmt, 'history_render_error')] += 1
            ct = qp.call_text(fmt, 'edit_file', args, order, form='emit')
            cls, _ = outcome(fmt, ct, case, host, nk, '')
            valid[(fmt, cls)] += 1
    summ = {'n_cases': len(slips), 'n_located': n_loc,
            'variants': {f'{f}:{v}': {'n': sum(c.values()), **{k: wilson(m, sum(c.values())) for k, m in c.items()}} for (f, v), c in tab.items()},
            'valid_intended': {f'{f}:{k}': m for (f, k), m in valid.items()},
            'history_rerender_of_delivered_invalid_J_bt': {f'{f}:{k}': m for (f, k), m in hist.items()}}
    json.dump(summ, open(os.path.join(od, 'format_ext_summary.json'), 'w'), indent=1)
    for k, v in summ['variants'].items():
        print(k, {kk: (x[0] if isinstance(x, list) else x) for kk, x in v.items()})
    print('valid', summ['valid_intended']); print('history', summ['history_rerender_of_delivered_invalid_J_bt'])


if __name__ == '__main__':
    sys.path.insert(0, os.path.join(HERE, 'frozen'))
    main()
