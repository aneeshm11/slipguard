"""vLLM 0.31.0 column of the CPU format analysis (run with /opt/envs/env_vllm31). Same 1,598 located real slip
payloads and the same variants as format_cpu.py (built by the same pure-Python constructors); parser paths:
  hermes.nonstream / hermes.stream            Hermes2ProToolParser (0.31)
  qwen3_coder.nonstream                       Qwen3EngineToolParser adapter (0.31 maps qwen3_coder AND qwen3_xml to it)
  qwen3_engine.server / qwen3_engine.stream   Qwen3Parser engine: parse() / parse_delta(), thinking enabled, text preceded
                                              by '</think>\\n\\n' (the call comes after the thought)
usage: format_v31.py out_dir [limit=0]
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qwenproto as qp  # noqa: E402  (pure-Python constructors only; no vLLM 0.19 import at module level)
from format_cpu import CASES, classify, locate, wilson  # noqa: E402

os.environ.setdefault('VLLM_LOGGING_LEVEL', 'ERROR')
import vllm  # noqa: E402
from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest  # noqa: E402
from vllm.tokenizers import get_tokenizer  # noqa: E402
from vllm.tool_parsers.hermes_tool_parser import Hermes2ProToolParser  # noqa: E402
from vllm.tool_parsers.qwen3_engine_tool_parser import Qwen3EngineToolParser  # noqa: E402
from vllm.parser.qwen3 import Qwen3Parser  # noqa: E402

TOK = {'hermes': get_tokenizer(qp.MODELS['qwen3-8b']['dir']), 'xml': get_tokenizer(qp.MODELS['qwen3.5-9b']['dir'])}


def req(tools, think=True):
    return ChatCompletionRequest(model='m', messages=[{'role': 'user', 'content': 'x'}], tools=tools or None, tool_choice='auto',
                                 chat_template_kwargs={'enable_thinking': think})


def args_obj(s):
    try:
        return json.loads(s)
    except Exception:
        return {'__unparseable_args__': s}


def deltas(tok, text):
    ids = tok.encode(text, add_special_tokens=False); out = []; prev = ''
    for k in range(len(ids)):
        cur = tok.decode(ids[:k + 1], skip_special_tokens=False)
        if cur.endswith('�'):
            out.append(('', ids[k])); continue
        out.append((cur[len(prev):], ids[k])); prev = cur
    return ids, out


def acc_deltas(dms):
    acc = {}; content = []
    for dm in dms:
        if dm is None:
            continue
        if dm.content:
            content.append(dm.content)
        for tc in dm.tool_calls or []:
            slot = acc.setdefault(tc.index, {'name': None, 'args': ''})
            fn = tc.function
            if fn is not None:
                name = fn.get('name') if isinstance(fn, dict) else fn.name
                a = fn.get('arguments') if isinstance(fn, dict) else fn.arguments
                if name:
                    slot['name'] = name
                if a:
                    slot['args'] += a
    return [{'name': s['name'], 'args': args_obj(s['args'] or '{}')} for _, s in sorted(acc.items())]


def paths(fmt, text, tools):
    r = {}; rq = req(tools); tok = TOK[fmt]
    try:
        if fmt == 'hermes':
            p = Hermes2ProToolParser(tok, rq.tools)
            info = p.extract_tool_calls(text, rq)
            r['hermes.nonstream'] = [{'name': tc.function.name, 'args': args_obj(tc.function.arguments)} for tc in info.tool_calls] if info.tools_called else []
            p = Hermes2ProToolParser(tok, rq.tools); ids, ds = deltas(tok, text); prev_t, prev_i = '', []; dms = []
            for dt, tid in ds:
                cur_t, cur_i = prev_t + dt, prev_i + [tid]
                dms.append(p.extract_tool_calls_streaming(prev_t, cur_t, dt, prev_i, cur_i, [tid], rq)); prev_t, prev_i = cur_t, cur_i
            r['hermes.stream'] = acc_deltas(dms)
        else:
            p = Qwen3EngineToolParser(tok, rq.tools)
            info = p.extract_tool_calls(text, rq)
            r['qwen3_coder.nonstream'] = [{'name': tc.function.name, 'args': args_obj(tc.function.arguments)} for tc in info.tool_calls] if info.tools_called else []
            full = '</think>\n\n' + text
            e = Qwen3Parser(tok, rq.tools, chat_template_kwargs={'enable_thinking': True})
            if hasattr(e, 'adjust_request'):
                rq = e.adjust_request(rq)
            _, _, tcs = e.parse(full, rq, enable_auto_tools=True, model_output_token_ids=tok.encode(full, add_special_tokens=False))
            r['qwen3_engine.server'] = [{'name': tc.name, 'args': args_obj(tc.arguments)} for tc in (tcs or [])]
            e = Qwen3Parser(tok, rq.tools, chat_template_kwargs={'enable_thinking': True}); ids, ds = deltas(tok, full)
            r['qwen3_engine.stream'] = acc_deltas([e.parse_delta(dt, [tid], rq, None, finished=(k == len(ds) - 1)) for k, (dt, tid) in enumerate(ds)])
    except Exception as ex:  # noqa: BLE001
        r['_exception'] = repr(ex)[:200]
    return r


def main():
    od = sys.argv[1]; limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    slips = []
    for line in open(CASES):
        d = json.loads(line)
        if d.get('subfamily') in ('slip_reassembled_sampled_old', 'slip_reassembled_retry_intent'):
            slips.append(d)
    if limit:
        slips = slips[:limit]
    tab = collections.defaultdict(lambda: collections.defaultdict(collections.Counter)); exc = collections.Counter()
    valid = collections.defaultdict(collections.Counter)
    for case in slips:
        loc = locate(case)
        if loc is None:
            continue
        host, X, nk = loc; it = case['intended'][0]; args = it['arguments']; order = list(args); tools = case['tools']
        V = {('hermes', 'J_bt'): qp.slip_text('hermes', 'edit_file', args, order, host, closer='`'),
             ('hermes', 'J_real'): None if X == '"' else qp.slip_text('hermes', 'edit_file', args, order, host, closer=X),
             ('hermes', 'J_omit'): qp.slip_text('hermes', 'edit_file', args, order, host, mode='omit'),
             ('xml', 'X_bt'): qp.slip_text('xml', 'edit_file', args, order, host, closer='`'),
             ('xml', 'X_real'): qp.slip_text('xml', 'edit_file', args, order, host, closer=X),
             ('xml', 'X_omit'): qp.slip_text('xml', 'edit_file', args, order, host, closer=''),
             ('xml', 'X_tag'): qp.slip_text('xml', 'edit_file', args, order, host, mode='tagname'),
             ('xml', 'X_open'): qp.slip_text('xml', 'edit_file', args, order, host, mode='opener')}
        for (fmt, v), text in V.items():
            if text is None:
                continue
            for pth, calls in paths(fmt, text, tools).items():
                if pth == '_exception':
                    exc[(v, calls[:60])] += 1; continue
                if pth == 'hermes.stream' and calls and any('__unparseable_args__' in (c['args'] or {}) for c in calls if isinstance(c['args'], dict)):
                    cls = 'delivered_invalid'
                else:
                    cls = classify(calls, it, host, nk, X)
                tab[v][pth][cls] += 1
        for fmt in ('hermes', 'xml'):
            for pth, calls in paths(fmt, qp.call_text(fmt, 'edit_file', args, order), tools).items():
                valid[pth]['exact' if (calls and calls[0]['args'] == args and len(calls) == 1) else ('loud' if not calls else 'wrong')] += 1
    summ = {'vllm': vllm.__version__, 'variants': {v: {p: {'n': sum(c.values()), **{k: wilson(m, sum(c.values())) for k, m in c.items()}}
                                                       for p, c in ps.items()} for v, ps in tab.items()},
            'valid_intended': {p: {k: wilson(m, sum(c.values())) for k, m in c.items()} for p, c in valid.items()},
            'exceptions': {f'{k[0]}:{k[1]}': v for k, v in exc.items()}}
    os.makedirs(od, exist_ok=True)
    json.dump(summ, open(os.path.join(od, 'format_summary_v31.json'), 'w'), indent=1)
    for v, ps in summ['variants'].items():
        for p, row in ps.items():
            print(v, p, {k: (x[0] if isinstance(x, list) else x) for k, x in row.items()})
    print('valid', json.dumps(summ['valid_intended'])); print('exceptions', summ['exceptions'])


if __name__ == '__main__':
    main()
