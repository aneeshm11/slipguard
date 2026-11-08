"""Model-free part of the FALSE-REPAIR test (QuoteStorm):
  * every payload rendered as a VALID edit_file call in both key orders (template/new-first and old-first)
  * guard: algorithm (i) detector and algorithm (ii) candidate enumeration must leave every valid call untouched
  * baselines without the guard: B1 pattern-only site detector, B2 lenient regex splitter (FastFlowLM-style),
    B3 vLLM 0.19.1 lenient parser (does it return the intended args for valid calls?)
  * synthetic slips with known ground truth: replace the delimiter closing the first content argument with a
    look-alike closer drawn from the empirical closer distribution of the 31B logs (and end-of-call slips on the
    last argument); measure detection, candidate coverage of the ground truth, #candidates, and the accuracy of the
    deterministic 'max' cut (whole look-alike run = closer).
Output: out/quotestorm_free.json (+ data/quotestorm_slips.jsonl consumed by quotestorm_model.py)
"""
import json, os, random, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import (D, schema_from_tools, is_valid, first_slip_site, repair_candidates, render_call, parse_strict,
                            sites_in_string, census_judge)
from stats import wilson

TOOLS = json.loads(open(os.path.join(HERE, 'data/tools_official.json')).read())
S = schema_from_tools(TOOLS)
rng = random.Random(0)

# empirical closer distribution (base 31B edit_file slips in the main-track logs, data/log_slips.jsonl)
def closer_dist():
    c = collections.Counter()
    for l in open(os.path.join(HERE, 'data/log_slips.jsonl')):
        r = json.loads(l)
        if r['tool'] == 'edit_file' and 'gemma-4-31b' in r['model']:
            c[r['closer_run']] += 1
    tot = sum(c.values())
    return [(k, v / tot) for k, v in c.most_common()]


def sample_closer(dist):
    x = rng.random(); acc = 0
    for k, p in dist:
        acc += p
        if x <= acc:
            return k
    return dist[0][0]


def b1_pattern_only(text):
    """site detector WITHOUT the validity guard (walk the strict reading of a valid call)."""
    sp = parse_strict(text)
    if not sp.ok:
        return True
    sc = S[sp.name]
    emitted = set()
    for p in sp.pairs:
        if p.kind == 'str':
            cs, e = p.vstart + len(D), p.vend - len(D)
            if sites_in_string(text, p.key, cs, e, emitted | {p.key}, sc, True, False):
                return True
        emitted.add(p.key)
    return False


B2 = re.compile(r'[`"\']+\s*,\s*(filepath|old_string|new_string|allow_multiple)\s*:')


def b2_regex_split(args):
    return any(isinstance(v, str) and B2.search(v) for v in args.values())


def main():
    pays = [json.loads(l) for l in open(os.path.join(HERE, 'data/quotestorm.jsonl'))]
    dist = closer_dist()
    res = collections.defaultdict(collections.Counter)
    slips = []
    for p in pays:
        grp = 'adversarial' if p['src'].startswith('adversarial') else 'natural'
        for order in ('new_first', 'old_first'):
            keys = ['filepath', 'new_string', 'old_string'] if order == 'new_first' else ['filepath', 'old_string', 'new_string']
            vals = {'filepath': p['filepath'], 'new_string': p['new'], 'old_string': p['old']}
            pairs = [(k, vals[k], 'str') for k in keys]
            text = render_call('edit_file', pairs)
            for g in (grp, 'all'):
                r = res[g]
                r['n'] += 1
                v = is_valid(text, S)
                r['valid'] += v
                r['i_changed'] += first_slip_site(text, S, finished=True) is not None
                r['ii_changed'] += len(repair_candidates(text, S, finished=True)) > 0
                r['b1_fires'] += b1_pattern_only(text)
                ok, why, args = census_judge(text, S)
                r['b2_fires'] += b2_regex_split(args)
                r['b3_vllm_wrong'] += not (args.get('filepath') == p['filepath'] and args.get('old_string') == p['old']
                                           and args.get('new_string') == p['new'])
                r['census_flags'] += not ok
            # synthetic slips: (a) key slip after the first content argument, (b) end-of-call slip on the last argument
            for kind in ('key', 'end'):
                L = sample_closer(dist)
                if kind == 'key':
                    j = 1  # first content argument (after filepath)
                    body = ','.join(f'{k}:{D}{v}{L if i == j else D}' for i, (k, v, _) in enumerate(pairs))
                    stxt = 'call:edit_file{' + body + '}'
                else:
                    body = ','.join(f'{k}:{D}{v}{D}' for (k, v, _) in pairs[:-1])
                    k, v, _ = pairs[-1]
                    stxt = 'call:edit_file{' + body + f',{k}:{D}{v}{L}' + '}'
                gtxt = text
                r = res[f'slip_{kind}_{grp}']
                r['n'] += 1
                if is_valid(stxt, S):
                    r['still_valid'] += 1   # injected closer created another valid reading (cannot be a detectable slip)
                    continue
                site = first_slip_site(stxt, S, finished=True)
                r['detected'] += site is not None
                cands = repair_candidates(stxt, S, finished=True)
                texts = [c.text('edit_file') for c in cands]
                r['gt_in_cands'] += gtxt in texts
                r['ncands_sum'] += len(texts)
                r['unique_cand'] += len(texts) == 1
                r['unique_and_gt'] += (len(texts) == 1 and texts[0] == gtxt)
                if site is not None:
                    cut = site.cut_positions()[0]
                    tgt_key = pairs[1][0] if kind == 'key' else pairs[-1][0]
                    r['max_cut_correct'] += stxt[site.content_start:cut] == vals[tgt_key]
                    r['site_on_target'] += site.key == tgt_key
                slips.append({'qid': p['qid'], 'grp': grp, 'order': order, 'kind': kind, 'closer': L, 'slipped': stxt,
                              'gt': gtxt, 'filepath': p['filepath'], 'old': p['old'], 'new': p['new'],
                              'cands': texts, 'gt_idx': texts.index(gtxt) if gtxt in texts else -1})
    out = {}
    for g, r in res.items():
        n = r['n']
        d = {'n': n}
        for k, v in r.items():
            if k == 'n' or k == 'ncands_sum':
                continue
            base = n if not g.startswith('slip') or k in ('still_valid',) else (n - r['still_valid'])
            d[k] = {'count': v, 'rate': v / max(base, 1), 'wilson95': wilson(v, max(base, 1))}
        if 'ncands_sum' in r:
            d['mean_cands'] = r['ncands_sum'] / max(n - r['still_valid'], 1)
        out[g] = d
    out['closer_dist'] = dist[:15]
    json.dump(out, open(os.path.join(HERE, 'out/quotestorm_free.json'), 'w'), indent=1)
    with open(os.path.join(HERE, 'data/quotestorm_slips.jsonl'), 'w') as fo:
        for s in slips:
            fo.write(json.dumps(s) + '\n')
    for g in sorted(out):
        if g == 'closer_dist':
            continue
        print(g, {k: (v['count'], round(v['rate'], 4)) if isinstance(v, dict) else v for k, v in out[g].items()})


if __name__ == '__main__':
    main()
