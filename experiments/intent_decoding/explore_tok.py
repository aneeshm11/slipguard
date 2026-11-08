import os  # added by the repo export (paths are env/config driven)
import json
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
for s in ['<|"|>', '`,old_string:', '``,old_string:', '",old_string:', '\\",old_string:', '"""', "'''", '```', '`}', 'foo`bar`,old_string:<|"|>', '    return x`,old_string:<|"|>', '<|tool_call>call:edit_file{filepath:<|"|>a.py<|"|>,new_string:<|"|>x<|"|>}<tool_call|>']:
    ids = tok.encode(s, add_special_tokens=False)
    print(repr(s), ids, [tok.decode([i]) for i in ids])
rows=[json.loads(l) for l in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/protocol/contexts.jsonl'))][:3]
def fix(msgs):
    out=[]
    for m in msgs:
        m=dict(m)
        if m.get('tool_calls'):
            tcs=[]
            for t in m['tool_calls']:
                t=json.loads(json.dumps(t)); f=t.get('function',{})
                if isinstance(f.get('arguments'),str):
                    try: f['arguments']=json.loads(f['arguments'])
                    except Exception: f['arguments']={}
                tcs.append(t)
            m['tool_calls']=tcs
        out.append(m)
    return out
for th in (True, False):
    p = tok.apply_chat_template(fix(rows[0]['messages']), tools=rows[0]['tools'], add_generation_prompt=True, tokenize=False, enable_thinking=th)
    print('THINK', th, len(tok.encode(p, add_special_tokens=False)), repr(p[-600:]))
p = tok.apply_chat_template(fix(rows[0]['messages']), tools=rows[0]['tools'], add_generation_prompt=True, tokenize=False, enable_thinking=True)
i = p.find('declaration:edit_file'); print(p[i:i+1500])
