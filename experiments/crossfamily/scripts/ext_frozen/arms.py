"""Counterfactual histories for workstream X, built at the OpenAI-message level and rendered by each Qwen model's own
chat template through vLLM 0.19.1's chat path (qwenproto.render).

Arms (k = 1: the most recent prior edit_file call of the context, valid and successful in the log, is replaced):
  P0    original history (also C0 = census arm on first-edit contexts: original history, no replacement).
  P1L   LAUNDERED exemplar: the same swallowed-argument dict workstream A uses for Gemma P1 (the call as vLLM's gemma4
        parser returns a backtick-closer slip: new_string ending in '`,old_string:' + junk keys, old_string missing),
        followed by the exact ADK missing-parameter error -> rendered by the Qwen template (tojson / <parameter=>).
  P1N   NATIVE slip of the model's own format: the call text with the slipped string argument's closing delimiter
        replaced by a backtick (hermes: the closing '"'; xml: the closing '\\n</parameter>'), passed through the format's
        production vLLM 0.19.1 parser (hermes / qwen3_coder):
          - no call returned (LOUD): the raw text stays in the assistant content, there is no tool response, and the
            harness's generic continuation nudge follows (swegemma agent_runner: '<|tool_call>' is not in the text);
          - a call returned: it is executed as ADK would (missing required -> ADK error; old_string intact -> the edit
            applies with the returned new_string -> success response whose diff shows the change; otherwise
            old_string-not-found error) and the returned call is re-rendered by the template.
  P5    removed + note (A's P5).
  P6    P1L's laundered exemplar followed by the ORIGINAL success response (A's P6; no retry motive).
  P8a   shipped quarantine, recovered: E's FROZEN quarantine_messages() applied to the P1L history with the slip's raw
        text (A's P8a construction) -> recovered call + MalformedToolCall error.
The message-level constructions of P1L/P5/P6/P8a are workstream A's (frozen copy, scripts/frozen/a_variants.py) and
E's (frozen copy, scripts/frozen/e_quarantine_renderer.py); only the rendering differs by model.
"""
import copy
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'frozen'))
import qwenproto as qp  # noqa: E402
import a_variants as AV  # noqa: E402  (frozen copy of contagion/scripts/variants.py, md5 in frozen/SOURCES.md5)
import e_quarantine_renderer as QR  # noqa: E402  (frozen copy of endtoend/export/quarantine_renderer.py)

ARMS_BATTERY = ['P0', 'P1L', 'P1N', 'P5', 'P6', 'P8a']
META_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl')
SHA = {n: hashlib.sha256(open(os.path.join(HERE, 'frozen', n), 'rb').read()).hexdigest()[:16]
       for n in ('a_variants.py', 'gemma_protocol.py', 'e_quarantine_renderer.py')}


def load_meta(path=META_PATH):
    M = {}
    for line in open(path):
        m = json.loads(line); M[m['id']] = m
    return M


def load_context(meta):
    return AV.load_context(meta)


def _tool_unescape(s):
    """approximation of the harness edit tool's 'unescaped' match strategy (literal escape sequences -> characters)"""
    return (s.replace('\\\\', '\x00').replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'")
            .replace('\x00', '\\'))


def patch_diff(resp_text, new_clean, new_corrupt):
    """The edit applied with new_string = new_corrupt instead of new_clean (new_corrupt = new_clean + residue): patch the
    unified diff of the logged success response so that it shows the residue where it lands. Returns (text, status);
    on failure the logged response is returned unchanged (status says why)."""
    try:
        obj = json.loads(resp_text)
    except Exception:
        return resp_text, 'nonjson'
    if not isinstance(obj, dict) or obj.get('status') != 'ok' or not isinstance(obj.get('diff'), str):
        return resp_text, 'no_diff'
    if not new_corrupt.startswith(new_clean):
        return resp_text, 'not_suffix'
    residue = new_corrupt[len(new_clean):]
    if '\n' in residue:
        return resp_text, 'multiline_residue'
    nc = _tool_unescape(new_clean) if obj.get('strategy') == 'unescaped' else new_clean
    nl = nc.split('\n')
    lines = obj['diff'].split('\n')

    def done(status):
        obj['diff'] = '\n'.join(lines)
        return json.dumps(obj, ensure_ascii=False), status
    if nl[-1] != '':  # residue appended to the last line of new_string
        last = nl[-1]
        for i in range(len(lines) - 1, -1, -1):
            if lines[i] == '+' + last:
                lines[i] = '+' + last + residue
                return done('patched_plus')
        for i in range(len(lines) - 1, -1, -1):
            if lines[i] == ' ' + last:
                lines[i:i + 1] = ['-' + last, '+' + last + residue]
                return done('patched_context')
        return resp_text, 'line_not_found'
    # new_string ends with a newline: the residue lands at the start of the next file line
    prev = next((x for x in reversed(nl) if x != ''), None)
    if prev is None:
        return resp_text, 'empty_new'
    for i in range(len(lines) - 2, -1, -1):
        if lines[i] in ('+' + prev, ' ' + prev) and lines[i + 1].startswith(' '):
            nxt = lines[i + 1][1:]
            lines[i + 1:i + 2] = ['-' + nxt, '+' + residue + nxt]
            return done('patched_nextline')
    return resp_text, 'nextline_not_found'


def native_variant(msgs, prior, tools, fmt, mk=None, closer='`'):
    """P1N (see module docstring). Returns (messages, info)."""
    p = prior[-1]; ai, ti = p['ai'], p['ti']
    m = copy.deepcopy(msgs[ai]); tc = m['tool_calls'][0]
    args = json.loads(tc['function']['arguments']); order = list(args.keys())
    sk = AV.slip_key_for(order)
    raw = qp.slip_text(fmt, 'edit_file', args, order, sk, closer=closer)
    prod = qp.parse_nonstream(raw, qp.PROD_PARSER[fmt], tools, mk)
    info = {'p1n_raw': raw, 'slip_key': sk}
    if not prod['tools_called']:
        info['p1n_outcome'] = 'loud'
        m.pop('tool_calls', None); m['content'] = raw
        out = [copy.deepcopy(x) for x in msgs[:ai]] + [m, {'role': 'user', 'content': qp.NUDGE_GENERIC}] + \
              [copy.deepcopy(x) for x in msgs[ti + 1:]]
        return out, info
    call = prod['calls'][0]; a2 = call['args'] if isinstance(call['args'], dict) else {}
    info['p1n_args'] = a2
    tc['function']['arguments'] = json.dumps(a2, ensure_ascii=False)
    if call['name'] != 'edit_file':
        info['p1n_outcome'] = 'silent_wrong_name'
    resp = copy.deepcopy(msgs[ti])
    missing = [k for k in ('filepath', 'old_string', 'new_string') if k not in a2]
    if a2 == args:
        info['p1n_outcome'] = 'repaired'
    elif missing:
        info['p1n_outcome'] = 'silent_missing'
        resp['content'] = json.dumps({'error': qp.MISSING_ERR.format(missing='\n'.join(missing))})
    elif a2.get('old_string') == args.get('old_string') and a2.get('filepath') == args.get('filepath'):
        info['p1n_outcome'] = 'silent_applied'
        if isinstance(a2.get('new_string'), str) and a2.get('new_string') != args.get('new_string'):
            resp['content'], info['diff_patch'] = patch_diff(resp['content'], args['new_string'], a2['new_string'])
    else:
        info['p1n_outcome'] = 'silent_not_found'
        resp['content'] = json.dumps(qp.NOT_FOUND)
    out = [copy.deepcopy(x) for x in msgs[:ai]] + [m, resp] + [copy.deepcopy(x) for x in msgs[ti + 1:]]
    return out, info


def build_messages(meta, ctx, arm, fmt, mk=None):
    """-> (messages, tools, info) for one context and arm."""
    msgs, tools = ctx
    if arm in ('P0', 'C0'):
        return copy.deepcopy(msgs), tools, {}
    prior = meta['prior']
    if arm == 'P1L':
        vm, subs, info = AV.make_variant(msgs, prior, 'P1', 1)
    elif arm == 'P6':
        vm, subs, info = AV.make_variant(msgs, prior, 'P6', 1)
    elif arm == 'P5':
        vm, subs, info = AV.make_variant(msgs, prior, 'P5', 1)
    elif arm == 'P8a':
        vm, subs, info = AV.make_variant(msgs, prior, 'P1', 1)
        vm, actions = QR.quarantine_messages(vm, tools, raw_by_call_id=info.get('raw_by_id', {}), canonical=False)
        info['quarantine_actions'] = actions
    elif arm == 'P1N':
        vm, info = native_variant(msgs, prior, tools, fmt, mk)
        subs = []
    else:
        raise ValueError(arm)
    assert not subs, 'sentinel substitutions are Gemma-template-specific and unused here'
    info.pop('raw_by_id', None)
    return vm, tools, info


def build_prompt(meta, ctx, arm, mk):
    fmt = qp.MODELS[mk]['fmt']
    vm, tools, info = build_messages(meta, ctx, arm, fmt, mk)
    return qp.render(vm, tools, mk), info
