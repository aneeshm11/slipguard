"""Synthetic S1 test set: A's first N gate contexts re-keyed to edit_file(file_path, old_string, new_string)."""
import os  # added by the repo export (paths are env/config driven)
import json, sys
sys.path.insert(0, 'scripts'); sys.path.insert(0, 'scripts/explore')
import arms as AR
from rekey_s1 import rekey
META = AR.load_meta(); N = int(sys.argv[1]); out = open(sys.argv[2], 'w')
ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()][:N]
for cid in ids:
    m = META[cid]; msgs, tools = AR.load_context(m); m1, t1 = rekey(msgs, tools)
    out.write(json.dumps({'id': 'S1test:' + cid, 'messages': m1, 'tools': t1, 'temperature': m['temp'], 'top_p': m['top_p'], 'cluster': m['task']}) + '\n')
