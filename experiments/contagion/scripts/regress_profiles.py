"""Regression for the tool-profile refactor (main_track profile must be byte-identical):
(1) re-judge every stored generation and compare with the stored judge dict;
(2) re-render a broad prompt set with the new variants.py vs variants_v2_backup.py (pre-refactor)."""
import os  # added by the repo export (paths are env/config driven)
import json, sys, glob, importlib.util, random
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/scripts'))
import gemma_protocol as gp
import variants as VN
from transformers import AutoTokenizer
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
n = bad = 0; ex = []
for f in sorted(glob.glob(f'{D}/out/main/*.jsonl')) + sorted(glob.glob(f'{D}/out/pilot/*.jsonl')):
    for l in open(f):
        d = json.loads(l)
        if d.get('error') or not d.get('judge') or d['judge'].get('decision_point') or d.get('s2_text') is None: continue
        j2 = gp.judge(d['s2_text'], d.get('s2_finish') != 'length' and (d.get('s2_stop') == 49 or d.get('s2_finish') in ('stop', 'decision_stop') or True))
        j1 = d['judge']
        n += 1
        if j1 != j2:
            # stopped_on_close is not stored explicitly; retry with False before calling it a mismatch
            j3 = gp.judge(d['s2_text'], False)
            if j1 != j3:
                bad += 1
                if len(ex) < 3: ex.append((f.split('/')[-1], d['id'], d['pathway'], j1.get('why'), j2.get('why')))
print('re-judged', n, 'mismatches', bad, ex)
spec = importlib.util.spec_from_file_location('variants_old', f'{D}/scripts/variants_v2_backup.py'); VO = importlib.util.module_from_spec(spec); spec.loader.exec_module(VO)
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
meta = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
order = json.load(open(f'{D}/data/order_main.json')); k4 = [x.strip() for x in open(f'{D}/data/ids_dose_k4.txt')]
random.seed(3); ids = random.sample(order[:600], 20) + k4[:6]
t = mm = 0
for cid in ids:
    m = meta[cid]; ctx = VN.load_context(m)
    for pw in ('P0', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P9', 'R2', 'R4', 'L2', 'P4P', 'P8a', 'P8b'):
        for k in ((0,) if pw == 'P0' else (1, 2, 4) if pw in ('P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7') else (1,)):
            if k > m['k_usable'] or (pw == 'L2' and m['k_usable'] < 2): continue
            a, _ = VO.build_prompt(tok, m, pw, k, ctx=ctx); b, _ = VN.build_prompt(tok, m, pw, k, ctx=ctx)
            t += 1; mm += (a != b)
a2 = [json.loads(l) for l in open(f'{D}/data/a2_meta.jsonl')][:15]
for m in a2:
    ctx = VN.load_context(m)
    for pw, k in (('P0', 0), ('P5', 1), ('Q8b', 0)):
        a, _ = VO.build_prompt(tok, m, pw, k, ctx=ctx); b, _ = VN.build_prompt(tok, m, pw, k, ctx=ctx); t += 1; mm += (a != b)
print('re-rendered', t, 'prompts; mismatches', mm)
