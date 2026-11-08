import json, sys, os
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
import arms as AR, qwenproto as qp
META = AR.load_meta()
ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()][:6]
for cid in ids:
    meta = META[cid]; msgs, tools = AR.load_context(meta); p = meta['prior'][-1]
    args = json.loads(msgs[p['ai']]['tool_calls'][0]['function']['arguments'])
    resp = json.loads(msgs[p['ti']]['content'])
    vm, info = AR.native_variant(msgs, meta['prior'], tools, 'xml', 'qwen3.5-9b')
    print('====', cid, info.get('diff_patch'), 'strategy', resp.get('strategy'))
    print('NEW last lines:', repr(args['new_string'][-200:]))
    print('DIFF:', resp.get('diff', '')[-700:])
