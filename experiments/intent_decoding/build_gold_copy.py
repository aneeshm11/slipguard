"""Gold-intent copy task with checkable edit-applies (P0-B(c)).
Payloads = every gold-patch hunk (patch + test_patch) of the 129 competition tasks, 2-14 lines, whose old block occurs
EXACTLY ONCE in the pre-patch file taken from the task's repository snapshot (data/comp/snapshots/<id>.tgz).
Output:
  data/gold_copy_payloads.jsonl : instance_id, filepath, old, new, feats, file_sha, file_len
  data/gold_copy_files/<sha>.txt : the pre-patch file (to check edit-applies: old_string occurs exactly once)
  data/gold_copy_ctx.jsonl       : contexts (official system prompt + tools + copy-task user message), gt
"""
import json, os, sys, tarfile, hashlib, collections
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mine_payloads as MP

COMP = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/comp')
OUTF = os.path.join(HERE, 'data/gold_copy_files')


def proc(task):
    iid = task['instance_id']
    want = collections.defaultdict(list)
    for col in ('patch', 'test_patch'):
        for fp, lines in MP.hunks(task.get(col) or ''):
            pl = MP.to_payload(lines)
            if pl:
                want[fp].append((col, pl))
    if not want:
        return iid, [], 'no_hunks'
    path = os.path.join(COMP, 'snapshots', iid + '.tgz')
    if not os.path.exists(path):
        return iid, [], 'no_snapshot'
    files = {}
    try:
        with tarfile.open(path, 'r:gz') as tf:
            for m in tf:
                name = m.name[2:] if m.name.startswith('./') else m.name
                if name in want and m.isfile():
                    f = tf.extractfile(m)
                    files[name] = f.read().decode('utf-8', errors='replace')
                    if len(files) == len(want):
                        break
    except Exception as e:
        return iid, [], 'tar_error:' + repr(e)[:80]
    out = []
    for fp, items in want.items():
        txt = files.get(fp)
        if txt is None:
            continue           # new file in the patch (no pre-image)
        sha = hashlib.sha1(txt.encode()).hexdigest()[:16]
        for col, (old, new) in items:
            while old.startswith('\n') and new.startswith('\n'):      # shared blank context lines: not part of intent
                old, new = old[1:], new[1:]
            while old.endswith('\n') and new.endswith('\n'):
                old, new = old[:-1], new[:-1]
            if not old.strip() or old == new or txt.count(old) != 1:
                continue
            out.append({'instance_id': iid, 'filepath': fp, 'old': old, 'new': new, 'from': col,
                        'feats': MP.feats(fp, old, new), 'lang': MP.lang_of(fp), 'file_sha': sha, 'file_len': len(txt),
                        '_file': txt})
    return iid, out, 'ok'


def main():
    tasks = [json.loads(l) for l in open(os.path.join(COMP, 'tasks.jsonl'))]
    os.makedirs(OUTF, exist_ok=True)
    allp, st = [], collections.Counter()
    with Pool(int(os.environ.get('NP', '8'))) as p:
        for iid, out, status in p.imap_unordered(proc, tasks):
            st[status] += 1
            for r in out:
                fp = os.path.join(OUTF, r['file_sha'] + '.txt')
                if not os.path.exists(fp):
                    open(fp, 'w').write(r['_file'])
                r.pop('_file')
                allp.append(r)
    allp.sort(key=lambda r: (r['instance_id'], r['filepath'], r['old']))
    seen, uniq = set(), []
    for r in allp:
        k = (r['instance_id'], r['filepath'], r['old'], r['new'])
        if k not in seen:
            seen.add(k); uniq.append(r)
    for i, r in enumerate(uniq):
        r['gid'] = i
    with open(os.path.join(HERE, 'data/gold_copy_payloads.jsonl'), 'w') as fo:
        for r in uniq:
            fo.write(json.dumps(r) + '\n')
    # contexts (same copy-task message as E3/E5)
    sysmsg = json.loads(open(os.path.join(HERE, 'data/replay_gemma_first_edit.jsonl')).readline())['messages'][0]
    tools = json.load(open(os.path.join(HERE, 'data/tools_official.json')))
    USER = ('Apply exactly this change to the file {fp} with a single edit_file call.\n'
            'Replace this text (everything between the marker lines; the marker lines themselves are not part of it):\n'
            '-----BEGIN OLD-----\n{old}\n-----END OLD-----\n'
            'with this text:\n'
            '-----BEGIN NEW-----\n{new}\n-----END NEW-----\n'
            'Copy both blocks character for character.')
    with open(os.path.join(HERE, 'data/gold_copy_ctx.jsonl'), 'w') as fo:
        for r in uniq:
            msgs = [sysmsg, {'role': 'user', 'content': USER.format(fp=r['filepath'], old=r['old'], new=r['new'])}]
            fo.write(json.dumps({'id': 'gc:%d' % r['gid'], 'gid': r['gid'], 'messages': msgs, 'tools': tools,
                                 'gt': {'filepath': r['filepath'], 'old_string': r['old'], 'new_string': r['new']},
                                 'file_sha': r['file_sha'], 'rich': r['feats']['rich'], 'src': 'comp:' + r['from']}) + '\n')
    print('tasks', dict(st), 'payloads', len(uniq), 'rich', sum(r['feats']['rich'] for r in uniq),
          'langs', collections.Counter(r['lang'] for r in uniq).most_common(6))


if __name__ == '__main__':
    main()
