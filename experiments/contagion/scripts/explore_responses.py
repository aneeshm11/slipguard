"""Exploration: tool-response texts that follow edit_file calls (success/error variety) and raw-call-in-content cases."""
import json, sys, collections, re
f = sys.argv[1]
lines = []
for line in open(f, errors='replace'):
    try: lines.append(json.loads(line))
    except Exception: pass
resp_kinds = collections.Counter(); ex = {}
raw_ex = []
for i, d in enumerate(lines):
    ms = d['messages']
    idmap = {}
    for m in ms:
        if m.get('role') == 'assistant':
            for t in m.get('tool_calls') or []:
                idmap[t.get('id')] = t['function']['name']
            c = m.get('content') or ''
            if '<|tool_call>' in c or re.search(r'call:\w+\{', c):
                raw_ex.append((i, c[:400], m.get('tool_calls')))
        if m.get('role') == 'tool' and idmap.get(m.get('tool_call_id')) == 'edit_file':
            c = m.get('content') or ''
            try:
                j = json.loads(c); k = ('error' if 'error' in j else j.get('status')), tuple(sorted(j.keys()))
            except Exception:
                k = ('nonjson', c[:60])
            resp_kinds[k] += 1
            ex.setdefault(k, c[:700])
for k, v in resp_kinds.most_common(12): print(v, k); print('    EX:', ex[k][:700].replace('\n', ' | ')); print()
print('RAW content examples', len(raw_ex))
seen = set()
for i, c, tc in raw_ex:
    if c in seen: continue
    seen.add(c); print('--', i, repr(c)[:400], 'tool_calls=', str(tc)[:150])
    if len(seen) > 5: break
