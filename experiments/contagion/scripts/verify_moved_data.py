"""Check that the moved main-track data are identical for the 300 gate contexts: re-render every thinking-ON gate job
(P0, P1, P5, P6, P8a; the discovery records' own render) through with_paths' locations and compare the prompt token count
with the n_prompt stored in the discovery record; also re-render the OFF jobs already done before the move.
run as: with_paths.py verify_moved_data.py <out.json>"""
import json, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import variants as V, run_cond as RC
from transformers import AutoTokenizer
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
meta = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
ids = set(x.strip() for x in open(f'{D}/data/ids_gate300.txt') if x.strip())
c = collections.Counter(); bad = []
def check(files, cond, tag, arms):
    RC.install(cond); ctxc = {}
    for f in files:
        for l in open(f):
            d = json.loads(l)
            if d.get('error') or d['id'] not in ids or (d['pathway'], d['k']) not in arms or d.get('template', 'old') != 'old': continue
            if tag == 'OFF_done' and d.get('cond') != 'OFF': continue
            if d['id'] not in ctxc: ctxc[d['id']] = V.load_context(meta[d['id']])
            p, _ = V.build_prompt(tok, meta[d['id']], d['pathway'], d['k'], ctx=ctxc[d['id']])
            n = len(tok(p, add_special_tokens=False)['input_ids'])
            ok = n == d['n_prompt']; c[f'{tag}:{"match" if ok else "MISMATCH"}'] += 1
            if not ok and len(bad) < 10: bad.append((tag, d['id'], d['pathway'], n, d['n_prompt']))
    RC.install('ON')
A = {('P0', 0), ('P1', 1), ('P5', 1), ('P6', 1), ('P8a', 1)}
check([f'{D}/out/main/r31b_old_{x}.jsonl' for x in ('A', 'G', 'a', 'b', 'P6', 'A1a')], 'ON', 'ON_discovery', A)
check([f'{D}/out/main/r31b_v21off.part1.jsonl'], 'OFF', 'OFF_done', A)
res = {'counts': dict(c), 'mismatches': bad, 'ROOT': V.ROOT}
json.dump(res, open(sys.argv[1], 'w'), indent=1); print(json.dumps(res))
