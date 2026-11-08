"""Controlled latency/cost benchmark (run when the lane is otherwise quiet; concurrency 1, sequential):
for real slipped first-edit calls from a replay output, time
  t_call : regenerating the whole call from the same prefix (what one baseline call costs; also = retry cost)
  t_i    : algorithm (i) rollback/resume (noisy-channel cut + resume) on the logged slipped call
  t_ii   : algorithm (ii) WCTF likelihood repair of the logged slipped call
Output: out/bench_latency_<name>.json
"""
import argparse, asyncio, json, os, sys, time, statistics
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import TC_START, TC_END, schema_from_tools
from intent_decode import Server, rollback_resume, lik_repair, ChannelPrior, ids_of
from replay_utils import fix_msgs

ap = argparse.ArgumentParser()
ap.add_argument('--replay', required=True)
ap.add_argument('--contexts', default=os.path.join(HERE, 'data/replay_first_edit.jsonl'))
ap.add_argument('--base', required=True)
ap.add_argument('--model', required=True)
ap.add_argument('--tok', required=True)
ap.add_argument('--n', type=int, default=30)
ap.add_argument('--out', required=True)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tok)
PRIOR = ChannelPrior.from_log_slips('ft_edit')


async def main():
    recs = [json.loads(l) for l in open(a.replay)]
    recs = [r for r in recs if r.get('status') == 'call' and r.get('site') and r.get('finished')][:a.n]
    need = {r['id'] for r in recs}
    ctx = {}
    for l in open(a.contexts):
        d = json.loads(l)
        if d['id'] in need:
            ctx[d['id']] = d
    srv = Server(a.base, a.model, conc=4)
    rows = []
    for r in recs:
        c = ctx[r['id']]
        schema = schema_from_tools(c['tools'])
        p0 = tok.apply_chat_template(fix_msgs(c['messages']), tools=c['tools'], add_generation_prompt=True,
                                     tokenize=False, enable_thinking=bool(r['think']))
        prefix = p0 + (r.get('A_text') or '') + TC_START
        pid = ids_of(tok, prefix)
        H = 'call:edit_file{' if r.get('forced') else ''
        # warm the prefix cache once (a real client has it warm right after generating the call)
        await srv.complete(pid, max_tokens=1, temperature=0.0)
        t0 = time.time()
        g = await srv.complete(pid + ids_of(tok, H), max_tokens=2048, stop=[TC_END], temperature=0.2, seed=11)
        t_call = time.time() - t0
        t0 = time.time()
        ri = await rollback_resume(srv, tok, prefix, r['call'], True, schema, rule='nc', prior=PRIOR, prefix_ids=pid)
        t_i = time.time() - t0
        t0 = time.time()
        rii = await lik_repair(srv, tok, prefix, r['call'], True, schema, tau=0.0, prior=PRIOR, prefix_ids=pid)
        t_ii = time.time() - t0
        rows.append({'id': r['id'], 'call_tokens': len(ids_of(tok, r['call'])), 'regen_tokens': g['_usage'].get('completion_tokens'),
                     't_call': t_call, 't_i': t_i, 't_ii': t_ii, 'i_valid': ri['valid'],
                     'i_resume_tokens': sum(x['gen_tokens'] for x in ri['rounds']),
                     'i_score_requests': sum(x['cut_choice'].get('requests', 0) for x in ri['rounds']),
                     'ii_requests': (rii.get('wctf') or {}).get('requests', 0), 'ii_decision': rii['decision']})
        print(json.dumps(rows[-1]), flush=True)
    def q(k):
        v = sorted(x[k] for x in rows)
        return {'median': statistics.median(v), 'p90': v[int(0.9 * (len(v) - 1))], 'mean': statistics.mean(v)} if v else None
    out = {'n': len(rows), 't_call': q('t_call'), 't_i': q('t_i'), 't_ii': q('t_ii'), 'call_tokens': q('call_tokens'),
           'i_resume_tokens': q('i_resume_tokens'), 'i_score_requests': q('i_score_requests'), 'ii_requests': q('ii_requests'),
           'ratio_t_i_over_t_call_median': statistics.median([x['t_i'] / max(x['t_call'], 1e-6) for x in rows]) if rows else None,
           'rows': rows, 'note': 'sequential, concurrency 1; other jobs on the server at the time are listed in progress.md'}
    json.dump(out, open(a.out, 'w'), indent=1)
    print({k: v for k, v in out.items() if k != 'rows'})
    await srv.close()

asyncio.run(main())
