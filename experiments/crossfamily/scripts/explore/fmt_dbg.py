import os  # added by the repo export (paths are env/config driven)
import json, sys
sys.path.insert(0, 'scripts'); sys.path.insert(0, 'scripts/frozen')
import qwenproto as qp
rs = [json.loads(l) for l in open('format/format_cases.jsonl')]
for r in rs:
    if 'skip' in r: continue
    e = r['res'].get('J_real', {})
    if isinstance(e, dict) and (e.get('hermes.nonstream') or {}).get('cls') == 'exact':
        print('J_real exact:', r['id'], repr(r['closer']), r['host'], r['next'])
print('skipped', [r['id'] for r in rs if 'skip' in r][:12])
n = 0
for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/conformance/fuzz/cases.jsonl')):
    d = json.loads(l)
    if d.get('subfamily') != 'real_clean_call': continue
    it = d['intended'][0]
    for fmt in ('hermes', 'xml'):
        t = qp.call_text(fmt, it['name'], it['arguments'], list(it['arguments']))
        st = qp.strict_parse(t, fmt, d['tools'])
        if not st['ok']:
            n += 1
            if n <= 8: print(fmt, st['code'], it['name'], json.dumps(it['arguments'])[:200])
