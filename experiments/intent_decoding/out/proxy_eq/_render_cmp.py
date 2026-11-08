import json, sys, collections, os
sys.dont_write_bytecode = True
sys.argv = ["x", "offline"]; sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "experiments/intent_decoding"))
import proxy_equivalence as PE
EGP, EPX = PE.load_e()
engine = EPX.Engine(PE.MODEL_DIR_JUNE)
tok = engine.tok
june = open(PE.JUNE_TPL).read()
cnt = collections.Counter(); diffs = collections.Counter()
for i, l in enumerate(open(PE.CTX)):
    if i >= 600: break
    c = json.loads(l)
    mine = tok.apply_chat_template(PE.fix_msgs(c['messages']), tools=c['tools'], add_generation_prompt=True, tokenize=False, enable_thinking=True, chat_template=june)
    ptext, pids = engine.render_ids(EGP.to_conversation(c['messages']), [dict(t) for t in c['tools']], {'enable_thinking': True}, False)
    nm = len(tok.encode(mine, add_special_tokens=False)); npx = len(pids)
    cnt['mine==logged'] += nm == c['prompt_tokens']; cnt['proxy==logged'] += npx == c['prompt_tokens']
    cnt['proxy-mine=%d' % (npx - nm)] += 1
    if len(ptext) - len(mine) == 1 and ptext.replace('. <|tool>', '.<|tool>', 1) == mine: diffs['only_space_before_tool_decl'] += 1
    else:
        i = next((k for k in range(min(len(mine), len(ptext))) if mine[k] != ptext[k]), None)
        diffs['other'] += 1
        if cnt['shown'] < 3:
            cnt['shown'] += 1; print('DIFF', c['id'], repr(mine[max(0,(i or 0)-60):(i or 0)+60]), '||', repr(ptext[max(0,(i or 0)-60):(i or 0)+60]))
    cnt['logged_minus_proxy=%d' % (c['prompt_tokens'] - npx)] += 1 if cnt['n'] < 600 else 0
    cnt['n'] += 1
print(dict(cnt)); print(dict(diffs))
