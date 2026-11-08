"""CPU checks for PREREG_v2.1 / v2.2 renders (no server): the closed-thought form in both templates, its tokenization,
the model's own generated thought forms in the thinking-ON gate runs, and the prompt endings of the 300 gate contexts.
usage: check_thought_forms.py <out.json>"""
import json, sys, os, re, collections, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemma_protocol as gp, variants as V
from transformers import AutoTokenizer
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
PRE = '<|channel>thought\n<channel|>'
res = {}
june, july = open(gp.OLD_TEMPLATE).read(), open(gp.NEW_TEMPLATE).read()
res['template_closed_thought_string'] = {'june_contains': june.count("'" + PRE.replace('\n', '\\n') + "'"), 'july_contains': july.count("'" + PRE.replace('\n', '\\n') + "'"),
                                         'june_history_thought_form': "'<|channel>thought\\n' + thinking_text + '\\n<channel|>'" in june}
ids = tok(PRE, add_special_tokens=False)['input_ids']
res['prefill_tokens'] = {'ids': ids, 'pieces': tok.convert_ids_to_tokens(ids),
                         'channel_open_id': tok.convert_tokens_to_ids('<|channel>'), 'channel_close_id': tok.convert_tokens_to_ids('<channel|>'),
                         'think_id': tok.convert_tokens_to_ids('<|think|>'),
                         'special': {t: (t in tok.all_special_tokens or t in tok.get_added_vocab()) for t in ('<|channel>', '<channel|>', '<|think|>')}}
# the model's own generated thoughts (thinking ON gate runs, P0)
ends = collections.Counter(); starts = collections.Counter(); empties = 0; n = 0
for f in sorted(glob.glob(f'{D}/out/main/r31b_old_*.jsonl')):
    for l in open(f):
        d = json.loads(l)
        if d.get('error') or d.get('pathway') != 'P0': continue
        s = d.get('s1_text') or ''
        i = s.find('<|channel>')
        if i < 0: starts['no_thought'] += 1; continue
        n += 1; starts[repr(s[i:i + 18])] += 1
        j = s.find('<channel|>', i)
        if j < 0: ends['unclosed'] += 1; continue
        ends['newline_before_close' if s[j - 1:j] == '\n' else 'no_newline_before_close'] += 1
        if s[i:j + len('<channel|>')] == PRE: empties += 1
        if n >= 2000: break
res['model_generated_thoughts_ON_P0'] = {'n_with_thought': n, 'starts': dict(starts.most_common(5)), 'ends': dict(ends), 'exact_empty_closed_thought': empties}
# prompt endings for the gate contexts under ON / OFF / S (flag off + prefill), arm P0 and P1
meta = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/data/contexts_meta.jsonl')}
ids300 = [x.strip() for x in open(f'{D}/data/ids_gate300.txt') if x.strip()]
orig = V.render
endc = collections.defaultdict(collections.Counter); think_tok = collections.Counter(); hist_thoughts = collections.Counter()
for cid in ids300:
    m = meta[cid]; ctx = V.load_context(m)
    for pw, k in (('P0', 0), ('P1', 1), ('P5', 1), ('P6', 1), ('P8a', 1)):
        for flag in (True, False):
            V.render = lambda tok_, msgs, tools, subs=(), which='old', think=True, _f=flag: orig(tok_, msgs, tools, subs, which, think=_f)
            p, _ = V.build_prompt(tok, m, pw, k, ctx=ctx)
            tail = p[-40:]
            e = ('template_closed_thought' if p.endswith('<|turn>model\n' + PRE) else 'turn_model_header' if p.endswith('<|turn>model\n')
                 else 'after_tool_response' if p.endswith('<tool_response|>') else 'other:' + repr(tail[-20:]))
            endc[f"{'ON' if flag else 'OFF'}:{pw}"][e] += 1
            think_tok[f"{'ON' if flag else 'OFF'}"] += ('<|think|>' in p)
            if pw == 'P0' and not flag: hist_thoughts['P0_OFF_history_has_thought'] += ('<|channel>thought\n' in p)
V.render = orig
res['prompt_endings'] = {k: dict(v) for k, v in endc.items()}
res['think_token_in_system'] = dict(think_tok)
res['history_thoughts'] = dict(hist_thoughts)
json.dump(res, open(sys.argv[1], 'w'), indent=1)
print(json.dumps(res, indent=1)[:4000])
