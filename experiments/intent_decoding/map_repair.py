"""MAP repairs of LOGGED natural slips (service for workstream A's P0-A2 'P4'-MAP' arm).
input : a file with one context_ref per line ('run/llm_calls_xxx.jsonl:LINE') or a JSONL with a 'context_ref' field
        -- the line of the main-track log whose response contained the slipped edit_file call (C's corpus key).
method: exact logged prefix (June template + logged thought + byte-exact raw call prefix from C's corpus), then
        IPD: noisy-channel cut at the slip site + GREEDY (T=0) resume -> deterministic MAP-style completion of the
        absorbed argument; opener rule enabled.  Only strictly valid repairs are returned as 'repaired_args'.
output: JSONL {context_ref, status, valid, repaired_args{filepath,new_string,old_string[,allow_multiple]},
        canonical_new_first (call text in the template's dict-sorted order), cut_k, closer, rounds}
"""
import argparse, asyncio, json, lzma, os, sys
from transformers import AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import (D, TC_START, schema_from_tools, is_valid, first_slip_site, parse_strict,
                            render_template_order)
from intent_decode import Server, rollback_resume, ChannelPrior, ids_of, Pin
from replay_utils import render_prompt

CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')
CTX = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz')
ap = argparse.ArgumentParser()
ap.add_argument('--refs', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--base', default='http://127.0.0.1:8302/v1')
ap.add_argument('--model', default='gemma-4-31b')
ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
ap.add_argument('--conc', type=int, default=6)
ap.add_argument('--workers', type=int, default=3)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tok)
PRIOR = ChannelPrior.from_log_slips('ft_edit')


def load_refs(p):
    """-> list of dicts {state_id, context_ref, call_id, raw_args} (plain lines = context_ref only)."""
    items = []
    for i, l in enumerate(open(p)):
        l = l.strip()
        if not l:
            continue
        d = json.loads(l) if l.startswith('{') else {'context_ref': l}
        d.setdefault('state_id', d.get('context_ref') + '#%d' % i)
        items.append(d)
    return items


def norm_args(a):
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except Exception:
            return None
    return a if isinstance(a, dict) else None


async def one(srv, item, d, ctx, fo, lock):
    ref = item['context_ref']
    rec = {'state_id': item.get('state_id'), 'context_ref': ref, 'call_id': item.get('call_id')}
    try:
        if d is None or ctx is None:
            raise ValueError('not in corpus' if d is None else 'no context')
        schema = schema_from_tools(ctx['tools'])
        p0 = render_prompt(tok, ctx['messages'], ctx['tools'], True, 'june')
        th = d.get('reasoning_content') or ''
        A = ('<|channel>thought\n' + th + ('' if th.endswith('\n') else '\n') + '<channel|>') if th else '<|channel>thought\n<channel|>'
        A += d.get('content') or ''
        prefix = p0 + A + TC_START
        pid = ids_of(tok, prefix)
        rawp = (d.get('raw') or {}).get('raw_prefix') or ''
        call = rawp[len(TC_START):] if rawp.startswith(TC_START) else rawp
        site = first_slip_site(call, schema, finished=False)
        rec.update(closer=(d['labels'].get('absorbed') or [{}])[0].get('closer'), site_found=site is not None,
                   raw_prefix_exact=(d.get('raw') or {}).get('raw_prefix_exact'))
        async with Pin(srv, pid):
            ri = await rollback_resume(srv, tok, prefix, call, False, schema, rule='nc', prior=PRIOR,
                                       rules=('closer', 'opener'), temperature=0.0, seed=0, prefix_ids=pid)
        ok = ri['finished'] and is_valid(ri['text'], schema)
        cc = ri['rounds'][0]['cut_choice'] if ri['rounds'] else {}
        margin = None
        if cc.get('lls') is not None:
            adj = sorted((l + p for l, p in zip(cc['lls'], cc['prior'])), reverse=True)
            margin = (adj[0] - adj[1]) if len(adj) > 1 else None
        cut = None
        if site is not None and ri['rounds']:
            cut = {'k': cc.get('k'), 'position_in_call': ri['rounds'][0]['cut'], 'look_alike_run': site.run,
                   'closer_removed': site.closer_for(ri['rounds'][0]['cut']) if ri['rounds'][0]['kind'] == 'key' else None,
                   'rule': cc.get('rule')}
        rec.update(status='ok', valid=ok, abstain=not ok, rounds=len(ri['rounds']), cut=cut, logp_margin=margin,
                   repaired_text=ri['text'])
        if ok:
            args = parse_strict(ri['text']).args()
            ordered = {k: args[k] for k in sorted(args)}           # template dict-sort = canonical new-first
            rec['repaired_call'] = {'name': 'edit_file', 'arguments': ordered}
            rec['canonical_new_first'] = '<|tool_call>' + render_template_order('edit_file', args) + '<tool_call|>'
    except Exception as e:
        rec.update(status='error', abstain=True, err=repr(e)[:300])
    async with lock:
        fo.write(json.dumps(rec) + '\n'); fo.flush()


async def main():
    items = load_refs(a.refs)
    want = {x['context_ref'] for x in items}
    by_ref = {}
    for l in open(CORPUS):
        d = json.loads(l)
        if d.get('context_ref') in want and d.get('tool') == 'edit_file' and d.get('kind') == 'parsed_malformed':
            by_ref.setdefault(d['context_ref'], []).append(d)

    def pick(item):
        cands = by_ref.get(item['context_ref']) or []
        ra = norm_args(item.get('raw_args'))
        for d in cands:                       # the corpus record whose logged (parsed) arguments match A's raw_args
            if ra is not None and norm_args(d.get('arguments_json')) == ra:
                return d
        return cands[0] if cands else None
    ctx = {}
    with lzma.open(CTX, 'rt') as f:
        for l in f:
            c = json.loads(l)
            if c['context_ref'] in want:
                ctx[c['context_ref']] = c
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            x = json.loads(l)
            if x.get('status') == 'ok':
                done.add(x.get('state_id'))
    items = [x for x in items if x.get('state_id') not in done]
    print(len(items), 'states;', sum(1 for x in items if pick(x)), 'matched in corpus;', len(ctx), 'contexts', flush=True)
    srv = Server(a.base, a.model, conc=a.conc)
    lock = asyncio.Lock()
    q = asyncio.Queue()
    for r in items:
        q.put_nowait(r)
    with open(a.out, 'a') as fo:
        async def worker():
            while True:
                try:
                    r = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(srv, r, pick(r), ctx.get(r['context_ref']), fo, lock)
        await asyncio.gather(*[worker() for _ in range(a.workers)])
    print('done', dict(srv.stats), flush=True)
    await srv.close()

asyncio.run(main())
