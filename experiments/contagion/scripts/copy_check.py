"""Is contagion verbatim copying? For generated edit_file calls under P1/P3/P6/P7 at k=1 (one replaced call), compare the
generated new_string (parsed by vLLM's parser) with
  injected : the corrupted new_string value the history shows (P1/P6/P7: parser output of the slip text, i.e. the original
             new_string + closer + ',old_string:'; P3: the same text inside the raw call),
  original : the clean new_string of the replaced (successful) call.
Classes: copy_corrupted (== injected), clean_retry (== original), same_content_other (starts with the original's first
40 chars but differs), other_edit. Reports counts and malformed rates per class, per arm and model.
usage: copy_check.py out.json results.jsonl ..."""
import json, sys, os, collections, math
sys.path.insert(0, os.path.dirname(__file__))
import gemma_protocol as gp
import variants as V


def wilson(k, n, z=1.96):
    if n == 0: return None
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(c - h, 4), round(c + h, 4), n]


META = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/contexts_meta.jsonl'))}
CL = {'P1': '`', 'P3': '`', 'P6': '`', 'P7': '"'}
cache = {}
tab = collections.defaultdict(lambda: collections.Counter())
files = sys.argv[2:]
KEEP = None
if files and files[0].startswith('--ids='):
    KEEP = set(x.strip() for x in open(files[0][6:]) if x.strip()); files = files[1:]
for f in files:
    for l in open(f):
        d = json.loads(l); j = d.get('judge') or {}
        if d.get('error') or d['k'] != 1 or d['pathway'] not in CL or j.get('name') != 'edit_file': continue
        if KEEP is not None and d['id'] not in KEEP: continue
        cid = d['id']
        if cid not in cache:
            msgs, _ = V.load_context(META[cid])
            p = META[cid]['prior'][-1]
            args = json.loads(msgs[p['ai']]['tool_calls'][0]['function']['arguments'])
            cache[cid] = (args, list(args.keys()))
        args, order = cache[cid]
        sk = V.slip_key_for(order)
        inj = gp.parse_args(gp.raw_args(args, order, slip_key=sk, closer=CL[d['pathway']])).get(sk)
        orig = args.get(sk)
        m = gp.TOOL_CALL_RE.search('<|tool_call>' + (d.get('s2_text') or '') + '<tool_call|>')
        gen = gp.parse_args(m.group(2)).get(sk) if m else None
        if gen is None: cls = 'unparsed_or_no_key'
        elif gen == inj: cls = 'copy_corrupted'
        elif gen == orig: cls = 'clean_retry'
        elif isinstance(orig, str) and gen[:40].strip() == orig[:40].strip(): cls = 'same_content_other'
        else: cls = 'other_edit'
        key = (d.get('model'), d['pathway'])
        tab[key][(cls, bool(j.get('malformed')))] += 1
out = {}
for (model, pw), c in sorted(tab.items()):
    row = {}
    for cls in ('copy_corrupted', 'clean_retry', 'same_content_other', 'other_edit', 'unparsed_or_no_key'):
        n = c[(cls, True)] + c[(cls, False)]
        if n: row[cls] = {'n': n, 'malformed': wilson(c[(cls, True)], n)}
    tot = sum(c.values()); mal = sum(v for (cls, b), v in c.items() if b)
    copy_mal = c[('copy_corrupted', True)]
    row['all_edits'] = {'n': tot, 'malformed': wilson(mal, tot)}
    row['share_of_malformed_that_are_verbatim_copies'] = wilson(copy_mal, mal) if mal else None
    out[f'{model}:{pw}k1'] = row
json.dump(out, open(sys.argv[1], 'w'), indent=1)
for k, v in out.items():
    print(k, json.dumps(v))
