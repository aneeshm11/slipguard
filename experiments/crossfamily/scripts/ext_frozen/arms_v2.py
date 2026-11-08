"""Schema- and harness-aware counterfactual histories (v2; for workstream P's public-corpus contexts under PREREG_v2).

Same arms and the same message-level constructions as the registered discovery path (scripts/discovery/arms.py, which
wraps workstream A's frozen make_variant and E's frozen quarantine renderer), generalised so the edit tool's key names
come from the declared tools (qwenproto.profile_from_tools):
  S0 edit_file(filepath, old_string, new_string[, allow_multiple])   main-track schema (discovery run)
  S1 edit_file(file_path, old_string, new_string)                    workstream P's harness
  S2 str_replace_editor(command, path, old_str, new_str, ...)        optional
and the harness-specific texts (missing-parameter error, old_string-not-found error, the no-tool-call nudge, what a
success response looks like) come from a HarnessProfile. 'adk' reproduces the swegemma/ADK texts used in the discovery
run; P's harness profile is added when its context schema (experiments/contagion/CONTEXT_SCHEMA.md) is published.

Equivalence check (scripts/explore/check_arms_v2_equiv.py): on S0 contexts with the 'adk' profile every arm's
messages equal the discovery construction's.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'frozen'))
import qwenproto as qp  # noqa: E402
import gemma_protocol as gp  # noqa: E402  (frozen copy of A's: vLLM 0.19.1 gemma4 parser + hang fix, raw_args)
import e_quarantine_renderer as QR  # noqa: E402  (frozen copy of E's shipped quarantine; schema-driven)

ARMS = ['P0', 'P1L', 'P1N', 'P5', 'P6', 'P8a']


class HarnessProfile:
    def __init__(self, name, missing_error, not_found, nudge_no_call, is_success, removal_note):
        self.name = name; self.missing_error = missing_error; self.not_found = not_found
        self.nudge_no_call = nudge_no_call; self.is_success = is_success; self.removal_note = removal_note


def _adk_success(text):
    try:
        return json.loads(text).get('status') == 'ok'
    except Exception:
        return False


HARNESS = {
    'adk': HarnessProfile(
        'adk',
        missing_error=lambda tool, missing: json.dumps({'error': (f'Invoking `{tool}()` failed as the following mandatory input parameters '
                                                                   f'are not present:\n' + '\n'.join(missing) + '\nYou could retry calling this tool, '
                                                                   'but it is IMPORTANT for you to provide all the mandatory parameters.')}),
        not_found=lambda tool: json.dumps(qp.NOT_FOUND),
        nudge_no_call=qp.NUDGE_GENERIC,
        is_success=_adk_success,
        removal_note=lambda tool: f'[{tool} call removed by the harness: the call was malformed and was not executed.]'),
}


def slip_key(order, prof_keys):
    old, new = prof_keys
    for k in order:
        if k in (new, old):
            return k
    return None


def keys_of(prof):
    return ('filepath', 'old_string', 'new_string') if prof is None else (prof.path, prof.old, prof.new)


def edit_tool_of(prof):
    return 'edit_file' if prof is None else prof.edit_tool


def required_of(tools, tool):
    d = qp._decl(tools)
    return list(((d.get(tool) or {}).get('parameters') or {}).get('required') or [])


# ------------------------------------------------------------------------------------------------ context analysis
def analyse_prior(msgs, tools, harness, prof='auto'):
    """prior edit calls of a context (A's analyse(), schema-aware): [{ai, ti, valid, status, single}] in order."""
    if prof == 'auto':
        prof = qp.profile_from_tools(tools)
    et = edit_tool_of(prof)
    tool_by_id = {m.get('tool_call_id'): i for i, m in enumerate(msgs) if m.get('role') == 'tool'}
    prior = []
    for i, m in enumerate(msgs):
        if m.get('role') != 'assistant':
            continue
        tcs = m.get('tool_calls') or []
        for tc in tcs:
            f = tc.get('function') or {}
            if f.get('name') != et:
                continue
            try:
                a = json.loads(f.get('arguments')) if isinstance(f.get('arguments'), str) else f.get('arguments')
            except Exception:
                a = None
            if not qp.is_edit_call(f.get('name'), a, prof, f.get('arguments') if isinstance(f.get('arguments'), str) else None):
                continue
            flags, _ = qp.call_flags(et, a, prof) if isinstance(a, dict) else (['args_not_object'], None)
            ti = tool_by_id.get(tc.get('id'))
            resp = msgs[ti].get('content') if ti is not None else None
            prior.append({'ai': i, 'ti': ti, 'valid': not flags, 'single': len(tcs) == 1,
                          'status': ('ok' if (isinstance(resp, str) and harness.is_success(resp)) else ('none' if resp is None else 'error'))})
    return prior


def k_usable(prior):
    k = 0
    for p in reversed(prior):
        if p['valid'] and p['status'] == 'ok' and p['single'] and p['ti'] is not None:
            k += 1
        else:
            break
    return k


# ------------------------------------------------------------------------------------------------ arms
def make_variant(msgs, prior, arm, tools, fmt, harness='adk', mk=None, prof='auto', closer='`'):
    """-> (messages, info). k = 1: the most recent prior edit call is replaced."""
    H = HARNESS[harness] if isinstance(harness, str) else harness
    if prof == 'auto':
        prof = qp.profile_from_tools(tools)
    if arm in ('P0', 'C0'):
        return copy.deepcopy(msgs), {}
    p = prior[-1]; ai, ti = p['ai'], p['ti']
    et = edit_tool_of(prof); PK, OK, NK = keys_of(prof)
    m = copy.deepcopy(msgs[ai]); tc = m['tool_calls'][0]
    args = json.loads(tc['function']['arguments']) if isinstance(tc['function']['arguments'], str) else copy.deepcopy(tc['function']['arguments'])
    order = list(args); sk = slip_key(order, (OK, NK))
    req = required_of(tools, et) or [PK, OK, NK]
    info = {'slip_key': sk}
    before = [copy.deepcopy(x) for x in msgs[:ai]]; after = [copy.deepcopy(x) for x in msgs[ti + 1:]]
    resp = copy.deepcopy(msgs[ti])
    if arm in ('P1L', 'P6', 'P8a'):
        raw = gp.raw_args(args, order, slip_key=sk, closer=closer)
        parsed = gp.parse_args(raw)  # what vLLM's lenient gemma4 parser returns for the slip (the laundered dict)
        tc['function']['arguments'] = json.dumps(parsed, ensure_ascii=False)
        missing = [x for x in req if x not in parsed]
        info['missing'] = missing
        if arm != 'P6':
            resp['content'] = H.missing_error(et, missing) if missing else H.not_found(et)
        out = before + [m, resp] + after
        if arm == 'P8a':
            out, actions = QR.quarantine_messages(out, tools, raw_by_call_id={tc.get('id'): raw}, canonical=False)
            info['quarantine_actions'] = actions
        return out, info
    if arm == 'P5':
        m.pop('tool_calls', None); m['content'] = H.removal_note(et)
        return before + [m] + after, info
    if arm == 'P1N':
        variant = (qp.MODELS.get(mk) or {}).get('xml_variant') if mk else None
        raw = qp.slip_text(fmt, et, args, order, sk, closer=closer, variant=variant)
        stop = None
        if fmt == 'harmony':
            import fmt_ext as fe
            stop = fe.harmony_encode('<|call|>')[0]
        prod = qp.parse_nonstream(raw, qp.PROD_PARSER[fmt], tools, mk, stop) if fmt in ('harmony', 'mistral') else \
            qp.parse_nonstream(raw, qp.PROD_PARSER[fmt], tools, mk)
        info['p1n_raw'] = raw
        if prod['tools_called'] and prod['calls'] and ('__unparseable_args__' in prod['calls'][0]['args']
                                                        or '__not_object__' in prod['calls'][0]['args']):
            # DELIVERED with non-JSON arguments (vLLM's harmony / mistral parsers do this): the harness keeps the call
            # as delivered and, unable to read any argument, answers with the missing-parameter error for every
            # required key (modelled client fallback; ADK itself would raise on json.loads)
            info['p1n_outcome'] = 'delivered_invalid'
            tc['function']['arguments'] = prod['calls'][0]['args_text']
            resp['content'] = H.missing_error(et, req)
            return before + [m, resp] + after, info
        if not prod['tools_called']:
            info['p1n_outcome'] = 'loud'
            m.pop('tool_calls', None); m['content'] = raw
            return before + [m, {'role': 'user', 'content': H.nudge_no_call}] + after, info
        call = prod['calls'][0]; a2 = call['args'] if isinstance(call['args'], dict) else {}
        info['p1n_args'] = a2
        tc['function']['arguments'] = json.dumps(a2, ensure_ascii=False)
        missing = [k for k in req if k not in a2]
        if a2 == args:
            info['p1n_outcome'] = 'repaired'
        elif missing:
            info['p1n_outcome'] = 'silent_missing'; resp['content'] = H.missing_error(et, missing)
        elif a2.get(OK) == args.get(OK) and a2.get(PK) == args.get(PK):
            info['p1n_outcome'] = 'silent_applied'
            if isinstance(a2.get(NK), str) and a2.get(NK) != args.get(NK) and isinstance(resp.get('content'), str):
                from arms import patch_diff
                resp['content'], info['diff_patch'] = patch_diff(resp['content'], args[NK], a2[NK])
        else:
            info['p1n_outcome'] = 'silent_not_found'; resp['content'] = H.not_found(et)
        return before + [m, resp] + after, info
    raise ValueError(arm)


def build_prompt(msgs, tools, prior, arm, mk, harness='adk'):
    fmt = qp.MODELS[mk]['fmt']
    vm, info = make_variant(msgs, prior, arm, tools, fmt, harness, mk)
    return qp.render(vm, tools, mk), info


def build_prompt_any(msgs, tools, prior, arm, mk, harness='adk'):
    """-> (prompt_text, prompt_ids or None, info) for every format (ids for harmony / mistral)"""
    fmt = qp.MODELS[mk]['fmt']
    vm, info = make_variant(msgs, prior, arm, tools, fmt, harness, mk)
    text, ids = qp.render_any(vm, tools, mk)
    return text, ids, info


# ------------------------------------------------------------------------------------------------ generic records
def context_from_record(rec, harness='adk'):
    """A context record with at least {id, messages (OpenAI format), tools}; optional temperature/top_p and a cluster id
    (attempt/task). Returns (meta, (messages, tools)) in the shape the runner and analysis use."""
    msgs, tools = rec['messages'], rec['tools']
    H = HARNESS[harness] if isinstance(harness, str) else harness
    prior = analyse_prior(msgs, tools, H)
    meta = {'id': rec['id'], 'task': rec.get('cluster') or rec.get('attempt') or rec.get('task') or rec['id'],
            'temp': rec.get('temperature', rec.get('temp')), 'top_p': rec.get('top_p'), 'prior': prior, 'k_usable': k_usable(prior),
            'schema': (qp.profile_from_tools(tools) or 'S0').__str__()}
    return meta, (msgs, tools)


# ------------------------------------------------------------------------------------------------ workstream P corpus
def harness_from_manifest(man):
    """HarnessProfile from a CONTEXT_SCHEMA.md manifest (experiments/contagion/CONTEXT_SCHEMA.md §1)."""
    H = (man.get('harness') or {}); R = H.get('responses') or {}
    miss = R.get('missing_required'); nf = R.get('edit_not_found'); ok_ex = R.get('edit_ok_example')
    unp = R.get('unparsed_call'); nudges = H.get('nudges') or {}
    try:
        ok_status = json.loads(ok_ex).get('status') if ok_ex else None
    except Exception:
        ok_status = None

    def is_success(text):
        if ok_status is not None:
            try:
                return json.loads(text).get('status') == ok_status
            except Exception:
                return False
        return bool(text) and text != nf and not (miss and text.startswith(miss.split('{missing}')[0]))
    if unp and unp.strip().lower() not in ('ignored', 'none', 'null'):
        nudge = unp
    else:
        nudge = next((v for k, v in nudges.items() if 'no_tool' in k or 'continue' in k), qp.NUDGE_GENERIC)
    return HarnessProfile(man.get('corpus_id', 'manifest'),
                          missing_error=lambda tool, missing: (miss or '').replace('{missing}', '\n'.join(missing)),
                          not_found=lambda tool: nf,
                          nudge_no_call=nudge, is_success=is_success,
                          removal_note=lambda tool: f'[{tool} call removed by the harness: the call was malformed and was not executed.]')


def load_p_corpus(manifest_path):
    """-> (records, HarnessProfile). records: {id, messages, tools, temperature, top_p, cluster} per context, read from
    the manifest's contexts file (CONTEXT_SCHEMA.md §2). Outcomes are never read here (blinding)."""
    man = json.load(open(manifest_path)); base = os.path.dirname(os.path.abspath(manifest_path))
    cpath = os.path.join(base, (man.get('files') or {}).get('contexts', 'contexts.jsonl'))
    samp = man.get('sampling') or {}; recs = []
    for line in open(cpath):
        c = json.loads(line)
        tools = man['tools'] if c.get('tools_ref', 'manifest') == 'manifest' else c['tools']
        so = c.get('sampling') or {}
        recs.append({'id': c['context_id'], 'messages': c['messages'], 'tools': tools,
                     'temperature': so.get('temperature', samp.get('temperature')), 'top_p': so.get('top_p', samp.get('top_p')),
                     'cluster': c.get('attempt_id') or c.get('task_id'), 'task_id': c.get('task_id'),
                     'request_index': c.get('request_index')})
    return recs, harness_from_manifest(man)
