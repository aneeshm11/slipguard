"""PREREG_v2.5 replay preconditions (CPU; metadata and prompts only, NO outcome field is read or computed).
For every record of A's C1 run (out/main/rC31b_v2.jsonl: arms P0/P1/P8a at the A1 states) and of v2.3 (out/main/rO_v23.jsonl:
O0/O1), re-render the prompt with A's frozen pathway builders and compare its token count with the logged n_prompt;
record sha256(prompt). Also tabulate the stop / finish metadata (s1_finish, s1_stop, s2_finish, s2_stop, budget_forced,
s1_tokens vs max_tokens) and the sampling fields. Fields read: id, pathway, k, n_prompt, seed, temp, top_p, server,
template, model, s1_finish, s1_stop, s1_tokens, s2_finish, s2_stop, budget_forced, error. Never: judge, s1_text,
s2_text, opened_call.
usage: v25_replay_preconditions.py <out.json> <manifest.jsonl>"""
import json, sys, os, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemma_protocol as gp, variants as V, run_onset as RO
from transformers import AutoTokenizer
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
CDIR = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
man = json.load(open(f'{CDIR}/manifest.json'))
gp.set_profile(man['tool_profile'], tools=man['tools'], responses=man['harness'].get('responses'))
gp.PROFILE['system_as_parts'] = man['render'].get('system_content_form', 'parts') == 'parts'
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
META = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/confirmatory/meta_S1.jsonl')}
KEEP = ('id', 'pathway', 'k', 'n_prompt', 'seed', 'temp', 'top_p', 'server', 'template', 'model', 's1_finish', 's1_stop', 's1_tokens',
        's2_finish', 's2_stop', 'budget_forced', 'error')
res = {'renderer_sha256': hashlib.sha256(open(V.QR_PATH, 'rb').read()).hexdigest(), 'files': {}}
mf = open(sys.argv[2], 'w')
for fn, arms in (('out/main/rC31b_v2.jsonl', {('P0', 0), ('P1', 1), ('P8a', 1)}), ('out/main/rO_v23.jsonl', {('O0', 0), ('O1', 0)})):
    path = f'{D}/{fn}'
    st = collections.defaultdict(collections.Counter); ctx = {}
    for l in open(path):
        d0 = json.loads(l); d = {k: d0.get(k) for k in KEEP}; del d0
        if (d['pathway'], d['k']) not in arms: continue
        arm = f"{d['pathway']}k{d['k']}"; c = st[arm]; c['records'] += 1
        if d['error']: c['error'] += 1; continue
        m = META[d['id']]
        if d['id'] not in ctx:
            if len(ctx) > 32: ctx.clear()
            ctx[d['id']] = V.load_context(m)
        build = RO.build_prompt if d['pathway'] in ('O0', 'O1') else V.build_prompt
        p, _ = build(tok, m, d['pathway'], d['k'], ctx=ctx[d['id']])
        n = len(tok(p, add_special_tokens=False)['input_ids'])
        ok = n == d['n_prompt']; c['len_match' if ok else 'LEN_MISMATCH'] += 1
        c['starts_with_bos_text'] += p.startswith('<bos>')
        c['prompt_ends_<|channel>thought\\n'] += p.endswith('<|channel>thought\n')
        room = 32768 - d['n_prompt'] - 8; mt = min(7168, room)
        c[f"s1_finish={d['s1_finish']}"] += 1; c[f"s1_stop={d['s1_stop']}"] += 1
        c[f"s2_finish={d['s2_finish']}"] += 1; c[f"s2_stop={d['s2_stop']}"] += 1
        c['budget_forced'] += bool(d['budget_forced'])
        c['s1_tokens_eq_max_tokens'] += (d['s1_tokens'] == mt)
        c[f"temp={d['temp']},top_p={d['top_p']}"] += 1; c[f"server={d['server']}"] += 1
        c['seed_matches_md5_rule'] += d['seed'] == (int(hashlib.md5(d['id'].encode()).hexdigest()[:8], 16)) % (2 ** 31 - 8)
        mf.write(json.dumps({'file': fn, 'id': d['id'], 'pathway': d['pathway'], 'k': d['k'], 'n_prompt_logged': d['n_prompt'], 'n_prompt_rerender': n,
                             'prompt_sha256': hashlib.sha256(p.encode()).hexdigest(), 'seed': d['seed']}) + '\n')
    res['files'][fn] = {'sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest(), 'per_arm': {k: dict(v) for k, v in st.items()}}
mf.close()
# BOS handling as sent: text prompt to /v1/completions; vLLM 0.19.1 CompletionRequest.add_special_tokens default
from vllm.entrypoints.openai.completion.protocol import CompletionRequest  # noqa
fld = CompletionRequest.model_fields.get('add_special_tokens')
res['vllm_completion_add_special_tokens_default'] = getattr(fld, 'default', None)
ex = tok('<bos>hi', add_special_tokens=True)['input_ids']; ex0 = tok('<bos>hi', add_special_tokens=False)['input_ids']
res['tokenizer_bos'] = {'with_special': ex[:3], 'without_special': ex0[:3], 'bos_id': tok.bos_token_id, 'add_bos_token': getattr(tok, 'add_bos_token', None)}
json.dump(res, open(sys.argv[1], 'w'), indent=1)
print(json.dumps(res, indent=1)[:6000])
