"""Build injection metadata for a workstream-P corpus (CONTEXT_SCHEMA.md): one meta line per context with the prior
edit calls of the active tool profile (message indices, validity, tool-result status, masking, emitted order), history
cleanliness, k_usable, k_unmasked, sampling, template and clustering keys. Reads ONLY manifest.json + contexts.jsonl
(never the outcomes or requests files).
v1.1 (2026-11-04 ~15:50 UTC, PI decision on P's observation masking; decided before any P data existed):
  - prior-edit status comes from the context's `history_tool_status` (status as executed), never from the rendered
    text (masked outputs hide it); k_usable uses it;
  - each prior edit carries `masked` (its tool result is the manifest's masked_tool_output placeholder) and the meta
    carries `k_unmasked` (consecutive most recent prior edits with an unmasked result); the pools (sample_pools_v2.py
    v1.1) admit a state only if its injection targets are unmasked;
  - validity and protocol-cleanliness use the same PREREG_v2 malformed criterion as sample_pools_v2.py (imported, so
    the two cannot drift);
  - a relative chat_template_path resolves against the manifest's directory; `split` is recorded.
usage: build_contexts_P.py <manifest.json> <out_meta.jsonl>
"""
import json, sys, os, collections
sys.path.insert(0, os.path.dirname(__file__))
import gemma_protocol as gp
import sample_pools_v2 as SP

man_path, outp = sys.argv[1], sys.argv[2]
man = json.load(open(man_path)); base = os.path.dirname(os.path.abspath(man_path))
H = man['harness']; R = H.get('responses', {})
gp.set_profile(man['tool_profile'], tools=man['tools'], responses=R)
ctx_file = man['files']['contexts'] if os.path.isabs(man['files']['contexts']) else os.path.join(base, man['files']['contexts'])
assert 'outcome' not in os.path.basename(ctx_file).lower() and 'request' not in os.path.basename(ctx_file).lower(), 'refusing to read an outcomes/requests file'
mask_text = SP.mask_text_of(man)
tpl = man['render']['chat_template_path']
tpl = tpl if os.path.isabs(tpl) else os.path.join(base, tpl)
assert os.path.exists(tpl), f'template not found: {tpl}'

samp = man.get('sampling', {})
n = 0; agg = collections.Counter()
with open(ctx_file, 'rb') as f, open(outp, 'w') as fo:
    off = 0
    for raw in f:
        o = off; off += len(raw)
        d = json.loads(raw)
        if 'history_tool_status' not in d:
            sys.exit(f"v1.1: context {d.get('context_id')} has no history_tool_status (status must not come from the rendered text)")
        tools = d.get('tools') or man['tools']
        msgs = d['messages']
        clean, prior = SP.analyse(msgs, SP.decl_of(tools), d['history_tool_status'] or {}, mask_text)
        for p in prior:
            p['gap_msgs'] = len(msgs) - 1 - (p['ti'] if p['ti'] is not None else p['ai'])
        n_user = sum(1 for m in msgs if m.get('role') == 'user')
        s = dict(samp, **(d.get('sampling') or {}))
        dtpl = d.get('template')
        if dtpl and not os.path.isabs(dtpl): dtpl = os.path.join(base, dtpl)
        row = {'id': d['context_id'], 'source': 'P', 'corpus_id': man['corpus_id'], 'contexts_file': ctx_file, 'off': o,
               'tools': tools, 'task': d['attempt_id'], 'task_id': d['task_id'], 'split': d.get('split'),
               'request_index': d['request_index'], 'temp': s.get('temperature'), 'top_p': s.get('top_p'), 'top_k': s.get('top_k'),
               'pt': d.get('prompt_tokens'), 'template_path': dtpl or tpl, 'profile': man['tool_profile'], 'protocol_clean': clean,
               'k_usable': SP.k_usable(prior), 'k_unmasked': SP.k_unmasked(prior), 'n_prior_edits': len(prior), 'n_user': n_user,
               'prior': prior}
        fo.write(json.dumps(row) + '\n'); n += 1
        agg['all'] += 1; agg['clean'] += clean
        for K in (1, 2, 4):
            agg[f'clean_k>={K}'] += (clean and row['k_usable'] >= K)
            agg[f'clean_k>={K}_unmasked'] += (clean and row['k_usable'] >= K and row['k_unmasked'] >= K)
print('contexts', n, dict(agg))
