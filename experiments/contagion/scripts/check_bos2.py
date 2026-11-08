import os  # added by the repo export (paths are env/config driven)
import json, httpx
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
msgs = [{'role': 'system', 'content': 'hi'}, {'role': 'user', 'content': 'Say OK.'}]
r1 = httpx.post('http://127.0.0.1:8300/tokenize', json={'model': 'gemma-4-31b', 'messages': msgs, 'chat_template_kwargs': {'enable_thinking': True}, 'add_generation_prompt': True}, timeout=60).json()
s = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=True)
r2 = httpx.post('http://127.0.0.1:8300/tokenize', json={'model': 'gemma-4-31b', 'prompt': s}, timeout=60).json()
print('chat tokens', r1.get('count'), r1.get('tokens')[:6])
print('prompt tokens', r2.get('count'), r2.get('tokens')[:6])
print("CHAT", [tok.decode([t]) for t in r1["tokens"]]); print("PROMPT", [tok.decode([t]) for t in r2["tokens"]])
