"""Evidence for out/template_thinking_off_gap.md: render the 300 gate contexts (arm P0, unmodified logged histories)
with the June (main-track) and July (HF) templates, enable_thinking true / false, and record the prompt endings and their
last token ids. Also renders a context whose last message is a user turn (fresh model turn) as the control.
usage: check_template_thinking_off.py <out.json>"""
import json, sys, os, collections, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemma_protocol as gp, variants as V
from transformers import AutoTokenizer
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
meta = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
ids = [x.strip() for x in open(f'{D}/data/ids_gate300.txt') if x.strip()]
TPL = {'june': gp.OLD_TEMPLATE, 'july': gp.NEW_TEMPLATE}
res = {'token_ids': {t: tok.convert_tokens_to_ids(t) for t in ('<|channel>', '<channel|>', '<|think|>', '<|tool_response>', '<tool_response|>', '<|turn>', '<turn|>', '<|tool_call>', '<tool_call|>')},
       'endings': {}, 'last_tokens_example': {}, 'think_token_in_system': {}, 'fresh_turn_control': {}}
for name, path in TPL.items():
    tpl = open(path).read()
    for flag in (True, False):
        c = collections.Counter(); key = f"{name}:{'ON' if flag else 'OFF'}"; nthink = 0
        for cid in ids:
            msgs, tools = V.load_context(meta[cid])
            s = tok.apply_chat_template(gp.to_template_messages(msgs), tools=tools, add_generation_prompt=True, tokenize=False, enable_thinking=flag, chat_template=tpl)
            nthink += '<|think|>' in s
            e = ('<tool_response|><|channel>thought\\n (open thought)' if s.endswith('<tool_response|><|channel>thought\n') else
                 '<tool_response|> (nothing appended)' if s.endswith('<tool_response|>') else
                 '<|turn>model\\n<|channel>thought\\n<channel|> (closed thought)' if s.endswith('<|turn>model\n<|channel>thought\n<channel|>') else 'other: ' + repr(s[-30:]))
            c[e] += 1
            if key not in res['last_tokens_example']:
                ids_ = tok(s, add_special_tokens=False)['input_ids'][-6:]
                res['last_tokens_example'][key] = {'ids': ids_, 'pieces': tok.convert_ids_to_tokens(ids_)}
        res['endings'][key] = dict(c); res['think_token_in_system'][key] = nthink
    # control: same first context truncated after its first user message (a fresh model turn)
    msgs, tools = V.load_context(meta[ids[0]])
    k = max(i for i, m in enumerate(msgs) if m['role'] == 'user' and i <= 2)
    for flag in (True, False):
        s = tok.apply_chat_template(gp.to_template_messages(msgs[:k + 1]), tools=tools, add_generation_prompt=True, tokenize=False, enable_thinking=flag, chat_template=tpl)
        ids_ = tok(s, add_special_tokens=False)['input_ids'][-6:]
        res['fresh_turn_control'][f"{name}:{'ON' if flag else 'OFF'}"] = {'tail': s[-45:], 'last_ids': ids_, 'pieces': tok.convert_ids_to_tokens(ids_)}
json.dump(res, open(sys.argv[1], 'w'), indent=1); print(json.dumps(res, indent=1))
