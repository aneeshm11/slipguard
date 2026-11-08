"""Smoke test of (i) and (ii) code paths against a live server on a synthetic slip in a real context.
usage: python tests/smoke_server.py <base> <model> <tokenizer_dir>"""
import asyncio, json, sys, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from transformers import AutoTokenizer
from gemma_protocol import D, TC_START, TC_END, schema_from_tools, first_slip_site, is_valid
from intent_decode import Server, rollback_resume, lik_repair, ChannelPrior, ids_of, token_logprob
from replay_utils import fix_msgs
base, model, tokp = sys.argv[1], sys.argv[2], sys.argv[3]
tok = AutoTokenizer.from_pretrained(tokp)
c = json.loads(open(os.path.join(HERE, 'data/replay_first_edit.jsonl')).readline())
schema = schema_from_tools(c['tools'])
p0 = tok.apply_chat_template(fix_msgs(c['messages']), tools=c['tools'], add_generation_prompt=True, tokenize=False,
                             enable_thinking=False)
prefix = p0 + TC_START
fp = c['filepath'] or 'a.py'
text = 'call:edit_file{filepath:' + D + fp + D + ',new_string:' + D + 'x = "a"`,old_string:' + D + 'x = 1' + D + '}'
PRIOR = ChannelPrior.from_log_slips('ft_edit')


async def main():
    srv = Server(base, model, conc=8)
    pid = ids_of(tok, prefix)
    # exactness check: forced logprob of the true delimiter after an unremarkable prefix
    lp = await token_logprob(srv, pid + ids_of(tok, 'call:edit_file{filepath:' + D + fp), 52)
    print('forced lp(<|"|> after filepath) =', round(lp, 4))
    print('site', first_slip_site(text, schema, True))
    r = await rollback_resume(srv, tok, prefix, text, True, schema, rule='nc', prior=PRIOR, max_tokens=256, prefix_ids=pid)
    print('i:', r['valid'], repr(r['text'][-120:]),
          [(x['cut_choice'].get('lls'), x['cut_choice'].get('prior'), x['cut_choice'].get('k')) for x in r['rounds']])
    ii = await lik_repair(srv, tok, prefix, text, True, schema, tau=0.0, prior=PRIOR, prefix_ids=pid)
    print('ii:', ii['decision'], ii.get('margin'), [(round(x['ll'], 3), round(x['prior'], 3), x['cuts']) for x in ii['cands']],
          ii.get('wctf'))
    v = 'call:edit_file{filepath:' + D + fp + D + ',new_string:' + D + 'x = "`,old_string:' + D + ',old_string:' + D + 'x' + D + '}'
    r2 = await rollback_resume(srv, tok, prefix, v, True, schema, rule='nc', prior=PRIOR, max_tokens=64, prefix_ids=pid)
    ii2 = await lik_repair(srv, tok, prefix, v, True, schema, prior=PRIOR, prefix_ids=pid)
    print('valid adversarial call untouched:', is_valid(v, schema), r2['changed'] is False, ii2['decision'] == 'identity')
    print(dict(srv.stats))
    await srv.close()
asyncio.run(main())
