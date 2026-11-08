"""CPU check of A's injectors on P's 4 SMOKE contexts (contexts only; no outcomes): P0 render == logged prompt_tokens,
and every confirmatory arm builds (P1, P5, P6, P8a, P8b, P9 at k 1; P6 at k 2 where k_usable allows).
usage: test_P_smoke.py <corpus dir> <meta.jsonl>"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemma_protocol as gp, variants as V
from transformers import AutoTokenizer
cdir, metap = sys.argv[1:3]
man = json.load(open(os.path.join(cdir, 'manifest.json')))
gp.set_profile(man['tool_profile'], tools=man['tools'], responses=man['harness'].get('responses'))
gp.PROFILE['system_as_parts'] = man['render'].get('system_content_form', 'parts') == 'parts'
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
for l in open(metap):
    m = json.loads(l); ctx = V.load_context(m)
    p0, _ = V.build_prompt(tok, m, 'P0', 0, which=m['template_path'], ctx=ctx)
    n0 = len(tok(p0, add_special_tokens=False)['input_ids'])
    line = f"{m['id']}: k_usable {m['k_usable']} k_unmasked {m['k_unmasked']} | P0 tokens {n0} vs logged {m['pt']} -> {'OK' if n0 == m['pt'] else 'MISMATCH'}"
    if m['k_usable'] >= 1:
        for pw in ('P1', 'P5', 'P6', 'P8a', 'P8b', 'P9'):
            p, info = V.build_prompt(tok, m, pw, 1, which=m['template_path'], ctx=ctx)
            line += f" | {pw} +{len(tok(p, add_special_tokens=False)['input_ids']) - n0} tok"
            if pw == 'P1':
                tail = p[p.rfind('call:edit_file{'):][:160]
                assert 'Error: edit_file was called without the required argument(s)' in p, 'P1 error text missing'
                line += f" missing={info.get('missing')}"
        if m['k_usable'] >= 2:
            p, _ = V.build_prompt(tok, m, 'P6', 2, which=m['template_path'], ctx=ctx); line += ' | P6k2 ok'
    print(line)
print('P SMOKE INJECTION CHECK DONE')
