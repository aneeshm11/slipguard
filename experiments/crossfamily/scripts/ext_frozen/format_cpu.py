"""CPU format analysis (workstream X with C's parser harness): what does each format's production parser do with the
format's NATIVE single-closer slip, built over the 1,610 real Gemma-4 slip payloads (conformance/fuzz/cases.jsonl,
subfamilies slip_reassembled_*; intended arguments known)?

Per case: host key (the string argument whose closer slipped), the real look-alike closer text X, the next key.
Variants (one call each; arguments in the real emitted order):
  gemma  G      the real Gemma-4 text (`<|"|>` closer replaced by X)                 -> vLLM 0.19.1 gemma4
  hermes J_real host value's closing '"' replaced by X (X == '"' => no slip in JSON: counted as 'benign')
         J_bt   ... replaced by a backtick (the GPU P1N construction)
         J_omit ... closing '"' omitted
         J_unesc first escaped quote inside the host value left unescaped (cases whose host value contains '"')
  xml    X_real host's closing '\\n</parameter>' replaced by X                        -> vLLM 0.19.1 qwen3_coder / qwen3_xml
         X_bt   ... replaced by a backtick (the GPU P1N construction)
         X_omit ... omitted (no closer at all)
         X_tag  closed with '</host_key>' instead of '</parameter>'
         X_open host closer omitted AND the next argument opened as '<next_key>' (opener drift)
Paths: hermes non-streaming / streaming (one Qwen3 token per delta) / strict reference; qwen3_coder non-streaming /
streaming; qwen3_xml non-streaming; xml strict reference; gemma4 non-streaming (tool parser).
Outcome vs the intended call:
  loud              no tool call returned (the text stays visible as content)
  exact             the intended call is returned
  silent_local      a call is returned with every intended key; only the host value differs, by a short suffix residue
                    (re-synchronised at the next argument)
  silent_absorbed   the next argument is missing or swallowed into the host value (Gemma-style laundering)
  silent_other      any other wrong call (junk keys, type drift, ...)
  delivered_invalid streaming only: a tool call whose argument text is not valid JSON reaches the client
  error             the parser raised (the request would fail visibly)
For every silent outcome: 'laundered' = the returned call, re-rendered by the format's template serializer and
re-parsed by the same parser, is a fixed point; 'flagged' = X's malformed judge flags the returned call.
Valid inputs (the intended calls serialised canonically, plus C's 1,500 real clean calls): exact-match rate per path.
usage: format_cpu.py out_dir [workers=8] [limit=0]
"""
import collections
import json
import math
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CASES = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/fuzz/cases.jsonl')
D = '<|"|>'


def wilson(k, n, z=1.959964):
    if n == 0:
        return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0.0, c - h), 4), round(min(1.0, c + h), 4), n]


def locate(case):
    """-> (host, closer_text, next_key) from the real Gemma text and the intended arguments."""
    args = case['intended'][0]['arguments']; order = list(args); text = case['text']
    for i, k in enumerate(order[:-1]):
        v = args[k]
        if not isinstance(v, str):
            continue
        head = k + ':' + D + v
        pos = text.find(head)
        if pos < 0:
            continue
        after = pos + len(head)
        if text.startswith(D, after):
            continue
        nk = order[i + 1]
        idx = text.find(',' + nk + ':', after)
        if idx < 0:
            continue
        X = text[after:idx]
        if len(X) <= 8 and D not in X:
            return k, X, nk
    return None


def classify(calls, intended, host, nk, closer):
    """outcome class of a returned call list vs the intended call"""
    if not calls:
        return 'loud'
    c = calls[0]; ia = intended['arguments']
    if len(calls) == 1 and c['name'] == intended['name'] and c['args'] == ia:
        return 'exact'
    a = c['args'] if isinstance(c['args'], dict) else {}
    if c['name'] != intended['name'] or not a or '__unparseable_args__' in a:
        return 'silent_other'
    hv = a.get(host); iv = ia.get(host); nxt = ia.get(nk)
    absorbed = nk not in a
    if not absorbed and isinstance(hv, str) and isinstance(iv, str) and isinstance(nxt, str) and len(nxt) >= 4:
        tail = hv[len(iv):] if hv.startswith(iv) else hv
        absorbed = nxt[:40] in tail
    if absorbed:
        return 'silent_absorbed'
    others_equal = all(a.get(k) == v for k, v in ia.items() if k != host) and set(a) == set(ia)
    if others_equal and isinstance(hv, str) and isinstance(iv, str) and hv.startswith(iv) and 0 < len(hv) - len(iv) <= 24:
        return 'silent_local'
    if others_equal and isinstance(hv, str) and isinstance(iv, str) and hv != iv:
        return 'silent_local' if (iv.startswith(hv) and len(iv) - len(hv) <= 24) else 'silent_other'
    return 'silent_other'


_W = {}


def _init():
    import qwenproto as qp
    import gemma_protocol as gp  # frozen copy (A): vLLM 0.19.1 gemma4 parser with the main track's hang fix
    _W['qp'] = qp; _W['gp'] = gp


def gemma_parse(text, tools):
    from vllm.tool_parsers.gemma4_tool_parser import Gemma4ToolParser
    qp = _W['qp']
    if 'g4' not in _W:
        from vllm.tokenizers import get_tokenizer
        _W['g4tok'] = get_tokenizer(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
        _W['g4'] = Gemma4ToolParser(_W['g4tok'], qp.ccr(tools).tools)
    try:
        info = _W['g4'].extract_tool_calls(text, qp.ccr(tools))
    except Exception as e:  # noqa: BLE001
        return {'calls': [], 'exception': repr(e)[:100]}
    if not info.tools_called:
        return {'calls': []}
    return {'calls': [{'name': tc.function.name, 'args': json.loads(tc.function.arguments)} for tc in info.tool_calls]}


def run_paths(fmt, text, tools):
    qp = _W['qp']; res = {}
    if fmt == 'gemma':
        res['gemma4.nonstream'] = gemma_parse(text, tools)
        return res
    if fmt == 'hermes':
        res['hermes.nonstream'] = qp.parse_nonstream(text, 'hermes', tools)
        res['hermes.stream'] = qp.parse_stream(text, 'hermes', tools)
    else:
        res['qwen3_coder.nonstream'] = qp.parse_nonstream(text, 'qwen3_coder', tools)
        res['qwen3_coder.stream'] = qp.parse_stream(text, 'qwen3_coder', tools)
        res['qwen3_xml.nonstream'] = qp.parse_nonstream(text, 'qwen3_xml', tools)
    st = qp.strict_parse(text, fmt, tools)
    res[f'strict_{fmt}'] = {'calls': st['calls'] if st['ok'] else [], 'code': st.get('code')}
    return res


def serialize(fmt, call):
    qp = _W['qp']
    a = call['args'] if isinstance(call['args'], dict) else {}
    return qp.call_text(fmt, call['name'], a, list(a))


def one_case(case):
    qp = _W['qp']
    loc = locate(case)
    tools = case['tools']; intended = case['intended'][0]
    if loc is None:
        return {'id': case['id'], 'skip': 'no_host'}
    host, X, nk = loc; args = intended['arguments']; order = list(args)
    variants = {('gemma', 'G'): case['text']}
    if X == '"':
        variants[('hermes', 'J_real')] = None  # benign: the look-alike IS the JSON closer
    else:
        variants[('hermes', 'J_real')] = qp.slip_text('hermes', 'edit_file', args, order, host, closer=X)
    variants[('hermes', 'J_bt')] = qp.slip_text('hermes', 'edit_file', args, order, host, closer='`')
    variants[('hermes', 'J_omit')] = qp.slip_text('hermes', 'edit_file', args, order, host, mode='omit')
    variants[('hermes', 'J_unesc')] = qp.slip_text('hermes', 'edit_file', args, order, host, mode='unesc')
    variants[('xml', 'X_real')] = qp.slip_text('xml', 'edit_file', args, order, host, closer=X)
    variants[('xml', 'X_bt')] = qp.slip_text('xml', 'edit_file', args, order, host, closer='`')
    variants[('xml', 'X_omit')] = qp.slip_text('xml', 'edit_file', args, order, host, closer='')
    variants[('xml', 'X_tag')] = qp.slip_text('xml', 'edit_file', args, order, host, mode='tagname')
    variants[('xml', 'X_open')] = qp.slip_text('xml', 'edit_file', args, order, host, mode='opener')
    out = {'id': case['id'], 'host': host, 'closer': X, 'next': nk, 'closer_class': case['meta'].get('closer'), 'res': {}}
    for (fmt, vname), text in variants.items():
        if text is None:
            out['res'][vname] = {'benign_or_na': True}; continue
        paths = run_paths(fmt, text, tools)
        r = {}
        for pth, pr in paths.items():
            calls = pr.get('calls') or []
            if pth.endswith('.stream') and fmt == 'hermes' and calls and any('__unparseable_args__' in (c['args'] or {}) for c in calls if isinstance(c['args'], dict)):
                cls = 'delivered_invalid'
            elif pr.get('exception') and not calls:
                cls = 'error'
            else:
                cls = classify(calls, intended, host, nk, X)
            e = {'cls': cls}
            if cls.startswith('silent'):
                c0 = calls[0]
                flags, _ = qp.call_flags(c0['name'], c0['args'])
                e['flagged'] = bool(flags)
                if fmt != 'gemma' and not pth.startswith('strict'):
                    rt = serialize(fmt, c0)
                    rp = run_paths(fmt, rt, tools)[pth]
                    e['laundered'] = bool(rp.get('calls')) and rp['calls'][0]['args'] == c0['args']
                elif fmt == 'gemma':
                    # history re-render with the logged (June-5) template: arguments in case-insensitive dictsort order,
                    # strings between <|"|> with no escaping; laundered = re-parses to the same corrupted dict
                    gp = _W['gp']; a0 = c0['args'] if isinstance(c0['args'], dict) else {}
                    rt = '<|tool_call>call:' + c0['name'] + '{' + ','.join(f'{k}:{gp.fmt_value(a0[k])}' for k in sorted(a0, key=str.lower)) + '}<tool_call|>'
                    rp = gemma_parse(rt, tools)
                    e['laundered'] = bool(rp.get('calls')) and rp['calls'][0]['args'] == a0
                hv = c0['args'].get(host) if isinstance(c0['args'], dict) else None
                iv = args.get(host)
                if cls == 'silent_local' and isinstance(hv, str) and isinstance(iv, str):
                    e['residue'] = hv[len(iv):] if hv.startswith(iv) else ('-' + iv[len(hv):])
            r[pth] = e
        out['res'][vname] = r
    # valid input: the intended call serialised canonically in each format
    vv = {}
    for fmt in ('hermes', 'xml'):
        t = qp.call_text(fmt, 'edit_file', args, order)
        for pth, pr in run_paths(fmt, t, tools).items():
            vv[pth] = classify(pr.get('calls') or [], intended, host, nk, '')
    out['valid'] = vv
    return out


def one_clean(case):
    qp = _W['qp']
    intended = case['intended'][0]; tools = case['tools']; a = intended['arguments']
    r = {}
    for fmt in ('hermes', 'xml'):
        t = qp.call_text(fmt, intended['name'], a, list(a))
        for pth, pr in run_paths(fmt, t, tools).items():
            calls = pr.get('calls') or []
            r[pth] = 'exact' if (len(calls) == 1 and calls[0]['name'] == intended['name'] and calls[0]['args'] == a) else \
                ('loud' if not calls else 'wrong')
    return {'id': case['id'], 'name': intended['name'], 'valid': r}


def main():
    od = sys.argv[1]; workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    os.makedirs(od, exist_ok=True)
    slips, clean = [], []
    for line in open(CASES):
        d = json.loads(line)
        if d.get('subfamily') in ('slip_reassembled_sampled_old', 'slip_reassembled_retry_intent'):
            slips.append(d)
        elif d.get('subfamily') == 'real_clean_call':
            clean.append(d)
    if limit:
        slips, clean = slips[:limit], clean[:limit]
    with Pool(workers, initializer=_init) as pool:
        rs = list(pool.imap(one_case, slips, chunksize=8))
        cs = list(pool.imap(one_clean, clean, chunksize=16))
    with open(os.path.join(od, 'format_cases.jsonl'), 'w') as f:
        for r in rs:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    # ---- summary
    summ = {'n_slip_cases': len(slips), 'n_located': sum(1 for r in rs if 'skip' not in r),
            'closer_classes': dict(collections.Counter(r.get('closer_class') for r in rs if 'skip' not in r)),
            'variants': {}, 'valid_intended': {}, 'valid_real_clean_calls': {}}
    tab = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for r in rs:
        if 'skip' in r:
            continue
        for v, paths in r['res'].items():
            if paths.get('benign_or_na'):
                tab[v]['_'][('benign_or_na', None, None)] += 1; continue
            for pth, e in paths.items():
                tab[v][pth][(e['cls'], e.get('laundered'), e.get('flagged'))] += 1
    for v, pths in tab.items():
        summ['variants'][v] = {}
        for pth, c in pths.items():
            n = sum(c.values())
            cls = collections.Counter()
            for (k, la, fl), m in c.items():
                cls[k] += m
            row = {'n': n, **{k: wilson(m, n) for k, m in cls.items()}}
            sil = sum(m for (k, la, fl), m in c.items() if k.startswith('silent'))
            if sil:
                row['silent_laundered_share'] = wilson(sum(m for (k, la, fl), m in c.items() if k.startswith('silent') and la), sil)
                row['silent_flagged_by_judge_share'] = wilson(sum(m for (k, la, fl), m in c.items() if k.startswith('silent') and fl), sil)
            summ['variants'][v][pth] = row
    res_by = collections.defaultdict(collections.Counter)
    for r in rs:
        if 'skip' in r:
            continue
        for v in ('X_real', 'X_bt'):
            e = (r['res'].get(v) or {}).get('qwen3_coder.nonstream') or {}
            if 'residue' in e:
                res_by[v][e['residue'][:12]] += 1
    summ['xml_residues_top'] = {v: dict(c.most_common(10)) for v, c in res_by.items()}
    vt = collections.defaultdict(collections.Counter)
    for r in rs:
        for pth, k in (r.get('valid') or {}).items():
            vt[pth][k] += 1
    summ['valid_intended'] = {p: {k: wilson(m, sum(c.values())) for k, m in c.items()} for p, c in vt.items()}
    ct = collections.defaultdict(collections.Counter)
    for r in cs:
        for pth, k in r['valid'].items():
            ct[pth][k] += 1
    summ['valid_real_clean_calls'] = {p: {k: wilson(m, sum(c.values())) for k, m in c.items()} for p, c in ct.items()}
    json.dump(summ, open(os.path.join(od, 'format_summary.json'), 'w'), indent=1)
    print(json.dumps({v: {p: {k: x for k, x in row.items() if k in ('n', 'loud', 'exact', 'silent_local', 'silent_absorbed', 'silent_other', 'delivered_invalid', 'error')}
                          for p, row in pths.items()} for v, pths in summ['variants'].items()}, indent=1))


if __name__ == '__main__':
    sys.path.insert(0, os.path.join(HERE, 'frozen'))
    main()
