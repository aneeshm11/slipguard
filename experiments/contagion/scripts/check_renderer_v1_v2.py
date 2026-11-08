"""E's shipped quarantine renderer changed on 2026-11-04 at 18:48:10 UTC (v1 sha256 13e28567... -> v2 6b08b6e9...). This is a
byte-identity check of every render of A's that used it.

For every unique (context, arm, k) among A's records with pathway P8a, P8b, Q8b or Q8M (all models, all conditions;
out/main/*.jsonl), it builds the prompt with v1 and with v2 through A's own build_prompt, ON render, June template. v1 is
E's archived copy, byte-identical to the hash A froze; v2 is the shipped file. It compares:
  (a) the full prompt strings;
  (b) the quarantine actions.
It also checks P's 4 SMOKE contexts (S1 profile, July template; contexts only): P8a/P8b under v1 vs v2.
Any difference is explained by the first differing position and its surroundings. E's modules are loaded read-only, with
no bytecode written.
run as: with_paths.py check_renderer_v1_v2.py <out.json>"""
import sys
sys.dont_write_bytecode = True
import json, os, hashlib, importlib.util, collections, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemma_protocol as gp, variants as V
from transformers import AutoTokenizer
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
V1 = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/archive/candidate_0c2a5278/export/quarantine_renderer.py')
SHIPPED = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend/export/quarantine_renderer.py')
V2_6B08 = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/proxy_vendor_fix/export/quarantine_renderer.py')  # copy of the version the PI announced
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()


def load(path, name):
    src = open(path, 'rb').read()   # read once: the shipped file may be edited while this runs
    spec = importlib.util.spec_from_loader(name, loader=None); m = importlib.util.module_from_spec(spec)
    m.__file__ = path; sys.modules[name] = m; exec(compile(src, path, 'exec'), m.__dict__); return m, hashlib.sha256(src).hexdigest()


M = {'v1': load(V1, 'qr_e_v1')}
assert M['v1'][1].startswith('13e285673b70aa9a'), M['v1'][1]
cand = {'v2_6b08b6e9': V2_6B08, 'shipped_at_run': SHIPPED}
for tag, path in cand.items():
    if os.path.exists(path): M[tag] = load(path, 'qr_e_' + tag)
if 'v2_6b08b6e9' in M and not M['v2_6b08b6e9'][1].startswith('6b08b6e9700dba4e'): M.pop('v2_6b08b6e9')
if 'shipped_at_run' in M and 'v2_6b08b6e9' in M and M['shipped_at_run'][1] == M['v2_6b08b6e9'][1]: M.pop('shipped_at_run')
VERS = [t for t in M if t != 'v1']
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
META = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
A2M = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/a2_meta_8303.jsonl')}
keys = collections.defaultdict(set)   # (id, pathway, k) -> source files
for f in sorted(glob.glob(f'{D}/out/main/*.jsonl')):
    for l in open(f):
        try: d = json.loads(l)
        except Exception: continue
        if d.get('error') or d.get('pathway') not in ('P8a', 'P8b', 'Q8b', 'Q8M'): continue
        keys[(d['id'], d['pathway'], d['k'])].add(os.path.basename(f))


def build(meta, pw, k, ver, ctx):
    V._QR['m'], V._QR['sha256'] = M[ver]
    return V.build_prompt(tok, meta, pw, k, ctx=ctx)


def explain(a, b):
    i = next((j for j in range(min(len(a), len(b))) if a[j] != b[j]), min(len(a), len(b)))
    return {'first_diff_at': i, 'len_v1': len(a), 'len_v2': len(b), 'v1': a[max(0, i - 120):i + 160], 'v2': b[max(0, i - 120):i + 160]}


res = {'versions': {t: {'sha256': M[t][1]} for t in M}, 'v1_path': V1, 'shipped_path': SHIPPED, 'by_arm': {}, 'differences': []}
cnt = collections.defaultdict(collections.Counter); ctxc = {}
for (cid, pw, k), srcs in sorted(keys.items()):
    meta = A2M.get(cid) if cid.startswith('A2:') else META.get(cid)
    if meta is None or (pw == 'Q8M' and 'map_repair' not in meta):
        cnt[pw]['meta_missing'] += 1; continue
    if cid not in ctxc:
        if len(ctxc) > 64: ctxc.clear()
        ctxc[cid] = V.load_context(meta)
    p1, i1 = build(meta, pw, k, 'v1', ctxc[cid])
    for ver in VERS:
        p2, i2 = build(meta, pw, k, ver, ctxc[cid])
        same_p = p1 == p2; same_a = json.dumps(i1.get('quarantine_actions'), sort_keys=True, default=str) == json.dumps(i2.get('quarantine_actions'), sort_keys=True, default=str)
        cnt[f'{ver}:{pw}']['identical' if same_p else 'DIFFERENT'] += 1
        cnt[f'{ver}:{pw}']['actions_identical' if same_a else 'actions_DIFFERENT'] += 1
        if not same_p or not same_a:
            res['differences'].append({'version': ver, 'id': cid, 'pathway': pw, 'k': k, 'files': sorted(srcs), 'prompt_identical': same_p, 'actions_identical': same_a,
                                       'diff': explain(p1, p2) if not same_p else None, 'actions_v1': i1.get('quarantine_actions'), 'actions_new': i2.get('quarantine_actions')})
res['by_arm'] = {k: dict(v) for k, v in cnt.items()}
res['records_per_arm'] = dict(collections.Counter(pw for (_, pw, _) in keys))
# P's 4 smoke contexts (S1 profile, July template from P's corpus dir; contexts only)
try:
    pdir = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/pnc/runs/smoke1/data/contexts/P-swebench-31b-S1-v1')
    man = json.load(open(f'{pdir}/manifest.json'))
    gp.set_profile(man['tool_profile'], tools=man['tools'], responses=man['harness'].get('responses'))
    pc = collections.Counter()
    for l in open(f'{D}/data/smoke_P/meta_S1.jsonl'):
        m = json.loads(l)
        if m['k_usable'] < 1: continue
        ctx = V.load_context(m)
        for pw in ('P8a', 'P8b'):
            a, _ = build(m, pw, 1, 'v1', ctx)
            for ver in VERS:
                b, _ = build(m, pw, 1, ver, ctx)
                pc[f'{ver}:{pw}:' + ('identical' if a == b else 'DIFFERENT')] += 1
                if a != b: res['differences'].append({'version': ver, 'id': m['id'], 'pathway': pw, 'P_smoke': True, 'diff': explain(a, b)})
    res['P_smoke_S1'] = dict(pc)
    gp.set_profile('main_track')
except Exception as e:
    res['P_smoke_S1'] = 'error: ' + repr(e)[:300]
json.dump(res, open(sys.argv[1], 'w'), indent=1, default=str)
print(json.dumps({'versions': res['versions'], 'by_arm': res['by_arm'], 'records_per_arm': res['records_per_arm'], 'P_smoke_S1': res['P_smoke_S1'], 'n_differences': len(res['differences'])}, indent=1))
