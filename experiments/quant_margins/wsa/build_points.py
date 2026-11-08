"""T1 decision points from the PUBLIC PNC corpus only (data/pnc/episodes). No main-track data is read.
For every model turn whose FIRST tool call is the edit tool (S1 edit_file; S2 str_replace_editor/str_replace):
  * valid call (vLLM-faithful parse: all three string args present, no look-alike leak in any value, delivered args equal the
    raw values): decision positions = the closing <|"|> of path / new / old (token index into the completion);
  * slip (a value contains a look-alike closer followed by ',<key>:', i.e. the model closed the string with a look-alike):
    decision position = the look-alike token (boundary = the token starts exactly at the look-alike);
  * protected positions: look-alike tokens that are legitimate string CONTENT inside valid values (must not be suppressed).
Split by episode: sha256(episode_id) even -> 'calib', odd -> 'heldout'.
Output: data/pnc_points_all.jsonl (one line per edit turn; metadata, positions; prompts are re-rendered on demand)."""
import json, os, re, sys, hashlib, collections, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pnc_render as R

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'pnc_points_all.jsonl')
TC = re.compile(r'<\|tool_call>call:([\w\-\.]+)\{')
LA_IDS = set(R.lookalike_ids())


def split_of(eid):
    return 'calib' if int(hashlib.sha256(eid.encode()).hexdigest()[:8], 16) % 2 == 0 else 'heldout'


def parse_call(body):
    """Parse a native call body (text after '{') exactly like the gemma4 parser's delimiter logic.
    Returns list of (key, value_or_None, value_start, value_end, closer_offset) with offsets into body, and end offset."""
    out = []; i = 0
    while i < len(body):
        m = re.match(r'\s*,?\s*([A-Za-z_][\w\-]*)\s*:', body[i:])
        if not m:
            break
        key = m.group(1); j = i + m.end()
        if body.startswith(R.D, j):
            vs = j + len(R.D); ve = body.find(R.D, vs)
            if ve < 0:
                out.append((key, body[vs:], vs, len(body), None)); return out, len(body)
            out.append((key, body[vs:ve], vs, ve, ve)); i = ve + len(R.D)
        else:
            m2 = re.match(r'[^,}]*', body[j:]); out.append((key, None, j, j + m2.end(), None)); i = j + m2.end()
        if body.startswith('}', i):
            return out, i
    return out, i


def main():
    tok = R.tokenizer(); t0 = time.time()
    stats = collections.Counter()
    with open(OUT, 'w') as fo:
        for fn in R.episodes():
            n_bad = 0; turns = [json.loads(l) for l in open(fn)]
            turns = sorted([t for t in turns if t.get('record_type') == 'turn'], key=lambda t: t['turn_index'])
            for t in turns:
                sch = t['schema']; E = R.EDIT[sch]; raw = t.get('raw_completion') or ''
                m = TC.search(raw)
                if not m or m.group(1) != E['tool']:
                    continue
                body_off = m.end(); body = raw[body_off:]
                end = body.find('<tool_call|>')
                args, _ = parse_call(body if end < 0 else body[:end])
                keys = [a[0] for a in args]
                if E['fixed'] and not any(a[0] == 'command' and (a[1] == 'str_replace' or (a[1] is None and 'str_replace' in body[a[2]:a[3]])) for a in args):
                    stats['skip_non_str_replace'] += 1; continue
                stats['edit_turns'] += 1
                allkeys = set(k for k in keys) | {E['path'], E['old'], E['new']}
                leak_re = re.compile(r'(["`\\\']+)\s*,\s*(' + '|'.join(map(re.escape, sorted(allkeys, key=len, reverse=True))) + r')\s*:')
                vals = {a[0]: a for a in args}
                leak = None
                for a in args:
                    if a[1] is not None:
                        lm = leak_re.search(a[1])
                        if lm:
                            leak = (a, lm); break
                delivered = (t['response'].get('message') or {}).get('tool_calls') or []
                dargs = {}
                if delivered:
                    try: dargs = json.loads(delivered[0]['function']['arguments'])
                    except Exception: dargs = {}
                complete = all(k in vals and vals[k][1] is not None for k in (E['path'], E['old'], E['new']))
                valid = complete and leak is None and all(dargs.get(k) == vals[k][1] for k in (E['path'], E['old'], E['new']))
                kind = 'valid' if valid else ('slip' if leak is not None else 'other_malformed')
                stats[kind] += 1
                rec = {'episode_id': t['episode_id'], 'turn_index': t['turn_index'], 'schema': sch, 'split': split_of(t['episode_id']),
                       'corpus_split': t.get('split'), 'repo': t.get('repo'), 'kind': kind, 'n_prior_bad': n_bad,
                       'edit_calls_before': t.get('edit_calls_before'), 'prompt_tokens': t['prompt_tokens'],
                       'gen_tokens': (t.get('proxy') or {}).get('gen_tokens'), 'masking': (t.get('masking') or {}).get('applied'),
                       'emission_order': keys}
                enc = tok(raw, add_special_tokens=False, return_offsets_mapping=True)
                ids, offs = enc['input_ids'], enc['offset_mapping']
                start_at = {}
                for ti, (a, b) in enumerate(offs):
                    start_at.setdefault(a, ti)
                rec['completion_tokens'] = len(ids); rec['retok_len_equal'] = (len(ids) == rec['gen_tokens'])
                pos = []
                if valid:
                    for a in args:
                        if a[0] in (E['path'], E['old'], E['new']) and a[4] is not None:
                            co = body_off + a[4]; ti = start_at.get(co)
                            if ti is not None and ids[ti] == R.DQ:
                                role = {E['path']: 'path', E['old']: 'old', E['new']: 'new'}[a[0]]
                                pos.append({'pos': ti, 'kind': 'close', 'arg': role, 'arg_order': keys.index(a[0]), 'logged': R.DQ})
                    # protected: look-alike tokens that are legitimate content inside old/new values
                    for a in args:
                        if a[0] in (E['old'], E['new']) and a[1]:
                            vs, ve = body_off + a[2], body_off + a[3]
                            for ti, (s, e) in enumerate(offs):
                                if vs <= s < ve and ids[ti] in LA_IDS:
                                    pos.append({'pos': ti, 'kind': 'protected', 'arg': 'old' if a[0] == E['old'] else 'new', 'logged': ids[ti]})
                elif leak is not None:
                    a, lm = leak
                    co = body_off + a[2] + lm.start(1)
                    ti = None
                    for k_, (s, e) in enumerate(offs):
                        if s <= co < e:
                            ti = k_; break
                    if ti is not None:
                        role = {E['path']: 'path', E['old']: 'old', E['new']: 'new'}.get(a[0], a[0])
                        pos.append({'pos': ti, 'kind': 'slip', 'arg': role, 'logged': ids[ti], 'boundary': offs[ti][0] == co,
                                    'closer': lm.group(1), 'leak_key': lm.group(2)})
                if not valid:
                    n_bad += 1
                rec['positions'] = pos
                stats['positions_' + kind] += sum(p['kind'] != 'protected' for p in pos)
                stats['protected'] += sum(p['kind'] == 'protected' for p in pos)
                fo.write(json.dumps(rec) + '\n')
    print(dict(stats), f'{time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
