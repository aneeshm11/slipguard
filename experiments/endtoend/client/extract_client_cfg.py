"""Make the no-nudge client see EXACTLY what the official harness sends: copy the system message and the tool
declarations from the first logged request of a harness session (proxy log record with 'request'), dropping
declarations that are not swegemma tools (the ADK AgentTool sub-agent needs ADK machinery).
Usage: extract_client_cfg.py <proxy_log.jsonl> <task_tag_prefix> <out_dir>"""
import json
import sys
from pathlib import Path

SWE = {'run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch',
       'get_code_neighbors', 'search_similar_code', 'get_code_subgraph'}
log, prefix, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
for line in open(log):
    r = json.loads(line)
    if r.get('task', '').startswith(prefix) and r.get('request') and r['request'].get('tools'):
        req = r['request']
        break
else:
    sys.exit('no first-call request found')
msgs = req['messages']
sysm = msgs[0]
assert sysm['role'] == 'system', sysm['role']
text = sysm['content'] if isinstance(sysm['content'], str) else ''.join(p.get('text', '') for p in sysm['content'])
tools = [t for t in req['tools'] if (t.get('function') or t)['name'] in SWE]
dropped = [(t.get('function') or t)['name'] for t in req['tools'] if (t.get('function') or t)['name'] not in SWE]
out.mkdir(parents=True, exist_ok=True)
(out / 'client_system.txt').write_text(text)
(out / 'client_tools.json').write_text(json.dumps(tools, indent=1))
samp = {k: v for k, v in req.items() if k not in ('messages', 'tools')}
(out / 'client_request_params.json').write_text(json.dumps({'from_task': r['task'], 'harness_params': samp,
                                                            'dropped_tools': dropped}, indent=1))
print(json.dumps({'system_chars': len(text), 'tools': [(t.get('function') or t)['name'] for t in tools],
                  'dropped': dropped, 'params': samp}, indent=1)[:3000])
