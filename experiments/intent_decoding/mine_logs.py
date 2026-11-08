"""Read-only miner over the main-track logs (/harness/work/runs/*/llm_calls_*.jsonl).

Outputs (under experiments/intent_decoding/data/):
  first_edit_contexts.jsonl : the state immediately before the FIRST edit_file call of every attempt
                              (messages + carried-forward tool declarations + logged outcome of that call)
  log_slips.jsonl           : every logged edit_file call (all models) whose parsed arguments show the
                              look-alike-closer signature  <run>,<declared key>:  (tail of the swallowing value),
                              plus a sample of clean calls, for closer statistics
The logger stores `tools` only on the first line of each file, so tools are carried forward per file.
"""
import json, os, re, sys, glob, collections
from multiprocessing import Pool

ROOT = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
EDIT_KEYS = ('filepath', 'old_string', 'new_string', 'allow_multiple')
SIG = re.compile(r'([`"\'\\]*)\s*,\s*(old_string|new_string|filepath|allow_multiple)\s*:\s*$')
SIG_ANY = re.compile(r'([`"\'\\]*)\s*,\s*(old_string|new_string|filepath|allow_multiple)\s*:')


def census_bad(a):
    """Census criterion (format_census / synthesis): missing required key, leaked closer+key, special token, unknown key."""
    if not isinstance(a, dict):
        return True, 'unparseable'
    for k in ('filepath', 'old_string', 'new_string'):
        if k not in a:
            return True, 'missing:' + k
    for k, v in a.items():
        if isinstance(v, str) and (SIG_ANY.search(v) or '<|"|>' in v or '<tool_call|>' in v or '<|tool_call>' in v):
            return True, 'leak'
    if any(k not in EDIT_KEYS for k in a):
        return True, 'extra_key'
    return False, 'ok'


def proc(path):
    run = path.split('/')[-2]
    tools = None
    seen_edit = set()
    firsts, slips = [], []
    with open(path, errors='replace') as f:
        for ln, line in enumerate(f):
            if ln == 0 or tools is None:
                pass
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('tools'):
                tools = d['tools']
            r = d.get('response') or {}
            tcs = r.get('tool_calls') or []
            att = d.get('task')
            model = str(d.get('model'))
            th = bool(((d.get('extra_body') or {}).get('chat_template_kwargs') or {}).get('enable_thinking'))
            for t in tcs:
                fn = t.get('function', t)
                name = fn.get('name')
                a = fn.get('arguments')
                if isinstance(a, str):
                    try:
                        a = json.loads(a)
                    except Exception:
                        a = None
                # slip signature in ANY tool's string args (value ending in run,key:)
                if isinstance(a, dict):
                    for k, v in a.items():
                        if isinstance(v, str):
                            m = SIG.search(v)
                            if m:
                                slips.append({'run': run, 'model': model, 'tool': name, 'key': k, 'closer_run': m.group(1),
                                              'next_key': m.group(2), 'tail': v[max(0, m.start() - 120):],
                                              'keys': list(a.keys()), 'vlen': len(v)})
                if name != 'edit_file':
                    continue
                if att in seen_edit:
                    continue
                seen_edit.add(att)
                bad, why = census_bad(a)
                if tools is None:
                    continue
                firsts.append({'id': f'{run}:{os.path.basename(path)}:{ln}', 'run': run, 'attempt': att, 'model': model,
                               'think': th, 'temperature': d.get('temperature'), 'prompt_tokens': d.get('prompt_tokens'),
                               'messages': d['messages'], 'tools': tools,
                               'filepath': (a or {}).get('filepath') if isinstance(a, dict) else None,
                               'orig_args': a if isinstance(a, dict) else None, 'orig_bad': bad, 'orig_why': why,
                               'orig_reasoning': r.get('reasoning_content')})
                break
    return firsts, slips


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(ROOT, '*', 'llm_calls_*.jsonl')))
    nproc = int(os.environ.get('NP', '8'))
    nf = ns = 0
    stats = collections.Counter()
    with open(os.path.join(OUT, 'first_edit_contexts.jsonl'), 'w') as fo, open(os.path.join(OUT, 'log_slips.jsonl'), 'w') as so, Pool(nproc) as p:
        for firsts, slips in p.imap_unordered(proc, files, chunksize=1):
            for r in firsts:
                fo.write(json.dumps(r) + '\n'); nf += 1
                stats[('base' if 'gemma-4-31b' in r['model'] else 'ft', r['orig_why'].split(':')[0])] += 1
            for s in slips:
                so.write(json.dumps(s) + '\n'); ns += 1
    print('first-edit contexts', nf, 'slip-signature values', ns)
    for k, v in sorted(stats.items()):
        print(k, v)
