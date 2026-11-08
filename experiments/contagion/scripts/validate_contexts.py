"""Validate a workstream-P corpus against CONTEXT_SCHEMA.md before any arm runs:
(1) re-render the first N contexts with the manifest's template and compare the token count with `prompt_tokens`
    (exact match required; system content tried as declared, then the other form, and the result is reported);
(2) every tool response follows its call; (3) the contexts file holds no outcome fields.
usage: validate_contexts.py <manifest.json> [N=50] [--tok <tokenizer dir>]"""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import gemma_protocol as gp
from transformers import AutoTokenizer
man_path = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 50
tokdir = sys.argv[sys.argv.index('--tok') + 1] if '--tok' in sys.argv else os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')
man = json.load(open(man_path)); base = os.path.dirname(os.path.abspath(man_path))
gp.set_profile(man['tool_profile'], tools=man['tools'], responses=man['harness'].get('responses'))
tok = AutoTokenizer.from_pretrained(tokdir)
tpl = open(man['render']['chat_template_path']).read(); kw = man['render'].get('chat_template_kwargs', {'enable_thinking': True})
ctx_file = os.path.join(base, man['files']['contexts'])
res = {'checked': 0, 'token_match_declared': 0, 'token_match_other_form': 0, 'order_ok': 0, 'outcome_fields_present': 0, 'mismatch_examples': []}
for i, l in enumerate(open(ctx_file)):
    if i >= N: break
    d = json.loads(l); res['checked'] += 1
    if any(k in d for k in ('response', 'outcome', 'attempt_resolved')): res['outcome_fields_present'] += 1
    msgs = d['messages']; tools = d.get('tools') or man['tools']
    ids = {}; ok = True
    for j, m in enumerate(msgs):
        for tc in m.get('tool_calls') or []: ids[tc['id']] = j
        if m.get('role') == 'tool' and not (m.get('tool_call_id') in ids and ids[m['tool_call_id']] < j): ok = False
    res['order_ok'] += ok
    def count(parts):
        gp.PROFILE['system_as_parts'] = parts
        mm = gp.to_template_messages(msgs) if parts else [dict(m, tool_calls=[dict(t, function=dict(t['function'], arguments=json.loads(t['function']['arguments']) if isinstance(t['function'].get('arguments'), str) else t['function'].get('arguments'))) for t in m['tool_calls']]) if m.get('tool_calls') else m for m in msgs]
        s = tok.apply_chat_template(mm, tools=tools, add_generation_prompt=True, tokenize=False, chat_template=tpl, **kw)
        return len(tok(s, add_special_tokens=False)['input_ids'])
    declared_parts = man['render'].get('system_content_form', 'parts') == 'parts'
    c1 = count(declared_parts)
    if c1 == d.get('prompt_tokens'): res['token_match_declared'] += 1
    else:
        c2 = count(not declared_parts)
        if c2 == d.get('prompt_tokens'): res['token_match_other_form'] += 1
        elif len(res['mismatch_examples']) < 5: res['mismatch_examples'].append({'context_id': d['context_id'], 'logged': d.get('prompt_tokens'), 'declared_form': c1, 'other_form': c2})
gp.PROFILE['system_as_parts'] = True
res['PASS'] = (res['token_match_declared'] == res['checked'] and res['order_ok'] == res['checked'] and res['outcome_fields_present'] == 0)
print(json.dumps(res, indent=1))
