"""Offline tests of the proxy's segmented generation (thinking-budget emulation + intent-preserving decoding as
VERIFY-THEN-REPAIR, workstream B's algorithm (i+)) against a scripted mock backend that mimics vLLM /v1/completions
stop/max_tokens/EOS semantics."""
import os  # added by the repo export (paths are env/config driven)
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'proxy'))
import e2e_proxy as ep  # noqa: E402
import gemma_protocol as gp  # noqa: E402

MD = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')
eng = ep.Engine(MD)
D = gp.D
SCH = gp.tool_schemas([{'type': 'function', 'function': {'name': 'edit_file', 'parameters': {'type': 'object', 'properties': {
    'filepath': {'type': 'string'}, 'old_string': {'type': 'string'}, 'new_string': {'type': 'string'},
    'allow_multiple': {'type': 'boolean'}}, 'required': ['filepath', 'old_string', 'new_string']}}},
    {'type': 'function', 'function': {'name': 'read_file', 'parameters': {'type': 'object', 'properties': {
        'filepath': {'type': 'string'}}, 'required': ['filepath']}}}])
EOS = '<|tool_response>'
TCS, TCE = gp.TC_START, gp.TC_END
VALID = f'{TCS}call:edit_file{{filepath:{D}a.py{D},old_string:{D}y = 1{D},new_string:{D}y = 2{D}}}{TCE}'
SLIP = f'{TCS}call:edit_file{{filepath:{D}a.py{D},new_string:{D}y = 2`,old_string:{D}y = 1{D}}}{TCE}'
FIXED = f'{TCS}call:edit_file{{filepath:{D}a.py{D},new_string:{D}y = 2{D},old_string:{D}y = 1{D}}}{TCE}'
CONT_OLD = f',old_string:{D}y = 1{D}}}{TCE}' + EOS          # model's continuation after a repaired new_string
BASE_PROMPT = ('<|turn>user\nfix<turn|>\n<|turn>model\n<|tool_call>call:read_file{filepath:<|"|>a.py<|"|>}<tool_call|>'
               '<|tool_response>response:read_file{value:<|"|>ok<|"|>}<tool_response|><|channel>thought\n')
base_ids = eng.encode(BASE_PROMPT)
PRIOR = gp.ChannelPrior(json.load(open(Path(__file__).resolve().parents[1] / 'configs/channel_prior.json'))['priors']['ft_edit'])
n_ok = 0


def check(c, m):
    global n_ok
    assert c, m
    n_ok += 1


def make_backend(script_fn, log):
    async def backend(ids, max_tokens, stops):
        gen = eng.decode(ids[len(base_ids):])
        cont = script_fn(gen)
        log.append((gen, max_tokens, list(stops)))
        cids = eng.encode(cont)
        out_ids, fr, sr = [], 'length', None
        for t in cids:
            if len(out_ids) >= max_tokens:
                break
            if eng.decode([t]) == EOS:  # EOS-like stop token: generated, not in text
                out_ids.append(t)
                fr, sr = 'stop', t
                break
            out_ids.append(t)
            txt = eng.decode(out_ids)
            hit = [s for s in stops if s in txt]
            if hit:
                s = min(hit, key=lambda s: txt.index(s) + len(s))
                return 200, {'token_ids': out_ids, 'text': txt[:txt.index(s) + len(s)], 'finish_reason': 'stop', 'stop_reason': s}
        else:
            if fr != 'stop':
                fr = 'stop' if not cids or len(out_ids) == len(cids) else 'length'
        text = eng.decode([t for t in out_ids if eng.decode([t]) != EOS])
        return 200, {'token_ids': out_ids, 'text': text, 'finish_reason': fr, 'stop_reason': sr}
    return backend


def model(thinking_words, answer, think_extra='', resumes=()):
    """deterministic 'model': think N words, end thinking, emit `answer` (calls/text), EOS. After a rollback the
    generated text ends with a repaired prefix; `resumes` = [(suffix, continuation)] says how the model goes on."""
    full = ' w' * thinking_words + think_extra + '<channel|>' + answer + EOS

    def fn(gen):
        if full.startswith(gen):
            return full[len(gen):]
        for suf, cont in resumes:
            if gen.endswith(suf):
                return cont
        if gen.endswith('<channel|>'):  # forced end of thinking
            return answer + EOS
        raise AssertionError(f'unexpected state: {gen[-100:]!r}')
    return fn


def make_lp(table, default=-0.1, fail=False):
    """mock exact forced-token logprob: table maps (prefix-text suffix, target text) -> logprob"""
    async def lp(ids, target):
        if fail:
            return None
        gen = eng.decode(ids[len(base_ids):])
        t = eng.decode([target])
        for (suf, tt), v in table.items():
            if t == tt and gen.endswith(suf):
                return v
        return default
    return lp


async def run(fn, *, budget=100, ipd=True, max_total=4000, lp=None, prior=PRIOR, rules=None, user_stops=(),
              max_rounds=gp.IPD_MAX_ROUNDS):
    log = []
    g = await ep.generate(eng, base_ids, max_total=max_total, budget=budget, user_stops=list(user_stops), schemas=SCH,
                          backend_fn=make_backend(fn, log), budget_slack=20, max_interventions=8,
                          lp_fn=lp, prior=prior, ipd=ipd, rules=rules, max_rounds=max_rounds)
    ids = g['gen_ids']
    txt = eng.decode(ids)
    return g, txt, log


def answer_args(txt):
    t = txt[:-len(EOS)] if txt.endswith(EOS) else txt
    _, _, calls = eng.parse(t)
    return [(c['name'], json.loads(c['arguments'])) for c in calls]


def reps(g):
    return [e for e in g['events'] if e['ev'] == 'ipd_repair']


async def main():
    # 1. budget not binding, IPD off: one backend request, output == script, no IPD stop strings ever sent
    g, txt, log = await run(model(5, VALID), ipd=False)
    check(len(log) == 1 and txt == ' w' * 5 + '<channel|>' + VALID + EOS and log[0][2] == [], f'single segment identity {txt!r}')
    check(not g['events'], 'no events')
    # 2. budget binding: prompt has 2 thinking tokens ("thought\n"); budget 10 -> 8 sampled thinking tokens then forced end
    g, txt, log = await run(model(40, VALID), budget=10, ipd=False)
    ev = [e for e in g['events'] if e['ev'] == 'budget_forced_end']
    check(len(ev) == 1, f'forced end once {g["events"]}')
    check(txt.startswith(' w' * 8 + '<channel|>') and txt.endswith(VALID + EOS), f'budget cut at 8 {txt[:60]!r}')
    check(log[0][1] == 8 + 20, f'first segment capped at budget_left+slack {log[0][:2]}')

    # 3. closer slip: the call is generated to the end FIRST, verified (not strictly valid), rolled back to the cut,
    #    <|"|> inserted, generation resumed -> valid call; no scorer -> whole-run cut (B's 'max')
    m3 = model(5, SLIP, resumes=[(f'y = 2{D}', CONT_OLD)])
    g, txt, log = await run(m3)
    r = reps(g)
    check(len(log) == 2 and log[0][2] == [] and log[1][0].endswith(f'y = 2{D}'), f'generate, then resume after the cut {[(x[0][-30:], x[2]) for x in log]}')
    check(len(r) == 1 and r[0]['kind'] == 'key' and r[0]['in'] == 'new_string' and r[0]['key'] == 'old_string'
          and r[0]['run'] == '`' and r[0]['cut_k'] == 0 and r[0]['closer'] == '`' and r[0]['how'] == 'whole_run(no_scorer)', f'repair {r}')
    check(r[0]['discarded_chars'] > 0 and g['ipd_audit']['strict_valid'] == 1, f"discard + final audit {r[0]['discarded_chars']} {g['ipd_audit']}")
    check(txt.endswith(FIXED + EOS), f'repaired text {txt[-120:]!r}')
    check(answer_args(txt) == [('edit_file', {'filepath': 'a.py', 'new_string': 'y = 2', 'old_string': 'y = 1'})], f'parsed {answer_args(txt)}')
    # 4. without IPD the slip passes through unchanged (vLLM's lenient parser loses old_string)
    g, txt, log = await run(m3, ipd=False)
    check('old_string' not in answer_args(txt)[0][1] and len(log) == 1, 'base keeps the slip')

    # 5. P1 byte identity: VALID calls whose strings literally contain look-alike + ',KEY:' are never touched
    LIT = f'{TCS}call:edit_file{{filepath:{D}a.py{D},new_string:{D}s = "``,old_string:"{D},old_string:{D}y = 1{D}}}{TCE}'
    g, txt, log = await run(model(5, LIT))
    check(len(log) == 1 and not g['events'] and txt == ' w' * 5 + '<channel|>' + LIT + EOS, f'adversarial literal identity {g["events"]}')
    check(g['ipd_audit'] == {'calls': 1, 'strict_valid': 1, 'invalid': 0, 'no_site': 0, 'site_in_undeclared_key': 0,
                             'rounds_exhausted': 0}, f"audit {g['ipd_audit']}")
    LIT2 = f"{TCS}call:edit_file{{filepath:{D}a.py{D},old_string:{D}x = 0{D},new_string:{D}s = '`,allow_multiple:true'{D}}}{TCE}"
    g, txt, log = await run(model(5, LIT2))
    check(len(log) == 1 and not g['events'] and txt.endswith(LIT2 + EOS), 'boolean-opener literal identity')

    # 6. B's gate whitespace-variant slip (", new_string:" with a space; out/v3_r31_on_june.jsonl
    #    ctx-311005d2c5): repaired at the same site and cut as B's reference, and the final call
    #    equals B's reference output when the model continues as it did there
    GATE = (f'{TCS}call:edit_file{{filepath:{D}repro.py{D}, old_string:{D}dirs = PlatformDirs()`, new_string:{D}'
            f'dirs = PlatformDirs(appname="myapp", appauthor="myauthor")`}}{TCE}')
    B_OUT = (f'call:edit_file{{filepath:{D}repro.py{D}, old_string:{D}dirs = PlatformDirs(){D}, new_string:{D}'
             f'dirs = PlatformDirs(appname="test_app", appversion="1.0"){D}}}')
    m6 = model(5, GATE, resumes=[(f'PlatformDirs(){D}', B_OUT[B_OUT.index(f'PlatformDirs(){D}') + len(f'PlatformDirs(){D}'):] + TCE + EOS)])
    g, txt, log = await run(m6, lp=make_lp({}))
    r = reps(g)
    check(len(r) == 1 and r[0]['kind'] == 'key' and r[0]['in'] == 'old_string' and r[0]['key'] == 'new_string'
          and r[0]['run'] == '`' and r[0]['gap'] == '' and r[0]['cut_k'] == 0 and r[0]['how'] == 'noisy_channel', f'gate site {r}')
    check(txt.endswith(TCS + B_OUT + TCE + EOS) and gp.strictly_valid(B_OUT, gp.b_schema(SCH)), f'gate final == B reference {txt[-200:]!r}')

    # 7. B's noisy-channel cut INSIDE the run keeps a content backtick ('y = `x`' + closer '`')
    SLIP2 = f'{TCS}call:edit_file{{filepath:{D}a.py{D},new_string:{D}y = `x``,old_string:{D}y = 1{D}}}{TCE}'
    m7 = model(5, SLIP2, resumes=[(f'y = `x`{D}', CONT_OLD), (f'y = `x{D}', CONT_OLD)])
    lp7 = make_lp({('y = `x`', D): -0.5, ('y = `x', D): -8.0, ('y = `x``', D): -6.0})
    g, txt, log = await run(m7, lp=lp7)
    r = reps(g)
    check(len(r) == 1 and r[0]['how'] == 'noisy_channel' and r[0]['cut_k'] == 1 and r[0]['closer'] == '`', f'nc cut {r}')
    check(answer_args(txt)[0][1] == {'filepath': 'a.py', 'new_string': 'y = `x`', 'old_string': 'y = 1'}, f'content keeps its backtick {answer_args(txt)}')
    # 7b. likelihood alone prefers keeping the backtick (k_lik=1), the closer prior overrules (k=0)
    m7b = model(5, SLIP, resumes=[(f'y = 2{D}', CONT_OLD)])
    g, txt, log = await run(m7b, lp=make_lp({('y = 2', D): -6.25, ('y = 2`', D): -4.89}))
    r = reps(g)
    check(len(r) == 1 and r[0]['cut_k'] == 0 and r[0]['k_lik'] == 1 and txt.endswith(FIXED + EOS), f'nc vs lik {r}')
    # 7c. scoring failure -> whole run is the closer
    g, txt, log = await run(m7, lp=make_lp({}, fail=True))
    r = reps(g)
    check(len(r) == 1 and r[0]['how'] == 'whole_run(scoring_failed)' and r[0]['closer'] == '``', f'fallback {r}')

    # 8. opener drift (B's opener rule): old_string opened with a Python triple quote -> rollback right after
    #    'old_string:', <|"|> forced, resume
    TQ = '"' * 3
    OPN = f'{TCS}call:edit_file{{filepath:{D}a.py{D},old_string:{TQ}a = 1{TQ},new_string:{D}a = 2{D}}}{TCE}'
    m8 = model(5, OPN, resumes=[(f'old_string:{D}', f'a = 1{D},new_string:{D}a = 2{D}}}{TCE}' + EOS)])
    g, txt, log = await run(m8)
    r = reps(g)
    check(len(r) == 1 and r[0]['kind'] == 'opener' and r[0]['key'] == 'old_string' and r[0]['lead'].startswith(TQ), f'opener {r}')
    check(answer_args(txt) == [('edit_file', {'filepath': 'a.py', 'old_string': 'a = 1', 'new_string': 'a = 2'})], 'opener repaired')
    # 8b. B's opener rule also covers a BARE string value that vLLM would parse leniently (strict guard decides)
    BARE = f'{TCS}call:edit_file{{filepath:a.py,old_string:{D}y = 1{D},new_string:{D}y = 2{D}}}{TCE}'
    m8b = model(5, BARE, resumes=[(f'filepath:{D}', f'a.py{D},old_string:{D}y = 1{D},new_string:{D}y = 2{D}}}{TCE}' + EOS)])
    g, txt, log = await run(m8b)
    r = reps(g)
    check(len(r) == 1 and r[0]['kind'] == 'opener' and r[0]['key'] == 'filepath' and txt.endswith(VALID + EOS), f'bare value -> opener rule {r}')
    # 8c. separator drift 'new_string="..."' is NOT in B's (i+) rules: delivered as generated; opt-in rule 'kwarg' repairs it
    KW = f'{TCS}call:edit_file{{filepath:{D}a.py{D},old_string:{D}y = 1{D},new_string="y = 2"}}{TCE}'
    m8c = model(5, KW, resumes=[(f'new_string:{D}', f'y = 2{D}}}{TCE}' + EOS)])
    g, txt, log = await run(m8c)
    check(not reps(g) and txt.endswith(KW + EOS) and g['ipd_audit']['no_site'] == 1, f"kwarg drift untouched by default {g['ipd_audit']}")
    g, txt, log = await run(m8c, rules=('closer', 'opener', 'kwarg'))
    r = reps(g)
    check(len(r) == 1 and r[0]['kind'] == 'kwarg' and txt.endswith(VALID + EOS), f'kwarg opt-in {r}')

    # 9. a slip inside an argument NOT declared in the schema is never repaired (declared-keys-only restriction)
    #    (B's reference finder WOULD cut here: its strict scan reaches the undeclared key's string first)
    UND = f'{TCS}call:edit_file{{insert_after:{D}x`,old_string:{D}y = 1{D},filepath:{D}a.py{D},new_string:{D}z{D}}}{TCE}'
    bs = gp.b_schema(SCH)
    site = gp.BG.first_violation(UND[len(TCS):-len(TCE)], bs, finished=True, rules=gp.IPD_RULES)
    check(site is not None and site.key == 'insert_after', f'B finder returns a site in the undeclared key {site}')
    g, txt, log = await run(model(5, UND))
    check(not reps(g) and len(log) == 1 and g['ipd_audit']['site_in_undeclared_key'] == 1, f"undeclared key {g['ipd_audit']}")
    # 9b. undeclared key AFTER a declared one: B's scan stops at the first locally inconsistent string (filepath) and
    #     finds no site there -> nothing to repair (same outcome as B's reference)
    UND2 = f'{TCS}call:edit_file{{filepath:{D}a.py{D},insert_after:{D}x`,old_string:{D}y = 1{D},new_string:{D}z{D}}}{TCE}'
    g, txt, log = await run(model(5, UND2))
    check(not reps(g) and g['ipd_audit']['no_site'] == 1, f"undeclared key after filepath {g['ipd_audit']}")

    # 10. last argument closed by a look-alike before '}' (B's 'end' site)
    END = f'{TCS}call:edit_file{{filepath:{D}a.py{D},old_string:{D}y = 1{D},new_string:{D}y = 2`}}{TCE}'
    m10 = model(5, END, resumes=[(f'new_string:{D}y = 2{D}', f'}}{TCE}' + EOS)])
    g, txt, log = await run(m10)
    r = reps(g)
    check(len(r) == 1 and r[0]['kind'] == 'end' and r[0]['in'] == 'new_string' and txt.endswith(VALID + EOS), f'end site {r}')

    # 11. budget overflow + slip
    g, txt, log = await run(model(40, SLIP, resumes=[(f'y = 2{D}', CONT_OLD)]), budget=10)
    check([e['ev'] for e in g['events']] == ['budget_forced_end', 'ipd_repair'] and txt.endswith(FIXED + EOS), f'both events {g["events"]}')

    # 12. a model that keeps slipping in successive strings of the same call: at most max_rounds repairs per call,
    #     then the call is delivered as generated (here max_rounds=2 and a chain of three slips)
    G12 = f'{TCS}call:edit_file{{filepath:{D}a.py`,old_string:{D}y = 1{D},new_string:{D}y = 2{D}}}{TCE}'
    C1 = f',old_string:{D}y = 1`,new_string:{D}y = 2{D}}}{TCE}' + EOS
    C2 = f',new_string:{D}y = 2`}}{TCE}' + EOS
    m12 = model(5, G12, resumes=[(f'a.py{D}', C1), (f'y = 1{D}', C2)])
    g, txt, log = await run(m12, max_rounds=2)
    r = reps(g)
    check([(x['in'], x['round']) for x in r] == [('filepath', 0), ('old_string', 1)] and len(log) == 3
          and g['ipd_audit']['rounds_exhausted'] == 1 and txt.endswith(f'y = 2`}}{TCE}' + EOS), f"rounds cap {r} {g['ipd_audit']}")

    # 13. verify-then-repair also runs when the turn ends at a USER stop string (not only at EOS)
    m13 = model(5, SLIP + '\nSTOP here', resumes=[(f'y = 2{D}', CONT_OLD[:-len(EOS)] + '\nSTOP here' + EOS)])
    g, txt, log = await run(m13, user_stops=['\nSTOP'])
    check(len(reps(g)) == 1 and g['finish'] == 'stop' and g['stop_reason'] == '\nSTOP' and txt.endswith(FIXED), f'user stop {g["events"]} {txt[-80:]!r}')

    # 14. two calls in one turn: the valid first call is kept byte-identical, the slipped second call is repaired
    TWO = VALID + SLIP
    m14 = model(5, TWO, resumes=[(f'y = 2{D}', CONT_OLD)])
    g, txt, log = await run(m14)
    r = reps(g)
    check(len(r) == 1 and r[0]['call_index'] == 1 and txt.endswith(VALID + FIXED + EOS), f'two calls {r}')

    # 15. a slipped call inside THINKING is not a tool call (vLLM's content region) -> untouched
    g, txt, log = await run(model(5, VALID, think_extra=f' e.g. {SLIP} '))
    check(not reps(g) and len(log) == 1 and g['ipd_audit']['calls'] == 1, f"thinking ignored {g['ipd_audit']}")
    print(f'ALL {n_ok} CHECKS PASSED')


asyncio.run(main())
