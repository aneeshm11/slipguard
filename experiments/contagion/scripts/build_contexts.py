"""Pass 2: materialise real pre-edit agent states of the plain base gemma-4-31b-it-qat-w4a16-ct from the main-track logs.

A context = the exact `messages` the model received right before a logged response whose first tool call is edit_file,
plus the tool declarations carried forward from the most recent line of the same log file that recorded them.
For every context we also analyse the history: each prior edit_file call (parsed args, emission order, validity, the tool
response status) and protocol cleanliness (no malformed/raw tool calls, no missing-parameter errors, no harness nudges).

usage: build_contexts.py index.jsonl out.jsonl [--stats]
"""
import json, sys, re, collections, random, os
sys.path.insert(0, os.path.dirname(__file__))
from extract_index import edit_flags, CLOSER

ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
MISSING_ERR = 'Invoking `edit_file()` failed as the following mandatory input parameters are not present'
RAW_RE = re.compile(r'<\|tool_call>|call:\w+\{')
# look-alike closer followed by ANY declared parameter of the six tools (broader than the edit-only CLOSER)
LEAK_ANY = re.compile(r'(["`\\\']+)\s*,\s*(filepath|old_string|new_string|allow_multiple|content|command|start_line|end_line)\s*:')
REQ = {'edit_file': ['filepath', 'old_string', 'new_string'], 'write_file': ['filepath', 'content'], 'read_file': ['filepath'],
       'run_command': ['command']}


def call_ok(name, a):
    if not isinstance(a, dict): return False
    for k in REQ.get(name, []):
        if k not in a: return False
    for v in a.values():
        if isinstance(v, str) and (LEAK_ANY.search(v) or '<|"|>' in v or '<tool_call|>' in v or '<|tool_call>' in v): return False
    if name == 'edit_file' and edit_flags(a): return False
    return True


def analyse(msgs):
    prior = []; protocol_clean = True; n_user = 0; first_user = None
    tool_by_id = {}
    for i, m in enumerate(msgs):
        if m.get('role') == 'tool': tool_by_id[m.get('tool_call_id')] = i
    for i, m in enumerate(msgs):
        role = m.get('role')
        if role == 'user':
            n_user += 1
            if first_user is None: first_user = i
        if role == 'assistant':
            c = m.get('content') or ''
            if isinstance(c, str) and RAW_RE.search(c): protocol_clean = False
            tcs = m.get('tool_calls') or []
            for tc in tcs:
                f = tc.get('function') or {}
                name = f.get('name'); astr = f.get('arguments')
                try: a = json.loads(astr) if isinstance(astr, str) else astr
                except Exception: a = None
                ok = call_ok(name, a)
                if not ok: protocol_clean = False
                ti = tool_by_id.get(tc.get('id'))
                resp = msgs[ti].get('content') if ti is not None else None
                if isinstance(resp, str) and MISSING_ERR in resp: protocol_clean = False
                if name == 'edit_file':
                    status = 'none'
                    if isinstance(resp, str):
                        try:
                            j = json.loads(resp)
                            status = 'ok' if j.get('status') == 'ok' else ('missing' if 'error' in j and MISSING_ERR in str(j.get('error')) else 'edit_error')
                        except Exception: status = 'nonjson'
                    keys = list(a.keys()) if isinstance(a, dict) else []
                    order = ('new_first' if ('new_string' in keys and 'old_string' in keys and keys.index('new_string') < keys.index('old_string'))
                             else ('old_first' if 'old_string' in keys else 'other'))
                    prior.append({'ai': i, 'ti': ti, 'valid': ok, 'status': status, 'order': order, 'single': len(tcs) == 1,
                                  'nlen': len(a.get('new_string', '')) if isinstance(a, dict) and isinstance(a.get('new_string'), str) else None,
                                  'olen': len(a.get('old_string', '')) if isinstance(a, dict) and isinstance(a.get('old_string'), str) else None})
    # number of messages after each prior edit's tool response (gap to the end of the context)
    for p in prior:
        p['gap_msgs'] = len(msgs) - 1 - (p['ti'] if p['ti'] is not None else p['ai'])
    return {'prior': prior, 'protocol_clean': protocol_clean, 'n_user': n_user, 'n_msgs': len(msgs)}


def usable_k(info):
    """Largest k such that the k most recent prior edits are valid, successful, single-call, with a tool response."""
    k = 0
    for p in reversed(info['prior']):
        if p['valid'] and p['status'] == 'ok' and p['single'] and p['ti'] is not None: k += 1
        else: break
    return k


if __name__ == '__main__':
    idx_path, outp = sys.argv[1], sys.argv[2]
    stats_only = '--stats' in sys.argv
    recs = [json.loads(l) for l in open(idx_path)]
    by_file = collections.defaultdict(list)
    for r in recs:
        if r.get('bad_line'): continue
        by_file[(r['run'], r['file'])].append(r)
    cands = []
    for key, rs in by_file.items():
        rs.sort(key=lambda r: r['ln'])
        last_tools_off = None
        for r in rs:
            if r['has_tools']: last_tools_off = r['off']
            if r['teacher'] or r['model'] != 'openai/gemma-4-31b-it-qat-w4a16-ct': continue
            if not r['calls'] or r['calls'][0]['name'] != 'edit_file': continue
            cands.append((r, last_tools_off))
    print('candidate pre-edit states (base, first call edit_file):', len(cands), file=sys.stderr)
    tools_cache = {}
    out = open(outp, 'w')
    agg = collections.Counter(); gaps = collections.Counter()
    for r, toff in cands:
        path = f"{ROOT}/{r['run']}/{r['file']}"
        if toff is None: agg['no_tools'] += 1; continue
        if (path, toff) not in tools_cache:
            with open(path, 'rb') as f:
                f.seek(toff); tools_cache[(path, toff)] = json.loads(f.readline())['tools']
        with open(path, 'rb') as f:
            f.seek(r['off']); d = json.loads(f.readline())
        info = analyse(d['messages'])
        k = usable_k(info)
        c0 = r['calls'][0]
        tgt = {'bad_syn': c0['bad_syn'], 'flags': c0.get('flags'), 'keys': c0.get('keys'), 'closer': c0.get('closer'), 'fp': c0.get('fp'), 'nh': c0.get('nh')}
        n_prior_bad = sum(1 for p in info['prior'] if not p['valid'])
        agg['all'] += 1
        agg['clean'] += info['protocol_clean']
        if info['protocol_clean']:
            agg['clean_k>=1'] += k >= 1; agg['clean_k>=2'] += k >= 2; agg['clean_k>=4'] += k >= 4
            if k >= 1: gaps[min(info['prior'][-1]['gap_msgs'], 12)] += 1
        row = {'id': f"{r['run']}:{r['file']}:{r['ln']}", 'run': r['run'], 'file': r['file'], 'ln': r['ln'], 'off': r['off'], 'tools_off': toff,
               'task': r['task'], 'temp': r['temp'], 'top_p': r['top_p'], 'pt': r['pt'], 'think': r['think'], 'tbudget': r['tbudget'],
               'protocol_clean': info['protocol_clean'], 'k_usable': k, 'n_prior_edits': len(info['prior']), 'n_prior_bad': n_prior_bad,
               'n_user': info['n_user'], 'n_msgs': info['n_msgs'], 'prior': info['prior'], 'target': tgt}
        out.write(json.dumps(row) + '\n')
    out.close()
    print(dict(agg), file=sys.stderr)
    print('gap (messages after most recent prior edit response) among clean k>=1:', dict(sorted(gaps.items())), file=sys.stderr)
