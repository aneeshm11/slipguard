import json, sys, os, copy
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
import qwenproto as qp
qp.MODELS['devstral-24b'] = {'dir': qp.MD + 'Devstral-Small-2-24B-Instruct-2512', 'fmt': 'mistral', 'model_type': 'mistral3'}
import fmt_ext as fe
import arms_v2 as A2
recs, H = A2.load_p_corpus(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/test_S1/manifest.json'))
rec = recs[0]; meta, (msgs, tools) = A2.context_from_record(rec, H)
p = meta['prior'][-1]; a = msgs[p['ai']]['tool_calls'][0]['function']['arguments']
m2 = copy.deepcopy(msgs); bad = a[:-40] + '`, "old_string": "x"}'
m2[p['ai']]['tool_calls'][0]['function']['arguments'] = bad
t3 = fe.mistral_decode(fe.mistral_render_ids(m2, tools, 'devstral-24b'), 'devstral-24b')
i = t3.rfind('[TOOL_CALLS]'); print(repr(t3[i:i+200])); print('...', repr(t3[i+len(bad)-150:i+len(bad)+120]))
print('bad tail:', repr(bad[-80:]))
