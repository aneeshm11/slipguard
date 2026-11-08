import os  # added by the repo export (paths are env/config driven)
import json, httpx
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
s = tok.apply_chat_template([{'role': 'system', 'content': 'hi'}, {'role': 'user', 'content': 'Say OK.'}], add_generation_prompt=True, tokenize=False, enable_thinking=True)
print(repr(s[:40]))
a = tok(s, add_special_tokens=False)['input_ids']; b = tok(s, add_special_tokens=True)['input_ids']
print('local no-special', len(a), a[:3], ' with-special', len(b), b[:3])
for ast in (None, False):
    body = {'model': 'gemma-4-31b', 'prompt': s, 'max_tokens': 1, 'temperature': 0}
    if ast is not None: body['add_special_tokens'] = ast
    r = httpx.post('http://127.0.0.1:8300/v1/completions', json=body, timeout=600).json()
    print('server add_special_tokens=', ast, 'prompt_tokens', r['usage']['prompt_tokens'])
body = {'model': 'gemma-4-31b', 'messages': [{'role': 'system', 'content': 'hi'}, {'role': 'user', 'content': 'Say OK.'}], 'max_tokens': 1, 'temperature': 0, 'chat_template_kwargs': {'enable_thinking': True}}
r = httpx.post('http://127.0.0.1:8300/v1/chat/completions', json=body, timeout=600).json()
print('server chat prompt_tokens', r['usage']['prompt_tokens'])
