"""Natural production slips of a Qwen XML-format model in the SAME harness (read-only, descriptive; NOT a Gemma
statistic and not part of any replication contrast): the main-track teacher runs t1_qwen / t2_qwen_rebench /
t3_qwen_rebench served Qwen3.8-flash-next with vLLM's qwen3_coder parser under the Gemma alias. Every logged tool call
(as returned by the parser) is judged with X's call_flags; responses whose content still carries <tool_call> /
<function= text are counted as loud (unparsed). XML residue signatures inside values are tallied.
usage: teacher_xml_slips.py out.json"""
import glob, json, re, sys, collections, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qwenproto as qp
RUNS = ['t1_qwen', 't2_qwen_rebench', 't3_qwen_rebench']
c = collections.Counter(); ex = collections.defaultdict(list); per_run = collections.Counter()
RESID = re.compile(r'(</?param[a-z]*>?|</?parameter|</?function|</?tool_call|</(old_string|new_string|filepath|content|command)>)\s*$')
for run in RUNS:
    for fn in sorted(glob.glob(fos.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs/{run}/llm_calls_*.jsonl'))):
        for line in open(fn, errors='replace'):
            try:
                d = json.loads(line)
            except Exception:
                c['bad_line'] += 1; continue
            r = d.get('response') or {}
            c['responses'] += 1
            content = r.get('content') or ''
            if '<tool_call>' in content or '<function=' in content:
                c['loud_unparsed_response'] += 1
                if len(ex['loud']) < 5: ex['loud'].append(content[-600:])
            for tc in r.get('tool_calls') or []:
                f = tc.get('function') or {}
                name = f.get('name')
                try:
                    a = json.loads(f.get('arguments') or '{}')
                except Exception:
                    a = {'__unparseable_args__': f.get('arguments')}
                c['calls'] += 1; c[f'calls:{name}'] += 1; per_run[(run, name)] += 1
                flags, gem = qp.call_flags(name, a)
                if flags:
                    c['malformed_calls'] += 1; c[f'malformed:{name}'] += 1
                    for fl in flags: c['flag:' + fl.split(':')[0] + (':' + name if fl.startswith('missing') else '')] += 1
                    if len(ex[name]) < 6: ex[name].append({'flags': flags, 'args': json.dumps(a, ensure_ascii=False)[:500]})
                if isinstance(a, dict):
                    for k, v in a.items():
                        if isinstance(v, str) and RESID.search(v):
                            c['xml_residue_at_value_end'] += 1
                            if len(ex['residue']) < 6: ex['residue'].append({'name': name, 'key': k, 'tail': v[-120:]})
out = {'counts': dict(c), 'per_run_calls': {f'{k[0]}:{k[1]}': v for k, v in per_run.items()}, 'examples': ex}
json.dump(out, open(sys.argv[1], 'w'), indent=1)
print(json.dumps({k: v for k, v in c.items()}, indent=0))
