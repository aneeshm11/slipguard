"""Proxy equivalence (PI job, 2026-11-04 18:15 UTC): does workstream E's SHIPPED proxy IPD behave like B's reference
decoder (algorithm (i+), `intent_decode.rollback_resume`)?

E's frozen-candidate code is used read-only from a vendored, hash-verified copy (proxy_vendor/VENDOR_MANIFEST.txt;
e2e_proxy.py sha256 0c2a5278...).  B's reference outputs are the June thinking-ON gate records (out/v3_r31_on_june.jsonl).

subcommands
  offline     CPU only.  (a) prompt rendering: proxy (to_conversation + Engine.render_ids) vs B's replay render, June
              template, all 600 gate contexts.  (b) the proxy's decode-time IPD logic replayed on B's identical logged
              generations: IPD stop strings (vLLM semantics: earliest-ending match, a resumed segment sees only new
              text), thinking check, detect_slip, opener confirmation using the LOGGED next token, cut candidates,
              closer prior, and the cut decision applied to B's logged likelihoods; then the proxy's post-hoc paths
              (opener rollback on EOS; text-only intent_parse_args repair).  (c) byte identity on the valid calls.
  quotestorm  CPU only.  The proxy's decode-time logic + post-hoc paths on the 229,414 valid QuoteStorm calls (both key
              orders): any intervention on a valid call is a change.
  scores      needs the 31B server.  The proxy's own nc_scores (its lp_fn request format) on the identical generations
              vs B's logged per-cut log-likelihoods and chosen cut.
  live        needs the 31B server and a running proxy.  The 600 gate contexts through the proxy, cfgs given, seed 0,
              T 0.2, top-p 0.95, max_tokens 6144, thinking ON, no budget (as the gate).
  analyze     merge everything into out/proxy_equivalence.json.
"""
import argparse, asyncio, collections, hashlib, importlib.util, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HERE, 'proxy_vendor')
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
import gemma_protocol as BGP                      # B's reference library (imported BEFORE E's modules)
from replay_utils import fix_msgs
from stats import wilson

D, TC_START, TC_END = BGP.D, BGP.TC_START, BGP.TC_END
CH_START, CH_END = '<|channel>', '<channel|>'
OUTD = os.path.join(HERE, 'out/proxy_eq')
GATE = os.path.join(HERE, 'out/v3_r31_on_june.jsonl')
CTX = os.path.join(HERE, 'data/replay_gemma_first_edit.jsonl')
MODEL_DIR_JUNE = os.path.join(HERE, 'data/proxy_modeldir_june')   # tokenizer symlinks + the June-5 template copy
JUNE_TPL = '<competition-logs>'   # moved main-track tree
JUNE_MD5 = 'd6c5bd0d1e797798f3a598dd7fd7f020'
for _p in (JUNE_TPL, os.path.join(MODEL_DIR_JUNE, 'chat_template.jinja')):
    assert hashlib.md5(open(_p, 'rb').read()).hexdigest() == JUNE_MD5, _p


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def load_e(vendor=None):
    """E's proxy modules under private names; B's `gemma_protocol` stays bound to B's module."""
    global V
    V = vendor or V
    saved_path = list(sys.path)
    egp = _load('e_gemma_protocol', os.path.join(V, 'proxy/gemma_protocol.py'))
    sys.modules['gemma_protocol'] = egp
    try:
        epx = _load('e_e2e_proxy', os.path.join(V, 'proxy/e2e_proxy.py'))
    finally:
        sys.modules['gemma_protocol'] = BGP
        sys.path[:] = saved_path
    assert epx.gp is egp
    return egp, epx


def W(k, n):
    return {'k': k, 'n': n, 'rate': (k / n) if n else None, 'wilson95': wilson(k, n)}


def wjson(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, 'w'), indent=1, default=str)


# ------------------------------------------------------------------------------------------- proxy logic replay
def in_think_at(G, e):
    s = G.rfind(CH_START, 0, e)
    return s >= 0 and G.rfind(CH_END, 0, e) < s


def next_tok_text(G, e, tok):
    if e >= len(G):
        return None
    if G.startswith(D, e):
        return D
    for sp in (TC_END, TC_START, CH_START, CH_END):
        if G.startswith(sp, e):
            return sp
    ids = tok.encode(G[e:e + 64], add_special_tokens=False)
    return tok.decode(ids[:1]) if ids else None


def sim_decode(EGP, G, schemas, tok, max_interventions=8):
    """Replay the proxy's decode-time IPD on a fixed generation G (stop strings -> detect_slip -> confirmation).
    Returns the first confirmed intervention (the proxy would cut and resume there) or None, plus the events."""
    stops = EGP.ipd_stop_strings(schemas)
    events, pos = [], 0
    while True:
        best = None
        for s in stops:
            i = G.find(s, pos)
            if i >= 0 and (best is None or i + len(s) < best[0]):
                best = (i + len(s), s)
        if best is None:
            return None, events
        e, s = best
        cut_text = G[:e]
        it = in_think_at(G, e)
        slip = None if it else EGP.detect_slip(cut_text, schemas)
        if slip is None:
            events.append({'ev': 'ipd_no_repair', 'stop': s, 'in_think': it, 'at': e})
            pos = e
            continue
        if slip.kind == 'key':
            nxt = next_tok_text(G, e, tok)
            if nxt is None:
                events.append({'ev': 'confirm_unknown', 'at': e})
                return None, events
            if not EGP.opener_ok(nxt, slip.next_type):
                events.append({'ev': 'ipd_rejected', 'next_tok': nxt[:20], 'run': slip.run, 'key': slip.next_key, 'at': e})
                pos = e + len(nxt)
                continue
        cuts = slip.cuts()
        return {'stop': s, 'at': e, 'kind': slip.kind, 'in_key': slip.in_key, 'next_key': slip.next_key, 'run': slip.run,
                'gap': slip.gap, 'run_start': slip.run_start, 'struct_pos': slip.struct_pos, 'cuts': cuts,
                'closers': [slip.run[k:] if k <= len(slip.run) else '' for k in range(len(cuts))], '_slip': slip}, events


def sim_posthoc(EGP, EPX, engine, G, finished, schemas):
    """The proxy's post-hoc paths after a generation that ended naturally: opener rollback (only if the call is
    malformed under vLLM's parser), else the text-only intent_parse_args repair of a malformed delivered call."""
    if finished:
        site = EGP.find_opener_site(G, schemas)
        if site is not None and EPX._call_malformed(G, site, schemas):
            return {'path': 'opener_rollback', 'key': site['key'], 'cut': site['cut'], 'lead': site['lead']}
    reasoning, content, calls = engine.parse(G)
    raw_calls = EGP.CALL_RE.findall(G)
    if not calls:
        return {'path': 'no_call_parsed'}
    c = calls[0]
    args = json.loads(c['arguments'])
    cls = EGP.classify_args(c['name'], args, schemas)
    out = {'path': 'delivered', 'ok_emitted': cls['ok'], 'why': cls['why'], 'args': args}
    if not cls['ok'] and c['name'] in schemas and raw_calls:
        rec_args = EGP.intent_parse_args(raw_calls[0][1], schemas[c['name']]['properties'])
        if EGP.classify_args(c['name'], rec_args, schemas)['ok']:
            out.update(path='posthoc_text_repair', args=rec_args)
    out['ok_delivered'] = EGP.classify_args(c['name'], out['args'], schemas)['ok']
    return out


def ref_round0(r):
    ip = r.get('i_plus') or r.get('i_nc')
    if not ip or not ip.get('rounds'):
        return None
    return ip['rounds'][0]


# ------------------------------------------------------------------------------------------------- offline
def cmd_offline(a):
    EGP, EPX = load_e()
    engine = EPX.Engine(MODEL_DIR_JUNE)
    tok = engine.tok
    prior = EGP.ChannelPrior(json.load(open(os.path.join(V, 'configs/channel_prior.json')))['priors']['ft_edit'], 0.5)
    june = open(JUNE_TPL).read()
    assert engine.tpl_official == june
    ctx = {}
    for l in open(CTX):
        c = json.loads(l)
        ctx[c['id']] = c
        if len(ctx) >= 600:
            break
    # (a) prompt rendering equality on all 600 gate contexts
    rend = collections.Counter(); rmis = []
    for cid, c in ctx.items():
        mine = tok.apply_chat_template(fix_msgs(c['messages']), tools=c['tools'], add_generation_prompt=True, tokenize=False,
                                       enable_thinking=True, chat_template=june)
        try:
            ptext, pids = engine.render_ids(EGP.to_conversation(c['messages']), [dict(t) for t in c['tools']],
                                            {'enable_thinking': True}, False)
        except Exception as e:  # noqa: BLE001
            rend['proxy_render_error'] += 1; rmis.append({'id': cid, 'err': repr(e)[:200]}); continue
        same_text = ptext == mine
        same_ids = same_text or pids == tok.encode(mine, add_special_tokens=False)
        rend['identical_text'] += same_text
        rend['identical_ids'] += same_ids
        if not same_text and len(rmis) < 10:
            i = next((k for k in range(min(len(mine), len(ptext))) if mine[k] != ptext[k]), min(len(mine), len(ptext)))
            rmis.append({'id': cid, 'first_diff': i, 'mine': mine[max(0, i - 80):i + 80], 'proxy': ptext[max(0, i - 80):i + 80]})
    rend['n'] = len(ctx)
    # (b)+(c) decode-time + post-hoc replay on B's logged generations
    rows = []
    for l in open(GATE):
        r = json.loads(l)
        if r.get('status') != 'call':
            continue
        c = ctx.get(r['id'])
        schemas = EGP.tool_schemas(c['tools'])
        off = len(r['A_text']) + len(TC_START)
        G = r['A_text'] + TC_START + r['call'] + (TC_END if r['finished'] else '')
        iv, events = sim_decode(EGP, G, schemas, tok)
        row = {'id': r['id'], 'forced': bool(r.get('forced')), 'finished': r['finished'], 'base_valid': r['base']['strict_valid'],
               'base_census_ok': r['base']['census_ok'], 'ref_site': r.get('site'), 'events': events}
        r0 = ref_round0(r)
        ref_changed = bool((r.get('i_plus') or r.get('i_nc') or {}).get('changed'))
        row['ref'] = {'changed': ref_changed, 'kind': r0 and r0.get('kind'), 'cut': r0 and r0.get('cut'),
                      'cands': r0 and (r0.get('cut_choice') or {}).get('cands'), 'k': r0 and (r0.get('cut_choice') or {}).get('k'),
                      'lls': r0 and (r0.get('cut_choice') or {}).get('lls'), 'prior': r0 and (r0.get('cut_choice') or {}).get('prior')}
        if iv is not None:
            sl = iv.pop('_slip')
            cuts_rel = [x - off for x in iv['cuts']]
            pri = [prior.logp(cl) for cl in iv['closers']]
            row['proxy'] = {'path': 'decode_time_cut', **{k: v for k, v in iv.items() if k not in ('cuts',)},
                            'cuts_rel': cuts_rel, 'prior': [round(x, 4) for x in pri],
                            'resume_prefix_tail': EGP.apply_cut(G[:iv['at']], sl, iv['cuts'][0])[-40:]}
            rs = r.get('site') or {}
            row['agree_site'] = bool(rs) and (rs.get('pos') == iv['run_start'] - off and rs.get('run') == iv['run'] and
                                              rs.get('key') == iv['in_key'] and rs.get('next_key') == iv['next_key'] and
                                              rs.get('kind') == iv['kind'] and (rs.get('gap') or '') == iv['gap'])
            rc = row['ref']['cands']
            row['agree_cands'] = rc is not None and list(rc) == cuts_rel
            if row['ref']['lls'] is not None and row['agree_cands']:
                lls = row['ref']['lls']
                adj = [lls[k] + pri[k] for k in range(len(lls))]
                kp = max(range(len(adj)), key=lambda i: (adj[i], -i))
                row['k_proxy_on_ref_lls'] = kp
                row['agree_k'] = kp == row['ref']['k']
                row['prior_equal'] = all(abs(x - y) < 1e-3 for x, y in zip(row['ref']['prior'], pri))
            elif rc is not None and len(rc) == 1:
                row['agree_k'] = None
        else:
            row['proxy'] = sim_posthoc(EGP, EPX, engine, G, r['finished'], schemas)
            if 'args' in row['proxy']:
                row['proxy']['args_sha'] = hashlib.sha1(json.dumps(row['proxy'].pop('args'), sort_keys=True).encode()).hexdigest()[:12]
        rows.append(row)
    os.makedirs(OUTD, exist_ok=True)
    with open(os.path.join(OUTD, 'offline_gate.jsonl'), 'w') as fo:
        for row in rows:
            fo.write(json.dumps(row, default=str) + '\n')
    wjson(os.path.join(OUTD, 'offline_render.json'), {'counts': dict(rend), 'mismatch_examples': rmis})
    print('render', dict(rend), flush=True)
    print('offline rows', len(rows), collections.Counter(x['proxy']['path'] for x in rows), flush=True)


def cmd_offline_fix(a):
    """CPU check of the FIXED proxy (verify-then-repair) on the identical gate generations: E's ipd_scan (verify every
    call; plan = first not-strictly-valid call with a repairable site in a declared key) vs B's logged reference site,
    candidate cuts and prior; and E's cut rule (pick_cut mirror) applied to B's logged likelihoods."""
    EGP, EPX = load_e(a.vendor)
    BGv = EGP.BG
    ctx = {}
    for l in open(CTX):
        c = json.loads(l); ctx[c['id']] = c
        if len(ctx) >= 600:
            break
    prior_counts = json.load(open(os.path.join(V, 'configs/channel_prior.json')))['priors']['ft_edit']
    rows = []
    for l in open(GATE):
        r = json.loads(l)
        if r.get('status') != 'call':
            continue
        S = BGv.schema_from_tools(ctx[r['id']]['tools'])
        G = r['A_text'] + TC_START + r['call'] + (TC_END if r['finished'] else '')
        plan, audit = EGP.ipd_scan(G, S)
        ip = r.get('i_plus') or r.get('i_nc')
        r0 = (ip or {}).get('rounds', [{}])[0] if ip and ip.get('rounds') else None
        row = {'id': r['id'], 'forced': bool(r.get('forced')), 'base_valid': r['base']['strict_valid'], 'ref_site': r.get('site'),
               'ref_round0': None if r0 is None else {'kind': r0.get('kind'), 'cut': r0.get('cut'),
                                                      'cands': (r0.get('cut_choice') or {}).get('cands'), 'k': (r0.get('cut_choice') or {}).get('k')},
               'audit': audit, 'plan': None}
        if plan is not None:
            site = plan['site']
            off = plan.get('pos', 0)
            cps = [x for x in site.cut_positions()] if hasattr(site, 'cut_positions') else None
            row['plan'] = {'kind': site.kind, 'key': getattr(site, 'key', None), 'next_key': getattr(site, 'next_key', None),
                           'run': getattr(site, 'run', getattr(site, 'lead', None)), 'cuts': cps,
                           'call_text_equal': plan.get('text') == r['call']}
            if r0 is not None and cps is not None and r0.get('cut_choice', {}).get('lls'):
                lls = r0['cut_choice']['lls']
                closers = [EGP.closer_at(site, k) for k in range(len(cps))]
                pri = EGP.ChannelPrior(prior_counts, 0.5) if hasattr(EGP, 'ChannelPrior') else None
                pv = [pri.logp(cl) for cl in closers] if pri else None
                if pv and len(pv) == len(lls):
                    adj = [lls[k] + pv[k] for k in range(len(lls))]
                    row['k_fix_on_ref_lls'] = max(range(len(adj)), key=lambda i: (adj[i], -i))
                    row['prior_equal'] = all(abs(x - y) < 1e-3 for x, y in zip(pv, r0['cut_choice']['prior']))
        rows.append(row)
    with open(os.path.join(OUTD, 'offline_gate_efix.jsonl'), 'w') as fo:
        for row in rows:
            fo.write(json.dumps(row, default=str) + '\n')
    agg = collections.Counter()
    for x in rows:
        g = 'valid' if x['base_valid'] else ('slip' if x['ref_site'] is not None else 'invalid_other')
        agg['n_' + g] += 1
        agg[g + '|plan'] += x['plan'] is not None
        if x['plan'] is not None and x['ref_round0'] is not None:
            rr = x['ref_round0']
            agg[g + '|both_act'] += 1
            agg[g + '|same_kind'] += x['plan']['kind'] == rr['kind']
            if rr.get('cands') is not None:
                agg[g + '|same_cands'] += x['plan']['cuts'] == rr['cands']
            if 'k_fix_on_ref_lls' in x:
                agg[g + '|scored'] += 1
                agg[g + '|same_k'] += x['k_fix_on_ref_lls'] == rr['k']
                agg[g + '|prior_equal'] += bool(x.get('prior_equal'))
        if x['plan'] is None and x['ref_round0'] is not None:
            agg[g + '|ref_acts_fix_not'] += 1
        if x['plan'] is not None and x['ref_round0'] is None:
            agg[g + '|fix_acts_ref_not'] += 1
    out = {'vendor': V, 'counts': dict(agg)}
    wjson(os.path.join(OUTD, 'offline_gate_efix_summary.json'), out)
    print(json.dumps(out, default=str), flush=True)


# ------------------------------------------------------------------------------------------------- quotestorm
def _qs_work(args):
    lo, hi = args
    EGP, EPX = load_e()
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL_DIR_JUNE)
    tools = json.load(open(os.path.join(HERE, 'data/tools_official.json')))
    schemas = EGP.tool_schemas(tools)
    stops = EGP.ipd_stop_strings(schemas)
    allp = _qs_payloads()
    c = collections.Counter(); ex = []
    for p in allp[lo:hi]:
        for order in ('new_first', 'old_first'):
            keys = ['filepath', 'new_string', 'old_string'] if order == 'new_first' else ['filepath', 'old_string', 'new_string']
            vals = {'filepath': p['filepath'], 'new_string': p['new'], 'old_string': p['old']}
            call = BGP.render_call('edit_file', [(k, vals[k], 'str') for k in keys])
            G = TC_START + call + TC_END
            c['n'] += 1
            c['g_' + ('adversarial' if p['src'] == 'adversarial' else 'natural')] += 1
            if not any(s in G for s in stops):
                continue
            c['stop_fires'] += 1
            iv, events = sim_decode(EGP, G, schemas, tok)
            c['rejected_by_confirmation'] += any(e_['ev'] == 'ipd_rejected' for e_ in events)
            if iv is not None:
                c['changed'] += 1
                c['changed_' + ('adversarial' if p['src'] == 'adversarial' else 'natural')] += 1
                if len(ex) < 20:
                    ex.append({'src': p['src'], 'order': order, 'ctx': G[max(0, iv['at'] - 120):iv['at'] + 20], 'run': iv['run'],
                               'in_key': iv['in_key'], 'next_key': iv['next_key']})
    return c, ex


_QS = None


def _qs_payloads():
    global _QS
    if _QS is None:
        import mine_payloads as MP
        pool = []
        for src, files in MP.SRC.items():
            for f in files:
                t = MP.pq.read_table(f, columns=['instance_id', 'patch', 'test_patch']).to_pylist()
                for r in t:
                    for col in ('patch', 'test_patch'):
                        for fp, lines in MP.hunks(r.get(col) or ''):
                            pl = MP.to_payload(lines)
                            if not pl:
                                continue
                            old, new = pl
                            if not MP.feats(fp, old, new)['rich']:
                                continue
                            pool.append({'src': src, 'filepath': fp, 'old': old, 'new': new})
        seen, uniq = set(), []
        for p in pool:
            k = (p['filepath'], p['old'], p['new'])
            if k not in seen:
                seen.add(k); uniq.append(p)
        adv = [json.loads(l) for l in open(os.path.join(HERE, 'data/quotestorm.jsonl'))]
        adv = [{'src': 'adversarial', 'filepath': p['filepath'], 'old': p['old'], 'new': p['new']} for p in adv if p['src'].startswith('adversarial')]
        _QS = uniq + adv
    return _QS


def cmd_quotestorm(a):
    from multiprocessing import Pool
    n = len(_qs_payloads())
    step = (n + a.np - 1) // a.np
    tot = collections.Counter(); ex = []
    with Pool(a.np) as pl:
        for c, e_ in pl.imap_unordered(_qs_work, [(i, min(n, i + step)) for i in range(0, n, step)]):
            tot.update(c); ex.extend(e_)
    out = {'payloads': n, 'calls': tot['n'], 'natural_calls': tot['g_natural'], 'adversarial_calls': tot['g_adversarial'],
           'stop_string_fires': tot['stop_fires'], 'rejected_by_opener_confirmation': tot['rejected_by_confirmation'],
           'proxy_changed_valid_calls': W(tot['changed'], tot['n']),
           'proxy_changed_natural': W(tot['changed_natural'], tot['g_natural']),
           'proxy_changed_adversarial': W(tot['changed_adversarial'], tot['g_adversarial']),
           'reference_changed_valid_calls': {'k': 0, 'n': tot['n'], 'note': 'B guard: is_valid first (out/quotestorm_free_big.json)'},
           'examples': ex[:20]}
    wjson(os.path.join(OUTD, 'quotestorm_proxy.json'), out)
    print(json.dumps({k: v for k, v in out.items() if k != 'examples'}, default=str), flush=True)


# ------------------------------------------------------------------------------------------------- scores (server)
def cmd_scores(a):
    EGP, EPX = load_e()
    engine = EPX.Engine(MODEL_DIR_JUNE)
    tok = engine.tok
    prior = EGP.ChannelPrior(json.load(open(os.path.join(V, 'configs/channel_prior.json')))['priors']['ft_edit'], 0.5)
    ctx = {}
    for l in open(CTX):
        c = json.loads(l)
        ctx[c['id']] = c
        if len(ctx) >= 600:
            break
    gate = {json.loads(l)['id']: json.loads(l) for l in open(GATE) if json.loads(l).get('status') == 'call'}
    rows = [json.loads(l) for l in open(os.path.join(OUTD, 'offline_gate.jsonl'))]
    rows = [x for x in rows if x['proxy'].get('path') == 'decode_time_cut']
    import aiohttp

    async def main():
        sem = asyncio.Semaphore(a.conc)
        conn = aiohttp.TCPConnector(limit=0, force_close=True)
        async with aiohttp.ClientSession(connector=conn) as sess:
            async def lp_fn(ids, target):     # verbatim request format of the proxy's lp_fn
                req = {'model': a.model, 'prompt': ids, 'max_tokens': 1, 'temperature': 0.0, 'logprobs': 1,
                       'allowed_token_ids': [int(target)], 'skip_special_tokens': False, 'return_tokens_as_token_ids': True}
                async with sem:
                    async with sess.post(a.base + '/completions', json=req) as resp:
                        txt = await resp.text(); status = resp.status
                try:
                    lp = json.loads(txt)['choices'][0]['logprobs']
                    if status != 200 or lp['tokens'][0] != f'token_id:{int(target)}':
                        return None
                    return float(lp['token_logprobs'][0])
                except Exception:  # noqa: BLE001
                    return None

            async def one(x):
                r = gate[x['id']]; c = ctx[x['id']]
                schemas = EGP.tool_schemas(c['tools'])
                _, pids = engine.render_ids(EGP.to_conversation(c['messages']), [dict(t) for t in c['tools']], {'enable_thinking': True}, False)
                G = r['A_text'] + TC_START + r['call'] + (TC_END if r['finished'] else '')
                iv, _ = sim_decode(EGP, G, schemas, tok)
                cut_text = G[:iv['at']]
                gen_ids = tok.encode(cut_text, add_special_tokens=False)
                t0 = time.time()
                sc = await EPX.nc_scores(engine, pids, gen_ids, cut_text, iv['_slip'], lp_fn, prior)
                out = {'id': x['id'], 'latency': time.time() - t0, 'proxy_sc': sc, 'ref_k': x['ref']['k'], 'ref_lls': x['ref']['lls'],
                       'ref_cands': x['ref']['cands']}
                if sc is not None:
                    out['agree_k'] = sc['k'] == x['ref']['k']
                    if x['ref']['lls']:
                        out['max_abs_ll_diff'] = max(abs(p - q) for p, q in zip(sc['lls'], x['ref']['lls'])) if len(sc['lls']) == len(x['ref']['lls']) else None
                return out
            return await asyncio.gather(*[one(x) for x in rows])

    res = asyncio.run(main())
    with open(os.path.join(OUTD, 'scores_gate.jsonl'), 'w') as fo:
        for r_ in res:
            fo.write(json.dumps(r_, default=str) + '\n')
    ok = [r_ for r_ in res if r_.get('proxy_sc') is not None]
    print('scored', len(ok), '/', len(res), 'agree_k', sum(r_['agree_k'] for r_ in ok),
          'max |dll|', max((r_.get('max_abs_ll_diff') or 0) for r_ in ok) if ok else None, flush=True)


# ------------------------------------------------------------------------------------------------- teacher-forced (server)
def _g1_items():
    import lzma
    CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slips.jsonl')
    CTXX = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz')
    recs = [d for d in (json.loads(l) for l in open(CORPUS))
            if d.get('intent_from_retry') and d['model_family'] == 'base' and d.get('run_status') == 'ok']
    need = {d['context_ref'] for d in recs}
    ctx = {}
    with lzma.open(CTXX, 'rt') as f:
        for l in f:
            c = json.loads(l)
            if c['context_ref'] in need:
                ctx[c['context_ref']] = c
    items = []
    for d in recs:
        c = ctx.get(d['context_ref'])
        if c is None:
            continue
        args = json.loads(d['arguments_json']); lab = d['labels']['absorbed'][0]
        host = args.get(lab['host_key']) or ''
        payload = host[:lab['offset']] if 'offset' in lab else host[:d['labels'].get('payload_chars_before_closer', 0)]
        th = d.get('reasoning_content') or ''
        A = ('<|channel>thought\n' + th + ('' if th.endswith('\n') else '\n') + '<channel|>') if th else '<|channel>thought\n<channel|>'
        A += d.get('content') or ''
        rawp = d['raw']['raw_prefix']
        cp = rawp[len(TC_START):] if rawp.startswith(TC_START) else rawp
        items.append({'id': d['id'], 'messages': c['messages'], 'tools': c['tools'], 'gen': A + TC_START + cp, 'logged_end': 'live',
                      'temp': float(d['temperature']), 'seed': int(hashlib.sha256(('PX|' + d['id']).encode()).hexdigest()[:8], 16),
                      'gold': {'filepath': args.get('filepath'), 'new_string': payload, 'old_string': d['intent_from_retry']['old_string']},
                      'max_new': 2048})
    return items


def _gate_items():
    ctx = {}
    for l in open(CTX):
        c = json.loads(l)
        ctx[c['id']] = c
        if len(ctx) >= 600:
            break
    items = []
    for l in open(GATE):
        r = json.loads(l)
        if r.get('status') != 'call':
            continue
        c = ctx[r['id']]
        items.append({'id': r['id'], 'messages': c['messages'], 'tools': c['tools'], 'forced': bool(r.get('forced')),
                      'gen': r['A_text'] + TC_START + r['call'] + (TC_END if r['finished'] else ''),
                      'logged_end': 'eos' if r['finished'] else 'length', 'temp': 0.2, 'seed': 0, 'max_new': 2048})
    return items


def cmd_tf(a):
    """The proxy's own generate() (decode-time IPD, confirmation, nc_scores, resume, opener rule) run in-process on the
    identical logged generations: the backend replays the logged text while the proxy's token prefix is consistent with
    it (stop strings applied with vLLM semantics), and samples live on :8302 once the proxy has cut. confirm_fn returns
    the logged next token while consistent. lp_fn is the proxy's request, verbatim. Then the proxy's post-hoc block."""
    EGP, EPX = load_e(a.vendor)
    engine = EPX.Engine(MODEL_DIR_JUNE)
    tok = engine.tok
    prior = EGP.ChannelPrior(json.load(open(os.path.join(V, 'configs/channel_prior.json')))['priors'][a.prior_source], 0.5)
    EOS = 106
    assert EOS in engine.eos_ids
    items = _gate_items() if a.set == 'gate' else _g1_items()
    if a.ids:
        keep = set(a.ids.split(','))
        items = [x for x in items if x['id'] in keep]
    out_path = os.path.join(OUTD, f'tf_{a.set}_{a.tag}.jsonl')
    done = set()
    if os.path.exists(out_path):
        for l in open(out_path):
            d = json.loads(l)
            if d.get('status') == 'ok':
                done.add(d['id'])
    items = [x for x in items if x['id'] not in done]
    print(f'tf {a.set} [{a.tag}] {len(items)} items to do ({len(done)} done); vendor {V}', flush=True)
    import aiohttp

    async def main():
        rsem = asyncio.Semaphore(a.conc)       # all requests to the backend
        isem = asyncio.Semaphore(a.items)      # items in flight
        lock = asyncio.Lock()
        stats = collections.Counter()
        conn = aiohttp.TCPConnector(limit=0, force_close=True)
        async with aiohttp.ClientSession(connector=conn, timeout=aiohttp.ClientTimeout(total=3600)) as sess:
            async def post(path, req):
                for att in range(3):
                    try:
                        async with rsem:
                            async with sess.post(a.base + path, json=req) as resp:
                                txt = await resp.text()
                                if resp.status >= 500:
                                    await asyncio.sleep(2 + 3 * att); continue
                                return resp.status, txt
                    except (asyncio.TimeoutError, aiohttp.ClientError):
                        await asyncio.sleep(2 + 3 * att)
                return 504, ''

            async def run_item(it, fo):
                async with isem:
                    rec = {'id': it['id'], 'set': a.set, 'tag': a.tag, 'forced': it.get('forced', False)}
                    try:
                        conv = EGP.to_conversation(it['messages'])
                        _, pids = await asyncio.to_thread(engine.render_ids, conv, [dict(t) for t in it['tools']],
                                                          {'enable_thinking': True}, False)
                        schemas = EGP.tool_schemas(it['tools'])
                        logged = it['gen']
                        samp = {'temperature': it['temp'], 'top_p': 0.95, 'seed': it['seed']}
                        n = collections.Counter()
                        warm = {'done': False}
                        wlock = asyncio.Lock()

                        def cur_of(ids):
                            cur = engine.decode(ids[len(pids):])
                            return cur if logged.startswith(cur) else None

                        async def backend_fn(ids, seg_max, stops):
                            cur = await asyncio.to_thread(cur_of, ids)
                            if cur is not None:
                                rest = logged[len(cur):]
                                if rest or it['logged_end'] != 'live':
                                    n['replayed_segments'] += 1
                                    best = None
                                    for s_ in stops:
                                        i = rest.find(s_)
                                        if i >= 0 and (best is None or i + len(s_) < best[0]):
                                            best = (i + len(s_), s_)
                                    if best is not None:
                                        ch = rest[:best[0]]
                                        return 200, {'text': ch, 'token_ids': tok.encode(ch, add_special_tokens=False),
                                                     'finish_reason': 'stop', 'stop_reason': best[1]}
                                    ids_ = tok.encode(rest, add_special_tokens=False) if rest else []
                                    if it['logged_end'] == 'eos':
                                        return 200, {'text': rest, 'token_ids': ids_ + [EOS], 'finish_reason': 'stop', 'stop_reason': None}
                                    return 200, {'text': rest, 'token_ids': ids_, 'finish_reason': 'length', 'stop_reason': None}
                            n['live_segments'] += 1
                            req = {'model': a.model, 'prompt': ids, 'max_tokens': seg_max, 'skip_special_tokens': False,
                                   'include_stop_str_in_output': True, 'return_token_ids': True, 'stop': stops, **samp}
                            st, txt = await post('/completions', req)
                            if st != 200:
                                return st, txt
                            return 200, json.loads(txt)['choices'][0]

                        async def confirm_fn(ids):
                            cur = await asyncio.to_thread(cur_of, ids)
                            if cur is not None and len(cur) < len(logged):
                                n['confirm_replayed'] += 1
                                return tok.encode(logged[len(cur):len(cur) + 64], add_special_tokens=False)[0]
                            n['confirm_live'] += 1
                            req = {'model': a.model, 'prompt': ids, 'max_tokens': 1, 'skip_special_tokens': False,
                                   'return_token_ids': True, **samp}
                            st, txt = await post('/completions', req)
                            try:
                                return int(json.loads(txt)['choices'][0]['token_ids'][0]) if st == 200 else None
                            except Exception:  # noqa: BLE001
                                return None

                        async def lp_fn(ids, target):
                            async def once():
                                n['lp_requests'] += 1
                                req = {'model': a.model, 'prompt': ids, 'max_tokens': 1, 'temperature': 0.0, 'logprobs': 1,
                                       'allowed_token_ids': [int(target)], 'skip_special_tokens': False,
                                       'return_tokens_as_token_ids': True}
                                st, txt = await post('/completions', req)
                                try:
                                    lp = json.loads(txt)['choices'][0]['logprobs']
                                    if st != 200 or lp['tokens'][0] != f'token_id:{int(target)}':
                                        return None
                                    return float(lp['token_logprobs'][0])
                                except Exception:  # noqa: BLE001
                                    return None
                            if not warm['done']:            # first request alone (fills the prefix cache), as B's wctf does
                                async with wlock:
                                    if not warm['done']:
                                        r_ = await once(); warm['done'] = True
                                        return r_
                            return await once()

                        max_total = len(tok.encode(logged, add_special_tokens=False)) + it['max_new']
                        t0 = time.time()
                        g = await EPX.generate(engine, pids, max_total=max_total, budget=None, ipd_stops=EGP.ipd_stop_strings(schemas),
                                               user_stops=[], schemas=schemas, backend_fn=backend_fn, budget_slack=1536,
                                               max_interventions=8, confirm_fn=confirm_fn, lp_fn=lp_fn, prior=prior, opener=True)
                        if 'error' in g:
                            raise RuntimeError(str(g['error'])[:300])
                        gen_ids, finish, sr = g['gen_ids'], g['finish'], g['stop_reason']
                        text_ids = gen_ids[:-1] if (finish == 'stop' and not isinstance(sr, str) and gen_ids and gen_ids[-1] in engine.eos_ids) else gen_ids
                        text = engine.decode(text_ids)
                        # ---- post-hoc block of Proxy.engine_chat (same logic, first call only)
                        reasoning, content, calls = engine.parse(text)
                        raw_calls = EGP.CALL_RE.findall(text)
                        call = None
                        if calls:
                            c = calls[0]
                            args = json.loads(c['arguments'])
                            cls = EGP.classify_args(c['name'], args, schemas)
                            call = {'name': c['name'], 'ok_emitted': cls['ok'], 'why': cls['why'], 'posthoc_repaired': False}
                            raw_args = raw_calls[0][1] if raw_calls else None
                            if not cls['ok'] and c['name'] in schemas and raw_args is not None:
                                rec_args = EGP.intent_parse_args(raw_args, schemas[c['name']]['properties'])
                                if EGP.classify_args(c['name'], rec_args, schemas)['ok']:
                                    args = rec_args; call['posthoc_repaired'] = True
                            call['ok_delivered'] = EGP.classify_args(c['name'], args, schemas)['ok']
                            call['args'] = args
                            call['raw_args'] = raw_args
                        rec.update(status='ok', text_tail=text[-3000:], identical_to_logged=(text == logged.removesuffix('')),
                                   events=g['events'], n_interv=g['n_interv'], finish=finish, call=call, counts=dict(n),
                                   latency=time.time() - t0, n_tool_call_tags=text.count(TC_START))
                        rec['identical_to_logged'] = text == (logged if it['logged_end'] != 'live' else None)
                        if 'gold' in it and call:
                            gd = it['gold']; ag = call['args']
                            rec['exact_intent'] = bool(call['ok_delivered'] and all(ag.get(k) == gd[k] for k in ('filepath', 'new_string', 'old_string')))
                            rec['new_exact'] = ag.get('new_string') == gd['new_string']
                            rec['old_exact'] = ag.get('old_string') == gd['old_string']
                        stats['ok'] += 1
                    except Exception as e:  # noqa: BLE001
                        import traceback
                        rec.update(status='error', err=traceback.format_exc()[-1500:])
                        stats['error'] += 1
                    async with lock:
                        fo.write(json.dumps(rec, default=str, ensure_ascii=False) + '\n'); fo.flush()
                        if (stats['ok'] + stats['error']) % 25 == 0:
                            print(time.strftime('%H:%M:%S'), dict(stats), flush=True)

            with open(out_path, 'a') as fo:
                await asyncio.gather(*[run_item(it, fo) for it in items])
        print('done', dict(stats), flush=True)

    asyncio.run(main())


# ------------------------------------------------------------------------------------------------- CPU P1 test (E's generate)
def _p1_worker(args):
    """Run E's own generate() + the post-hoc block of engine_chat on fixed VALID generations (teacher-forced, CPU):
    the backend replays the call; any divergence (a cut/rollback) or any post-hoc rewrite is a CHANGE. lp_fn is a stub
    (0.0) and live segments end the turn at once: they are reached only after the proxy has already altered the call."""
    vendor, set_name, lo, hi = args
    EGP, EPX = load_e(vendor)
    engine = EPX.Engine(MODEL_DIR_JUNE)
    tok = engine.tok
    prior = EGP.ChannelPrior(json.load(open(os.path.join(V, 'configs/channel_prior.json')))['priors']['ft_edit'], 0.5)
    EOS = 106
    tools = json.load(open(os.path.join(HERE, 'data/tools_official.json')))
    schemas = EGP.tool_schemas(tools)
    stops = EGP.ipd_stop_strings(schemas)
    pids = tok.encode('<|turn>model\n', add_special_tokens=False)
    if set_name == 'quotestorm':
        gens = []
        for p in _qs_payloads()[lo:hi]:
            for order in ('new_first', 'old_first'):
                keys = ['filepath', 'new_string', 'old_string'] if order == 'new_first' else ['filepath', 'old_string', 'new_string']
                vals = {'filepath': p['filepath'], 'new_string': p['new'], 'old_string': p['old']}
                gens.append(('adversarial' if p['src'] == 'adversarial' else 'natural', order,
                             TC_START + BGP.render_call('edit_file', [(k, vals[k], 'str') for k in keys]) + TC_END))
    c = collections.Counter(); ex = []

    async def one(G):
        def cur_of(ids):
            cur = engine.decode(ids[len(pids):])
            return cur if G.startswith(cur) else None

        async def backend_fn(ids, seg_max, st):
            cur = cur_of(ids)
            if cur is None:
                return 200, {'text': '', 'token_ids': [EOS], 'finish_reason': 'stop', 'stop_reason': None}
            rest = G[len(cur):]
            best = None
            for s_ in st:
                i = rest.find(s_)
                if i >= 0 and (best is None or i + len(s_) < best[0]):
                    best = (i + len(s_), s_)
            if best is not None:
                ch = rest[:best[0]]
                return 200, {'text': ch, 'token_ids': tok.encode(ch, add_special_tokens=False), 'finish_reason': 'stop', 'stop_reason': best[1]}
            return 200, {'text': rest, 'token_ids': (tok.encode(rest, add_special_tokens=False) if rest else []) + [EOS],
                         'finish_reason': 'stop', 'stop_reason': None}

        async def confirm_fn(ids):
            cur = cur_of(ids)
            if cur is not None and len(cur) < len(G):
                return tok.encode(G[len(cur):len(cur) + 64], add_special_tokens=False)[0]
            return EOS

        async def lp_fn(ids, target):
            return 0.0

        g = await EPX.generate(engine, pids, max_total=len(tok.encode(G, add_special_tokens=False)) + 64, budget=None,
                               ipd_stops=stops, user_stops=[], schemas=schemas, backend_fn=backend_fn, budget_slack=1536,
                               max_interventions=8, confirm_fn=confirm_fn, lp_fn=lp_fn, prior=prior, opener=True)
        gen_ids = g['gen_ids']
        text_ids = gen_ids[:-1] if (g['finish'] == 'stop' and not isinstance(g['stop_reason'], str) and gen_ids and gen_ids[-1] in engine.eos_ids) else gen_ids
        text = engine.decode(text_ids)
        decode_changed = text != G or g['n_interv'] > 0
        reasoning, content, calls = engine.parse(text)
        raw_calls = EGP.CALL_RE.findall(text)
        posthoc_changed = False
        if calls:
            args = json.loads(calls[0]['arguments'])
            if not EGP.classify_args(calls[0]['name'], args, schemas)['ok'] and raw_calls:
                rec_args = EGP.intent_parse_args(raw_calls[0][1], schemas['edit_file']['properties'])
                if EGP.classify_args('edit_file', rec_args, schemas)['ok'] and rec_args != args:
                    posthoc_changed = True
        return decode_changed, posthoc_changed, g['events']

    async def run_all():
        for grp, order, G in gens:
            if tok.decode(tok.encode(G, add_special_tokens=False)) != G:     # not emittable token-exactly: untestable
                c['roundtrip_skipped_' + grp] += 1
                continue
            c['n'] += 1; c['n_' + grp] += 1
            dch, pch, ev = await one(G)
            c['decode_changed_' + grp] += dch
            c['posthoc_changed_' + grp] += pch
            c['changed_' + grp] += (dch or pch)
            if (dch or pch) and len(ex) < 12:
                ex.append({'grp': grp, 'order': order, 'decode': dch, 'posthoc': pch,
                           'events': [{k: e_.get(k) for k in ('ev', 'kind', 'run', 'key', 'in')} for e_ in ev][:3]})
    asyncio.run(run_all())
    return c, ex


def _p1e_worker(args):
    """P1 test through E's REAL request path: Proxy.engine_chat (render -> generate() -> post-hoc repair -> response) with
    the model replaced by a replay of the valid call (teacher-forced stub backend). The tool call returned to the client
    must carry exactly the intended arguments; the proxy's raw text must equal the replayed call. Any difference = CHANGE."""
    vendor, cfg_name, lo, hi, logdir = args
    EGP, EPX = load_e(vendor)
    from types import SimpleNamespace

    class NS(SimpleNamespace):          # tolerant of new CLI fields in a patched Proxy: unknown -> None
        def __getattr__(self, k):
            return None
    pa = NS(configs=os.path.join(V, 'proxy/configs.json'), model_dir=MODEL_DIR_JUNE, logdir=logdir, cpu_workers=1,
                         max_backend_conc=4, call_timeout=60.0, max_interventions=8, budget_slack=1536,
                         prior=os.path.join(V, 'configs/channel_prior.json'), prior_source='ft_edit', replay_plan=None,
                         seed_salt=None, backend='http://127.0.0.1:9/v1', served='gemma-4-31b')
    px = EPX.Proxy(pa)
    engine = px.engine; tok = engine.tok
    EOS = 106
    tools = json.load(open(os.path.join(HERE, 'data/tools_official.json')))
    msgs = [{'role': 'system', 'content': 'You are a coding agent.'}, {'role': 'user', 'content': 'Apply the edit.'}]
    _, pids = engine.render_ids(EGP.to_conversation(msgs), [dict(t) for t in tools], {'enable_thinking': False}, False)
    cur_G = {'G': None}
    c = collections.Counter(); ex = []

    async def stub_backend(path, body, timeout):
        G = cur_G['G']
        ids = body['prompt']
        cur = engine.decode(ids[len(pids):])
        if body.get('allowed_token_ids'):                       # lp_fn
            t = int(body['allowed_token_ids'][0])
            return 200, json.dumps({'choices': [{'logprobs': {'tokens': [f'token_id:{t}'], 'token_logprobs': [0.0]}}]})
        ok = G.startswith(cur)
        if body.get('max_tokens') == 1:                          # confirm_fn
            t = tok.encode(G[len(cur):len(cur) + 64], add_special_tokens=False)[0] if (ok and len(cur) < len(G)) else EOS
            return 200, json.dumps({'choices': [{'token_ids': [t], 'text': tok.decode([t])}]})
        if not ok:                                               # after a rewrite: end the turn at once
            return 200, json.dumps({'choices': [{'text': '', 'token_ids': [EOS], 'finish_reason': 'stop', 'stop_reason': None}]})
        rest = G[len(cur):]
        best = None
        for s_ in body.get('stop') or []:
            i = rest.find(s_)
            if i >= 0 and (best is None or i + len(s_) < best[0]):
                best = (i + len(s_), s_)
        if best is not None:
            ch = rest[:best[0]]
            return 200, json.dumps({'choices': [{'text': ch, 'token_ids': tok.encode(ch, add_special_tokens=False),
                                                 'finish_reason': 'stop', 'stop_reason': best[1]}]})
        return 200, json.dumps({'choices': [{'text': rest, 'token_ids': (tok.encode(rest, add_special_tokens=False) if rest else []) + [EOS],
                                             'finish_reason': 'stop', 'stop_reason': None}]})

    px.backend = stub_backend
    cfg = px.cfgs[cfg_name]

    async def run_all():
        for p in _qs_payloads()[lo:hi]:
            for order in ('new_first', 'old_first'):
                keys = ['filepath', 'new_string', 'old_string'] if order == 'new_first' else ['filepath', 'old_string', 'new_string']
                vals = {'filepath': p['filepath'], 'new_string': p['new'], 'old_string': p['old']}
                G = TC_START + BGP.render_call('edit_file', [(k, vals[k], 'str') for k in keys]) + TC_END
                grp = 'adversarial' if p['src'] == 'adversarial' else 'natural'
                if tok.decode(tok.encode(G, add_special_tokens=False)) != G:   # not emittable token-exactly: untestable
                    c['roundtrip_skipped_' + grp] += 1
                    continue
                cur_G['G'] = G
                body = {'messages': msgs, 'tools': tools, 'temperature': 0.2, 'top_p': 0.95, 'seed': 0,
                        'max_tokens': len(tok.encode(G, add_special_tokens=False)) + 64,
                        'chat_template_kwargs': {'enable_thinking': False}}
                rec = {'cfg': cfg_name}
                st, out = await px.engine_chat(body, cfg, rec)
                c['n'] += 1; c['n_' + grp] += 1
                tcs = (out.get('choices') or [{}])[0].get('message', {}).get('tool_calls') or [] if st == 200 else []
                args = json.loads(tcs[0]['function']['arguments']) if tcs else None
                raw_same = rec.get('raw') == G
                args_same = args == vals
                changed = not (raw_same and args_same)
                c['changed_' + grp] += changed
                c['raw_changed_' + grp] += not raw_same
                c['args_changed_' + grp] += not args_same
                if changed and len(ex) < 12:
                    ex.append({'grp': grp, 'order': order, 'raw_same': raw_same, 'args_same': args_same,
                               'events': [{k: e_.get(k) for k in ('ev', 'kind', 'run', 'key', 'in')} for e_ in rec.get('events', [])][:3]})
    asyncio.run(run_all())
    return c, ex


def cmd_p1e(a):
    from multiprocessing import Pool
    n = len(_qs_payloads())
    step = (n + a.np - 1) // a.np
    logdir = os.path.join(os.path.dirname(a.out) if a.out else OUTD, f'p1e_proxylogs_{a.tag}')
    res = {}
    for cfg_name in a.cfgs.split(','):
        tot = collections.Counter(); ex = []
        with Pool(a.np) as pl:
            for c, e_ in pl.imap_unordered(_p1e_worker, [(a.vendor, cfg_name, i, min(n, i + step), logdir) for i in range(0, n, step)]):
                tot.update(c); ex.extend(e_)
        res[cfg_name] = {'calls': tot['n'], 'natural_calls': tot['n_natural'], 'adversarial_calls': tot['n_adversarial'],
                         'changed_all': W(tot['changed_natural'] + tot['changed_adversarial'], tot['n']),
                         'changed_natural': W(tot['changed_natural'], tot['n_natural']),
                         'changed_adversarial': W(tot['changed_adversarial'], tot['n_adversarial']),
                         'raw_text_changed': {'natural': tot['raw_changed_natural'], 'adversarial': tot['raw_changed_adversarial']},
                         'delivered_args_changed': {'natural': tot['args_changed_natural'], 'adversarial': tot['args_changed_adversarial']},
                         'tokenizer_roundtrip_skipped': {'natural': tot['roundtrip_skipped_natural'], 'adversarial': tot['roundtrip_skipped_adversarial']},
                         'pass': (tot['changed_natural'] + tot['changed_adversarial']) == 0, 'examples': ex[:12]}
        print(cfg_name, json.dumps({k: v for k, v in res[cfg_name].items() if k != 'examples'}, default=str), flush=True)
    out = {'vendor': a.vendor, 'code_sha256': {f: hashlib.sha256(open(os.path.join(a.vendor, f), 'rb').read()).hexdigest()
                                               for f in ('proxy/e2e_proxy.py', 'proxy/gemma_protocol.py', 'export/quarantine_renderer.py')},
           'path': "Proxy.engine_chat (E's real request path) with a teacher-forced stub backend replaying each valid call",
           'criterion': 'P1: 0 of 229,414 valid QuoteStorm calls (incl. 1,200 adversarial) changed (raw text or delivered args)',
           'by_cfg': res}
    wjson(a.out or os.path.join(OUTD, f'p1e_quotestorm_{a.tag}.json'), out)


def cmd_p1(a):
    from multiprocessing import Pool
    n = len(_qs_payloads())
    step = (n + a.np - 1) // a.np
    tot = collections.Counter(); ex = []
    with Pool(a.np) as pl:
        for c, e_ in pl.imap_unordered(_p1_worker, [(a.vendor, 'quotestorm', i, min(n, i + step)) for i in range(0, n, step)]):
            tot.update(c); ex.extend(e_)
    out = {'vendor': a.vendor, 'code_sha256': {f: hashlib.sha256(open(os.path.join(a.vendor, f), 'rb').read()).hexdigest()
                                               for f in ('proxy/e2e_proxy.py', 'proxy/gemma_protocol.py', 'export/quarantine_renderer.py')},
           'calls': tot['n'], 'natural_calls': tot['n_natural'], 'adversarial_calls': tot['n_adversarial'],
           'changed_all': W(tot['changed_natural'] + tot['changed_adversarial'], tot['n']),
           'changed_natural': W(tot['changed_natural'], tot['n_natural']),
           'changed_adversarial': W(tot['changed_adversarial'], tot['n_adversarial']),
           'decode_time_changed': {'natural': tot['decode_changed_natural'], 'adversarial': tot['decode_changed_adversarial']},
           'posthoc_changed': {'natural': tot['posthoc_changed_natural'], 'adversarial': tot['posthoc_changed_adversarial']},
           'tokenizer_roundtrip_skipped': {'natural': tot['roundtrip_skipped_natural'], 'adversarial': tot['roundtrip_skipped_adversarial']},
           'pass': (tot['changed_natural'] + tot['changed_adversarial']) == 0, 'examples': ex[:12],
           'criterion': 'P1 byte identity: 0 of the 229,414 valid QuoteStorm calls (both key orders; 1,200 adversarial) changed by '
                        "the proxy's generate() (decode-time IPD, opener rule) or by its post-hoc intent_parse_args repair"}
    dst = a.out or os.path.join(OUTD, f'p1_quotestorm_{a.tag}.json')
    wjson(dst, out)
    print(json.dumps({k: v for k, v in out.items() if k != 'examples'}, default=str), flush=True)


def cmd_tfe(a):
    """Like `tf`, but through E's REAL request path Proxy.engine_chat (render -> generate() -> post-hoc -> response), with a
    hybrid backend: requests whose token prefix is consistent with the logged generation are answered from the log
    (stop strings with vLLM semantics; the confirmation token is the logged next token); everything else (likelihood
    scoring, resumed generation after a cut or rollback) goes live to the 31B server through the proxy's own backend."""
    import contextvars
    from types import SimpleNamespace
    EGP, EPX = load_e(a.vendor)

    class NS(SimpleNamespace):
        def __getattr__(self, k):
            return None
    logdir = os.path.join(OUTD, f'tfe_proxylogs_{a.set}_{a.tag}')
    pa = NS(configs=os.path.join(V, 'proxy/configs.json'), model_dir=MODEL_DIR_JUNE, logdir=logdir, cpu_workers=4,
            max_backend_conc=a.conc, call_timeout=3600.0, max_interventions=8, budget_slack=1536,
            prior=os.path.join(V, 'configs/channel_prior.json'), prior_source=a.prior_source, replay_plan=None, seed_salt=None,
            backend=a.base, served=a.model)
    px = EPX.Proxy(pa)
    engine = px.engine; tok = engine.tok
    EOS = 106
    assert EOS in engine.eos_ids
    CUR = contextvars.ContextVar('cur')
    live_backend = px.backend
    items = _gate_items() if a.set == 'gate' else _g1_items()
    if a.ids:
        keep = set(a.ids.split(','))
        items = [x for x in items if x['id'] in keep]
    if a.slips_only:
        slip_ids = {r['id'] for r in (json.loads(l) for l in open(GATE)) if r.get('status') == 'call' and r.get('site') is not None}
        items = [x for x in items if x['id'] in slip_ids]
    if a.seed_override is not None:
        for x in items:
            x['seed'] = a.seed_override
    out_path = os.path.join(OUTD, f'tfe_{a.set}_{a.tag}.jsonl')
    done = set()
    if os.path.exists(out_path):
        for l in open(out_path):
            d = json.loads(l)
            if d.get('status') == 'ok':
                done.add(d['id'])
    items = [x for x in items if x['id'] not in done]
    print(f'tfe {a.set} [{a.tag}] cfg {a.cfg}: {len(items)} items to do ({len(done)} done); vendor {V}', flush=True)

    async def hybrid_backend(path, body, timeout):
        it, rec, n = CUR.get()
        npr = rec.get('prompt_tokens')
        ids = body.get('prompt')
        if path == '/completions' and isinstance(ids, list) and npr is not None and not body.get('allowed_token_ids'):
            cur = engine.decode(ids[npr:])
            logged = it['gen']
            if logged.startswith(cur):
                rest = logged[len(cur):]
                if body.get('max_tokens') == 1 and 'stop' not in body:          # confirm_fn
                    if rest:
                        n['confirm_replayed'] += 1
                        t = tok.encode(rest[:64], add_special_tokens=False)[0]
                        return 200, json.dumps({'choices': [{'token_ids': [t], 'text': tok.decode([t])}]})
                elif not rest and it['logged_end'] == 'length':
                    # the logged generation hit its token cap here: end the turn (a repeated empty 'length' segment
                    # would make generate() loop forever); the proxy then verifies / post-processes as at a cap
                    n['logged_length_end'] += 1
                    return 200, json.dumps({'choices': [{'text': '', 'token_ids': [], 'finish_reason': 'stop',
                                                         'stop_reason': '__logged_length_end__'}]})
                elif rest or it['logged_end'] != 'live':                       # generation segment
                    n['replayed_segments'] += 1
                    best = None
                    for s_ in body.get('stop') or []:
                        i = rest.find(s_)
                        if i >= 0 and (best is None or i + len(s_) < best[0]):
                            best = (i + len(s_), s_)
                    if best is not None:
                        ch = rest[:best[0]]
                        return 200, json.dumps({'choices': [{'text': ch, 'token_ids': tok.encode(ch, add_special_tokens=False),
                                                             'finish_reason': 'stop', 'stop_reason': best[1]}]})
                    rid = tok.encode(rest, add_special_tokens=False) if rest else []
                    if it['logged_end'] == 'eos':
                        return 200, json.dumps({'choices': [{'text': rest, 'token_ids': rid + [EOS], 'finish_reason': 'stop', 'stop_reason': None}]})
                    if it['logged_end'] == 'live' and rest:
                        # logged prefix ends mid-call: replay it and let the model continue live IN THE SAME segment
                        n['live_gen_after_replay'] += 1
                        body2 = dict(body); body2['prompt'] = list(ids) + rid
                        body2['max_tokens'] = max(1, int(body.get('max_tokens') or 1) - len(rid))
                        st2, txt2 = await live_backend(path, body2, timeout)
                        if st2 != 200:
                            return st2, txt2
                        ch2 = json.loads(txt2)['choices'][0]
                        return 200, json.dumps({'choices': [{'text': rest + (ch2.get('text') or ''),
                                                             'token_ids': rid + list(ch2.get('token_ids') or []),
                                                             'finish_reason': ch2.get('finish_reason'), 'stop_reason': ch2.get('stop_reason')}]})
                    return 200, json.dumps({'choices': [{'text': rest, 'token_ids': rid, 'finish_reason': 'length', 'stop_reason': None}]})
        n['live_' + ('lp' if body.get('allowed_token_ids') else ('confirm' if body.get('max_tokens') == 1 and 'stop' not in body else 'gen'))] += 1
        return await live_backend(path, body, timeout)

    px.backend = hybrid_backend
    cfg = px.cfgs[a.cfg]

    async def main():
        await px.start(None)
        isem = asyncio.Semaphore(a.items)
        lock = asyncio.Lock()
        stats = collections.Counter()
        try:
            with open(out_path, 'a') as fo:
                async def run_item(it):
                    async with isem:
                        rec = {'cfg': a.cfg, 'task': 'tfe:' + it['id']}
                        n = collections.Counter()
                        CUR.set((it, rec, n))
                        body = {'model': a.model, 'messages': it['messages'], 'tools': it['tools'], 'temperature': it['temp'],
                                'top_p': 0.95, 'seed': it['seed'], 'max_tokens': len(tok.encode(it['gen'], add_special_tokens=False)) + it['max_new'],
                                'chat_template_kwargs': {'enable_thinking': True}}
                        out = {'id': it['id'], 'set': a.set, 'tag': a.tag, 'cfg': a.cfg, 'forced': it.get('forced', False)}
                        t0 = time.time()
                        try:
                            st, resp = await px.engine_chat(body, cfg, rec)
                            if st != 200:
                                raise RuntimeError(f'status {st}: {str(resp)[:300]}')
                            text = rec.get('raw') or ''
                            raw_calls = EGP.CALL_RE.findall(text)
                            meta = (rec.get('calls') or [None])[0]
                            call = None
                            if meta:
                                call = {'name': meta['name'], 'ok_emitted': meta.get('ok_emitted'), 'why': meta.get('why'),
                                        'posthoc_repaired': bool(meta.get('posthoc_repaired')), 'ok_delivered': meta.get('ok_delivered'),
                                        'args': meta.get('args'), 'raw_args': raw_calls[0][1] if raw_calls else None}
                            _i = text.find(TC_START)
                            out.update(status='ok', text_tail=text[-3000:], call_region=(text[_i:_i + 6000] if _i >= 0 else None),
                                       events=rec.get('events'), finish=rec.get('finish'),
                                       call=call, counts=dict(n), latency=time.time() - t0, prompt_tokens=rec.get('prompt_tokens'),
                                       identical_to_logged=(text == it['gen']) if it['logged_end'] != 'live' else None,
                                       n_tool_call_tags=text.count(TC_START))
                            if 'gold' in it and call:
                                gd = it['gold']; ag = call['args'] or {}
                                out['exact_intent'] = bool(call['ok_delivered'] and all(ag.get(k) == gd[k] for k in ('filepath', 'new_string', 'old_string')))
                                out['new_exact'] = ag.get('new_string') == gd['new_string']
                                out['old_exact'] = ag.get('old_string') == gd['old_string']
                            stats['ok'] += 1
                        except Exception:  # noqa: BLE001
                            import traceback
                            out.update(status='error', err=traceback.format_exc()[-1500:]); stats['error'] += 1
                        async with lock:
                            fo.write(json.dumps(out, default=str, ensure_ascii=False) + '\n'); fo.flush()
                            if (stats['ok'] + stats['error']) % 25 == 0:
                                print(time.strftime('%H:%M:%S'), dict(stats), flush=True)
                await asyncio.gather(*[run_item(it) for it in items])
        finally:
            await px.stop(None)
        print('done', dict(stats), flush=True)

    asyncio.run(main())


# ------------------------------------------------------------------------------------------------- live (proxy)
def cmd_live(a):
    import aiohttp
    ctx = []
    for l in open(CTX):
        ctx.append(json.loads(l))
        if len(ctx) >= 600:
            break
    out_path = os.path.join(OUTD, f'live_{a.cfg}.jsonl')
    done = set()
    if os.path.exists(out_path):
        for l in open(out_path):
            d = json.loads(l)
            if d.get('status') == 200:
                done.add(d['id'])
    todo = [c for c in ctx if c['id'] not in done]
    print(f'{a.cfg}: {len(todo)} to do ({len(done)} done)', flush=True)

    async def main():
        sem = asyncio.Semaphore(a.conc)
        conn = aiohttp.TCPConnector(limit=0, force_close=True)
        lock = asyncio.Lock()
        async with aiohttp.ClientSession(connector=conn, timeout=aiohttp.ClientTimeout(total=None)) as sess:
            with open(out_path, 'a') as fo:
                async def one(c):
                    body = {'model': 'gemma-4-31b', 'messages': c['messages'], 'tools': c['tools'], 'temperature': a.temp,
                            'top_p': a.top_p, 'seed': a.seed, 'max_tokens': a.max_tokens,
                            'chat_template_kwargs': {'enable_thinking': True}}
                    async with sem:
                        t0 = time.time()
                        try:
                            async with sess.post(f'{a.proxy}/{a.cfg}/v1/chat/completions', json=body,
                                                 headers={'X-E2E-Task': 'eq:' + c['id']}) as resp:
                                txt = await resp.text(); st = resp.status
                        except Exception as e:  # noqa: BLE001
                            txt, st = json.dumps({'error': repr(e)[:300]}), 599
                    rec = {'id': c['id'], 'cfg': a.cfg, 'status': st, 'latency': time.time() - t0}
                    try:
                        o = json.loads(txt)
                        ch = o['choices'][0]
                        rec.update(message=ch['message'], finish_reason=ch['finish_reason'], usage=o.get('usage'))
                    except Exception:  # noqa: BLE001
                        rec['body'] = txt[:2000]
                    async with lock:
                        fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()
                await asyncio.gather(*[one(c) for c in todo])
    asyncio.run(main())


# ------------------------------------------------------------------------------------------------- analysis
def census_args(name, args, schemas_b):
    """B's census criterion applied to delivered ARGUMENTS (as census_judge does after vLLM's parse)."""
    if not isinstance(args, dict):
        return False, 'no_call'
    if name not in schemas_b:
        return False, 'unknown_tool'
    sc = schemas_b[name]
    miss = [k for k in sc['required'] if k not in args]
    if miss:
        return False, 'missing:' + ','.join(miss)
    for k, v in args.items():
        if isinstance(v, str):
            for mm in BGP.SIG_ANY.finditer(v):
                if mm.group(2) in sc['props']:
                    return False, 'leak'
            if D in v or TC_END in v or TC_START in v:
                return False, 'leak_tok'
    if any(k not in sc['props'] for k in args):
        return False, 'extra_key'
    return True, 'ok'


def _gate_ref():
    ref = {}
    for l in open(GATE):
        r = json.loads(l)
        if r.get('status') == 'call':
            ref[r['id']] = r
    return ref


def summarize_offline():
    rows = [json.loads(l) for l in open(os.path.join(OUTD, 'offline_gate.jsonl'))]
    rend = json.load(open(os.path.join(OUTD, 'offline_render.json')))
    grp = lambda x: 'valid' if x['base_valid'] else ('slip' if x['ref_site'] is not None else 'invalid_other')
    paths = collections.Counter((grp(x), x['proxy']['path']) for x in rows)
    dc = [x for x in rows if grp(x) == 'slip' and x['proxy']['path'] == 'decode_time_cut']
    sl = [x for x in rows if grp(x) == 'slip']
    misses = [{'id': x['id'], 'forced': x['forced'], 'ref_site': x['ref_site'], 'proxy': x['proxy'].get('path'),
               'ok_delivered': x['proxy'].get('ok_delivered')} for x in sl if x['proxy']['path'] != 'decode_time_cut']
    valid = [x for x in rows if grp(x) == 'valid']
    return {'description': "E's decode-time IPD logic (stop strings, detect_slip, opener confirmation with the logged next token, "
                           "cut candidates, closer prior, decision on B's logged likelihoods) and post-hoc paths, replayed "
                           'on the 595 identical gate generations (CPU)',
            'render': {'proxy_render_equals_logged_prompt_length': '600/600', 'b_replay_render_equals_logged_prompt_length': '0/600',
                       'only_difference': "one space before the <|tool> declarations (system content as text parts vs plain string)",
                       'proxy_vs_b_render': rend['counts']},
            'paths_by_group': {f'{g}|{p_}': n for (g, p_), n in sorted(paths.items())},
            'valid_calls_changed': W(sum(x['proxy']['path'] != 'delivered' for x in valid), len(valid)),
            'slips': {'n': len(sl), 'decode_time_cut': len(dc),
                      'agree_site': W(sum(bool(x.get('agree_site')) for x in dc), len(dc)),
                      'agree_candidate_cuts': W(sum(bool(x.get('agree_cands')) for x in dc), len(dc)),
                      'agree_prior_values': W(sum(bool(x.get('prior_equal')) for x in dc), len(dc)),
                      'agree_chosen_cut_on_identical_lls': W(sum(x.get('agree_k') is True for x in dc), len(dc)),
                      'not_cut_at_decode_time': misses}}


def summarize_tf_gate(tag, kind='tfe'):
    path = os.path.join(OUTD, f'{kind}_gate_{tag}.jsonl')
    if not os.path.exists(path):
        return None
    ref = _gate_ref()
    ctx = {}
    for l in open(CTX):
        c = json.loads(l); ctx[c['id']] = c
        if len(ctx) >= 600:
            break
    rows = {}
    for l in open(path):
        d = json.loads(l)
        if d.get('status') == 'ok':
            rows[d['id']] = d
    agg = collections.Counter(); diffs = []
    for cid, r in ref.items():
        x = rows.get(cid)
        if x is None:
            agg['missing'] += 1; continue
        S = BGP.schema_from_tools(ctx[cid]['tools'])
        g = 'valid' if r['base']['strict_valid'] else ('slip' if r.get('site') is not None else 'invalid_other')
        agg['n_' + g] += 1
        ev = x.get('events') or []
        reps = [e_ for e_ in ev if e_.get('ev') == 'ipd_repair']
        call = x.get('call') or {}
        posthoc = bool(call.get('posthoc_repaired'))
        intervened = bool(reps) or posthoc
        # proxy delivery (lenient: whatever parses is delivered)
        p_deliv = bool(call)
        p_ok, p_why = census_args(call.get('name'), call.get('args'), S) if call else (False, 'no_call')
        raw_call = ('call:' + call['name'] + '{' + call['raw_args'] + '}') if call and call.get('raw_args') is not None else None
        p_strict = bool(raw_call and BGP.is_valid(raw_call, S))
        # B reference (IPD with fail-loud fallback)
        ip = r.get('i_plus') or r.get('i_nc')
        b_text = ip['text'] if ip else r['call']
        b_fin = ip['finished'] if ip else r['finished']
        b_strict = bool(b_fin and BGP.is_valid(b_text, S))
        b_args = BGP.parse_strict(b_text).args() if b_strict else None
        b_ok = b_strict and BGP.census_judge(b_text, S)[0]
        agg[g + '|proxy_intervened'] += intervened
        agg[g + '|proxy_delivered'] += p_deliv
        agg[g + '|proxy_delivered_malformed'] += p_deliv and not p_ok
        agg[g + '|proxy_delivered_clean'] += p_deliv and p_ok
        agg[g + '|proxy_no_call'] += not p_deliv
        agg[g + '|b_loud'] += not b_strict
        agg[g + '|b_delivered_malformed'] += b_strict and not b_ok
        agg[g + '|b_delivered_clean'] += b_ok
        agg[g + '|both_clean_same_args'] += bool(p_ok and b_ok and call.get('args') == b_args)
        if g == 'valid':
            agg['valid|identical_to_logged'] += bool(x.get('identical_to_logged'))
        if g == 'slip':
            k_ref = ((ip or {}).get('rounds') or [{}])[0].get('cut_choice', {}).get('k') if ip else None
            if reps and reps[0].get('kind') in ('closer', 'last_arg', 'key', 'end'):
                agg['slip|cut_by_rule'] += 1
                agg['slip|cut_agrees_with_B'] += reps[0].get('cut_k') == k_ref
            if not (p_ok and b_ok and call.get('args') == b_args):
                diffs.append({'id': cid, 'forced': r.get('forced'), 'run': (r.get('site') or {}).get('run'),
                              'proxy': {'intervened': intervened, 'events': [e_.get('kind') for e_ in reps], 'posthoc': posthoc,
                                        'clean': p_ok, 'why': p_why},
                              'b': {'clean': b_ok, 'loud': not b_strict},
                              'proxy_cut_k': reps[0].get('cut_k') if reps else None, 'b_cut_k': k_ref})
    n = sum(agg['n_' + g] for g in ('valid', 'slip', 'invalid_other'))
    out = {'tag': tag, 'n_calls': n, 'missing': agg['missing'],
           'valid_calls': {'n': agg['n_valid'], 'proxy_byte_identical': W(agg['valid|identical_to_logged'], agg['n_valid']),
                           'proxy_intervened': W(agg['valid|proxy_intervened'], agg['n_valid'])},
           'slips': {'n': agg['n_slip'], 'proxy_intervened': W(agg['slip|proxy_intervened'], agg['n_slip']),
                     'proxy_clean': W(agg['slip|proxy_delivered_clean'], agg['n_slip']),
                     'b_clean': W(agg['slip|b_delivered_clean'], agg['n_slip']),
                     'proxy_delivered_malformed': W(agg['slip|proxy_delivered_malformed'], agg['n_slip']),
                     'b_loud': W(agg['slip|b_loud'], agg['n_slip']),
                     'cut_by_rule': agg['slip|cut_by_rule'], 'cut_agrees_with_B': agg['slip|cut_agrees_with_B'],
                     'both_clean_identical_args': W(agg['slip|both_clean_same_args'], agg['n_slip'])},
           'all_calls': {'proxy_delivered_malformed': W(sum(agg[g + '|proxy_delivered_malformed'] for g in ('valid', 'slip', 'invalid_other')), n),
                         'b_delivered_malformed': W(sum(agg[g + '|b_delivered_malformed'] for g in ('valid', 'slip', 'invalid_other')), n),
                         'proxy_no_call': W(sum(agg[g + '|proxy_no_call'] for g in ('valid', 'slip', 'invalid_other')), n),
                         'b_loud': W(sum(agg[g + '|b_loud'] for g in ('valid', 'slip', 'invalid_other')), n)},
           'invalid_other': {'n': agg['n_invalid_other'], 'proxy_clean': agg['invalid_other|proxy_delivered_clean'],
                             'proxy_delivered_malformed': agg['invalid_other|proxy_delivered_malformed'],
                             'b_clean': agg['invalid_other|b_delivered_clean'], 'b_loud': agg['invalid_other|b_loud']},
           'slip_and_other_differences': diffs[:40]}
    return out


def summarize_tf_g1(tag, kind='tfe'):
    path = os.path.join(OUTD, f'{kind}_g1_{tag}.jsonl')
    if not os.path.exists(path):
        return None
    b = {}
    for l in open(os.path.join(HERE, 'out/rs279_31b.jsonl')):
        d = json.loads(l)
        if d.get('status') == 'ok':
            b[d['id']] = d
    rows = [json.loads(l) for l in open(path)]
    rows = [x for x in rows if x.get('status') == 'ok' and x['id'] in b]
    pe = [bool(x.get('exact_intent')) for x in rows]
    be = [bool(b[x['id']]['arms'].get('i_nc', {}).get('exact_intent')) for x in rows]
    return {'tag': tag, 'n': len(rows), 'proxy_exact_intent': W(sum(pe), len(pe)), 'b_ipd_exact_intent_same_states': W(sum(be), len(be)),
            'proxy_only': sum(p_ and not q for p_, q in zip(pe, be)), 'b_only': sum(q and not p_ for p_, q in zip(pe, be)),
            'proxy_new_exact': W(sum(bool(x.get('new_exact')) for x in rows), len(rows)),
            'proxy_old_exact': W(sum(bool(x.get('old_exact')) for x in rows), len(rows)),
            'proxy_intervened': W(sum(any(e_.get('ev') == 'ipd_repair' for e_ in (x.get('events') or [])) for x in rows), len(rows)),
            'note': ("same states and gold as B's G1 (C's corpus, base 31B, retry-derived intent); the proxy runs its own "
                     "generate() from the identical logged prefix (logged thought + raw call prefix up to the old_string "
                     "opener), the model live after the logged prefix; seeds differ from B's (B's G1 used Python's salted "
                     'hash, not reproducible), so the regenerated old_string is an independent sample')}


def summarize_live(logdir, tag):
    """Live HTTP runs through the proxy: first tool call of each gate context per cfg; B's census/slip detector on the
    raw text, E's classify on the delivered args; base vs ipd paired on the same seed and prompt."""
    import re as _re
    ctx = {}
    for l in open(CTX):
        c = json.loads(l); ctx[c['id']] = c
        if len(ctx) >= 600:
            break
    res = {'tag': tag, 'logdir': logdir, 'cfgs': {}}
    per = {}
    for cfg in ('base', 'ipd', 'fullp'):
        fp = os.path.join(logdir, f'proxy_{cfg}.jsonl')
        if not os.path.exists(fp):
            continue
        recs = {}
        for l in open(fp):
            d = json.loads(l)
            t = d.get('task') or ''
            if t.startswith('eq:') and d.get('status') == 200:
                recs[t[3:]] = d
        per[cfg] = recs
        agg = collections.Counter(); tools = collections.Counter()
        for cid, d in recs.items():
            S = BGP.schema_from_tools(ctx[cid]['tools'])
            raw = d.get('raw') or ''
            m = _re.search(_re.escape(TC_START) + r'(call:.*?)(' + _re.escape(TC_END) + r'|$)', raw, _re.S)
            calls = d.get('calls') or []
            first = calls[0] if calls else None
            name = (first or {}).get('name') or ('<unparsed>' if TC_START in raw else '<no_call>')
            tools[name] += 1
            agg['n'] += 1
            ev = d.get('events') or []
            agg['ipd_repair_events'] += sum(e_.get('ev') == 'ipd_repair' for e_ in ev)
            agg['contexts_with_intervention'] += any(e_.get('ev') in ('ipd_repair', 'posthoc_repair') for e_ in ev)
            if name != 'edit_file':
                continue
            agg['edit'] += 1
            call_text = m.group(1) if m else None
            fin = bool(m and m.group(2) == TC_END)
            if call_text is not None:
                import signal as _sig

                def _alarm(*_a):
                    raise TimeoutError()
                _sig.signal(_sig.SIGALRM, _alarm); _sig.alarm(5)
                try:
                    agg['edit_slip_site'] += BGP.first_slip_site(call_text, S, finished=fin) is not None
                except TimeoutError:
                    agg['edit_slip_site_timeout'] += 1
                finally:
                    _sig.alarm(0)
                _sig.signal(_sig.SIGALRM, _alarm); _sig.alarm(10)
                try:
                    agg['edit_census_bad_raw'] += not (fin and BGP.census_judge(call_text, S)[0])
                except TimeoutError:
                    agg['edit_census_timeout'] += 1; agg['edit_census_bad_raw'] += 1
                finally:
                    _sig.alarm(0)
                agg['edit_strict_valid_raw'] += bool(fin and BGP.is_valid(call_text, S))
            agg['edit_delivered_bad_E'] += not first.get('ok_delivered', False)
            okb, _ = census_args('edit_file', first.get('args'), S)
            agg['edit_delivered_bad_B'] += not okb
            agg['edit_posthoc_repaired'] += bool(first.get('posthoc_repaired'))
        res['cfgs'][cfg] = {'contexts': agg['n'], 'first_tool': tools.most_common(6), 'edit_calls': agg['edit'],
                            'edit_closer_slips_raw': W(agg['edit_slip_site'], agg['edit']),
                            'edit_slip_detector_timeouts_5s': agg['edit_slip_site_timeout'],
                            'edit_census_timeouts_10s_counted_malformed': agg['edit_census_timeout'],
                            'edit_census_malformed_raw': W(agg['edit_census_bad_raw'], agg['edit']),
                            'edit_delivered_malformed_B_census': W(agg['edit_delivered_bad_B'], agg['edit']),
                            'edit_delivered_malformed_E_classify': W(agg['edit_delivered_bad_E'], agg['edit']),
                            'edit_posthoc_repaired': agg['edit_posthoc_repaired'],
                            'contexts_with_intervention': agg['contexts_with_intervention'], 'ipd_repair_events': agg['ipd_repair_events']}
    if 'base' in per and 'ipd' in per:
        both = sorted(set(per['base']) & set(per['ipd']))
        same_prompt = [c_ for c_ in both if per['base'][c_].get('prompt_sha') == per['ipd'][c_].get('prompt_sha')]
        noint = [c_ for c_ in same_prompt if not any(e_.get('ev') in ('ipd_repair', 'ipd_rejected', 'ipd_no_repair', 'posthoc_repair')
                                                     for e_ in per['ipd'][c_].get('events') or [])]
        ident = sum(per['base'][c_].get('raw') == per['ipd'][c_].get('raw') for c_ in noint)
        res['paired_base_ipd'] = {'contexts': len(both), 'same_prompt': len(same_prompt),
                                  'ipd_no_stop_event': len(noint), 'raw_identical_when_no_stop_event': W(ident, len(noint)),
                                  'note': 'same seed + same prompt; identity is expected unless vLLM batch nondeterminism changes a sample'}
    return res


def live_paired(logdir):
    """Unconditional per-context outcome 'first call is edit_file and is delivered malformed (B census on the delivered
    args)', paired by context across cfgs; context bootstrap for the base->ipd/fullp relative reduction."""
    import random as _r
    ctx = {}
    for l in open(CTX):
        c = json.loads(l); ctx[c['id']] = c
        if len(ctx) >= 600:
            break
    per = {}
    for cfg in ('base', 'ipd', 'fullp'):
        fp = os.path.join(logdir, f'proxy_{cfg}.jsonl')
        if not os.path.exists(fp):
            continue
        d_ = {}
        for l in open(fp):
            d = json.loads(l)
            t = d.get('task') or ''
            if t.startswith('eq:') and d.get('status') == 200:
                cid = t[3:]
                S = BGP.schema_from_tools(ctx[cid]['tools'])
                calls = d.get('calls') or []
                first = calls[0] if calls else None
                bad = bool(first and first.get('name') == 'edit_file' and not census_args('edit_file', first.get('args'), S)[0])
                d_[cid] = int(bad)
        per[cfg] = d_
    out = {}
    for alt in ('ipd', 'fullp'):
        if 'base' not in per or alt not in per:
            continue
        ids = sorted(set(per['base']) & set(per[alt]))
        if not ids:
            continue
        b = [per['base'][i] for i in ids]; x = [per[alt][i] for i in ids]
        rng = _r.Random(7); bs = []
        for _ in range(2000):
            idx = [rng.randrange(len(ids)) for _ in ids]
            sb = sum(b[i] for i in idx); sx = sum(x[i] for i in idx)
            if sb:
                bs.append(1 - sx / sb)
        bs.sort()
        out[f'base_vs_{alt}'] = {'contexts': len(ids), 'base_malformed_edit_delivered': W(sum(b), len(ids)),
                                 f'{alt}_malformed_edit_delivered': W(sum(x), len(ids)),
                                 'relative_reduction': (1 - sum(x) / sum(b)) if sum(b) else None,
                                 'relative_reduction_context_boot95': [bs[int(0.025 * (len(bs) - 1))], bs[int(0.975 * (len(bs) - 1))]] if bs else None}
    return out


def cmd_analyze(a):
    # vLLM 0.19.1's _parse_gemma4_array can loop forever (and grow memory) on some malformed arrays; install the same
    # no-progress fix that workstream A and E's proxy use before any census judgement of fresh (live) samples
    _egp, _epx = load_e(os.path.join(HERE, 'proxy_vendor_fix'))
    _epx._install_array_hang_patch()
    out = {'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'job': ("PI 2026-11-04 18:15: does the SHIPPED proxy (workstream E, e2e_proxy.py cfg ipd/fullp) give the same results "
                   "as B's reference decoder (algorithm (i+), intent_decode.rollback_resume)?"),
           'code': {'prefix': open(os.path.join(HERE, 'proxy_vendor/VENDOR_MANIFEST.txt')).read().splitlines()}}
    fx = os.path.join(HERE, 'proxy_vendor_fix/VENDOR_MANIFEST.txt')
    if os.path.exists(fx):
        out['code']['postfix'] = open(fx).read().splitlines()
    out['offline_deterministic_prefix'] = summarize_offline()
    ofx = os.path.join(OUTD, 'offline_gate_efix_summary.json')
    if os.path.exists(ofx):
        out['offline_deterministic_postfix'] = {
            'description': ("E's fixed proxy (verify-then-repair): ipd_scan on the 595 identical gate generations vs B's logged "
                            "reference site / candidate cuts / prior / chosen cut (E's pick_cut mirror on B's logged lls)"),
            **json.load(open(ofx))}
    qs = os.path.join(OUTD, 'quotestorm_proxy.json')
    out['findings'] = {
        'F1_whitespace_variant': {
            'what': "a closer slip written '<closer>, <key>:' (space after the comma) is never stopped by the pre-fix proxy "
                    "(stop strings are '<closer>[\\n],<key>:' only) and its post-hoc text repair leaks the key into the value",
            'gate': {'k': 1, 'n': 104, 'id': 'ctx-311005d2c5 (forced call)'},
            'corpus_C_base_edit_slips_with_closer_pattern': W(50, 3209),
            'b_reference': 'repaired (relaxed grammar allows [ws] , [ws] KEY [ws] :)'},
        'F2_P1_byte_identity': {'what': 'valid calls altered by the proxy (decode-time cut before the call ends, and post-hoc '
                                        'intent_parse_args on values whose literal text looks like a leak)'}}
    for tag in ('prefix', 'efix', 'efix_renderer6b08'):
        for kind in ('p1e', 'p1'):
            pth = os.path.join(OUTD, f'{kind}_quotestorm_{tag}.json')
            if os.path.exists(pth):
                out['findings']['F2_P1_byte_identity'][f'{kind}_{tag}'] = json.load(open(pth))
    if os.path.exists(qs):
        out['findings']['F2_P1_byte_identity']['decode_time_only_sim_prefix'] = {k: v for k, v in json.load(open(qs)).items() if k != 'examples'}
    out['tf_gate'] = {t: summarize_tf_gate(t) for t in ('prefix', 'efix') if summarize_tf_gate(t)}
    out['tf_g1'] = {t: summarize_tf_g1(t) for t in ('prefix', 'efix') if summarize_tf_g1(t)}
    out['live_http'] = {}
    for tag in ('prefix', 'efix'):
        ld = os.path.join(OUTD, f'live_logs_{tag}')
        if os.path.isdir(ld):
            out['live_http'][tag] = summarize_live(ld, tag)
            out['live_http'][tag]['paired_unconditional'] = live_paired(ld)
            out['live_http'][tag]['gate_reference_natural_calls'] = {
                'base_census_malformed': {'k': 67, 'n': 406}, 'base_closer_slips': {'k': 63, 'n': 406},
                'after_B_IPD_census_malformed': {'k': 4, 'n': 406},
                'note': "B's discovery gate, natural (unforced) first edits, June template (1 token shorter prompts, §3.1)"}
    wjson(os.path.join(HERE, 'out/proxy_equivalence.json'), out)
    print(json.dumps({k: (list(v.keys()) if isinstance(v, dict) else v) for k, v in out.items()}, default=str)[:2000], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['offline', 'offline_fix', 'quotestorm', 'scores', 'live', 'tf', 'tfe', 'p1', 'p1e', 'analyze'])
    ap.add_argument('--cfgs', default='ipd,fullp')
    ap.add_argument('--out', default='')
    ap.add_argument('--vendor', default=V)
    ap.add_argument('--set', default='gate', choices=['gate', 'g1'])
    ap.add_argument('--tag', default='prefix')
    ap.add_argument('--ids', default='')
    ap.add_argument('--items', type=int, default=12)
    ap.add_argument('--prior_source', default='ft_edit')
    ap.add_argument('--slips_only', action='store_true')
    ap.add_argument('--seed_override', type=int, default=None)
    ap.add_argument('--np', type=int, default=8)
    ap.add_argument('--base', default='http://127.0.0.1:8302/v1')
    ap.add_argument('--model', default='gemma-4-31b')
    ap.add_argument('--conc', type=int, default=16)
    ap.add_argument('--proxy', default='http://127.0.0.1:8461')
    ap.add_argument('--cfg', default='ipd')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--temp', type=float, default=0.2)
    ap.add_argument('--top_p', type=float, default=0.95)
    ap.add_argument('--max_tokens', type=int, default=6144)
    a = ap.parse_args()
    {'offline': cmd_offline, 'quotestorm': cmd_quotestorm, 'scores': cmd_scores, 'live': cmd_live, 'tf': cmd_tf, 'p1': cmd_p1, 'p1e': cmd_p1e, 'tfe': cmd_tfe, 'offline_fix': cmd_offline_fix, 'analyze': cmd_analyze}.get(a.cmd, lambda a: None)(a)


if __name__ == '__main__':
    main()
