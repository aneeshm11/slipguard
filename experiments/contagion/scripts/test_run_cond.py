"""CPU render test of scripts/run_cond.py on the 300 gate contexts (no server): ON is byte-identical to the default
render; OFF differs from ON only by the system '<|think|>\\n' (and, for P5 where the template restarts the model turn,
the template's own closed thought); S = OFF + the closed thought at the very end (token ids 100 45518 107 101 as the last
four prompt tokens); H has no rendered thought in the history and keeps '<|think|>'.
usage: test_run_cond.py <out.json>"""
import json, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import variants as V, run_cond as RC
from transformers import AutoTokenizer
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
meta = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
ids = [x.strip() for x in open(f'{D}/data/ids_gate300.txt') if x.strip()]
PRE = RC.PRE; c = collections.Counter(); ex = {}
arms = {'OFF': [('P0', 0), ('P1', 1), ('P5', 1), ('P6', 1), ('P8a', 1)], 'S': [('P0', 0), ('P1', 1), ('P6', 1), ('P8a', 1)], 'H': [('P0', 0), ('P1', 1)]}
for cid in ids:
    m = meta[cid]; ctx = V.load_context(m)
    base = {}
    for pw, k in arms['OFF']:
        RC.install('ON'); p0, _ = V.build_prompt(tok, m, pw, k, ctx=ctx); base[pw] = p0
        RC.install('ON'); pon, _ = V.build_prompt(tok, m, pw, k, ctx=ctx)
        c['ON_identical'] += (pon == p0)
        RC.install('OFF'); poff, _ = V.build_prompt(tok, m, pw, k, ctx=ctx)
        diff_ok = (poff == p0.replace('<|turn>system\n<|think|>\n', '<|turn>system\n', 1)) or \
                  (pw == 'P5' and poff == p0.replace('<|turn>system\n<|think|>\n', '<|turn>system\n', 1) + PRE)
        c[f'OFF_only_think_token:{pw}'] += diff_ok
        c[f'OFF_template_closed:{pw}'] += poff.endswith('<|turn>model\n' + PRE)
        if (pw, k) in arms['S']:
            RC.install('S'); ps, _ = V.build_prompt(tok, m, pw, k, ctx=ctx)
            ok = ps == poff + PRE and tok(ps, add_special_tokens=False)['input_ids'][-4:] == [100, 45518, 107, 101] and ps.count(PRE) == 1 + poff.count(PRE)
            c[f'S_ok:{pw}'] += ok
            if pw == 'P1' and 'S' not in ex: ex['S'] = ps[-160:]
        if (pw, k) in arms['H']:
            RC.install('H'); ph, _ = V.build_prompt(tok, m, pw, k, ctx=ctx)
            c[f'H_no_history_thought:{pw}'] += ('<|channel>thought' not in ph and '<|think|>' in ph)
            c[f'ON_history_has_thought:{pw}'] += ('<|channel>thought' in p0)
            if pw == 'P1' and 'H' not in ex: ex['H_len_vs_ON_tokens'] = [len(tok(ph, add_special_tokens=False)['input_ids']), len(tok(p0, add_special_tokens=False)['input_ids'])]
RC.install('ON')
res = {'contexts': len(ids), 'counts': dict(sorted(c.items())), 'examples': ex}
json.dump(res, open(sys.argv[1], 'w'), indent=1); print(json.dumps(res, indent=1))
