"""Protocol-failure log for the conformance corpus (workstream C): every malformed / unparsed / repaired tool call
seen by the workstream-E proxies, with the FULL raw call text, what vLLM 0.19.1's gemma4 parser delivered, our
classification, and what intent-preserving decoding did.

Classes (first match wins):
  closer_slip        string closed by a look-alike run (` " ' \\) followed by ',<other declared key>:' or '}<tool_call|>'
  key_restart        closer + ',' + newline/indent + the SAME (or an already-emitted) key + ':' + <|"|>: the model
                     restarts an argument inside its own value; not covered by the stop strings nor by B's rules
  opener_drift       declared argument with separator '=' or a string value not opened by <|"|> (JSON/Python quotes,
                     bare text)
  key_drift          a key carrying quote characters (e.g. 'start_line":451'): JSON-mode drift on the key side
  missing_opener     call text 'call:NAME{...}<tool_call|>' without the <|tool_call> opener token (seen right after forced
                     thinking-budget ends); the parser returns it as plain content
  unparsed_call      '<|tool_call>' emitted but no call parsed (e.g. 'call edit_file{' with a space, unclosed call)
  unknown_tool       call to an undeclared tool
  other_malformed    anything else malformed under the SYNTHESIS §5 criterion
Output: failures/failure_log.jsonl (+ failures/summary.json). Usage: failure_log.py [proxy_log_dir ...]
"""
import os  # added by the repo export (paths are env/config driven)
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'proxy'))
import gemma_protocol as gp  # noqa: E402

E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))
DEFAULT = ['logs/proxy_dev', 'logs/archive_preref/proxy_dev2_oldproxy', 'logs/archive_closure_rule/proxy_e4b_closure',
           'logs/proxy_e4b_v2', 'logs/proxy_12b', 'logs/proxy_p12a', 'logs/proxy_p4a']
MODEL_OF = {'proxy_dev': 'gemma-4-31b', 'proxy_dev2_oldproxy': 'gemma-4-31b', 'proxy_e4b_closure': 'gemma-4-e4b',
            'proxy_e4b_v2': 'gemma-4-e4b', 'proxy_12b': 'gemma-4-12b', 'proxy_p12a': 'gemma-4-12b', 'proxy_p4a': 'gemma-4-e4b'}
RESTART = re.compile(r'([`"\'\\]*),[ \t]*\n[ \t]*([A-Za-z_][\w]*)[ \t]*:[ \t]*<\|"\|>')


def call_texts(raw):
    """every '<|tool_call>' segment of the answer part (up to <tool_call|> or end of text)"""
    out, i = [], 0
    while True:
        a = raw.find(gp.TC_START, i)
        if a < 0:
            return out
        b = raw.find(gp.TC_END, a)
        out.append(raw[a:(b + len(gp.TC_END)) if b >= 0 else len(raw)])
        i = a + len(gp.TC_START)


def classify_raw(seg, schemas, delivered):
    m = re.match(r'<\|tool_call>call:([\w\-\.]+)\{', seg)
    if not m:
        return 'unparsed_call', 'no call:NAME{ header'
    name = m.group(1)
    if name not in schemas:
        return 'unknown_tool', name
    for mm in RESTART.finditer(seg):
        k = mm.group(2)
        if k in schemas[name]['properties']:
            before = seg[:mm.start()]
            st = gp.open_call_state(before)
            if st and st.get('str_key') and (k == st['str_key'] or k in st['done_keys']):
                return 'key_restart', f'key {k} restarted inside {st["str_key"]} (closer {mm.group(1)!r})'
    if not seg.endswith(gp.TC_END):
        return 'unparsed_call', 'unclosed call'
    if delivered is not None and delivered.get('leak'):
        return 'closer_slip', f"closer {delivered['leak']['closer']!r} in {delivered['leak']['in']} before {delivered['leak']['key']}"
    site = gp.find_opener_site(seg, schemas)
    if site:
        return 'opener_drift', f"{site['key']} sep {site['sep']!r} lead {site['lead']!r}"
    props = schemas[name]['properties']
    for k in ((delivered or {}).get('args') or {}):
        if k not in props and k.strip(' "\'`') in props:
            return 'key_drift', f'key {k!r} (JSON/Python quoting on the key side)'

    return 'other_malformed', ','.join((delivered or {}).get('why') or [])


def main():
    dirs = sys.argv[1:] or DEFAULT
    out, seen = [], set()
    for d in dirs:
        for f in sorted(glob.glob(str(E / d / 'proxy_*.jsonl'))):
            cfg = Path(f).stem.replace('proxy_', '')
            for line in open(f):
                try:
                    r = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if r.get('status') != 200 or not r.get('raw'):
                    continue
                req = r.get('request') or {}
                tools = req.get('tools')
                calls = r.get('calls') or []
                ev = [e for e in r.get('events') or [] if e['ev'] in ('ipd_repair', 'posthoc_repair')]
                bad = [c for c in calls if not c['ok_delivered'] or not c['ok_emitted']]
                raw0 = r['raw']
                ans0 = raw0[raw0.rfind(gp.CH_END) + len(gp.CH_END):] if gp.CH_END in raw0 else raw0
                orphan = not calls and gp.TC_START not in ans0 and re.search(r'call:[\w\-\.]+\{', ans0)
                if not (bad or ev or r.get('unparsed_tool_call') or orphan):
                    continue
                raw = r['raw']
                key = (r.get('task'), r.get('rid'))
                if key in seen:
                    continue
                seen.add(key)
                # schemas: from the logged first request if present, else the competition tool set
                schemas = gp.tool_schemas(tools) if tools else STD
                segs = call_texts(raw)
                answer_start = raw.rfind(gp.CH_END)
                segs = [s for s in segs if raw.find(s) > answer_start] or segs
                for c in calls:
                    if c['ok_delivered'] and c['ok_emitted'] and not any(e.get('tool') == c['name'] for e in ev):
                        continue
                    seg = next((s for s in segs if s.startswith(f"{gp.TC_START}call:{c['name']}{{")), segs[0] if segs else '')
                    cls, detail = classify_raw(seg, schemas, c)
                    rep = [e for e in ev if e.get('tool') == c['name']]
                    if rep and cls == 'other_malformed':
                        cls = 'closer_slip' if rep[0].get('kind') in ('key', 'end', 'closer', 'last_arg') else 'opener_drift'
                        detail = f"repaired by IPD ({rep[0].get('kind')}): {rep[0].get('ctx', '')[-80:]!r}"
                    out.append({'class': cls, 'detail': detail, 'model': MODEL_OF.get(Path(d).name, '?'), 'source': f'{d}/{Path(f).name}',
                                'cfg': cfg, 'task': r.get('task'), 'rid': r.get('rid'), 'tool': c['name'],
                                'delivered_ok': c['ok_delivered'], 'why': c.get('why'),
                                'ipd': [{k: e.get(k) for k in ('ev', 'kind', 'closer', 'sep', 'lead', 'cut_k', 'how')} for e in rep],
                                'raw_call': seg if rep == [] else '(final text after repair; the slipped prefix is in ipd.ctx)',
                                'raw_call_final': seg, 'vllm_args': c.get('args')})
                ans = raw[raw.rfind(gp.CH_END) + len(gp.CH_END):] if gp.CH_END in raw else raw
                if not calls and gp.TC_START not in ans and re.search(r'call:[\w\-\.]+\{', ans):
                    out.append({'class': 'missing_opener', 'detail': 'call text without the <|tool_call> opener token'
                                + (' right after a forced thinking-budget end' if any(e['ev'] == 'budget_forced_end' for e in r.get('events') or []) else ''),
                                'model': MODEL_OF.get(Path(d).name, '?'), 'source': f'{d}/{Path(f).name}', 'cfg': cfg,
                                'task': r.get('task'), 'rid': r.get('rid'), 'tool': None, 'delivered_ok': False, 'why': ['no_call_parsed'],
                                'ipd': [], 'raw_call': ans[:2000], 'raw_call_final': ans[:2000], 'vllm_args': None})
                if r.get('unparsed_tool_call'):
                    for s in segs:
                        if not gp.CALL_RE.match(s):
                            cls, detail = classify_raw(s, schemas, None)
                            out.append({'class': cls if cls != 'other_malformed' else 'unparsed_call', 'detail': detail,
                                        'model': MODEL_OF.get(Path(d).name, '?'), 'source': f'{d}/{Path(f).name}', 'cfg': cfg,
                                        'task': r.get('task'), 'rid': r.get('rid'), 'tool': None, 'delivered_ok': False,
                                        'why': ['unparsed'], 'ipd': [], 'raw_call': s, 'raw_call_final': s, 'vllm_args': None})
    od = E / 'failures'
    od.mkdir(exist_ok=True)
    with open(od / 'failure_log.jsonl', 'w') as fo:
        for o in out:
            fo.write(json.dumps(o, ensure_ascii=False) + '\n')
    summ = {'n': len(out), 'by_class': Counter(o['class'] for o in out),
            'by_class_model': Counter(f"{o['model']}|{o['class']}" for o in out),
            'delivered_malformed_by_class': Counter(o['class'] for o in out if not o['delivered_ok']),
            'repaired_by_ipd_by_class': Counter(o['class'] for o in out if o['ipd'])}
    (od / 'summary.json').write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


STD = gp.tool_schemas(json.loads((E / 'configs/client_tools.json').read_text()))

if __name__ == '__main__':
    main()
