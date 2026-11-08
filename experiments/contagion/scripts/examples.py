"""Pull illustrative records: malformed next edits under P1/P3 (thought snippet + call tail around the slip) and the
order flip after P4. usage: examples.py out.json results.jsonl..."""
import json, sys, re, collections
out = collections.defaultdict(list)
CL = re.compile(r'(["`\\\']+)\s*,\s*(old_string|new_string)\s*:')
for f in sys.argv[2:]:
    for l in open(f):
        d = json.loads(l); j = d.get('judge') or {}
        if d.get('error') or j.get('name') != 'edit_file': continue
        arm = f"{d['pathway']}k{d['k']}"
        t2 = d.get('s2_text') or ''
        m = CL.search(t2)
        tail = t2[max(0, (m.start() if m else 0) - 120):(m.end() if m else 0) + 40] if m else t2[:200]
        th = (d.get('s1_text') or '').replace('<|channel>thought\n', '').split('<channel|>')[0].strip()
        rec = {'id': d['id'], 'model': d.get('model'), 'arm': arm, 'malformed': j.get('malformed'), 'why': j.get('why'),
               'order': j.get('order'), 'closer': j.get('closer'), 'thought_head': th[:300], 'call_around_slip': tail}
        if j.get('malformed') and arm in ('P1k1', 'P3k1', 'P1k2', 'P1k4') and len(out[arm]) < 6: out[arm].append(rec)
        if arm == 'P4k1' and j.get('order') == 'old_first' and len(out['P4k1_old_first']) < 3: out['P4k1_old_first'].append(rec)
json.dump(out, open(sys.argv[1], 'w'), indent=1)
for k, v in out.items():
    print('==', k, len(v))
    for r in v[:3]: print('   thought:', repr(r['thought_head'][:200])); print('   call   :', repr(r['call_around_slip'][:260]))
