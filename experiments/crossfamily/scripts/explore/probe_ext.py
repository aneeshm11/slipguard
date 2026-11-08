import json, sys, os
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
import qwenproto as qp
qp.MODELS['gpt-oss-20b'] = {'dir': qp.MD + 'gpt-oss-20b', 'fmt': 'harmony', 'model_type': 'gpt_oss'}
qp.MODELS['devstral-24b'] = {'dir': qp.MD + 'Devstral-Small-2-24B-Instruct-2512', 'fmt': 'mistral', 'model_type': 'mistral3'}
import fmt_ext as fe
import arms_v2 as A2
recs, H = A2.load_p_corpus(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/test_S1/manifest.json'))
rec = recs[0]; meta, (msgs, tools) = A2.context_from_record(rec, H)
ids = fe.harmony_render_ids(msgs, tools)
txt = fe.harmony_decode(ids)
print('HARMONY n_ids', len(ids)); print(txt[:900]); print('.....'); print(txt[-1500:])
p = meta['prior'][-1]; a = msgs[p['ai']]['tool_calls'][0]['function']['arguments']
print('history call present:', fe.harmony_history_call('edit_file', a) in txt)
print('re-encode equal:', fe.harmony_encode(txt) == ids)
try:
    mids = fe.mistral_render_ids(msgs, tools, 'devstral-24b')
    mt = fe.mistral_decode(mids, 'devstral-24b')
    print('MISTRAL n_ids', len(mids)); print(mt[:600]); print('.....'); print(mt[-1200:])
    print('mistral history call present:', fe.mistral_history_call('edit_file', a) in mt)
except Exception as e:
    import traceback; traceback.print_exc()
