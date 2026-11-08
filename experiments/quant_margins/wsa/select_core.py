"""Select the CORE item set for hidden-state extraction (HF teacher forcing) from data/pnc_points_all.jsonl.
 * all slip items (both splits); * valid items: N_PER_SPLIT random per split (seed 20261105), total tokens <= CAP;
 * per item: decision positions (path/new/old closers, slips), up to 4 protected positions, and 'generic' positions
   (12 random completion positions outside the tool call whose next token is ordinary text, 12 random prompt positions,
   same rule) for side-effect (KL / NLL) estimates on non-protocol text.
Output: data/core_items.jsonl (positions are completion-relative for decisions/protected; generic prompt positions are
absolute indices of the PREDICTED token in the full sequence, filled in by the extractor after rendering)."""
import json, random, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
H = os.path.dirname(os.path.abspath(__file__))
N_PER_SPLIT, CAP = 450, 21000
rng = random.Random(20261105)
rows = [json.loads(l) for l in open(os.path.join(H, 'data', 'pnc_points_all.jsonl'))]
fits = lambda r: r['prompt_tokens'] + r['completion_tokens'] <= CAP
sel = [r for r in rows if r['kind'] == 'slip' and fits(r)]
for sp in ('calib', 'heldout'):
    pool = [r for r in rows if r['kind'] == 'valid' and r['split'] == sp and fits(r)]
    sel += rng.sample(pool, min(N_PER_SPLIT, len(pool)))
with open(os.path.join(H, 'data', 'core_items.jsonl'), 'w') as fo:
    for r in sel:
        prot = [p for p in r['positions'] if p['kind'] == 'protected']
        keep = [p for p in r['positions'] if p['kind'] != 'protected'] + rng.sample(prot, min(4, len(prot)))
        r = dict(r, positions=keep, gen_seed=rng.randrange(1 << 30))
        fo.write(json.dumps(r) + '\n')
import collections
print(len(sel), collections.Counter((r['split'], r['kind']) for r in sel), 'excluded by cap:', sum(not fits(r) for r in rows))
