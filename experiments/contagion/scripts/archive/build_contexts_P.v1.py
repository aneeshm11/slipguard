"""Build injection metadata for a workstream-P corpus (CONTEXT_SCHEMA.md): one meta line per context with the prior
edit calls of the active tool profile (message indices, validity, response status, emitted order), history
cleanliness, k_usable, sampling, template and clustering keys. Reads ONLY manifest.json + contexts.jsonl (never the
outcomes file).
usage: build_contexts_P.py <manifest.json> <out_meta.jsonl>
"""
import json, sys, os, re, collections
sys.path.insert(0, os.path.dirname(__file__))
import gemma_protocol as gp

man_path, outp = sys.argv[1], sys.argv[2]
man = json.load(open(man_path)); base = os.path.dirname(os.path.abspath(man_path))
H = man['harness']; R = H.get('responses', {})
gp.set_profile(man['tool_profile'], tools=man['tools'], responses=R)
P = gp.PROFILE
ctx_file = os.path.join(base, man['files']['contexts']) if not os.path.isabs(man['files']['contexts']) else man['files']['contexts']
assert 'outcome' not in os.path.basename(ctx_file), 'refusing to read an outcomes file'
miss_prefix = (R.get('missing_required') or gp.MISSING_ERR).split('{missing}')[0].strip()[:60]
not_found = (R.get('edit_not_found') or '').strip()[:60]
RAW_RE = re.compile(r'<\|tool_call>|call:\w+\{')


def status_of(content):
    c = content if isinstance(content, str) else json.dumps(content)
    if miss_prefix and miss_prefix in c: return 'missing'
    if not_found and not_found in c: return 'edit_error'
    try:
        j = json.loads(c)
        if isinstance(j, dict) and ('error' in j or str(j.get('status', '')).lower() in ('error', 'failed')): return 'edit_error'
    except Exception:
        if c.lower().startswith(('error', 'failed')): return 'edit_error'
    return 'ok'


def call_ok(name, a):
    if not isinstance(a, dict): return False
    for k in gp.REQ.get(name, []):
        if k not in a: return False
    for v in a.values():
        if isinstance(v, str) and (gp.CLOSER.search(v) or gp.D in v or '<tool_call|>' in v or '<|tool_call>' in v): return False
    if name == P['edit_tool'] and any(k not in gp.EDIT_KEYS for k in a): return False
    return True


def analyse(msgs):
    prior = []; clean = True; n_user = 0
    tool_idx = {m.get('tool_call_id'): i for i, m in enumerate(msgs) if m.get('role') == 'tool'}
    for i, m in enumerate(msgs):
        if m.get('role') == 'user': n_user += 1
        if m.get('role') != 'assistant': continue
        c = m.get('content') or ''
        if isinstance(c, str) and RAW_RE.search(c): clean = False
        tcs = m.get('tool_calls') or []
        for tc in tcs:
            f = tc.get('function') or {}; name = f.get('name')
            try: a = json.loads(f.get('arguments')) if isinstance(f.get('arguments'), str) else f.get('arguments')
            except Exception: a = None
            ok = call_ok(name, a)
            if not ok: clean = False
            ti = tool_idx.get(tc.get('id')); resp = msgs[ti].get('content') if ti is not None else None
            st = status_of(resp) if resp is not None else 'none'
            if st == 'missing': clean = False
            if gp.is_edit_call(name, a):
                keys = list(a.keys()) if isinstance(a, dict) else []
                order = ('new_first' if (P['new_key'] in keys and P['old_key'] in keys and keys.index(P['new_key']) < keys.index(P['old_key']))
                         else ('old_first' if P['old_key'] in keys else 'other'))
                prior.append({'ai': i, 'ti': ti, 'valid': ok, 'status': st, 'order': order, 'single': len(tcs) == 1})
    for p in prior: p['gap_msgs'] = len(msgs) - 1 - (p['ti'] if p['ti'] is not None else p['ai'])
    return prior, clean, n_user


def k_usable(prior):
    k = 0
    for p in reversed(prior):
        if p['valid'] and p['status'] == 'ok' and p['single'] and p['ti'] is not None: k += 1
        else: break
    return k


samp = man.get('sampling', {}); tpl = man['render']['chat_template_path']
n = 0; agg = collections.Counter()
with open(ctx_file, 'rb') as f, open(outp, 'w') as fo:
    off = 0
    for raw in f:
        o = off; off += len(raw)
        d = json.loads(raw)
        tools = d.get('tools') or man['tools']
        prior, clean, n_user = analyse(d['messages'])
        s = dict(samp, **(d.get('sampling') or {}))
        row = {'id': d['context_id'], 'source': 'P', 'corpus_id': man['corpus_id'], 'contexts_file': ctx_file, 'off': o,
               'tools': tools if d.get('tools') else None, 'task': d['attempt_id'], 'task_id': d['task_id'],
               'request_index': d['request_index'], 'temp': s.get('temperature'), 'top_p': s.get('top_p'), 'pt': d.get('prompt_tokens'),
               'template_path': d.get('template') or tpl, 'profile': man['tool_profile'], 'protocol_clean': clean,
               'k_usable': k_usable(prior), 'n_prior_edits': len(prior), 'n_user': n_user, 'prior': prior}
        if row['tools'] is None: row['tools'] = man['tools']
        fo.write(json.dumps(row) + '\n'); n += 1
        agg['all'] += 1; agg['clean'] += clean; agg['clean_k>=1'] += (clean and row['k_usable'] >= 1); agg['clean_k>=4'] += (clean and row['k_usable'] >= 4)
print('contexts', n, dict(agg))
