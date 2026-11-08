"""PREREG_v2.4 (injected-slip repair battery; sha256 e7af894b...) -- STATE SELECTION + SLIP INJECTION INPUTS (CPU only).

Source: P's public S1 corpus (manifest/contexts/outcomes of P-swebench-31b-S1-v1).  A candidate is the logged response of
a context (a request whose response's FIRST call is edit_file, P's contexts definition) such that
  * the logged raw call (first '<|tool_call>' after the thinking channel) is STRICTLY VALID under B's frozen reference
    parser + schema (confirm/gemma_protocol.is_valid) and closed by '<tool_call|>';
  * the delivered call (response.tool_calls[0]) is edit_file, its parsed arguments equal the strict parse, and its tool
    result status is 'ok';
  * the prompt renders byte-exactly (token count == logged prompt_tokens) under P's manifest template, and is <= 24,000.
Rank: sha256("PREREG_v2.4|20261105|" + episode_id + "|" + str(turn_index)) ascending (episode_id = attempt_id,
turn_index = request_index).  Accept in rank order: <= 2 per episode; a repository's further calls are skipped once it
holds 40% of the target (240); target 600.  Stratum = ['BT','DQ','EQ','TB'][(accepted_rank - 1) % 4].
Injection: prefix = rendered prompt + logged raw text up to (excluding) the closing <|"|> of new_string + the stratum's
closer.  Gold intent = the logged call's arguments.  One sampling seed per state.
Writes v24/battery_inputs.jsonl and v24/battery_manifest.json (sha256 of inputs, sources and this script).
Reads outcomes.jsonl (PREREG_v2 is frozen; this script's sha256 is logged in PROGRESS.md before it is run).
usage: build_battery.py [--dry_n N --out_dir DIR]
"""
import argparse, copy, hashlib, json, os, sys, collections, time
HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(B, 'confirm'))           # frozen copies only
from gemma_protocol import D, TC_START, TC_END, schema_from_tools, is_valid, parse_strict  # noqa: E402

PREREG_SHA = 'e7af894ba355a03a5fb7b023c3c7ad860a5e8c3d666a4ab80e6ff6c7ea102090'
CORPUS = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc/contexts/P-swebench-31b-S1-v1')
TOK = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')
TARGET, EP_CAP, REPO_FRAC, MAX_PROMPT = 600, 2, 0.40, 24000
STRATA = ['BT', 'DQ', 'EQ', 'TB']
CLOSER = {'BT': '`', 'DQ': '"', 'EQ': '\\"', 'TB': '```'}
CH_END = '<channel|>'


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def rank_key(episode_id, turn_index):
    return hashlib.sha256(f'PREREG_v2.4|20261105|{episode_id}|{turn_index}'.encode()).hexdigest()


def state_seed(context_id):
    return int(hashlib.sha256(f'PREREG_v2.4|20261105|seed|{context_id}'.encode()).hexdigest()[:8], 16) % 1_000_000


def to_template_messages(msgs):
    out = []
    for i, m in enumerate(msgs):
        m = copy.deepcopy(m)
        for t in m.get('tool_calls') or []:
            f = t['function']
            if isinstance(f.get('arguments'), str):
                f['arguments'] = json.loads(f['arguments']) if f['arguments'] else {}
        if i == 0 and m.get('role') == 'system' and isinstance(m.get('content'), str):
            m['content'] = [{'type': 'text', 'text': m['content']}]      # manifest system_content_form = parts
        out.append(m)
    return out


def first_raw_call(raw):
    """-> (index of '<|tool_call>' of the first call after the thinking channel, call text, finished) or None."""
    start = raw.rfind(CH_END)
    start = start + len(CH_END) if start >= 0 else 0
    i = raw.find(TC_START, start)
    if i < 0:
        return None
    j = raw.find(TC_END, i)
    nxt = raw.find(TC_START, i + len(TC_START))
    if j < 0 or (0 <= nxt < j):
        return i, raw[i + len(TC_START):(nxt if nxt >= 0 else len(raw))], False
    return i, raw[i + len(TC_START):j], True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out_dir', default=HERE)
    a = ap.parse_args()
    man = json.load(open(os.path.join(CORPUS, 'manifest.json')))
    assert man['render']['system_content_form'] == 'parts'
    tools = man['tools']; schema = schema_from_tools(tools)
    E = man['harness']['edit_tool']; EDIT, PATHK, OLDK, NEWK = E['name'], E['path_key'], E['old_key'], E['new_key']
    tpl = open(os.path.join(CORPUS, man['render']['chat_template_path'])).read()
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(TOK)
    ctx = {}
    for l in open(os.path.join(CORPUS, 'contexts.jsonl')):
        c = json.loads(l)
        ctx[c['context_id']] = c
    reasons = collections.Counter()
    cands = []
    for l in open(os.path.join(CORPUS, 'outcomes.jsonl')):
        o = json.loads(l)
        c = ctx.get(o['context_id'])
        if c is None:
            reasons['no_context'] += 1; continue
        raw = o.get('raw_response_text')
        if not isinstance(raw, str) or not raw:
            reasons['no_raw_text'] += 1; continue
        fc = first_raw_call(raw)
        if fc is None:
            reasons['no_raw_call'] += 1; continue
        i, call, fin = fc
        if not (fin and is_valid(call, schema)):
            reasons['not_strictly_valid'] += 1; continue
        sp = parse_strict(call)
        if sp.name != EDIT:
            reasons['not_edit_tool'] += 1; continue
        tcs = (o.get('response') or {}).get('tool_calls') or []
        if not tcs or tcs[0]['function']['name'] != EDIT:
            reasons['delivered_not_edit'] += 1; continue
        try:
            dargs = json.loads(tcs[0]['function']['arguments'])
        except Exception:
            reasons['delivered_args_unparseable'] += 1; continue
        gold = sp.args()
        if dargs != gold:
            reasons['delivered_args_differ_from_strict_parse'] += 1; continue
        st = {t.get('tool_call_id'): t.get('status') for t in o.get('tool_results') or []}
        if st.get(tcs[0].get('id')) != 'ok':
            reasons['tool_result_not_ok'] += 1; continue
        if (c.get('prompt_tokens') or 10 ** 9) > MAX_PROMPT:
            reasons['prompt_over_24000'] += 1; continue
        newp = [p for p in sp.pairs if p.key == NEWK]
        if len(newp) != 1 or newp[0].kind != 'str':
            reasons['new_string_not_single_string'] += 1; continue
        close_in_call = newp[0].vend - len(D)
        assert call[close_in_call:close_in_call + len(D)] == D
        cands.append({'context_id': c['context_id'], 'episode_id': c['attempt_id'], 'turn_index': c['request_index'],
                      'repo': c['repo'], 'split': c.get('split'), 'prompt_tokens': c['prompt_tokens'],
                      'rank_hash': rank_key(c['attempt_id'], c['request_index']),
                      'pre_call_text': raw[:i], 'call_text': call, 'new_close_pos': close_in_call,
                      'new_is_last_arg': sp.pairs[-1].key == NEWK, 'key_order': [p.key for p in sp.pairs],
                      'gold': gold, 'logged_finish_reason': o.get('finish_reason')})
        reasons['eligible'] += 1
    cands.sort(key=lambda x: x['rank_hash'])
    per_ep, per_repo, acc = collections.Counter(), collections.Counter(), []
    skipped = collections.Counter()
    cap_repo = int(REPO_FRAC * TARGET)
    for x in cands:
        if len(acc) >= TARGET:
            break
        if per_ep[x['episode_id']] >= EP_CAP:
            skipped['episode_cap'] += 1; continue
        if per_repo[x['repo']] >= cap_repo:
            skipped['repo_cap'] += 1; continue
        # render check (exact prompt reproduction is required to teacher-force the logged call)
        c = ctx[x['context_id']]
        p0 = tok.apply_chat_template(to_template_messages(c['messages']), tools=tools, add_generation_prompt=True,
                                     tokenize=False, chat_template=tpl, **man['render']['chat_template_kwargs'])
        if len(tok(p0, add_special_tokens=False)['input_ids']) != c['prompt_tokens']:
            skipped['render_mismatch'] += 1; continue
        per_ep[x['episode_id']] += 1; per_repo[x['repo']] += 1
        r = len(acc) + 1
        s = STRATA[(r - 1) % 4]
        call = x['call_text']
        x.update(accepted_rank=r, stratum=s, closer=CLOSER[s], seed=state_seed(x['context_id']),
                 slipped_call_prefix=call[:x['new_close_pos']] + CLOSER[s],
                 logged_remainder=call[x['new_close_pos']:],
                 logged_remainder_tokens=len(tok(call[x['new_close_pos']:], add_special_tokens=False)['input_ids']),
                 logged_call_tokens=len(tok(call, add_special_tokens=False)['input_ids']),
                 new_ends_in_lookalike=bool(x['gold'][NEWK]) and x['gold'][NEWK][-1] in '`"\'\\')
        acc.append(x)
    os.makedirs(a.out_dir, exist_ok=True)
    inp = os.path.join(a.out_dir, 'battery_inputs.jsonl')
    with open(inp, 'w') as fo:
        for x in acc:
            fo.write(json.dumps(x, ensure_ascii=False) + '\n')
    rem = sorted(x['logged_remainder_tokens'] for x in acc); ct = sorted(x['logged_call_tokens'] for x in acc)
    q = lambda v, f: v[min(len(v) - 1, int(f * len(v)))] if v else None
    manifest = {
        'prereg': {'file': 'paper/protocol_theory/prereg/PREREG_v2.4_injectedSlipRepair.md', 'sha256': PREREG_SHA},
        'built_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'script': {'path': os.path.relpath(os.path.abspath(__file__), B), 'sha256': sha256_file(os.path.abspath(__file__))},
        'frozen_library': {f: sha256_file(os.path.join(B, 'confirm', f)) for f in ('gemma_protocol.py', 'intent_decode.py', 'arms.py', 'prior_ft_edit.json')},
        'sources': {'manifest': os.path.join(CORPUS, 'manifest.json'), 'manifest_sha256': sha256_file(os.path.join(CORPUS, 'manifest.json')),
                    'contexts_sha256': sha256_file(os.path.join(CORPUS, 'contexts.jsonl')),
                    'outcomes_sha256': sha256_file(os.path.join(CORPUS, 'outcomes.jsonl')),
                    'chat_template_md5': hashlib.md5(tpl.encode()).hexdigest()},
        'rules': {'rank': 'sha256("PREREG_v2.4|20261105|" + episode_id + "|" + str(turn_index)) ascending',
                  'episode_cap': EP_CAP, 'repo_cap': cap_repo, 'max_prompt_tokens': MAX_PROMPT, 'target': TARGET,
                  'stratum': "['BT','DQ','EQ','TB'][(accepted_rank-1) % 4]", 'closers': CLOSER,
                  'seed': 'int(sha256("PREREG_v2.4|20261105|seed|" + context_id)[:8], 16) % 1,000,000'},
        'counts': {'outcome_rows': sum(reasons.values()), 'exclusions': dict(reasons), 'eligible': len(cands),
                   'skipped_during_acceptance': dict(skipped), 'accepted': len(acc),
                   'per_stratum': dict(collections.Counter(x['stratum'] for x in acc)),
                   'episodes': len(per_ep), 'repos': dict(per_repo.most_common()),
                   'split': dict(collections.Counter(x['split'] for x in acc)),
                   'new_string_is_last_argument': sum(x['new_is_last_arg'] for x in acc),
                   'new_string_ends_in_lookalike_by_stratum': {s_: sum(x['new_ends_in_lookalike'] for x in acc if x['stratum'] == s_) for s_ in STRATA}},
        'gold_call_tokens': {'median': q(ct, 0.5), 'p90': q(ct, 0.9), 'p99': q(ct, 0.99), 'max': ct[-1] if ct else None},
        'logged_remainder_tokens': {'median': q(rem, 0.5), 'p90': q(rem, 0.9), 'p99': q(rem, 0.99), 'max': rem[-1] if rem else None},
        'inputs': {'path': os.path.relpath(inp, B), 'sha256': sha256_file(inp), 'n': len(acc)}}
    json.dump(manifest, open(os.path.join(a.out_dir, 'battery_manifest.json'), 'w'), indent=1)
    print(json.dumps(manifest['counts'], indent=1)); print(manifest['gold_call_tokens'], manifest['logged_remainder_tokens'])
    print('inputs sha256', manifest['inputs']['sha256'])


if __name__ == '__main__':
    main()
