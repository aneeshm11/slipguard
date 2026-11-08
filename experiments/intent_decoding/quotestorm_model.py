"""Intent recovery on SYNTHETIC slips with known ground truth (QuoteStorm payloads, data/quotestorm_slips.jsonl).
Context ('copy'): official system prompt + official tools + a user message that shows the exact edit;
('compact'): one-line system prompt + edit_file declaration only (short, allows a full-teacher-forcing check);
('blind'): official prompt, user message names only the file (intent not inferable from the context).
For every slipped call:
  (ii) exact windowed cached teacher forcing (WCTF) log-likelihood of every repair candidate (+ closers for the prior)
  (i)  exact local log-likelihood of every cut at the first slip site (the deployed cut rule's inputs)
  --ftf: also FULL teacher forcing via prompt_logprobs when context+candidate <= 1024 tokens (PI cap), E4B only.
Decisions (argmax / tau / prior / cut rule) are computed offline by analyze_quotestorm.py.
"""
import argparse, asyncio, json, os, sys, random, math, time
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import D, TC_START, TC_END, schema_from_tools, first_slip_site, repair_candidates, is_valid
from intent_decode import (Server, wctf_scores, cut_scores, closer_at, ids_of, MAX_PROMPT_LOGPROBS_TOKENS)

ap = argparse.ArgumentParser()
ap.add_argument('--base', default='http://127.0.0.1:8311/v1')
ap.add_argument('--model', default='gemma-4-e4b')
ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-e4b-it-qat-w4a16-ct'))
ap.add_argument('--out', required=True)
ap.add_argument('--ctx', default='copy', choices=['copy', 'blind', 'compact'])
ap.add_argument('--ftf', action='store_true', help='also FULL teacher forcing via prompt_logprobs when total <= 1024')
ap.add_argument('--orders', default='new_first')
ap.add_argument('--kinds', default='key,end')
ap.add_argument('--n', type=int, default=100000)
ap.add_argument('--conc', type=int, default=16)
ap.add_argument('--seed', type=int, default=0)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tok)
TOOLS = json.load(open(os.path.join(HERE, 'data/tools_official.json')))
S = schema_from_tools(TOOLS)
SYSTEM = json.loads(open(os.path.join(HERE, 'data/replay_first_edit.jsonl')).readline())['messages'][0]
USER_COPY = ('Apply exactly this change to the file {fp} with a single edit_file call.\n'
             'Replace this text (everything between the marker lines; the marker lines themselves are not part of it):\n'
             '-----BEGIN OLD-----\n{old}\n-----END OLD-----\n'
             'with this text:\n'
             '-----BEGIN NEW-----\n{new}\n-----END NEW-----\n'
             'Copy both blocks character for character.')
USER_BLIND = 'Make the required change to the file {fp} with a single edit_file call.'
COMPACT_SYSTEM = {'role': 'system', 'content': 'You are a coding agent. Use the edit_file tool to change files.'}
EDIT_TOOL = [t for t in TOOLS if t['function']['name'] == 'edit_file']
FTF_SEM = asyncio.Semaphore(2)   # at most 2 short prompt_logprobs requests in flight


def ctx_prompt(s):
    if a.ctx == 'compact':
        u = USER_COPY.format(fp=s['filepath'], old=s['old'], new=s['new'])
        p = tok.apply_chat_template([COMPACT_SYSTEM, {'role': 'user', 'content': u}], tools=EDIT_TOOL,
                                    add_generation_prompt=True, tokenize=False, enable_thinking=False)
        return p + TC_START
    u = (USER_COPY if a.ctx == 'copy' else USER_BLIND).format(fp=s['filepath'], old=s['old'], new=s['new'])
    p = tok.apply_chat_template([SYSTEM, {'role': 'user', 'content': u}], tools=TOOLS, add_generation_prompt=True,
                                tokenize=False, enable_thinking=False)
    return p + TC_START


async def full_tf(srv, ctx_ids, cand_ids):
    """full teacher-forced LL of the candidate (all call tokens) - only for total <= 1024 tokens."""
    ids = list(ctx_ids) + list(cand_ids)
    if len(ids) > MAX_PROMPT_LOGPROBS_TOKENS:
        raise ValueError('too long for prompt_logprobs')
    async with FTF_SEM:
        c = await srv.complete(ids, max_tokens=1, temperature=0.0, prompt_logprobs=0, tag='ftf')
    pl = c['prompt_logprobs']
    tot = 0.0
    for pos in range(len(ctx_ids), len(ids)):
        ent = pl[pos]
        v = ent.get(str(ids[pos])) if ent else None
        if v is None:
            raise RuntimeError('missing prompt logprob entry')
        tot += v['logprob']
    return tot


async def one(srv, s, fo, lock):
    rec = {'qid': s['qid'], 'grp': s['grp'], 'order': s['order'], 'kind': s['kind'], 'closer': s['closer'],
           'ctx': a.ctx, 'model': a.model}
    try:
        cands = repair_candidates(s['slipped'], S, finished=True)
        texts = [c.text('edit_file') for c in cands]
        rec['ncands'] = len(texts)
        rec['gt_idx'] = texts.index(s['gt']) if s['gt'] in texts else -1
        rec['cand_closers'] = [[cl for _, _, cl in c.cuts] for c in cands]
        cp = ctx_prompt(s)
        ctx_ids = ids_of(tok, cp)
        cand_ids = [ids_of(tok, t + TC_END) for t in texts]
        rec['ctx_tokens'] = len(ctx_ids)
        if len(texts) > 1:
            lls, winfo = await wctf_scores(srv, ctx_ids, cand_ids, K=12)
        else:
            lls, winfo = [0.0], {'requests': 0}
        rec['lls'] = lls
        rec['wctf'] = {k: v for k, v in winfo.items() if k != 'per_token'}
        if a.ftf and len(texts) > 1 and len(ctx_ids) + max(len(x) for x in cand_ids) <= MAX_PROMPT_LOGPROBS_TOKENS:
            rec['ftf'] = [await full_tf(srv, ctx_ids, x) for x in cand_ids]
        site = first_slip_site(s['slipped'], S, finished=True)
        if site is not None:
            cps, clls, cinfo = await cut_scores(srv, tok, ctx_ids, s['slipped'], site, S['edit_file'])
            gtv = {'new_string': s['new'], 'old_string': s['old'], 'filepath': s['filepath']}.get(site.key)
            vals = [s['slipped'][site.content_start:x] for x in cps]
            rec['cut'] = {'site_key': site.key, 'run': site.run, 'gap': site.gap, 'lls': clls,
                          'closers': [closer_at(site, k) for k in range(len(cps))],
                          'gt_k': vals.index(gtv) if gtv in vals else -1, 'requests': cinfo.get('requests', 0)}
        rec['status'] = 'ok'
    except Exception as e:
        rec['status'] = 'error'; rec['err'] = repr(e)[:300]
    async with lock:
        fo.write(json.dumps(rec) + '\n'); fo.flush()


async def main():
    orders = set(a.orders.split(',')); kinds = set(a.kinds.split(','))
    slips = [json.loads(l) for l in open(os.path.join(HERE, 'data/quotestorm_slips.jsonl'))]
    slips = [s for s in slips if s['order'] in orders and s['kind'] in kinds and s['cands']]
    random.Random(a.seed).shuffle(slips)
    slips = slips[:a.n]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            d = json.loads(l)
            if d.get('status') == 'ok':
                done.add((d['qid'], d['order'], d['kind']))
    slips = [s for s in slips if (s['qid'], s['order'], s['kind']) not in done]
    print(len(slips), 'slips to score', flush=True)
    srv = Server(a.base, a.model, conc=a.conc)
    lock = asyncio.Lock()
    q = asyncio.Queue()
    for s in slips:
        q.put_nowait(s)
    t0 = time.time()
    with open(a.out, 'a') as fo:
        async def worker():
            while True:
                try:
                    s = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(srv, s, fo, lock)
        await asyncio.gather(*[worker() for _ in range(max(1, a.conc // 4))])
    print('done %.0fs' % (time.time() - t0), dict(srv.stats), flush=True)
    await srv.close()

asyncio.run(main())
