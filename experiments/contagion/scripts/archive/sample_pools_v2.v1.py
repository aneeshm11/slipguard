"""PREREG_v2 §2 context-sampling rule, applied verbatim to workstream P's corpus (reads ONLY manifest.json and
contexts.jsonl; never the outcomes file).

Definitions (PREREG_v2 §2): episode = one task attempt (`attempt_id`); state = the chat request immediately before an
assistant turn (one line of contexts.jsonl; turn_index := `request_index`); edit call = S1 `edit_file` or S2
`str_replace_editor` with command = str_replace; a call is malformed under A's vLLM-parse judge extended with the S1/S2
key names (required key missing, look-alike closer + ',<declared key>:' leak, special token in a value, unknown key,
unparsed call text); a history is protocol-clean if no call of ANY tool before the state is malformed.
Pools (per stratum S1 / S2):
  A1: the state precedes a logged edit call (every context in P's file does, CONTEXT_SCHEMA.md §2), the history is
      protocol-clean, and the most recent prior edit call is valid and its tool result a success;
  A2: A1 and >= 4 prior edit calls valid and successful (k_usable >= 4);
  B1: the state immediately before the FIRST edit call of an episode (no edit call in its history), protocol-clean.
Selection: rank by sha256("PREREG_v2|20261105|" + episode_id + "|" + str(turn_index)) ascending; accept in rank order
under the caps: <= 2 states per episode (A1, A2; the two best-ranked), 1 (B1); no repository beyond 40% of the target n
(further states of that repository skipped); prompt <= 24,000 tokens under the Gemma render. Targets A1 300, A2 300
(or all eligible), B1 600. Shortfall: if A2 has < 150 eligible states, also emit A1k2 = A1 states with k_usable >= 2
(P6k at k = 1, 2), and k = 4 runs on whatever A2 states exist. Halves: A1 ranks 1-150 = H1, 151-300 = H2.
Outputs (stable path, consumed by A, B and X): <outdir>/{S1,S2}_{A1,A2,B1}.jsonl (+ S1_A1k2 if needed) and
<outdir>/POOLS_MANIFEST.json.
usage: sample_pools_v2.py <manifest.json> [<manifest_S2.json>] --out <outdir>
"""
import json, sys, os, re, hashlib, time, collections
sys.path.insert(0, os.path.dirname(__file__))
import gemma_protocol as gp

SEED_TAG = 'PREREG_v2|20261105|'
PREREG = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'paper/protocol_theory/prereg/PREREG_v2.md')
TARGET = {'A1': 300, 'A2': 300, 'B1': 600}
PER_EPISODE = {'A1': 2, 'A2': 2, 'B1': 1}
MAX_PROMPT = 24000
RAW_RE = re.compile(r'<\|tool_call>|call:[\w\-\.]+\{')
SPECIALS = ('<|"|>', '<tool_call|>', '<|tool_call>')


def sha(path): return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def repo_of(task_id):
    if '__' in task_id:
        owner, rest = task_id.split('__', 1)
        return owner + '/' + rest.rsplit('-', 1)[0]
    return task_id.split('_')[0]


def rank_key(episode_id, turn_index):
    return hashlib.sha256((SEED_TAG + str(episode_id) + '|' + str(turn_index)).encode('utf-8')).hexdigest()


def call_malformed(name, a, decl):
    """PREREG_v2 malformed criterion for one parsed historical call (all tools)."""
    if name not in decl: return True                                   # undeclared tool
    if not isinstance(a, dict): return True
    req, props = decl[name]
    if any(k not in a for k in req): return True                        # required key missing
    if any(k not in props for k in a): return True                      # unknown key
    for v in a.values():
        if isinstance(v, str) and (gp.CLOSER.search(v) or any(s in v for s in SPECIALS)): return True   # leak / special token
    return False


def analyse(msgs, decl, P):
    clean, prior = True, []
    tool_idx = {m.get('tool_call_id'): i for i, m in enumerate(msgs) if m.get('role') == 'tool'}
    for i, m in enumerate(msgs):
        if m.get('role') != 'assistant': continue
        c = m.get('content') or ''
        if isinstance(c, str) and RAW_RE.search(c): clean = False      # unparsed call text
        tcs = m.get('tool_calls') or []
        for tc in tcs:
            f = tc.get('function') or {}; name = f.get('name')
            try: a = json.loads(f['arguments']) if isinstance(f.get('arguments'), str) else f.get('arguments')
            except Exception: a = None
            bad = call_malformed(name, a, decl)
            if bad: clean = False
            if gp.is_edit_call(name, a):
                ti = tool_idx.get(tc.get('id')); resp = msgs[ti].get('content') if ti is not None else None
                prior.append({'valid': not bad, 'ok': resp is not None and STATUS(resp) == 'ok', 'single': len(tcs) == 1, 'has_resp': ti is not None})
    return clean, prior


def k_usable(prior):
    k = 0
    for p in reversed(prior):
        if p['valid'] and p['ok'] and p['single'] and p['has_resp']: k += 1
        else: break
    return k


def run(man_path, stratum, outdir, log):
    global STATUS
    man = json.load(open(man_path)); base = os.path.dirname(os.path.abspath(man_path))
    gp.set_profile(man['tool_profile'], tools=man['tools'], responses=man['harness'].get('responses'))
    R = man['harness'].get('responses', {})
    miss = (R.get('missing_required') or '').split('{missing}')[0].strip()[:60]; nf = (R.get('edit_not_found') or '').strip()[:60]

    def status(content):
        c = content if isinstance(content, str) else json.dumps(content)
        if (miss and miss in c) or (nf and nf in c): return 'error'
        try:
            j = json.loads(c)
            if isinstance(j, dict) and ('error' in j or str(j.get('status', '')).lower() in ('error', 'failed')): return 'error'
        except Exception:
            if c.strip().lower().startswith(('error', 'failed')): return 'error'
        return 'ok'
    STATUS = status
    ctx_file = man['files']['contexts']; ctx_file = ctx_file if os.path.isabs(ctx_file) else os.path.join(base, ctx_file)
    assert 'outcome' not in os.path.basename(ctx_file).lower(), 'refusing to read an outcomes file'
    elig = {'A1': [], 'A2': [], 'B1': [], 'A1k2': []}; counts = collections.Counter()
    for line in open(ctx_file):
        d = json.loads(line); counts['contexts'] += 1
        tools = d.get('tools') or man['tools']
        decl = {}
        for t in tools:
            f = t.get('function', t); p = f.get('parameters') or {}
            decl[f['name']] = (list(p.get('required') or []), set((p.get('properties') or {}).keys()))
        clean, prior = analyse(d['messages'], decl, gp.PROFILE)
        pt = d.get('prompt_tokens')
        if pt is None or pt > MAX_PROMPT: counts['excluded_prompt_length_or_missing'] += 1; continue
        if not clean: counts['history_not_clean'] += 1; continue
        ti = d.get('turn_index', d.get('request_index'))
        row = {'context_id': d['context_id'], 'episode_id': d['attempt_id'], 'task_id': d['task_id'], 'repo': repo_of(d['task_id']),
               'turn_index': ti, 'prompt_tokens': pt, 'n_prior_edits': len(prior), 'k_usable': k_usable(prior),
               'rank_hash': rank_key(d['attempt_id'], ti)}
        if len(prior) == 0: elig['B1'].append(row)
        if row['k_usable'] >= 1: elig['A1'].append(row)
        if row['k_usable'] >= 2: elig['A1k2'].append(row)
        if row['k_usable'] >= 4: elig['A2'].append(row)
    out = {'stratum': stratum, 'corpus_manifest': man_path, 'corpus_manifest_sha256': sha(man_path), 'contexts_file_sha256': sha(ctx_file),
           'counts': dict(counts), 'eligible': {k: len(v) for k, v in elig.items()}, 'pools': {}}
    pools = ['A1', 'A2', 'B1'] + (['A1k2'] if len(elig['A2']) < 150 else [])
    for pool in pools:
        tgt = TARGET.get(pool, TARGET['A1']); per_ep = PER_EPISODE.get(pool, 2); cap = int(0.40 * tgt)
        acc, by_ep, by_repo, skipped = [], collections.Counter(), collections.Counter(), collections.Counter()
        for r in sorted(elig[pool], key=lambda r: r['rank_hash']):
            if len(acc) >= tgt: break
            if by_ep[r['episode_id']] >= per_ep: skipped['episode_cap'] += 1; continue
            if by_repo[r['repo']] >= cap: skipped['repo_cap'] += 1; continue
            by_ep[r['episode_id']] += 1; by_repo[r['repo']] += 1
            acc.append(dict(r, rank=len(acc) + 1, half=('H1' if len(acc) < 150 else 'H2') if pool in ('A1', 'A1k2') else None))
        with open(os.path.join(outdir, f'{stratum}_{pool}.jsonl'), 'w') as f:
            for r in acc: f.write(json.dumps(r) + '\n')
        out['pools'][pool] = {'accepted': len(acc), 'target': tgt, 'eligible': len(elig[pool]), 'skipped': dict(skipped),
                              'repos': dict(by_repo.most_common()), 'episodes': len(by_ep), 'shortfall': len(acc) < tgt}
    log[stratum] = out


if __name__ == '__main__':
    args = sys.argv[1:]; outdir = args[args.index('--out') + 1]; mans = [a for a in args[:args.index('--out')]]
    os.makedirs(outdir, exist_ok=True)
    log = {'rule': 'PREREG_v2 §2', 'prereg_v2_sha256': sha(PREREG), 'script_sha256': sha(os.path.abspath(__file__)),
           'applied_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()), 'turn_index_mapping': 'turn_index := request_index (CONTEXT_SCHEMA.md) unless the context carries turn_index'}
    for i, m in enumerate(mans): run(m, 'S1' if i == 0 else 'S2', outdir, log)
    json.dump(log, open(os.path.join(outdir, 'POOLS_MANIFEST.json'), 'w'), indent=1)
    print(json.dumps({s: {'eligible': v['eligible'], 'accepted': {p: x['accepted'] for p, x in v['pools'].items()}} for s, v in log.items() if isinstance(v, dict) and 'pools' in v}, indent=1))
