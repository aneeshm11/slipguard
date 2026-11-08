"""Self-slip test in REAL agent contexts (known intent): take the model's own strictly-valid edit calls from a replay
output, inject a look-alike closer slip (closer drawn from the empirical base-31B distribution) at the end of the first
content argument ('key' slip, followed by the next argument) or of the last argument ('end' slip), then score with the
same model in the same context (+ its own thought), exactly as deployed:
  (ii) WCTF log-likelihood of every repair candidate (+ closers for the prior),
  (i)  local log-likelihood of every cut at the first slip site.
Decisions are computed offline (analyze_quotestorm.py syn ...).
"""
import argparse, asyncio, json, os, sys, random, math, time, collections
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import (D, TC_START, TC_END, schema_from_tools, first_slip_site, repair_candidates, parse_strict,
                            render_call, is_valid, fmt_value)
from intent_decode import Server, wctf_scores, cut_scores, closer_at, ids_of
from replay_utils import fix_msgs

ap = argparse.ArgumentParser()
ap.add_argument('--replay', required=True)
ap.add_argument('--contexts', default=os.path.join(HERE, 'data/replay_first_edit.jsonl'))
ap.add_argument('--base', required=True)
ap.add_argument('--model', required=True)
ap.add_argument('--tok', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--n', type=int, default=300)
ap.add_argument('--conc', type=int, default=12)
ap.add_argument('--seed', type=int, default=0)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tok)
rng = random.Random(a.seed)


def closer_dist():
    c = collections.Counter()
    for l in open(os.path.join(HERE, 'data/log_slips.jsonl')):
        r = json.loads(l)
        if r['tool'] == 'edit_file' and 'gemma-4-31b' in r['model']:
            c[r['closer_run']] += 1
    tot = sum(c.values())
    return [(k, v / tot) for k, v in c.most_common()]


DIST = closer_dist()


def sample_closer():
    x = rng.random(); acc = 0
    for k, p in DIST:
        acc += p
        if x <= acc:
            return k
    return '`'


async def one(srv, item, fo, lock):
    c, r, kind, L = item
    schema = schema_from_tools(c['tools'])
    sp = parse_strict(r['call'])
    pairs = [(p.key, p.value, p.kind) for p in sp.pairs]
    gt = render_call('edit_file', pairs)
    strs = [i for i, p in enumerate(pairs) if p[2] == 'str' and p[0] != 'filepath']
    if not strs:
        return
    if kind == 'key':
        j = strs[0]
        if j == len(pairs) - 1:
            return
    else:
        j = len(pairs) - 1
        if pairs[j][2] != 'str':
            return
    body = ','.join(f'{k}:{D}{v}{L if i == j else D}' if kd == 'str' else f'{k}:{fmt_value(v, kd)}'
                    for i, (k, v, kd) in enumerate(pairs))
    slipped = 'call:edit_file{' + body + '}'
    rec = {'id': r['id'], 'seed': r['seed'], 'sample': r.get('sample', 0), 'kind': kind, 'closer': L, 'model': a.model,
           'think': r['think'], 'grp': 'real', 'order': 'new_first' if [p[0] for p in pairs].index('new_string') <
           [p[0] for p in pairs].index('old_string') else 'old_first'}
    if is_valid(slipped, schema):
        rec['status'] = 'still_valid'
    else:
        try:
            cands = repair_candidates(slipped, schema, finished=True)
            texts = [x.text('edit_file') for x in cands]
            rec['ncands'] = len(texts); rec['gt_idx'] = texts.index(gt) if gt in texts else -1
            rec['cand_closers'] = [[cl for _, _, cl in x.cuts] for x in cands]
            p0 = tok.apply_chat_template(fix_msgs(c['messages']), tools=c['tools'], add_generation_prompt=True,
                                         tokenize=False, enable_thinking=bool(r['think']))
            prefix_ids = ids_of(tok, p0 + (r.get('A_text') or '') + TC_START)
            rec['ctx_tokens'] = len(prefix_ids)
            if len(texts) > 1:
                lls, winfo = await wctf_scores(srv, prefix_ids, [ids_of(tok, t + TC_END) for t in texts], K=12)
            else:
                lls, winfo = [0.0], {'requests': 0}
            rec['lls'] = lls
            rec['wctf'] = {k: v for k, v in winfo.items() if k != 'per_token'}
            site = first_slip_site(slipped, schema, finished=True)
            if site is not None:
                cps, clls, cinfo = await cut_scores(srv, tok, prefix_ids, slipped, site, schema['edit_file'])
                gv = dict((k, v) for k, v, _ in pairs).get(site.key)
                vals = [slipped[site.content_start:x] for x in cps]
                rec['cut'] = {'site_key': site.key, 'run': site.run, 'gap': site.gap, 'lls': clls,
                              'closers': [closer_at(site, k) for k in range(len(cps))],
                              'gt_k': vals.index(gv) if gv in vals else -1, 'requests': cinfo.get('requests', 0)}
            rec['status'] = 'ok'
        except Exception as e:
            rec['status'] = 'error'; rec['err'] = repr(e)[:300]
    async with lock:
        fo.write(json.dumps(rec) + '\n'); fo.flush()


async def main():
    recs = [json.loads(l) for l in open(a.replay)]
    recs = [r for r in recs if r.get('status') == 'call' and r.get('tool') == 'edit_file' and r['base']['strict_valid']
            and 'A_text' in r]
    rng.shuffle(recs)
    recs = recs[:a.n]
    need = {r['id'] for r in recs}
    ctx = {}
    with open(a.contexts) as f:
        for l in f:
            d = json.loads(l)
            if d['id'] in need:
                ctx[d['id']] = d
    items = [(ctx[r['id']], r, 'key' if rng.random() < 0.7 else 'end', sample_closer()) for r in recs]
    srv = Server(a.base, a.model, conc=a.conc)
    lock = asyncio.Lock()
    q = asyncio.Queue()
    for it in items:
        q.put_nowait(it)
    t0 = time.time()
    with open(a.out, 'a') as fo:
        async def worker():
            while True:
                try:
                    it = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(srv, it, fo, lock)
        await asyncio.gather(*[worker() for _ in range(max(1, a.conc // 4))])
    print('done %.0fs' % (time.time() - t0), dict(srv.stats), flush=True)
    await srv.close()

asyncio.run(main())
