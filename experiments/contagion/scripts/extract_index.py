"""Pass 1 (read-only over main-track logs): compact per-LLM-call index of every Gemma run.

For every logged call we keep: byte offset, attempt id, model, thinking flag/budget, sampling, token counts, and a
summary of the response (tool calls with emitted key order + malformation flags, raw call text left in content).
Messages are NOT copied here (contexts are materialised later from byte offsets).

Teacher runs served under the base model's name are excluded by run name (verified from launch.json / eval_cfg.json):
  t1_qwen, t2_qwen_rebench, t3_qwen_rebench -> port 8200 = Qwen teacher (qwen3_coder parser), served as gemma-4-31b
  dsprobe -> sub t_ds (DeepSeek-V4 teacher probe, thinking budget 12000)
usage: extract_index.py <runs_root> <out.jsonl>  (NP env = worker processes)
"""
import json, os, re, sys, glob, hashlib
from multiprocessing import Pool

TEACHER_RUNS = {'t1_qwen', 't2_qwen_rebench', 't3_qwen_rebench', 'dsprobe'}
ARGN = ['filepath', 'old_string', 'new_string', 'allow_multiple', 'content', 'command', 'start_line', 'end_line']
# synthesis criterion (ideation/community/synthesis_scripts/contagion.py), kept verbatim for replication
LEAK_SYN = re.compile(r'(["`\\]+\s*,\s*(%s)\s*:)|(<\|"\|>)|(<tool_call\|>)|(<\|tool_call>)|(call:\w+\{)' % '|'.join(ARGN))
CLOSER = re.compile(r'(["`\\\']+)\s*,\s*(old_string|new_string|filepath|allow_multiple)\s*:')
EDIT_KEYS = {'filepath', 'old_string', 'new_string', 'allow_multiple'}


def bad_edit_syn(a):
    """Exact replica of the synthesis malformed criterion."""
    if not isinstance(a, dict): return True, 'unparseable'
    for k in ('filepath', 'old_string', 'new_string'):
        if k not in a: return True, 'missing:' + k
    for k, v in a.items():
        if isinstance(v, str) and LEAK_SYN.search(v):
            m = CLOSER.search(v); return True, 'leak:' + (m.group(1) if m else 'tok')
    if any(k not in ARGN for k in a): return True, 'extra_key'
    return False, ''


def edit_flags(a):
    """Refined, schema-exact flags for one parsed edit_file argument dict."""
    if not isinstance(a, dict): return ['unparseable']
    fl = []
    for k in ('filepath', 'old_string', 'new_string'):
        if k not in a: fl.append('missing:' + k)
    for k in a:
        if k not in EDIT_KEYS: fl.append('extra_key')
    for k, v in a.items():
        if isinstance(v, str):
            if CLOSER.search(v): fl.append('leak_closer:' + k)
            if '<|"|>' in v or '<tool_call|>' in v or '<|tool_call>' in v: fl.append('special_tok:' + k)
    return sorted(set(fl))


def split_line(line):
    """Header dict (fields before messages) and response dict, without parsing the (huge) messages."""
    i = line.find('"messages": ')
    j = line.rfind('"response": ')
    if i < 0 or j < 0: return None, None
    head = json.loads(line[:i].rstrip().rstrip(',') + '}')
    # response is the last key: strip the final closing brace of the line object
    tail = line[j + len('"response": '):].rstrip()
    if tail.endswith('}'): tail = tail[:-1]
    try: resp = json.loads(tail)
    except Exception:
        resp = None
    return head, resp


def proc(path):
    run = path.split('/')[-2]
    out = []
    with open(path, 'rb') as f:
        off = 0
        ln = -1
        for raw in f:
            ln += 1
            o = off; off += len(raw)
            try:
                line = raw.decode('utf-8', errors='replace')
                head, resp = split_line(line)
            except Exception:
                head, resp = None, None
            if head is None:
                try:
                    d = json.loads(line); head = {k: v for k, v in d.items() if k not in ('messages', 'tools', 'response')}
                    resp = d.get('response')
                except Exception:
                    out.append({'run': run, 'file': os.path.basename(path), 'ln': ln, 'off': o, 'bad_line': 1}); continue
            has_tools = '"tools": [{"type": "function"' in line
            eb = head.get('extra_body') or {}
            ctk = eb.get('chat_template_kwargs') or {}
            rec = {'run': run, 'file': os.path.basename(path), 'ln': ln, 'off': o, 'task': head.get('task'),
                   'model': str(head.get('model')), 'think': bool(ctk.get('enable_thinking')),
                   'tbudget': eb.get('thinking_token_budget'), 'temp': head.get('temperature'), 'top_p': head.get('top_p'),
                   'pt': head.get('prompt_tokens'), 'ct': head.get('completion_tokens'), 'has_tools': has_tools,
                   'teacher': run in TEACHER_RUNS}
            r = resp or {}
            content = r.get('content') or ''
            rec['fin'] = r.get('finish_reason')
            rec['rlen'] = len(r.get('reasoning_content') or '')
            rec['clen'] = len(content)
            rec['raw'] = int('<|tool_call>' in content or bool(re.search(r'call:\w+\{', content)))
            rec['raw_edit'] = int(bool(re.search(r'call:edit_file\{', content)))
            calls = []
            for c in (r.get('tool_calls') or []):
                fn = c.get('function', c) or {}
                name = fn.get('name'); a = fn.get('arguments')
                if isinstance(a, str):
                    try: a = json.loads(a)
                    except Exception: a = None
                cc = {'name': name, 'id': c.get('id')}
                if name == 'edit_file':
                    b, why = bad_edit_syn(a)
                    cc['bad_syn'] = int(b); cc['why_syn'] = why
                    cc['flags'] = edit_flags(a)
                    cc['keys'] = list(a.keys()) if isinstance(a, dict) else None
                    m = None
                    if isinstance(a, dict):
                        for v in a.values():
                            if isinstance(v, str):
                                m = CLOSER.search(v)
                                if m: break
                    cc['closer'] = m.group(1) if m else None
                    cc['nlen'] = len(a.get('new_string') or '') if isinstance(a, dict) and isinstance(a.get('new_string'), str) else None
                    cc['olen'] = len(a.get('old_string') or '') if isinstance(a, dict) and isinstance(a.get('old_string'), str) else None
                    if isinstance(a, dict):
                        # content fingerprints (to tell retries of the same edit from new edits); new_string cut at a leak
                        ns = a.get('new_string') if isinstance(a.get('new_string'), str) else ''
                        mm = CLOSER.search(ns)
                        if mm: ns = ns[:mm.start()]
                        cc['fp'] = a.get('filepath') if isinstance(a.get('filepath'), str) else None
                        cc['nh'] = hashlib.md5(ns.strip()[:200].encode('utf-8', 'replace')).hexdigest()[:10]
                        os_ = a.get('old_string') if isinstance(a.get('old_string'), str) else None
                        cc['oh'] = hashlib.md5(os_.strip()[:200].encode('utf-8', 'replace')).hexdigest()[:10] if os_ is not None else None
                elif isinstance(a, dict):
                    cc['keys'] = list(a.keys())
                calls.append(cc)
            rec['calls'] = calls
            out.append(rec)
    return out


if __name__ == '__main__':
    root, outp = sys.argv[1], sys.argv[2]
    files = sorted(glob.glob(os.path.join(root, '*', 'llm_calls_*.jsonl')))
    files.sort(key=lambda p: -os.path.getsize(p))  # big first for load balance
    n = 0
    with Pool(int(os.environ.get('NP', '8'))) as p, open(outp, 'w') as fo:
        for recs in p.imap_unordered(proc, files, chunksize=1):
            for r in recs: fo.write(json.dumps(r) + '\n')
            n += len(recs)
    print('files', len(files), 'records', n)
