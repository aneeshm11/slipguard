import json, httpx, time
B='http://127.0.0.1:8311/v1'; M='gemma-4-e4b'
p = '<bos><|turn>user\nSay hi in a tool call.<turn|>\n<|turn>model\n<|channel>thought\n<channel|><|tool_call>call:edit_file{filepath:<|"|>a.py<|"|>,new_string:<|"|>x = 1'
r = httpx.post(B+'/completions', json={'model':M,'prompt':p,'max_tokens':3,'temperature':0,'logprobs':20,'skip_special_tokens':False,'spaces_between_special_tokens':False}, timeout=60).json()
c = r['choices'][0]; print(repr(c['text']), c.get('finish_reason'), c.get('stop_reason'))
print(list(c['logprobs'].keys()))
print(c['logprobs']['tokens'], c['logprobs']['top_logprobs'][0])
r = httpx.post(B+'/completions', json={'model':M,'prompt':p+'<|"|>}','max_tokens':1,'temperature':0,'prompt_logprobs':0,'skip_special_tokens':False}, timeout=60).json()
c = r['choices'][0]; pl = c.get('prompt_logprobs') or r.get('prompt_logprobs')
print('prompt_logprobs where:', 'choice' if c.get('prompt_logprobs') else 'top', len(pl)); print(pl[:2], pl[-3:])
r = httpx.post(B+'/completions', json={'model':M,'prompt':p,'max_tokens':50,'temperature':0,'stop':['<tool_call|>', 'zzz'],'skip_special_tokens':False,'spaces_between_special_tokens':False}, timeout=60).json()
c = r['choices'][0]; print(repr(c['text']), c.get('finish_reason'), c.get('stop_reason'), r['usage'])
