"""Which chat template produced the logged prompts?  Render logged contexts with the main-track (Jun-5) template and the
current HF template and compare the token count with the logged prompt_tokens (exact match expected for the right one)."""
import os  # added by the repo export (paths are env/config driven)
import json, sys, random
from transformers import AutoTokenizer
OLD = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')
NEW = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
tpl = {'old': open(OLD).read(), 'new': open(NEW).read()}
idx = [json.loads(l) for l in open(sys.argv[1])]
random.seed(1)
cand = [r for r in idx if not r.get('bad_line') and r['model'] == 'openai/gemma-4-31b-it-qat-w4a16-ct' and not r['teacher'] and r['think']]
sample = random.sample(cand, int(sys.argv[2]) if len(sys.argv) > 2 else 12)
root = os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/runs')


def fix(msgs):
    out = []
    for m in msgs:
        m = dict(m)
        if m.get('tool_calls'):
            tcs = []
            for t in m['tool_calls']:
                t = json.loads(json.dumps(t)); f = t['function']
                if isinstance(f.get('arguments'), str):
                    f['arguments'] = json.loads(f['arguments']) if f['arguments'] else {}
                tcs.append(t)
            m['tool_calls'] = tcs
        out.append(m)
    return out


tools_cache = {}
for r in sample:
    path = f"{root}/{r['run']}/{r['file']}"
    if path not in tools_cache:
        with open(path) as f: tools_cache[path] = json.loads(f.readline())['tools']
    with open(path, 'rb') as f:
        f.seek(r['off']); d = json.loads(f.readline())
    msgs = fix(d['messages'])
    row = {'run': r['run'], 'logged_pt': r['pt'], 'cached': d.get('cached_tokens')}
    for k, t in tpl.items():
        s = tok.apply_chat_template(msgs, tools=tools_cache[path], add_generation_prompt=True, tokenize=False, enable_thinking=True, chat_template=t)
        row[k] = len(tok(s, add_special_tokens=False)['input_ids'])
        row[k + '_tail'] = s[-60:]
    print(json.dumps(row))
