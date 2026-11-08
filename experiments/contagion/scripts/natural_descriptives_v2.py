"""PREREG_v2 §4 natural descriptives D1-D11 of workstream P's corpus (31B; S1 all episodes; S2 for D10). Computed by
workstream A (D wrote the predictions). Written, smoke-tested on DISCOVERY logs only, and hash-frozen before P's corpus
existed; run once after it lands. Reads each corpus dir's manifest.json + requests.jsonl (CONTEXT_SCHEMA.md §3b; it
contains outcomes, so this script is one of the governed readers; input sha256s are logged in the output).

Judge (PREREG_v2 §2, all tools, against the corpus declarations): a delivered call is malformed if its tool is
undeclared, its arguments are not an object, a required key is missing, an unknown key appears, a string value holds a
look-alike closer + ',<declared key>:' (gp.CLOSER over the declared keys) or a special token; call text left in the
content ('<|tool_call>' / 'call:NAME{') counts as one malformed unparsed call per 'call:NAME{' (at least one). Edit call
= S1 edit_file / S2 str_replace_editor with command = str_replace. Calls are taken in emission order: the delivered
calls of a response, then its unparsed call text. Episode = episode_id; requests ordered by request_index.
Definitions (mirroring D's discovery table T3.3, C's slip corpus, and PREREG_v2 §4):
  D1   first edit call of an episode malformed (secondary: D1_clean = no malformed call of any tool before it)
  D2   later edit calls with K = 0 malformed edit calls earlier in the episode
  D3   later edit calls with K >= 1 (as registered); secondary D3_K1 (K = 1, the discovery 59.8%)
  D4   later edit calls with run length R = 1 (exactly one malformed edit since the last valid edit) and distance D = 1
       (that malformed edit was in the immediately preceding assistant turn)
  D5   D3 / D2
  D6a  closer slips (malformed edits with a closer leak) / malformed edits (incl. unparsed edit text)
  D6b  closer slips whose closer contains a backtick / closer slips
  D7   closer slips whose lost arguments (missing required keys + absorbed keys, as C) include the old key
  D8   malformed calls per episode, all tools (secondary: D8_edit, edit calls only)
  D9   episodes with >= 5 consecutive malformed calls (all tools, emission order; a valid call resets the run)
  D10  D1 on the S2 stratum (secondary: D1 of S1 on the S2 task set, paired)
  D11  malformed delivered EDIT calls that re-enter history laundered, exactly as C defined it
       (experiments/conformance/slips/build_corpus.py): C's reference serializer renders the call with the corpus
       template (July if its md5 is f016bd4b..., June if d6c5bd0d...), C's strict parser parses it back, and it is
       well-formed AND values_equal to the delivered arguments (secondary: D11_all over all tools; D11_ill_formed)
Intervals: the 95% CI for the rule is the episode-cluster percentile bootstrap (B = 2000, seed 20261105; PREREG_v2 §3
convention). Wilson intervals are shown beside it, as in the discovery tables. Rule: CONSISTENT iff the 95% CI overlaps
D's 80% PI, else HIGHER / LOWER (no pass/fail language).
Primary = every S1 episode (the full corpus, PI entry 2026-11-04 15:27 UTC). Sensitivity = Verified-only
(split == 'verified').
usage: natural_descriptives_v2.py --s1 <S1 corpus dir> [--s2 <S2 corpus dir>] --out <json> [--B 2000]
"""
import json, sys, os, re, math, time, hashlib, argparse, collections
import numpy as np
sys.dont_write_bytecode = True                      # never write caches into other workstreams' directories
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gemma_protocol as gp
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance'))   # C's reference serializer + parser (read-only)
from gemmaproto import render_call, parse_call, values_equal, ParseError, JULY, JUNE

ap = argparse.ArgumentParser()
ap.add_argument('--s1', required=True); ap.add_argument('--s2', default='')
ap.add_argument('--out', required=True); ap.add_argument('--B', type=int, default=2000)
a = ap.parse_args()
SEED = 20261105
PRED = {'D1': (0.05, 0.25), 'D2': (0.015, 0.10), 'D3': (0.30, 0.80), 'D4': (0.45, 0.90), 'D5': (4.0, float('inf')),
        'D6a': (0.70, 1.0), 'D6b': (0.60, 1.0), 'D7': (0.85, 1.0), 'D8': (0.3, 2.5), 'D9': (0.02, 0.15), 'D10': (0.03, 0.30),
        'D11': (0.25, 0.90)}
CALL_RE = re.compile(r'call:([\w\-\.]+)\{')
SPECIALS = ('<|"|>', '<tool_call|>', '<|tool_call>')
HASHFILE = os.path.join(os.path.dirname(HERE), 'out', 'confirmatory_script_hashes_v1.txt')
PREREG = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/PREREG_v2.md')
RATIOS = ['D1', 'D1_clean', 'D2', 'D3', 'D3_K1', 'D4', 'D6a', 'D6b', 'D7', 'D8', 'D8_edit', 'D9', 'D11', 'D11_all', 'D11_ill_formed']


def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def wilson(k, n, z=1.96):
    if n == 0: return None
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 4), round(min(1, c + h), 4)]


def load_corpus(d):
    man = json.load(open(os.path.join(d, 'manifest.json')))
    req = ((man.get('files') or {}).get('requests') or 'requests.jsonl').split()[0]
    return man, (req if os.path.isabs(req) else os.path.join(d, req))


def setup(man):
    gp.set_profile(man['tool_profile'], tools=man['tools'], responses=(man.get('harness') or {}).get('responses'))
    decl = {}
    for t in man['tools']:
        f = t.get('function', t); p = f.get('parameters') or {}
        decl[f['name']] = (list(p.get('required') or []), set((p.get('properties') or {}).keys()))
    md5 = ((man.get('render') or {}).get('chat_template_md5') or '')
    return decl, (JUNE if md5.startswith('d6c5bd0d') else JULY)


def judge_call(name, args, decl):
    """-> (malformed, closer or None, lost keys = missing required + absorbed keys)."""
    if name not in decl or not isinstance(args, dict): return True, None, []
    req, props = decl[name]
    missing = [k for k in req if k not in args]
    bad = bool(missing) or any(k not in props for k in args)
    closer, absorbed = None, set()
    for v in args.values():
        if isinstance(v, str):
            for m in gp.CLOSER.finditer(v):
                bad = True; closer = closer or m.group(1); absorbed.add(m.group(2))
            if any(s in v for s in SPECIALS): bad = True
    return bad, closer, sorted(set(missing) | absorbed)


def laundered(name, args, tpl):
    """C's definition: (well_formed, laundered) of the history re-render of a delivered malformed call."""
    try:
        back = parse_call(render_call(name or '', args, template=tpl), template=tpl)
        return True, bool(values_equal(back.arguments, args))
    except (ParseError, Exception):
        return False, False


def calls_of(req, decl):
    out = []; resp = req.get('response') or {}
    fixed = gp.PROFILE['fixed']
    for tc in resp.get('tool_calls') or []:
        f = tc.get('function') or {}; name = f.get('name'); raw = f.get('arguments')
        if raw is None or (isinstance(raw, str) and not raw.strip()): raw = '{}'   # no-argument call (e.g. submit) = empty object
        try: args = json.loads(raw) if isinstance(raw, str) else raw
        except Exception: args = None
        bad, closer, lost = judge_call(name, args, decl)
        edit = gp.is_edit_call(name, args) if isinstance(args, dict) else (name == gp.PROFILE['edit_tool'] and (not fixed or 'str_replace' in str(raw)))
        out.append({'name': name, 'args': args, 'bad': bad, 'closer': closer, 'lost': lost, 'edit': edit, 'unparsed': False})
    c = resp.get('content')
    if isinstance(c, str) and ('<|tool_call>' in c or CALL_RE.search(c)):
        for nm in (CALL_RE.findall(c) or [None]):
            edit = nm == gp.PROFILE['edit_tool'] and (not fixed or bool(re.search(r'command\W{0,12}str_replace', c)))
            out.append({'name': nm, 'args': None, 'bad': True, 'closer': None, 'lost': [], 'edit': edit, 'unparsed': True})
    return out


def episodes(path, stratum):
    E = collections.defaultdict(list); n = 0
    for l in open(path):
        r = json.loads(l); n += 1
        if r.get('stratum') not in (None, stratum): continue
        resp = r.get('response') or {}
        E[r['episode_id']].append({'request_index': r['request_index'], 'task_id': r.get('task_id'), 'split': r.get('split'),
                                   'response': {'content': resp.get('content'), 'tool_calls': resp.get('tool_calls')}})
    for v in E.values(): v.sort(key=lambda r: r['request_index'])
    return E, n


def per_episode(reqs, decl, tpl):
    """-> dict metric -> [num, den] for one episode (+ the episode's task_id and split)."""
    M = {k: [0, 0] for k in RATIOS}
    K = 0; seen_edit = False; bad_before = False; run = 0; last_bad_turn = None; consec = 0; maxconsec = 0
    old_key = gp.PROFILE['old_key']
    for t, req in enumerate(reqs):
        for c in calls_of(req, decl):
            if c['bad']:
                M['D8'][0] += 1; consec += 1; maxconsec = max(maxconsec, consec)
                if c['args'] is not None and isinstance(c['args'], dict):
                    wf, la = laundered(c['name'], c['args'], tpl)
                    M['D11_all'][0] += la; M['D11_all'][1] += 1
                    if c['edit']:
                        M['D11'][0] += la; M['D11'][1] += 1; M['D11_ill_formed'][0] += (not wf); M['D11_ill_formed'][1] += 1
            else:
                consec = 0
            if not c['edit']:
                bad_before = bad_before or c['bad']; continue
            y = int(c['bad'])
            if not seen_edit:
                M['D1'][0] += y; M['D1'][1] += 1
                if not bad_before: M['D1_clean'][0] += y; M['D1_clean'][1] += 1
            else:
                key = 'D2' if K == 0 else 'D3'
                M[key][0] += y; M[key][1] += 1
                if K == 1: M['D3_K1'][0] += y; M['D3_K1'][1] += 1
                if run == 1 and last_bad_turn == t - 1: M['D4'][0] += y; M['D4'][1] += 1
            seen_edit = True
            if c['bad']:
                K += 1; run += 1; last_bad_turn = t; M['D8_edit'][0] += 1
                M['D6a'][1] += 1
                if c['closer']:
                    M['D6a'][0] += 1; M['D6b'][1] += 1; M['D7'][1] += 1
                    M['D6b'][0] += ('`' in c['closer']); M['D7'][0] += (old_key in c['lost'])
            else:
                run = 0
            bad_before = bad_before or c['bad']
    M['D8'][1] = 1; M['D8_edit'][1] = 1; M['D9'] = [int(maxconsec >= 5), 1]
    return M


def summarise(rows, B, seed):
    """rows: list of per-episode metric dicts -> estimates, Wilson, episode-cluster bootstrap CIs, D5."""
    out = {'episodes': len(rows)}
    if not rows: return out
    keys = RATIOS
    C = np.array([[r[k][0] for k in keys] + [r[k][1] for k in keys] for r in rows], float)
    nK = len(keys); tot = C.sum(0)
    rng = np.random.default_rng(seed)
    W = rng.multinomial(len(rows), np.full(len(rows), 1 / len(rows)), size=B).astype(float)
    S = W @ C
    with np.errstate(divide='ignore', invalid='ignore'):
        R = S[:, :nK] / S[:, nK:]
        d5 = R[:, keys.index('D3')] / R[:, keys.index('D2')]
    for j, k in enumerate(keys):
        num, den = tot[j], tot[nK + j]
        if den == 0: out[k] = {'n': 0, 'est': None, 'ci95_boot': None}; continue
        col = R[:, j]; col = col[np.isfinite(col)]
        out[k] = {'num': int(num), 'n': int(den), 'est': round(num / den, 4),
                  'ci95_boot': [round(float(np.percentile(col, 2.5)), 4), round(float(np.percentile(col, 97.5)), 4)] if len(col) else None}
        if k not in ('D8', 'D8_edit'): out[k]['wilson95'] = wilson(int(num), int(den))
    if out['D2'].get('est') and out['D3'].get('est') is not None:
        col = d5[np.isfinite(d5)]
        out['D5'] = {'est': round(out['D3']['est'] / out['D2']['est'], 3),
                     'ci95_boot': [round(float(np.percentile(col, 2.5)), 3), round(float(np.percentile(col, 97.5)), 3)] if len(col) else None,
                     'boot_draws_finite': int(len(col))}
    else:
        out['D5'] = {'est': None, 'ci95_boot': None, 'note': 'D2 = 0 or D3 undefined'}
    return out


def verdict(name, ci):
    if not ci: return 'NOT EVALUABLE'
    lo, hi = ci; plo, phi = PRED[name]
    return 'CONSISTENT' if (hi >= plo and lo <= phi) else ('HIGHER' if lo > phi else 'LOWER')


def verdicts(S1, S2=None):
    pick = {'D1': 'D1', 'D2': 'D2', 'D3': 'D3', 'D4': 'D4', 'D5': 'D5', 'D6a': 'D6a', 'D6b': 'D6b', 'D7': 'D7', 'D8': 'D8', 'D9': 'D9', 'D11': 'D11'}
    v = {d: {'est': (S1.get(k) or {}).get('est'), 'ci95': (S1.get(k) or {}).get('ci95_boot'), 'pi80': list(PRED[d]),
             'verdict': verdict(d, (S1.get(k) or {}).get('ci95_boot'))} for d, k in pick.items()}
    if S2 is not None:
        v['D10'] = {'est': (S2.get('D1') or {}).get('est'), 'ci95': (S2.get('D1') or {}).get('ci95_boot'), 'pi80': list(PRED['D10']),
                    'verdict': verdict('D10', (S2.get('D1') or {}).get('ci95_boot'))}
    return v


t0 = time.time()
script_sha = sha(os.path.abspath(__file__))
governed = os.path.exists(HASHFILE) and script_sha in open(HASHFILE).read()
res = {'prereg': 'PREREG_v2 §4', 'prereg_v2_sha256': sha(PREREG), 'script_sha256': script_sha, 'script_hash_frozen': governed,
       'run_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()), 'inputs': {}}
if not governed: print('WARNING: this script hash is not in', HASHFILE, '(smoke / development run only)', file=sys.stderr)
man1, req1 = load_corpus(a.s1)
res['inputs']['S1'] = {'manifest': os.path.join(a.s1, 'manifest.json'), 'manifest_sha256': sha(os.path.join(a.s1, 'manifest.json')),
                       'requests': req1, 'requests_sha256': sha(req1), 'corpus_id': man1.get('corpus_id')}
decl1, tpl1 = setup(man1)
E1, n1 = episodes(req1, 'S1')
rows1 = {e: per_episode(r, decl1, tpl1) for e, r in E1.items()}
split = {e: (r[0].get('split') if r else None) for e, r in E1.items()}
task1 = {e: (r[0].get('task_id') if r else None) for e, r in E1.items()}
res['S1'] = summarise(list(rows1.values()), a.B, SEED)
res['S1']['requests'] = n1; res['S1']['laundering_template'] = tpl1
res['S1']['splits'] = dict(collections.Counter(split.values()))
ver = [rows1[e] for e in rows1 if split[e] == 'verified']
res['S1_verified_only'] = summarise(ver, a.B, SEED)
S2 = None
if a.s2:
    man2, req2 = load_corpus(a.s2)
    res['inputs']['S2'] = {'manifest': os.path.join(a.s2, 'manifest.json'), 'manifest_sha256': sha(os.path.join(a.s2, 'manifest.json')),
                           'requests': req2, 'requests_sha256': sha(req2), 'corpus_id': man2.get('corpus_id')}
    decl2, tpl2 = setup(man2)
    E2, n2 = episodes(req2, 'S2')
    S2 = summarise([per_episode(r, decl2, tpl2) for r in E2.values()], a.B, SEED); S2['requests'] = n2; S2['laundering_template'] = tpl2
    res['S2'] = S2
    tasks2 = {r[0].get('task_id') for r in E2.values() if r}
    res['D10_paired_S1_on_S2_tasks'] = summarise([rows1[e] for e in rows1 if task1[e] in tasks2], a.B, SEED).get('D1')
res['verdicts_primary_full_corpus'] = verdicts(res['S1'], S2)
res['verdicts_sensitivity_verified_only'] = verdicts(res['S1_verified_only'], S2) if ver else 'NOT EVALUABLE (no verified episodes)'
res['seconds'] = round(time.time() - t0, 1)
json.dump(res, open(a.out, 'w'), indent=1)
print(json.dumps({k: (v['est'], v['ci95'], v['verdict']) for k, v in res['verdicts_primary_full_corpus'].items()}))
