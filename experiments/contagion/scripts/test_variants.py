import os  # added by the repo export (paths are env/config driven)
import json, sys, random
sys.path.insert(0, 'scripts')
from transformers import AutoTokenizer
import variants as V
tok = AutoTokenizer.from_pretrained(os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
metas = [json.loads(l) for l in open('data/contexts_meta.jsonl')]
pool = [m for m in metas if m['protocol_clean'] and m['k_usable'] >= 2]
random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
ms = random.sample(pool, 3)
for meta in ms:
    ctx = V.load_context(meta)
    p0, _ = V.build_prompt(tok, meta, 'P0', 0, ctx=ctx)
    n0 = len(tok(p0, add_special_tokens=False)['input_ids'])
    print('=' * 120); print(meta['id'], 'logged pt', meta['pt'], 'rendered P0 tokens', n0, 'k_usable', meta['k_usable'], 'temp', meta['temp'], 'target', meta['target']['keys'], meta['target']['bad_syn'])
    for pw in ['P1', 'P2', 'P3', 'P4', 'P5']:
        p, info = V.build_prompt(tok, meta, pw, 1, ctx=ctx)
        # show the region that differs from P0
        i = 0
        while i < min(len(p), len(p0)) and p[i] == p0[i]: i += 1
        print('-' * 40, pw, 'k=1', 'tokens', len(tok(p, add_special_tokens=False)['input_ids']), info)
        print(repr(p[max(0, i - 150): i + 900]))
        print('   ... TAIL:', repr(p[-200:]))
