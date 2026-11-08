"""vLLM LoRA smoke test over the W4A16 -ct base: zero adapter must reproduce the base log-probs; random adapter must change them."""
import os  # added by the repo export (paths are env/config driven)
import json, sys, httpx
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa'))
import pnc_render as R
B = sys.argv[1]
its = [json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa/data/core_items.jsonl'))]; its = [i for i in its if i['kind'] == 'valid'][:3]
out = []
for it in its:
    t = None
    for l in open(f"{R.PNC}/episodes/{it['episode_id']}.jsonl"):
        d = json.loads(l)
        if d.get('record_type') == 'turn' and d['turn_index'] == it['turn_index']: t = d; break
    pids = R.encode(R.render(t['request']['messages'], it['schema'])); cids = R.encode(t['raw_completion'])
    p = [x for x in it['positions'] if x['kind'] == 'close'][0]
    ids = pids + cids[:p['pos']]
    row = {}
    for m in ('gemma-4-31b', 'smoke_zero', 'smoke_rand'):
        j = httpx.post(B + '/completions', json={'model': m, 'prompt': ids, 'max_tokens': 1, 'temperature': 0, 'logprobs': 5,
                                                  'return_tokens_as_token_ids': True}, timeout=600).json()
        row[m] = j['choices'][0]['logprobs']['top_logprobs'][0] if 'choices' in j else j
    out.append(row)
    print(json.dumps(row)[:900], flush=True)
same = all(r['gemma-4-31b'] == r['smoke_zero'] for r in out); diff = any(r['gemma-4-31b'] != r['smoke_rand'] for r in out)
print('ZERO_ADAPTER_IDENTICAL', same, 'RAND_ADAPTER_CHANGES', diff)
