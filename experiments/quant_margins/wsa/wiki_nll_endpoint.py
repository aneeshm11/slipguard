"""General-text cross-check (descriptive, endpoint-based): next-token NLL on the 48 BOS-correct wikitext-2 TEST windows
(1,024 tokens each; same windows as hf_extract.py --wikitext_only) via vLLM prompt_logprobs=0 on a DEDICATED server
(1k-token prompts only; transient logits ~1 GB). Reports mean NLL over all predicted positions and per window.
usage: wiki_nll_endpoint.py --base http://127.0.0.1:8304/v1 --model NAME --out out/wiki_nll_<name>.json"""
import argparse, json, os, sys, math
import httpx, numpy as np
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import pnc_render as R
import pyarrow.parquet as pq
ap = argparse.ArgumentParser(); ap.add_argument('--base', required=True); ap.add_argument('--model', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--chat_wrap', action='store_true', help='present each window as the MODEL turn of a chat (instruction-tuned models)')
a = ap.parse_args()
txt = pq.read_table(os.path.join(H, 'data', 'generic', 'wikitext', 'wikitext-2-raw-v1', 'test-00000-of-00001.parquet')).column('text').to_pylist()
ids = R.encode(''.join(txt))
per = []
for w in range(48):
    body_ids = ids[w * 1023: (w + 1) * 1023]
    head = [2] + (R.encode('<|turn>user\nContinue this Wikipedia article.<turn|>\n<|turn>model\n') if a.chat_wrap else [])
    win = head + body_ids
    j = httpx.post(a.base + '/completions', json={'model': a.model, 'prompt': win, 'max_tokens': 1, 'temperature': 0, 'prompt_logprobs': 0}, timeout=600).json()
    pl = j['choices'][0]['prompt_logprobs']
    lps = []
    for k in range(len(head), len(win)):
        d = pl[k]
        v = d.get(str(win[k])) if d else None
        lps.append(v['logprob'] if isinstance(v, dict) else v)
    lps = [x for x in lps if x is not None]
    per.append(-float(np.mean(lps)))
res = {'model': a.model, 'chat_wrap': a.chat_wrap, 'n_windows': 48, 'tokens_per_window': 1023, 'mean_nll': float(np.mean(per)), 'per_window_nll': per,
       'note': 'endpoint prompt_logprobs (vLLM 0.19.1), dedicated server; descriptive general-text cross-check'}
json.dump(res, open(a.out, 'w'), indent=1)
print(a.model, 'wikitext-2 test mean NLL', round(res['mean_nll'], 4))
