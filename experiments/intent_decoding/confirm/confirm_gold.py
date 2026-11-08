"""FROZEN C16 (PREREG_v2 §3.2): IPD exact intent on P's REAL logged first-edit slips, gold from the model's own later
clean retry (same rule as the discovery G1 split): the logged first edit call of a B1 episode is a closer slip; a later
valid edit call in the same episode has the same path key and new_string == the payload before the look-alike run
-> gold = (path, payload, retry old_string).  IPD runs from the exact logged prefix (manifest render of the B1 context +
the logged raw response text up to the slip; P's sampling).  Reads outcomes.jsonl (raw_response_text) -- allowed only
after PREREG_v2 is frozen (governed script).  If P yields no such slip, C16 = NOT_ESTIMABLE.
usage: confirm_gold.py --pools_dir <...> [--stratum S1] --out <jsonl>
"""
import argparse, asyncio, copy, hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from transformers import AutoTokenizer
from gemma_protocol import (D, TC_START, TC_END, schema_from_tools, is_valid, first_slip_site, parse_strict)
from intent_decode import Server, rollback_resume, ChannelPrior, ids_of, Pin
from stats import wilson

CONTAGION = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ap = argparse.ArgumentParser()
ap.add_argument('--pools_dir', required=True)
ap.add_argument('--stratum', default='S1')
ap.add_argument('--base', default='http://127.0.0.1:8302/v1')
ap.add_argument('--model', default='gemma-4-31b')
ap.add_argument('--tok', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
ap.add_argument('--out', required=True)
ap.add_argument('--conc', type=int, default=8)
a = ap.parse_args()
PM = json.load(open(os.path.join(a.pools_dir, 'POOLS_MANIFEST.json')))
SM = PM[a.stratum]
man_path = SM['corpus_manifest'] if os.path.isabs(SM['corpus_manifest']) else os.path.join(CONTAGION, SM['corpus_manifest'])
MAN = json.load(open(man_path)); BASE_DIR = os.path.dirname(os.path.abspath(man_path))
F = MAN['files']
ctx_file = F['contexts'] if os.path.isabs(F['contexts']) else os.path.join(BASE_DIR, F['contexts'])
out_name = (F.get('outcomes') or 'outcomes.jsonl').split()[0]
outc_file = out_name if os.path.isabs(out_name) else os.path.join(BASE_DIR, out_name)
TPL = open(MAN['render']['chat_template_path']).read(); KW = MAN['render'].get('chat_template_kwargs', {'enable_thinking': True})
PARTS = MAN['render'].get('system_content_form', 'parts') == 'parts'
SAMP = MAN.get('sampling', {}); TEMP = float(SAMP.get('temperature', 1.0)); TOP_P = float(SAMP.get('top_p', 0.95)); TOP_K = SAMP.get('top_k')
ET = (MAN.get('harness') or {}).get('edit_tool', {}); EDIT = ET.get('name', 'edit_file')
PATHK, OLDK, NEWK = ET.get('path_key', 'file_path'), ET.get('old_key', 'old_string'), ET.get('new_key', 'new_string')
tok = AutoTokenizer.from_pretrained(a.tok)
_pj = json.load(open(os.path.join(HERE, 'prior_ft_edit.json'))); PRIOR = ChannelPrior(_pj['counts'], _pj.get('alpha', 0.5), name='ft_edit_frozen')


def to_template_messages(msgs, parts):
    out = []
    for i, m in enumerate(msgs):
        m = copy.deepcopy(m)
        for t in m.get('tool_calls') or []:
            f = t['function']
            if isinstance(f.get('arguments'), str):
                try:
                    f['arguments'] = json.loads(f['arguments']) if f['arguments'] else {}
                except Exception:
                    f['arguments'] = {}
        if i == 0 and m.get('role') == 'system' and isinstance(m.get('content'), str) and parts:
            m['content'] = [{'type': 'text', 'text': m['content']}]
        out.append(m)
    return out


def render(c, tools):
    for parts in (PARTS, not PARTS):
        s = tok.apply_chat_template(to_template_messages(c['messages'], parts), tools=tools, add_generation_prompt=True,
                                    tokenize=False, chat_template=TPL, **KW)
        if len(tok(s, add_special_tokens=False)['input_ids']) == c.get('prompt_tokens'):
            return s
    return None


def later_valid_edits(ctxs, after_idx, schema):
    """valid edit calls in assistant messages of the episode's contexts, after request index after_idx."""
    seen, out = set(), []
    for c in ctxs:
        for m in c['messages']:
            for t in m.get('tool_calls') or []:
                f = t.get('function') or {}
                if f.get('name') != EDIT or t.get('id') in seen:
                    continue
                seen.add(t.get('id'))
                try:
                    args = json.loads(f['arguments']) if isinstance(f.get('arguments'), str) else f.get('arguments')
                except Exception:
                    continue
                if isinstance(args, dict) and all(k in args for k in (PATHK, OLDK, NEWK)):
                    out.append((c.get('request_index', 0), args))
    return out


async def main():
    rows = sorted((json.loads(l) for l in open(os.path.join(a.pools_dir, f'{a.stratum}_B1.jsonl'))), key=lambda r: r.get('rank', 0))
    b1 = {r['context_id']: r for r in rows}
    ctx_all, by_ep = {}, {}
    for l in open(ctx_file):
        d = json.loads(l)
        ctx_all[d['context_id']] = d
        by_ep.setdefault(d.get('attempt_id') or d.get('episode_id'), []).append(d)
    outc = {}
    if os.path.exists(outc_file):
        for l in open(outc_file):
            d = json.loads(l)
            if d.get('context_id') in b1:
                outc[d['context_id']] = d
    items = []
    for cid, row in b1.items():
        c = ctx_all.get(cid); o = outc.get(cid)
        if not c or not o or not o.get('raw_response_text'):
            continue
        raw = o['raw_response_text']
        if TC_START not in raw:
            continue
        i = raw.index(TC_START)
        call = raw[i + len(TC_START):].split(TC_END)[0]
        tools = c.get('tools') or MAN['tools']; schema = schema_from_tools(tools)
        if is_valid(call, schema):
            continue
        site = first_slip_site(call, schema, finished=TC_END in raw[i:])
        if site is None or site.key != NEWK:
            continue
        payload = call[site.content_start:site.run_start]
        import re as _re
        mpath = _re.search(_re.escape(PATHK) + r'\s*:\s*' + _re.escape(D) + r'(.*?)' + _re.escape(D), call, _re.S)
        path = mpath.group(1) if mpath else None
        ep = by_ep.get(c.get('attempt_id') or c.get('episode_id'), [])
        gold = None
        for ri, args in sorted(later_valid_edits(ep, c.get('request_index', 0), schema), key=lambda x: x[0]):
            if args.get(NEWK) == payload and (path is None or args.get(PATHK) == path):
                gold = {PATHK: args.get(PATHK), NEWK: payload, OLDK: args.get(OLDK)}
                break
        if gold:
            items.append((cid, c, schema, raw[:i], call, site, gold))
    print(len(items), 'real P slips with retry-derived gold', flush=True)
    srv = Server(a.base, a.model, conc=a.conc, sampling_extra=({'top_k': int(TOP_K)} if TOP_K else None))
    recs = []
    for cid, c, schema, pre, call, site, gold in items:
        p0 = render(c, c.get('tools') or MAN['tools'])
        rec = {'context_id': cid, 'gold': gold, 'run': site.run}
        if p0 is None:
            rec['status'] = 'render_mismatch'; recs.append(rec); continue
        prefix = p0 + pre + TC_START; pid = ids_of(tok, prefix)
        seed = int(hashlib.sha256(('G|' + cid).encode()).hexdigest()[:8], 16)
        async with Pin(srv, pid):
            r = await rollback_resume(srv, tok, prefix, call, False, schema, rule='nc', prior=PRIOR, rules=('closer', 'opener'),
                                      temperature=TEMP, top_p=TOP_P, seed=seed, prefix_ids=pid)
        ok = r['finished'] and is_valid(r['text'], schema)
        args = parse_strict(r['text']).args() if ok else {}
        rec.update(status='ok', text=r['text'], valid=ok, exact_intent=bool(ok and all(args.get(k) == gold[k] for k in (PATHK, NEWK, OLDK))))
        recs.append(rec)
    with open(a.out, 'w') as fo:
        for rec in recs:
            fo.write(json.dumps(rec) + '\n')
    ok = [r for r in recs if r.get('status') == 'ok']
    k = sum(r['exact_intent'] for r in ok); n = len(ok)
    lo, hi = wilson(k, n) if n else (float('nan'), float('nan'))
    verdict = 'NOT_ESTIMABLE' if n == 0 else ('REPLICATES' if lo >= 0.80 else 'FAILS')
    print(json.dumps({'C16_IPD_exact_intent': {'k': k, 'n': n, 'wilson95': [lo, hi], 'verdict': verdict}}), flush=True)
    await srv.close()

asyncio.run(main())
