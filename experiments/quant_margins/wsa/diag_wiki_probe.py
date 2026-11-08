"""Diagnostic (F, 2026-11-05 19:28-19:31): per-token prompt_logprobs (top-1 vs actual) for one wikitext-2 test window on a live
endpoint at :8304. usage: diag_wiki_probe.py <window> <served_name> [chat]. Console output transcribed to out/wiki_probe_diag.json."""
import sys, os, json, httpx, numpy as np
H=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa'); sys.path.insert(0,H)
import pnc_render as R, pyarrow.parquet as pq
txt = pq.read_table(os.path.join(H,'data','generic','wikitext','wikitext-2-raw-v1','test-00000-of-00001.parquet')).column('text').to_pylist()
ids = R.encode(''.join(txt)); tok = R._tok() if hasattr(R,'_tok') else None
from transformers import AutoTokenizer
tk = AutoTokenizer.from_pretrained(R.TOK_DIR)
w=int(sys.argv[1]); model=sys.argv[2]
body = ids[w*1023:(w+1)*1023]; HEAD=[2]+(R.encode('<|turn>user\nContinue this Wikipedia article.<turn|>\n<|turn>model\n') if len(sys.argv)>3 else []); win=HEAD+body
j = httpx.post('http://127.0.0.1:8304/v1/completions', json={'model':model,'prompt':win,'max_tokens':1,'temperature':0,'prompt_logprobs':1}, timeout=600).json()
pl = j['choices'][0]['prompt_logprobs']
lp=[]; rows=[]
for k in range(len(HEAD),len(win)):
    d=pl[k]; v=d[str(win[k])]; lp.append(v['logprob'])
    top=max(d.items(), key=lambda kv: kv[1]['logprob'])
    rows.append((k, tk.decode([win[k]]), v['logprob'], tk.decode([int(top[0])]), top[1]['logprob']))
lp=np.array(lp); print('mean NLL', -lp.mean(), 'median', -np.median(lp), 'frac < -10', (lp<-10).mean())
print(repr(tk.decode(body[:120])))
for r in rows[:60]: print(r)
print('...')
for r in rows[500:540]: print(r)
