"""Check that vLLM + LoRA (over the W4A16 base) reproduces the EXACT offline predictions of the repair at held-out string
ends: compares log P(<|"|>) and the top-20 sets for base and edited models.
usage: lora_validate.py --base http://127.0.0.1:8304/v1 --model gemma-4-31b --adapter repairA --pred adapters/repairA/offline_predictions.json"""
import argparse, json, os, sys, httpx
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import pnc_render as R
ap = argparse.ArgumentParser(); ap.add_argument('--base', required=True); ap.add_argument('--model', required=True)
ap.add_argument('--adapter', required=True); ap.add_argument('--pred', required=True); ap.add_argument('--out', default='')
a = ap.parse_args()
P = json.load(open(a.pred)); rows = []
cache = {}
for p in P:
    k = (p['episode_id'], p['turn_index'])
    if k not in cache:
        it = next(json.loads(l) for l in open(os.path.join(H, 'data', 'core_items.jsonl')) if json.loads(l)['episode_id'] == k[0] and json.loads(l)['turn_index'] == k[1])
        t = next(json.loads(l) for l in open(os.path.join(R.PNC, 'episodes', k[0] + '.jsonl')) if '"turn_index": %d,' % k[1] in l and '"record_type": "turn"' in l)
        cache[k] = (R.encode(R.render(t['request']['messages'], it['schema'])), R.encode(t['raw_completion']))
    pids, cids = cache[k]
    ids = pids + cids[:p['pos']]
    m = a.adapter if p['edited'] else a.model
    j = httpx.post(a.base + '/completions', json={'model': m, 'prompt': ids, 'max_tokens': 1, 'temperature': 0, 'logprobs': 20,
                                                   'return_tokens_as_token_ids': True}, timeout=600).json()
    top = {int(t.split(':')[1]): v for t, v in j['choices'][0]['logprobs']['top_logprobs'][0].items()}
    off = {t: v for t, v in p['top']}
    rows.append({'edited': p['edited'], 'lp_DQ_offline': p['lp_DQ'], 'lp_DQ_vllm': top.get(52),
                 'top20_overlap': len(set(top) & set(off)) / 20, 'top1_same': max(top, key=top.get) == max(off, key=off.get),
                 'mean_abs_dlp_common_top10': float(np.mean([abs(top[t] - off[t]) for t in sorted(off, key=off.get, reverse=True)[:10] if t in top]))})
import numpy as np
summ = {}
for e in (False, True):
    rr = [r for r in rows if r['edited'] == e and r['lp_DQ_vllm'] is not None]
    d = np.array([r['lp_DQ_vllm'] - r['lp_DQ_offline'] for r in rr])
    summ['edited' if e else 'base'] = {'n': len(rr), 'median_abs_dlpDQ': float(np.median(np.abs(d))), 'p95_abs_dlpDQ': float(np.percentile(np.abs(d), 95)),
                                       'top20_overlap_mean': float(np.mean([r['top20_overlap'] for r in rr])),
                                       'top1_agree': float(np.mean([r['top1_same'] for r in rr])),
                                       'mean_abs_dlp_top10': float(np.nanmean([r['mean_abs_dlp_common_top10'] for r in rr]))}
print(json.dumps(summ, indent=1))
if a.out:
    json.dump({'summary': summ, 'rows': rows}, open(a.out, 'w'), indent=1)
