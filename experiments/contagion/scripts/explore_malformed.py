"""Exploration: show real malformed edit_file calls (parsed args as logged), the tool response the harness returned,
and how the call appears in the next call's history. Read-only over main-track logs."""
import json, sys, re
f = sys.argv[1]; nmax = int(sys.argv[2]) if len(sys.argv) > 2 else 4
CL = re.compile(r'(["`\\\']+)\s*,\s*(old_string|new_string|filepath|allow_multiple)\s*:')
lines = []
for line in open(f, errors='replace'):
    try: lines.append(json.loads(line))
    except Exception: pass
shown = 0
by_task = {}
for i, d in enumerate(lines): by_task.setdefault(d.get('task'), []).append(i)
for i, d in enumerate(lines):
    r = d.get('response') or {}
    for tc in r.get('tool_calls') or []:
        fn = tc.get('function', tc)
        if fn.get('name') != 'edit_file': continue
        a = fn.get('arguments')
        try: a = json.loads(a)
        except Exception: continue
        if 'old_string' in a: continue
        print('=' * 100); print('LINE', i, 'task', d.get('task'), 'model', d.get('model'))
        print('PARSED ARGS keys:', list(a.keys()))
        for k, v in a.items(): print('  ', repr(k)[:80], '=>', repr(v)[-300:])
        print('RAW content:', repr((r.get('content') or ''))[:300])
        # find the next call of the same task: tool response for this call id
        idx = by_task[d.get('task')]; nxt = [j for j in idx if j > i]
        if nxt:
            ms = lines[nxt[0]]['messages']
            for m in ms:
                if m.get('role') == 'tool' and m.get('tool_call_id') == tc.get('id'):
                    print('TOOL RESPONSE:', repr(m.get('content'))[:600])
                if m.get('role') == 'assistant' and any(t.get('id') == tc.get('id') for t in (m.get('tool_calls') or [])):
                    print('HISTORY assistant tool_calls:', repr(m.get('tool_calls'))[:500])
                    print('HISTORY assistant content:', repr(m.get('content'))[:200])
            # what did the model emit next?
            r2 = lines[nxt[0]].get('response') or {}
            for t2 in r2.get('tool_calls') or []:
                print('NEXT CALL:', (t2.get('function') or t2).get('name'), repr((t2.get('function') or t2).get('arguments'))[:300])
        shown += 1
        if shown >= nmax: sys.exit(0)
