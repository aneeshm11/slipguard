"""PREREG_v2.5b (stack gain on Gemma-4-E4B; sha256 c78e7512...) -- B's v2.5 GLUE (d3440af4...) pointed at E4B.
Diffs vs v25/stack_runner.py: OUTD = v25b/out; the replay reads A's E4B confirmatory run (rCe4b_v2.jsonl) only (no O23);
server defaults http://127.0.0.1:8311/v1, gemma-4-e4b.  Tokenizer: the 31B path (tokenizer.json / tokenizer_config.json
byte-identical to E4B's, md5 72b10445 / 3b43bf42).
PREREG_v2.5 (stack gain; sha256 50f8a395...) -- B's GLUE: render -> base decode -> IPD -> strict parse -> log.
No modelling code: composes frozen/shipped code with recorded hashes:
  B  confirm/ (gemma_protocol b8dac830, intent_decode bda60a08, arms 5a521ae8, prior 47f2853a): is_valid, rollback_resume
  A  experiments/contagion/scripts: variants.build_prompt / make_variant / load_context / render (pathway builder),
     gemma_protocol.judge (C1 judge), run_onset.o1_messages (v2.3 O1)
  L  release/lib/src/slipguard: history.HistoryGuard, parse.parse_call + parse.schema.schema_error, templates
modes:
  cpu     N1 (HistoryGuard no-op on P0), render identity HistoryGuard(P1) == A's P8a, I2 (native results inverse of O1),
          template T-check (thinking on / off)                                    -> v25/out/cpu_checks.json (+ ids)
  f3      thinking-off leak: A1 P0 histories, enable_thinking=false, official vs guarded template, 32 tokens, shared seed
  replay  post-hoc IPD + strict parse on A's logged base emissions: C1 P8a (R1), C1 P0 (N3), v2.3 O0 (F2)
  live    L1: HistoryGuard(P1) -> official July template -> base decode (budget emulation) -> IPD -> strict; --o1 for F2-live
usage: stack_runner.py MODE [--base URL] [--conc 22 --workers 10] [--n N]
"""
import argparse, asyncio, copy, hashlib, importlib.util, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(HERE)
OUTD = os.path.join(HERE, 'out')   # = v25b/out
A_DIR = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
TOKP = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')
SG_SRC = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'slipguard/src')
sys.dont_write_bytecode = True


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m)
    return m


# ---- A's modules (their own 'gemma_protocol'), then B's frozen confirm/ copies under B's names
_saved = list(sys.path)
sys.path.insert(0, os.path.join(A_DIR, 'scripts'))
AGP = _load('gemma_protocol', os.path.join(A_DIR, 'scripts', 'gemma_protocol.py'))
AV = _load('variants', os.path.join(A_DIR, 'scripts', 'variants.py'))
_onset_src = open(os.path.join(A_DIR, 'scripts', 'run_onset.py')).read()
AONSET = {'__file__': os.path.join(A_DIR, 'scripts', 'run_onset.py'), '__name__': 'run_onset_defs'}
exec(compile(_onset_src.split("V.build_prompt = build_prompt")[0], 'run_onset_defs', 'exec'), AONSET)   # o1_messages only
sys.path[:] = _saved
del sys.modules['gemma_protocol'], sys.modules['variants']
sys.path.insert(0, os.path.join(B, 'confirm'))
import gemma_protocol as BGP  # noqa: E402  (B's frozen reference)
from intent_decode import Server, rollback_resume, ChannelPrior, ids_of, Pin  # noqa: E402
assert BGP.__file__.startswith(os.path.join(B, 'confirm'))
sys.path.insert(0, SG_SRC)
from slipguard.history import HistoryGuard  # noqa: E402
import slipguard.parse as SGP  # noqa: E402
from slipguard.parse.schema import schema_error, tool_schemas  # noqa: E402

MAN = json.load(open(os.path.join(CORPUS, 'manifest.json')))
TOOLS = MAN['tools']
AGP.set_profile(MAN['tool_profile'], tools=TOOLS, responses=MAN['harness'].get('responses'))
AGP.PROFILE['system_as_parts'] = (MAN['render'].get('system_content_form', 'parts') == 'parts')
TPL_PATH = os.path.join(CORPUS, 'chat_template.jinja')
TPL_OFFICIAL = os.path.join(SG_SRC, 'slipguard/template/gemma4_july_official.jinja')
TPL_GUARDED = os.path.join(SG_SRC, 'slipguard/template/gemma4_july_guarded.jinja')
SCHEMA_B = BGP.schema_from_tools(TOOLS)
SCHEMA_SG = tool_schemas(TOOLS)
TEMP, TOP_P, TOP_K, BUDGET, MAX_TOK = 1.0, 0.95, 64, 4096, 8192
_pj = json.load(open(os.path.join(B, 'confirm', 'prior_ft_edit.json')))
PRIOR = ChannelPrior(_pj['counts'], _pj.get('alpha', 0.5), name='ft_edit_frozen')
META = {}
for l in open(os.path.join(A_DIR, 'data/confirmatory/meta_S1.jsonl')):
    m = json.loads(l); META[m['id']] = m
A1 = [json.loads(l) for l in open(os.path.join(A_DIR, 'data/confirmatory/pools/S1_A1.jsonl'))]
B1 = [json.loads(l) for l in open(os.path.join(A_DIR, 'data/confirmatory/pools/S1_B1.jsonl'))][:600]
_tok = None


def tok():
    global _tok
    if _tok is None:
        from transformers import AutoTokenizer
        _tok = AutoTokenizer.from_pretrained(TOKP)
    return _tok


def seed_of(cid):                      # A's run_injection.seed_of (offset 0): one seed per state, shared with C1 / v2.3
    return int(hashlib.md5(cid.encode()).hexdigest()[:8], 16) % (2 ** 31 - 8)


def ctx(cid):
    return AV.load_context(META[cid])


def a_prompt(cid, pathway, k):
    """A's frozen pathway builder, exactly as the C1 / v2.3 runs called it (template = P's chat_template.jinja)."""
    if pathway in ('O0', 'O1'):
        msgs, tools = ctx(cid)
        if pathway == 'O1':
            msgs = AONSET['o1_messages'](msgs)
        return AV.build_prompt(tok(), META[cid], 'P0', 0, which=TPL_PATH, ctx=(msgs, tools))[0]
    return AV.build_prompt(tok(), META[cid], pathway, k, which=TPL_PATH)[0]


def render_msgs(msgs, tools, think=True, template=TPL_PATH):
    return AV.render(tok(), msgs, tools, (), which=template, think=think)


def p1_history(cid, k=1):
    msgs, tools = ctx(cid)
    vm, subs, info = AV.make_variant(msgs, META[cid]['prior'], 'P1', k)
    assert not subs
    return vm, tools, info.get('raw_by_id') or {}


def strict_sg(call_text, finished):
    """slipguard strict parser + schema (residual -> loud)."""
    if call_text is None or not finished:
        return False, 'unfinished'
    try:
        tc = SGP.parse_call('<|tool_call>' + call_text + '<tool_call|>')
    except Exception as e:
        return False, getattr(e, 'code', type(e).__name__)
    err = schema_error(tc, SCHEMA_SG)
    return (err is None), (None if err is None else getattr(err, 'code', 'schema'))


def wjson(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(o, open(p, 'w'), indent=1, default=str)


# --------------------------------------------------------------------------------------------------------- cpu checks
def mode_cpu(a):
    res = {'n1': [], 'r1_identity': [], 'i2': [], 'tcheck': []}
    HG, HGN = HistoryGuard(), HistoryGuard(native_tool_results=True)
    for row in A1:
        cid = row['context_id']
        msgs, tools = ctx(cid)
        # N1
        try:
            m2, rep = HG.apply(copy.deepcopy(msgs), tools)
            same_msgs = m2 == msgs
            same_render = same_msgs or render_msgs(m2, tools) == render_msgs(msgs, tools)
            res['n1'].append({'id': cid, 'msgs_identical': same_msgs, 'render_identical': same_render, 'report': rep[:3]})
        except Exception as e:
            res['n1'].append({'id': cid, 'exception': repr(e)[:300]})
        # render identity HistoryGuard(P1) == A's P8a
        try:
            vm, tools_, raw = p1_history(cid)
            h, rep = HG.apply(vm, tools_, raw_by_call_id=raw)
            r_h = render_msgs(h, tools_)
            r_a = a_prompt(cid, 'P8a', 1)
            res['r1_identity'].append({'id': cid, 'identical': r_h == r_a, 'n_tokens_A': len(ids_of(tok(), r_a)),
                                       'first_diff': None if r_h == r_a else next((i for i, (x, y) in enumerate(zip(r_h, r_a)) if x != y), min(len(r_h), len(r_a)))})
        except Exception as e:
            res['r1_identity'].append({'id': cid, 'identical': False, 'exception': repr(e)[:300]})
        # template T-check (P0 histories)
        try:
            last_tool = (msgs[-1].get('role') == 'tool')
            on_o = render_msgs(msgs, tools, True, TPL_OFFICIAL); on_g = render_msgs(msgs, tools, True, TPL_GUARDED)
            off_o = render_msgs(msgs, tools, False, TPL_OFFICIAL); off_g = render_msgs(msgs, tools, False, TPL_GUARDED)
            app = '<|channel>thought\n<channel|>'
            res['tcheck'].append({'id': cid, 'last_is_tool': last_tool, 'on_identical': on_o == on_g,
                                  'off_guarded_is_official_plus_closed_thought': off_g == off_o + app,
                                  'appended_ids': ids_of(tok(), off_g[len(off_o):]) if off_g.startswith(off_o) else None})
        except Exception as e:
            res['tcheck'].append({'id': cid, 'exception': repr(e)[:300]})
    for row in B1:
        cid = row['context_id']
        try:
            msgs, tools = ctx(cid)
            o1 = AONSET['o1_messages'](msgs)
            h, rep = HGN.apply(o1, tools)
            res['i2'].append({'id': cid, 'identical': render_msgs(h, tools) == a_prompt(cid, 'O0', 0)})
        except Exception as e:
            res['i2'].append({'id': cid, 'identical': False, 'exception': repr(e)[:300]})
    summ = {'N1': {'n': len(res['n1']), 'msgs_identical': sum(bool(x.get('msgs_identical')) for x in res['n1']),
                   'render_identical': sum(bool(x.get('render_identical')) for x in res['n1']),
                   'exceptions': [x['id'] for x in res['n1'] if 'exception' in x]},
            'R1_render_identity': {'n': len(res['r1_identity']), 'identical': sum(bool(x.get('identical')) for x in res['r1_identity']),
                                   'exceptions': [x['id'] for x in res['r1_identity'] if 'exception' in x]},
            'I2': {'n': len(res['i2']), 'identical': sum(bool(x.get('identical')) for x in res['i2']),
                   'exceptions': [x['id'] for x in res['i2'] if 'exception' in x]},
            'Tcheck': {'n': len(res['tcheck']), 'last_is_tool': sum(bool(x.get('last_is_tool')) for x in res['tcheck']),
                       'on_identical': sum(bool(x.get('on_identical')) for x in res['tcheck']),
                       'off_plus_closed_thought': sum(bool(x.get('off_guarded_is_official_plus_closed_thought')) for x in res['tcheck']),
                       'appended_ids_seen': sorted({json.dumps(x.get('appended_ids')) for x in res['tcheck']})[:5],
                       'exceptions': [x['id'] for x in res['tcheck'] if 'exception' in x]}}
    wjson(os.path.join(OUTD, 'cpu_checks.json'), {'summary': summ, 'detail': res})
    print(json.dumps(summ, indent=1))


# ---------------------------------------------------------------------------------------------------------------- f3
async def mode_f3(a, srv):
    out = os.path.join(OUTD, 'f3.jsonl')
    done = {(json.loads(l)['id'], json.loads(l)['arm']) for l in open(out)} if os.path.exists(out) else set()
    sem = asyncio.Semaphore(a.workers); lock = asyncio.Lock()
    with open(out, 'a') as fo:
        async def one(cid, arm):
            async with sem:
                msgs, tools = ctx(cid)
                rec = {'id': cid, 'arm': arm, 'seed': seed_of(cid), 'last_is_tool': msgs[-1].get('role') == 'tool'}
                try:
                    p = render_msgs(msgs, tools, False, TPL_OFFICIAL if arm == 'STOCK' else TPL_GUARDED)
                    c = await srv.complete(ids_of(tok(), p), max_tokens=32, temperature=TEMP, top_p=TOP_P, seed=rec['seed'], tag='f3')
                    rec.update(text=c['text'], finish=c.get('finish_reason'), n_prompt=len(ids_of(tok(), p)))
                except Exception as e:
                    rec['error'] = repr(e)[:300]
                async with lock:
                    fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()
        await asyncio.gather(*[one(r['context_id'], arm) for r in A1[:a.n] for arm in ('STOCK', 'GUARDED')
                               if (r['context_id'], arm) not in done])


# ------------------------------------------------------------------------------------------------------------ replay
def a_closed(d):
    return (d.get('s2_stop', d.get('s1_stop')) == 49)


async def ipd_and_strict(srv, prefix_text, call, fin, seed, pin=True):
    """B's IPD (verify-then-repair) on the first call, then slipguard's strict parse. Returns a record fragment."""
    rec = {'base_strictly_valid_B': bool(fin and BGP.is_valid(call, SCHEMA_B))}
    if rec['base_strictly_valid_B']:
        text, ffin, changed, rounds = call, fin, False, []
    else:
        pid = ids_of(tok(), prefix_text)
        async with Pin(srv, pid):
            r = await rollback_resume(srv, tok(), prefix_text, call, fin, SCHEMA_B, rule='nc', prior=PRIOR,
                                      rules=('closer', 'opener'), max_tokens=4096, temperature=TEMP, top_p=TOP_P,
                                      seed=seed % 1_000_000, prefix_ids=pid)
        text, ffin, changed, rounds = r['text'], r['finished'], r['changed'], r['rounds']
    ok_sg, why_sg = strict_sg(text, ffin)
    ok_b = bool(ffin and BGP.is_valid(text, SCHEMA_B))
    rec.update(final_text=text, final_finished=ffin, ipd_changed=changed, ipd_rounds=len(rounds),
               ipd_kinds=[x.get('kind') for x in rounds], strict_sg=ok_sg, strict_sg_why=why_sg, strict_B=ok_b,
               parser_disagreement=(ok_sg != ok_b))
    return rec


async def mode_replay(a, srv):
    out = os.path.join(OUTD, 'replay.jsonl')
    done = {(json.loads(l)['id'], json.loads(l)['pathway']) for l in open(out)} if os.path.exists(out) else set()
    want = {'C1': {'P8a', 'P0'}, 'O23': {'O0'}}
    srcs = [(os.path.join(A_DIR, 'out/main/rCe4b_v2.jsonl'), 'C1', {r['context_id'] for r in A1})]   # E4B C1 only
    jobs = []
    for path, tag, ids in srcs:
        for l in open(path):
            d = json.loads(l)
            if d.get('id') in ids and d.get('pathway') in want[tag] and not d.get('error') and (d['id'], d['pathway']) not in done:
                jobs.append((tag, d))
    print(f'replay jobs {len(jobs)} ({len(done)} done)', flush=True)
    sem = asyncio.Semaphore(a.workers); lock = asyncio.Lock()
    with open(out, 'a') as fo:
        async def one(tag, d):
            async with sem:
                rec = {'id': d['id'], 'pathway': d['pathway'], 'k': d['k'], 'src': tag, 'seed': d['seed'],
                       'opened_call': bool(d.get('opened_call')), 'budget_forced': bool(d.get('budget_forced'))}
                try:
                    p = a_prompt(d['id'], d['pathway'], d['k'])   # main thread: A's parse_args uses signal.alarm
                    n = len(ids_of(tok(), p))
                    rec['n_prompt_match'] = (n == d['n_prompt'])
                    if not rec['n_prompt_match']:
                        rec['status'] = 'render_mismatch'
                    elif not d.get('opened_call') or d.get('s2_text') is None:
                        rec['status'] = 'no_call'
                    else:
                        fin = a_closed(d)
                        rec.update(base_finished=fin, status='ok',
                                   **(await ipd_and_strict(srv, p + (d.get('s1_text') or '') + '<|tool_call>', d['s2_text'], fin, d['seed'])))
                except Exception as e:
                    rec.update(status='error', err=repr(e)[:400])
                async with lock:
                    fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()
        await asyncio.gather(*[one(t, d) for t, d in jobs])


# -------------------------------------------------------------------------------------------------------------- live
async def stage_a(srv, p0, seed):
    """base decoding to the end of the first tool call; thinking budget emulated (as B's frozen confirm_runner)."""
    used, pre, hit = 0, '', None
    if p0.endswith('<|channel>thought\n'):
        c1 = await srv.complete(p0, max_tokens=BUDGET, stop=['<channel|>'], temperature=TEMP, top_p=TOP_P, seed=seed, tag='think')
        used = c1['_usage'].get('completion_tokens') or 0
        pre = c1['text'] + '<channel|>'
        hit = c1.get('finish_reason') == 'length'
    c2 = await srv.complete(p0 + pre, max_tokens=max(256, MAX_TOK - used), stop=['<tool_call|>'], temperature=TEMP,
                            top_p=TOP_P, seed=seed + 1, tag='answer')
    t = pre + c2['text']
    fin = c2.get('finish_reason') == 'stop' and c2.get('stop_reason') == '<tool_call|>'
    return t, fin, hit


async def mode_live(a, srv):
    name = 'live_f2' if a.o1 else 'live_l1'
    out = os.path.join(OUTD, name + '.jsonl')
    done = {json.loads(l)['id'] for l in open(out)} if os.path.exists(out) else set()
    rows = (B1[:100] if a.o1 else A1)[:a.n]
    HG = HistoryGuard(native_tool_results=True) if a.o1 else HistoryGuard()
    sem = asyncio.Semaphore(a.workers); lock = asyncio.Lock()
    with open(out, 'a') as fo:
        async def one(cid):
            async with sem:
                rec = {'id': cid, 'arm': name, 'seed': seed_of(cid)}
                t0 = time.time()
                try:
                    if a.o1:
                        msgs, tools = ctx(cid); hist, rep = HG.apply(AONSET['o1_messages'](msgs), tools)
                    else:
                        vm, tools, raw = p1_history(cid); hist, rep = HG.apply(vm, tools, raw_by_call_id=raw)
                    p0 = render_msgs(hist, tools)
                    rec['n_prompt'] = len(ids_of(tok(), p0))
                    t, fin, hit = await stage_a(srv, p0, rec['seed'])
                    rec['budget_hit'] = hit
                    if '<|tool_call>' not in t:
                        rec.update(status='no_call', tail=t[-300:])
                    else:
                        i = t.index('<|tool_call>')
                        rec.update(status='ok', s1_text=t[:i], s2_text=t[i + len('<|tool_call>'):], base_finished=fin,
                                   **(await ipd_and_strict(srv, p0 + t[:i] + '<|tool_call>', t[i + len('<|tool_call>'):], fin, rec['seed'])))
                except Exception as e:
                    rec.update(status='error', err=repr(e)[:400])
                rec['wall'] = time.time() - t0
                async with lock:
                    fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()
        await asyncio.gather(*[one(r['context_id']) for r in rows if r['context_id'] not in done])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['cpu', 'f3', 'replay', 'live'])
    ap.add_argument('--base', default='http://127.0.0.1:8311/v1')
    ap.add_argument('--model', default='gemma-4-e4b')
    ap.add_argument('--conc', type=int, default=22)
    ap.add_argument('--workers', type=int, default=10)
    ap.add_argument('--n', type=int, default=100000)
    ap.add_argument('--o1', action='store_true')
    a = ap.parse_args()
    if a.mode == 'cpu':
        return mode_cpu(a)

    async def run():
        srv = Server(a.base, a.model, conc=a.conc, sampling_extra={'top_k': TOP_K})
        try:
            await {'f3': mode_f3, 'replay': mode_replay, 'live': mode_live}[a.mode](a, srv)
        finally:
            print('done', dict(srv.stats), flush=True)
            await srv.close()
    asyncio.run(run())


if __name__ == '__main__':
    main()
