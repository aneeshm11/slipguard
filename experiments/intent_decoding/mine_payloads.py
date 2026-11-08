"""QuoteStorm: quote/backtick-rich VALID edit payloads mined from gold patches (SWE-bench Verified, SWE-bench-Live,
SWE-rebench, SWE-rebench-V2 multi-language) + adversarial protocol literals.

Each payload = one diff hunk turned into an edit_file(filepath, old_string, new_string) with 2..12 lines.
Selection is stratified on features that make escape-free strings hard:
  ends_lookalike (value ends with ` " ' \\), backtick, triple quote, escaped quote, JS/TS template literal, markdown/rst.
Adversarial payloads embed protocol-looking literals (e.g. '`,old_string:' at the very END of new_string, '"}' at the
end of the final argument) into real code lines; they are valid calls that a text-only heuristic would split.
Output: data/quotestorm.jsonl
"""
import glob, json, os, random, re, collections
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
HF = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'hf_cache/hub')
SRC = {
    'verified': glob.glob(HF + '/datasets--princeton-nlp--SWE-bench_Verified/snapshots/*/data/*.parquet'),
    'live': glob.glob(HF + '/datasets--SWE-bench-Live--SWE-bench-Live/snapshots/*/data/full-*.parquet'),
    'rebench': glob.glob(HF + '/datasets--nebius--SWE-rebench/snapshots/*/data/test-*.parquet'),
    'rebench_v2': glob.glob(HF + '/datasets--nebius--SWE-rebench-V2/snapshots/*/data/*.parquet'),
}
D = '<|"|>'
LA = set('`"\'\\')
rng = random.Random(0)


def hunks(patch):
    fp = None
    cur = None
    for line in patch.split('\n'):
        if line.startswith('+++ '):
            p = line[4:].strip()
            fp = p[2:] if p.startswith('b/') else p
            continue
        if line.startswith('--- ') or line.startswith('diff --git') or line.startswith('index '):
            continue
        if line.startswith('@@'):
            if cur and fp:
                yield fp, cur
            cur = []
            continue
        if cur is None:
            continue
        if line.startswith('\\'):
            continue
        if line[:1] in (' ', '-', '+'):
            cur.append((line[0], line[1:]))
        elif line == '':
            cur.append((' ', ''))
    if cur and fp:
        yield fp, cur


def to_payload(lines):
    # trim to at most 3 context lines at both ends, at most 14 lines in total
    i, j = 0, len(lines)
    while i < j and lines[i][0] == ' ' and sum(1 for t, _ in lines[i:j] if t == ' ') > 0 and \
            next((k for k in range(i, j) if lines[k][0] != ' '), j) - i > 3:
        i += 1
    while j > i and lines[j - 1][0] == ' ' and j - 1 - max((k for k in range(i, j) if lines[k][0] != ' '), default=i) > 3:
        j -= 1
    ls = lines[i:j]
    while ls and ls[-1] == (' ', ''):
        ls = ls[:-1]
    if not ls or len(ls) > 14:
        return None
    old = '\n'.join(t for k, t in ls if k in ' -')
    new = '\n'.join(t for k, t in ls if k in ' +')
    if old == new or not old.strip() or D in old or D in new or '<tool_call|>' in old + new or '<|tool_call>' in old + new:
        return None
    if len(old) > 1500 or len(new) > 1500:
        return None
    return old, new


def feats(fp, old, new):
    s = old + new
    f = {
        'backtick': '`' in s,
        'ends_lookalike': (new.rstrip(' ')[-1:] in LA) or (old.rstrip(' ')[-1:] in LA),
        'triple': '"""' in s or "'''" in s or '```' in s,
        'esc_quote': '\\"' in s or "\\'" in s,
        'template_lit': '${' in s and '`' in s,
        'markdown': fp.endswith(('.md', '.rst', '.txt')) or '``' in s,
        'quote': '"' in s or "'" in s,
    }
    f['rich'] = f['backtick'] or f['ends_lookalike'] or f['triple'] or f['esc_quote']
    return f


def lang_of(fp):
    ext = fp.rsplit('.', 1)[-1].lower() if '.' in fp else ''
    return {'py': 'python', 'js': 'js', 'ts': 'ts', 'tsx': 'ts', 'jsx': 'js', 'go': 'go', 'rs': 'rust', 'md': 'markdown',
            'rst': 'rst', 'java': 'java', 'rb': 'ruby', 'php': 'php', 'c': 'c', 'cpp': 'cpp', 'sh': 'shell'}.get(ext, ext or 'other')


def main():
    pool = []
    for src, files in SRC.items():
        for f in files:
            cols = ['instance_id', 'patch', 'test_patch']
            t = pq.read_table(f, columns=cols).to_pylist()
            if src == 'rebench_v2':
                rng.shuffle(t); t = t[:6000]
            for r in t:
                for col in ('patch', 'test_patch'):
                    p = r.get(col) or ''
                    for fp, lines in hunks(p):
                        pl = to_payload(lines)
                        if not pl:
                            continue
                        old, new = pl
                        ft = feats(fp, old, new)
                        if not ft['rich']:
                            continue
                        pool.append({'src': src, 'instance_id': r['instance_id'], 'filepath': fp, 'old': old, 'new': new,
                                     'lang': lang_of(fp), 'feats': ft, 'from_test_patch': col == 'test_patch'})
    print('rich hunks', len(pool), collections.Counter(p['src'] for p in pool))
    # dedupe and stratify: per instance cap 2; strata on ends_lookalike/backtick/triple/esc_quote/template_lit
    rng.shuffle(pool)
    seen, per_inst, out = set(), collections.Counter(), []
    quota = collections.Counter()
    caps = {'ends_lookalike': 900, 'template_lit': 250, 'triple': 350, 'esc_quote': 300, 'backtick': 900, 'markdown': 250}
    for p in pool:
        key = (p['old'], p['new'])
        if key in seen or per_inst[p['instance_id']] >= 2:
            continue
        tags = [k for k in caps if p['feats'][k]]
        if not tags or all(quota[k] >= caps[k] for k in tags):
            continue
        seen.add(key); per_inst[p['instance_id']] += 1
        for k in tags:
            quota[k] += 1
        out.append(p)
        if len(out) >= 2600:
            break
    print('natural selected', len(out), dict(quota), collections.Counter(p['lang'] for p in out).most_common(10))
    # adversarial protocol literals embedded in real code / docs lines
    lits = ['`,old_string:', '`,new_string:', '",filepath:', '\\",old_string:', '`,allow_multiple:true', '"""', "`}", '"}',
            '``,old_string:', "',new_string:", '`, old_string: ', '`,old_string:<', '`,content:']
    templates = ['    sig = "{L}"', "    marker = '{L}'", '    # the model closes strings with {L}', '    s = f"{{x}}{L}"',
                 '    return "{L}" + rest', 'const s = `${{a}}{L}`;', '- Fixed a bug where `{L}` was swallowed', '{L}']
    adv = []
    base = [p for p in out if p['lang'] in ('python', 'js', 'ts', 'markdown', 'rst')]
    for i in range(600):
        p = dict(rng.choice(base)); p['feats'] = dict(p['feats'])
        L = rng.choice(lits)
        line = rng.choice(templates).replace('{L}', L).replace('{{', '{').replace('}}', '}')
        where = rng.choice(['new_end', 'new_end_raw', 'new_mid', 'old_end', 'both'])
        if where == 'new_end':
            p['new'] = p['new'] + '\n' + line
        elif where == 'new_end_raw':      # value ends EXACTLY with the slip signature (hardest case)
            p['new'] = p['new'] + '\n' + L
        elif where == 'new_mid':
            ls = p['new'].split('\n'); k = rng.randrange(len(ls) + 1); ls.insert(k, line); p['new'] = '\n'.join(ls)
        elif where == 'old_end':
            p['old'] = p['old'] + '\n' + line; p['new'] = p['new'] + '\n' + line
        else:
            p['old'] = p['old'] + L; p['new'] = p['new'] + L
        p['src'] = 'adversarial:' + where; p['literal'] = L
        adv.append(p)
    allp = out + adv
    with open(os.path.join(HERE, 'data/quotestorm.jsonl'), 'w') as fo:
        for i, p in enumerate(allp):
            p['qid'] = i
            fo.write(json.dumps(p) + '\n')
    print('total payloads', len(allp))


if __name__ == '__main__':
    main()
