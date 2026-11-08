"""Counterfactual history construction for the contagion injection experiment.

Given a real pre-edit context (logged messages + carried-forward tools) whose k most recent prior edit_file calls were
valid and succeeded, build the variant history in which those k calls are replaced according to a pathway:

  P0  (k=0)  original history.
  P1  corrupted re-render: the call as vLLM 0.19.1 would have parsed the model's slip (string argument closed with a
      backtick instead of <|"|>) -> args dict with new_string ending in '`,old_string:' (+ whatever junk keys the
      parser makes of the swallowed text), re-rendered by the chat template, followed by the exact ADK error the harness
      returns for the missing mandatory parameter(s).
  P2  error message only: the original valid call is kept, the tool response is the ADK missing-old_string error.
  P3  raw slip text in content: the unparsed raw call text (with the slip) is left in the assistant content, there is
      no tool response, and the official swegemma nudge for a raw '<|tool_call>' in the text follows as a user message.
  P4  quarantine fix: the call re-rendered as a canonical VALID call in schema order (old_string before new_string)
      with its true tool response (the original success).
  P5  quarantine-lite: the call and its response are removed; the assistant turn carries a one-line neutral note.
  P6  (control) corrupted re-render as in P1 but followed by the ORIGINAL success response: format contagion without a
      failure, i.e. without the retry motive that P1's error creates.
  P7  (control) P1 with a double-quote closer instead of a backtick: if later slips copy the injected closer ('"', not the
      model's natural backtick), contagion is verbatim copying of the corrupted argument.

Returns the rendered prompt (log-faithful template by default) ready for /v1/completions.
"""
import json, copy, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import gemma_protocol as gp

P5_NOTE = '[edit_file call removed by the harness: the call was malformed and was not executed.]'
SENT_KEY = 'zzq_sentinel'
ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')


def load_context(meta, cache=None):
    path = f"{ROOT}/{meta['run']}/{meta['file']}"
    with open(path, 'rb') as f:
        f.seek(meta['tools_off']); tools = json.loads(f.readline())['tools']
        f.seek(meta['off']); d = json.loads(f.readline())
    return d['messages'], tools


def slip_key_for(order):
    for k in order:
        if k in ('new_string', 'old_string'): return k
    return None


INFO_ERR = ('Invoking `edit_file()` failed: the {sk} argument was closed with {cname} instead of the string delimiter, so '
            'everything after it was swallowed into {sk} and {missing} is missing. Call edit_file again with old_string and '
            'new_string as separate, properly closed string arguments.')
CNAME = {'`': 'a backtick (`)', '"': 'a double quote (")'}


def pathway_spec(pathway, k, prior):
    """Map a pathway label to (base, closer, targets, repeat, order_mode, error_mode).
    base in {P1, P2, P3, P4, P5, P6}; order_mode in {canonical, own}; error_mode in {adk, informative}."""
    spec = dict(base=pathway, closer='`', targets=prior[-k:] if k else [], repeat=1, order_mode='canonical', error_mode='adk')
    if pathway == 'P7': spec.update(base='P1', closer='"')                       # P1 with a double-quote closer
    elif pathway == 'P9': spec.update(base='P1', error_mode='informative')       # P1 + an informative error
    elif pathway in ('R2', 'R4'): spec.update(base='P1', targets=prior[-1:], repeat=int(pathway[1]))  # same corrupted call shown r times
    elif pathway == 'L2': spec.update(base='P1', targets=[prior[-2]])            # lag-2: second most recent edit corrupted, last edit valid
    elif pathway == 'P4P': spec.update(base='P4', order_mode='own')              # P4': canonical re-render in the model's own order
    return spec


def make_variant(msgs, prior, pathway, k, closer=None):
    """-> (messages, substitutions[(sentinel_text, replacement)], info)"""
    if k == 0 or pathway == 'P0':
        return copy.deepcopy(msgs), [], {}
    sp = pathway_spec(pathway, k, prior)
    base = sp['base']; closer = closer or sp['closer']
    act = {}  # message index -> action
    for j, p in enumerate(sp['targets']):
        act[p['ai']] = ('assistant', j, p)
        act[p['ti']] = ('tool', j, p)
    out = []; subs = []; info = {'missing': []}
    last_corrupt = {}
    for i, m in enumerate(msgs):
        if i not in act:
            out.append(copy.deepcopy(m)); continue
        kind, j, p = act[i]
        if kind == 'assistant':
            m = copy.deepcopy(m)
            tc = m['tool_calls'][0]
            args = json.loads(tc['function']['arguments'])
            order = list(args.keys())
            sk = slip_key_for(order)
            raw = gp.raw_args(args, order, slip_key=sk, closer=closer)
            if base in ('P1', 'P6'):
                info.setdefault('raw_by_id', {})[tc.get('id')] = raw
                parsed = gp.parse_args(raw)
                tc['function']['arguments'] = json.dumps(parsed, ensure_ascii=False)
                missing = [x for x in ('filepath', 'old_string', 'new_string') if x not in parsed]
                info['missing'].append(missing)
                last_corrupt = {'msg': m, 'missing': missing, 'sk': sk}
                out.append(m)
            elif base == 'P2':
                out.append(m)
            elif base == 'P3':
                m.pop('tool_calls', None)
                m['content'] = '<|tool_call>call:edit_file{' + raw + '}<tool_call|>'
                out.append(m)
                out.append({'role': 'user', 'content': gp.NUDGE_TRUNCATED_CALL})
            elif base == 'P4':
                sent = f'P4S{j}'
                tc['function']['arguments'] = json.dumps({SENT_KEY: sent})
                if sp['order_mode'] == 'own':
                    call = '<|tool_call>call:edit_file{' + ','.join(f'{kk}:{gp.fmt_value(args[kk])}' for kk in order) + '}<tool_call|>'
                else:
                    call = gp.canonical_call_text('edit_file', args)
                subs.append(('<|tool_call>call:edit_file{' + SENT_KEY + ':' + gp.D + sent + gp.D + '}<tool_call|>', call))
                out.append(m)
            elif base == 'P5':
                m.pop('tool_calls', None)
                m['content'] = P5_NOTE
                out.append(m)
            else:
                raise ValueError(pathway)
        else:  # tool response of a targeted call
            if base in ('P3', 'P5'):
                continue  # no call -> no response
            m = copy.deepcopy(m)
            if base in ('P6', 'P4'):  # keep the true (success) response
                out.append(m); continue
            if base == 'P1':
                missing = last_corrupt['missing']
                if missing and sp['error_mode'] == 'informative':
                    m['content'] = json.dumps({'error': INFO_ERR.format(sk=last_corrupt['sk'], cname=CNAME.get(closer, repr(closer)),
                                                                       missing=' and '.join(missing))})
                elif missing:
                    m['content'] = json.dumps({'error': gp.MISSING_ERR.format(missing='\n'.join(missing))})
                else:  # parser happened to recover an old_string key: the corrupted edit would fail to match
                    m['content'] = json.dumps({'status': 'error', 'error_type': 'FileEditError', 'error_message':
                                               "Failed to replace: old_string not found. Ensure you're not escaping content incorrectly and check whitespace, indentation, and context."})
                out.append(m)
                for rr in range(2, sp['repeat'] + 1):  # r-dose: the same corrupted call + error again (no thought on repeats)
                    a2 = copy.deepcopy(last_corrupt['msg'])
                    a2.pop('reasoning_content', None); a2.pop('reasoning', None); a2['content'] = None
                    a2['tool_calls'][0]['id'] = str(a2['tool_calls'][0].get('id')) + f'-r{rr}'
                    t2 = copy.deepcopy(m); t2['tool_call_id'] = a2['tool_calls'][0]['id']
                    out += [a2, t2]
                continue
            elif base == 'P2':
                m['content'] = json.dumps({'error': gp.MISSING_ERR.format(missing='old_string')})
            out.append(m)
    return out, subs, info


QR_PATH = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/export/quarantine_renderer.py')  # workstream E, FROZEN (read-only)
_QR = {}


def quarantine_renderer():
    """E's shipped quarantine renderer, loaded read-only from its exported file (never copied or modified)."""
    if 'm' not in _QR:
        import importlib.util, hashlib
        spec = importlib.util.spec_from_file_location('quarantine_renderer_E', QR_PATH)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        _QR['m'] = mod; _QR['sha256'] = hashlib.sha256(open(QR_PATH, 'rb').read()).hexdigest()
    return _QR['m']


_TPL = {}


def template_text(which):
    if which not in _TPL:
        _TPL[which] = open(gp.OLD_TEMPLATE if which == 'old' else gp.NEW_TEMPLATE).read()
    return _TPL[which]


def render(tok, msgs, tools, subs=(), which='old', think=True):
    s = tok.apply_chat_template(gp.to_template_messages(msgs), tools=tools, add_generation_prompt=True, tokenize=False,
                                enable_thinking=think, chat_template=template_text(which))
    for a, b in subs:
        assert s.count(a) == 1, ('sentinel not unique', a, s.count(a))
        s = s.replace(a, b)
    if P5_NOTE in s:
        # The Jun-5 template closes a text-only model turn with <turn|> but then omits the <|turn>model header of a
        # following assistant message (it treats it as a continuation). Restore the header so the turn structure stays
        # well formed (the current HF template avoids the issue by continuing the turn).
        s = s.replace(P5_NOTE + '<turn|>\n<|channel>', P5_NOTE + '<turn|>\n<|turn>model\n<|channel>')
        s = s.replace(P5_NOTE + '<turn|>\n<|tool_call>', P5_NOTE + '<turn|>\n<|turn>model\n<|tool_call>')
    return s


def build_prompt(tok, meta, pathway, k, which='old', closer=None, ctx=None):
    msgs, tools = ctx if ctx is not None else load_context(meta)
    if pathway == 'Q8b':  # A2: E's frozen renderer applied to the LOGGED history as is (no raw emission -> sanitized)
        vm, actions = quarantine_renderer().quarantine_messages(msgs, tools, raw_by_call_id=None, canonical=False)
        return render(tok, vm, tools, (), which=which), {'quarantine_actions': actions, 'renderer_sha256': _QR['sha256']}
    if pathway in ('P8a', 'P8b'):  # shipped quarantine (E's frozen renderer) applied to the P1 history
        vm, subs, info = make_variant(msgs, meta['prior'], 'P1', k, closer=closer)
        raw = info.get('raw_by_id', {}) if pathway == 'P8a' else None
        vm, actions = quarantine_renderer().quarantine_messages(vm, tools, raw_by_call_id=raw, canonical=False)
        info['quarantine_actions'] = actions; info['renderer_sha256'] = _QR['sha256']
        return render(tok, vm, tools, subs, which=which), info
    vm, subs, info = make_variant(msgs, meta['prior'], pathway, k, closer=closer)
    return render(tok, vm, tools, subs, which=which), info
