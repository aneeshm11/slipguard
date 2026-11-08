import os  # added by the repo export (paths are env/config driven)
import json, sys
sys.dont_write_bytecode = True
sys.argv = ["x"]; sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "experiments/intent_decoding"))
import proxy_equivalence as PE
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(PE.MODEL_DIR_JUNE)
n = bad = 0; ex = []
for p in PE._qs_payloads():
    for order in ('new_first', 'old_first'):
        keys = ['filepath', 'new_string', 'old_string'] if order == 'new_first' else ['filepath', 'old_string', 'new_string']
        vals = {'filepath': p['filepath'], 'new_string': p['new'], 'old_string': p['old']}
        G = PE.TC_START + PE.BGP.render_call('edit_file', [(k, vals[k], 'str') for k in keys]) + PE.TC_END
        n += 1
        if tok.decode(tok.encode(G, add_special_tokens=False)) != G:
            bad += 1
            if len(ex) < 3:
                i = next(k for k, (x, y) in enumerate(zip(G, tok.decode(tok.encode(G, add_special_tokens=False)))) if x != y) if True else 0
                ex.append((p['src'], repr(G[max(0, i-30):i+30])))
print('calls', n, 'tokenizer round-trip mismatches', bad); print(ex)
