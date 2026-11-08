"""Addendum (d): combined stack on post-slip (contagion) states. For each of the 37 logged post-slip slip states (PNC; all
out-of-sample for the adapter), the prompt is rendered from (i) the original history and (ii) the history after
slipguard.history quarantine (workstream E's frozen renderer, via the release library); the logged completion prefix up to
the slip position is teacher-forced, and P(look-alike) at the slip position is probed on the gate server for QAT-ct and
QAT-ct + adapter (generation mode, top-20, shipped sampler rebuilt).
usage: stack_d.py --base http://127.0.0.1:8304/v1 --adapter repairA --out out/stack_d.json"""
import argparse, json, os, sys, httpx
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H); sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'slipguard/src'))
import pnc_render as R
from audit import position_metrics
from slipguard.history import quarantine
ap = argparse.ArgumentParser(); ap.add_argument('--base', required=True); ap.add_argument('--adapter', required=True)
ap.add_argument('--model', default='gemma-4-31b'); ap.add_argument('--out', required=True); ap.add_argument('--limit', type=int, default=0)
a = ap.parse_args()
LA = set(R.lookalike_ids())
rows = [json.loads(l) for l in open(os.path.join(H, 'data', 'pnc_points_all.jsonl'))]
post = [r for r in rows if r['kind'] == 'slip' and r['n_prior_bad'] > 0]
if a.limit:
    post = post[:a.limit]
res = []
for r in post:
    turns = [json.loads(l) for l in open(os.path.join(R.PNC, 'episodes', r['episode_id'] + '.jsonl'))]
    t = next(x for x in turns if x.get('record_type') == 'turn' and x['turn_index'] == r['turn_index'])
    raw_by_id = {}
    for x in turns:
        if x.get('record_type') == 'turn' and x['turn_index'] < r['turn_index']:
            for tc in ((x.get('response') or {}).get('message') or {}).get('tool_calls') or []:
                raw_by_id[tc['id']] = x.get('raw_completion') or ''
    msgs = t['request']['messages']; tools = R.tools(r['schema'])
    qmsgs, actions = quarantine(msgs, tools, raw_by_call_id=raw_by_id)
    cids = R.encode(t['raw_completion']); p = next(q for q in r['positions'] if q['kind'] == 'slip')
    row = {'episode_id': r['episode_id'], 'turn_index': r['turn_index'], 'n_quarantine_actions': len(actions)}
    for hist, mm in (('original', msgs), ('quarantine', qmsgs)):
        ids = R.encode(R.render(mm, r['schema'])) + cids[:p['pos']]
        for m in (a.model, a.adapter):
            j = httpx.post(a.base + '/completions', json={'model': m, 'prompt': ids, 'max_tokens': 1, 'temperature': 0, 'logprobs': 20,
                                                          'return_tokens_as_token_ids': True}, timeout=1800).json()
            top = [(int(k.split(':')[1]), v) for k, v in j['choices'][0]['logprobs']['top_logprobs'][0].items()]
            met = position_metrics(top, LA)
            row[f'{hist}|{m}'] = {'pLA_T1': met['pLA_T1'], 'top1_is_la': met['top1'] in LA, 'n_prompt': len(ids)}
    res.append(row); print(json.dumps(row)[:400], flush=True)
summ = {'n_states': len(res), 'mean_quarantine_actions': float(np.mean([r['n_quarantine_actions'] for r in res]))}
for k in (f'original|{a.model}', f'original|{a.adapter}', f'quarantine|{a.model}', f'quarantine|{a.adapter}'):
    summ[k] = {'mean_pLA_T1': float(np.mean([r[k]['pLA_T1'] for r in res])), 'frac_top1_la': float(np.mean([r[k]['top1_is_la'] for r in res]))}
json.dump({'summary': summ, 'rows': res}, open(a.out, 'w'), indent=1)
print(json.dumps(summ, indent=1))
