import json, sys, os, copy
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
import qwenproto as qp
qp.MODELS['gpt-oss-20b'] = {'dir': qp.MD + 'gpt-oss-20b', 'fmt': 'harmony', 'model_type': 'gpt_oss'}
qp.MODELS['devstral-24b'] = {'dir': qp.MD + 'Devstral-Small-2-24B-Instruct-2512', 'fmt': 'mistral', 'model_type': 'mistral3'}
import fmt_ext as fe
import arms_v2 as A2
recs, H = A2.load_p_corpus(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/test_S1/manifest.json'))
rec = recs[0]; meta, (msgs, tools) = A2.context_from_record(rec, H)
p = meta['prior'][-1]; a = msgs[p['ai']]['tool_calls'][0]['function']['arguments']
ids = fe.harmony_render_ids(msgs, tools); txt = fe.harmony_decode(ids)
print('harmony history call present:', fe.harmony_history_call('edit_file', a) in txt)
mids = fe.mistral_render_ids(msgs, tools, 'devstral-24b'); mt = fe.mistral_decode(mids, 'devstral-24b')
print('MISTRAL n_ids', len(mids)); print(mt[:500]); print('.....'); print(mt[-900:])
print('mistral history call present:', fe.mistral_history_call('edit_file', a) in mt)
# invalid-JSON arguments in history (P1N delivered-invalid construction)
m2 = copy.deepcopy(msgs); bad = a[:-40] + '`, "old_string": "x"}'
m2[p['ai']]['tool_calls'][0]['function']['arguments'] = bad
try:
    t2 = fe.harmony_decode(fe.harmony_render_ids(m2, tools)); print('harmony renders invalid-JSON args verbatim:', bad in t2)
except Exception as e: print('harmony invalid args error', repr(e)[:200])
try:
    t3 = fe.mistral_decode(fe.mistral_render_ids(m2, tools, 'devstral-24b'), 'devstral-24b'); print('mistral renders invalid-JSON args:', bad in t3)
except Exception as e: print('mistral invalid args ERROR ->', repr(e)[:300])
