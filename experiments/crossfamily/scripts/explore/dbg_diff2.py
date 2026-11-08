import os  # added by the repo export (paths are env/config driven)
import json, sys, collections
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/scripts'))
import arms as AR
META = AR.load_meta()
ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()]
c = collections.Counter(); bad = []
for cid in ids:
    meta = META[cid]; msgs, tools = AR.load_context(meta)
    vm, info = AR.native_variant(msgs, meta['prior'], tools, 'xml', 'qwen3.5-9b')
    c[(info.get('p1n_outcome'), info.get('diff_patch'))] += 1
    if info.get('diff_patch') not in ('patched_plus', 'patched_context', 'patched_nextline') and len(bad) < 3:
        bad.append((cid, info.get('diff_patch')))
print(c.most_common())
print(bad)
