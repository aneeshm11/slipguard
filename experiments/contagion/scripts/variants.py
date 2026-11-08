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

P5_NOTE = '[edit_file call removed by the harness: the call was malformed and was not executed.]'  # main-track value


def p5_note():
    return f"[{gp.PROFILE['edit_tool']} call removed by the harness: the call was malformed and was not executed.]"
SENT_KEY = 'zzq_sentinel'
ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')


def load_context(meta, cache=None):
    if meta.get('source') == 'P':  # workstream P corpus (CONTEXT_SCHEMA.md): messages at a byte offset, tools in meta
        with open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), meta['contexts_file']), 'rb') as f:
            f.seek(meta['off']); d = json.loads(f.readline())
        return d['messages'], (d.get('tools') or meta['tools'])
    path = f"{ROOT}/{meta['run']}/{meta['file']}"
    with open(path, 'rb') as f:
        f.seek(meta['tools_off']); tools = json.loads(f.readline())['tools']
        f.seek(meta['off']); d = json.loads(f.readline())
    return d['messages'], tools


def slip_key_for(order):
    for k in order:
        if k in (gp.PROFILE['new_key'], gp.PROFILE['old_key']): return k
    return None


INFO_ERR = ('Invoking `{tool}()` failed: the {sk} argument was closed with {cname} instead of the string delimiter, so '
            'everything after it was swallowed into {sk} and {missing} is missing. Call {tool} again with {old} and '
            '{new} as separate, properly closed string arguments.')
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
                missing = [x for x in gp.REQ.get(gp.PROFILE['edit_tool'], [gp.PROFILE['path_key'], gp.PROFILE['old_key'], gp.PROFILE['new_key']]) if x not in parsed]
                info['missing'].append(missing)
                last_corrupt = {'msg': m, 'missing': missing, 'sk': sk}
                out.append(m)
            elif base == 'P2':
                out.append(m)
            elif base == 'P3':
                m.pop('tool_calls', None)
                m['content'] = '<|tool_call>call:' + gp.PROFILE['edit_tool'] + '{' + raw + '}<tool_call|>'
                out.append(m)
                out.append({'role': 'user', 'content': gp.PROFILE['nudge_unparsed']})
            elif base == 'P4':
                sent = f'P4S{j}'
                tc['function']['arguments'] = json.dumps({SENT_KEY: sent})
                if sp['order_mode'] == 'own':
                    call = '<|tool_call>call:' + gp.PROFILE['edit_tool'] + '{' + ','.join(f'{kk}:{gp.fmt_value(args[kk])}' for kk in order) + '}<tool_call|>'
                else:
                    call = gp.canonical_call_text(gp.PROFILE['edit_tool'], args)
                subs.append(('<|tool_call>call:' + gp.PROFILE['edit_tool'] + '{' + SENT_KEY + ':' + gp.D + sent + gp.D + '}<tool_call|>', call))
                out.append(m)
            elif base == 'P5':
                m.pop('tool_calls', None)
                m['content'] = p5_note()
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
                                                                       missing=' and '.join(missing), tool=gp.PROFILE['edit_tool'],
                                                                       old=gp.PROFILE['old_key'], new=gp.PROFILE['new_key'])})
                elif missing:
                    m['content'] = gp.missing_error_content(missing)
                else:  # parser happened to recover an old-key: the corrupted edit would fail to match
                    m['content'] = (json.dumps({'status': 'error', 'error_type': 'FileEditError', 'error_message': gp.PROFILE['edit_not_found']})
                                    if gp.PROFILE['name'] == 'main_track' else gp.PROFILE['edit_not_found'])
                out.append(m)
                for rr in range(2, sp['repeat'] + 1):  # r-dose: the same corrupted call + error again (no thought on repeats)
                    a2 = copy.deepcopy(last_corrupt['msg'])
                    a2.pop('reasoning_content', None); a2.pop('reasoning', None); a2['content'] = None
                    a2['tool_calls'][0]['id'] = str(a2['tool_calls'][0].get('id')) + f'-r{rr}'
                    t2 = copy.deepcopy(m); t2['tool_call_id'] = a2['tool_calls'][0]['id']
                    out += [a2, t2]
                continue
            elif base == 'P2':
                m['content'] = gp.missing_error_content([gp.PROFILE['old_key']])
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
        _TPL[which] = open(gp.OLD_TEMPLATE if which == 'old' else (gp.NEW_TEMPLATE if which == 'new' else which)).read()
    return _TPL[which]


def render(tok, msgs, tools, subs=(), which='old', think=True):
    s = tok.apply_chat_template(gp.to_template_messages(msgs), tools=tools, add_generation_prompt=True, tokenize=False,
                                enable_thinking=think, chat_template=template_text(which))
    for a, b in subs:
        assert s.count(a) == 1, ('sentinel not unique', a, s.count(a))
        s = s.replace(a, b)
    if p5_note() in s:
        # The Jun-5 template closes a text-only model turn with <turn|> but then omits the <|turn>model header of a
        # following assistant message (it treats it as a continuation). Restore the header so the turn structure stays
        # well formed (the current HF template avoids the issue by continuing the turn).
        note = p5_note()
        s = s.replace(note + '<turn|>\n<|channel>', note + '<turn|>\n<|turn>model\n<|channel>')
        s = s.replace(note + '<turn|>\n<|tool_call>', note + '<turn|>\n<|turn>model\n<|tool_call>')
    return s


def build_prompt(tok, meta, pathway, k, which='old', closer=None, ctx=None):
    msgs, tools = ctx if ctx is not None else load_context(meta)
    which = meta.get('template_path', which)
    if pathway in ('Q4M', 'Q8M'):  # A2 with B's MAP repair of the natural slip (meta['map_repair'] = repaired args)
        rep = meta['map_repair']; pr = meta['prior'][-1]
        vm = copy.deepcopy(msgs); tc = vm[pr['ai']]['tool_calls'][0]
        if pathway == 'Q4M':  # P4'-MAP: repaired call in the model's own new-first order + a success response
            P = gp.PROFILE
            order = [k for k in (P['path_key'], P['new_key'], P['old_key']) if k in rep] + [k for k in rep if k not in (P['path_key'], P['new_key'], P['old_key'])]
            sent = 'Q4MS'
            tc['function']['arguments'] = json.dumps({SENT_KEY: sent})
            call = '<|tool_call>call:' + P['edit_tool'] + '{' + ','.join(f'{kk}:{gp.fmt_value(rep[kk])}' for kk in order) + '}<tool_call|>'
            import difflib
            ol, nl = (rep.get(P['old_key']) or '').splitlines(keepends=True), (rep.get(P['new_key']) or '').splitlines(keepends=True)
            body = ''.join(difflib.unified_diff(ol, nl, fromfile='a/' + str(rep.get(P['path_key'])), tofile='b/' + str(rep.get(P['path_key']))))
            vm[pr['ti']]['content'] = json.dumps({'status': 'ok', 'filepath': rep.get(P['path_key']), 'occurrences': 1, 'strategy': 'exact', 'diff': body, 'is_truncated': False})
            return render(tok, vm, tools, [('<|tool_call>call:' + P['edit_tool'] + '{' + SENT_KEY + ':' + gp.D + sent + gp.D + '}<tool_call|>', call)], which=which), {'map_repair': True}
        # Q8M: E's frozen renderer recovering B's intent: raw slip text built from the repaired args (P1 closer)
        order = list(rep.keys()); sk = slip_key_for(order)
        raw = gp.raw_args(rep, order, slip_key=sk, closer='`')
        q, actions = quarantine_renderer().quarantine_messages(vm, tools, raw_by_call_id={tc.get('id'): raw}, canonical=False)
        return render(tok, q, tools, (), which=which), {'quarantine_actions': actions, 'renderer_sha256': _QR['sha256'], 'map_repair': True}
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
