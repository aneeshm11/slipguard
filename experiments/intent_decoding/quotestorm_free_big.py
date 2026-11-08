"""Large-scale model-free test on ALL quote/backtick-rich gold-patch hunks (no stratification cap) + adversarial literals:
every hunk rendered as a VALID edit_file call in both key orders.  Measures, per call:
  guard   : algorithm (i) slip detector and (ii) candidate enumeration leave it untouched (must be 0 changes)
  B1      : pattern-only detector without the validity guard (fires = would-be false repair)
  B2      : lenient regex splitter on the vLLM-parsed args (FastFlowLM-style '<quote>,<key>:' split)
  census  : the team's malformation criterion (leak '<closer>,<declared key>:')
  vllm    : does vLLM 0.19.1's lenient parser return exactly the intended arguments for the valid call?
and, for one synthetic slip per call (closer from the base-31B empirical distribution, key-slip or end-slip):
  detection, ground truth among minimal candidates, number of candidates, 'max' cut correctness.
Output: out/quotestorm_free_big.json
"""
import json, os, sys, random, collections, glob
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mine_payloads as MP
from gemma_protocol import D, schema_from_tools, is_valid, first_slip_site, repair_candidates, render_call, census_judge
from quotestorm_free import b1_pattern_only, b2_regex_split, closer_dist, S
from stats import wilson

DIST = None


def work(args):
    idx, p, seed = args
    rng = random.Random(seed)
    c = collections.Counter()
    for order in ('new_first', 'old_first'):
        keys = ['filepath', 'new_string', 'old_string'] if order == 'new_first' else ['filepath', 'old_string', 'new_string']
        vals = {'filepath': p['filepath'], 'new_string': p['new'], 'old_string': p['old']}
        pairs = [(k, vals[k], 'str') for k in keys]
        text = render_call('edit_file', pairs)
        c['n'] += 1
        c['valid'] += is_valid(text, S)
        c['i_changed'] += first_slip_site(text, S, finished=True) is not None
        c['ii_changed'] += len(repair_candidates(text, S, finished=True)) > 0
        c['b1_fires'] += b1_pattern_only(text)
        ok, why, args_ = census_judge(text, S)
        c['b2_fires'] += b2_regex_split(args_)
        c['census_flags'] += not ok
        c['vllm_wrong'] += not (args_.get('filepath') == p['filepath'] and args_.get('old_string') == p['old']
                                and args_.get('new_string') == p['new'])
        kind = 'key' if rng.random() < 0.5 else 'end'
        x = rng.random(); acc = 0; L = '`'
        for k, pr in DIST:
            acc += pr
            if x <= acc:
                L = k; break
        if kind == 'key':
            body = ','.join(f'{k}:{D}{v}{L if i == 1 else D}' for i, (k, v, _) in enumerate(pairs))
            tgt = pairs[1][0]
        else:
            body = ','.join(f'{k}:{D}{v}{D}' for (k, v, _) in pairs[:-1]) + f',{pairs[-1][0]}:{D}{pairs[-1][1]}{L}'
            tgt = pairs[-1][0]
        stxt = 'call:edit_file{' + body + '}'
        c['slip_n'] += 1
        if is_valid(stxt, S):
            c['slip_still_valid'] += 1
            continue
        site = first_slip_site(stxt, S, finished=True)
        c['slip_detected'] += site is not None
        cands = repair_candidates(stxt, S, finished=True)
        texts = [cc.text('edit_file') for cc in cands]
        c['slip_gt_in_cands'] += text in texts
        c['slip_ncands'] += len(texts)
        c['slip_unique'] += len(texts) == 1
        if site is not None:
            c['slip_site_on_target'] += site.key == tgt
            c['slip_max_cut_correct'] += stxt[site.content_start:site.cut_positions()[0]] == vals[tgt]
    return idx, p['src'], c


def init(d):
    global DIST
    DIST = d


def main():
    pool = []
    for src, files in MP.SRC.items():
        for f in files:
            t = MP.pq.read_table(f, columns=['instance_id', 'patch', 'test_patch']).to_pylist()
            for r in t:
                for col in ('patch', 'test_patch'):
                    for fp, lines in MP.hunks(r.get(col) or ''):
                        pl = MP.to_payload(lines)
                        if not pl:
                            continue
                        old, new = pl
                        if not MP.feats(fp, old, new)['rich']:
                            continue
                        pool.append({'src': src, 'filepath': fp, 'old': old, 'new': new})
    seen, uniq = set(), []
    for p in pool:
        k = (p['filepath'], p['old'], p['new'])
        if k not in seen:
            seen.add(k); uniq.append(p)
    adv = [json.loads(l) for l in open(os.path.join(HERE, 'data/quotestorm.jsonl'))]
    adv = [{'src': 'adversarial', 'filepath': p['filepath'], 'old': p['old'], 'new': p['new']} for p in adv if p['src'].startswith('adversarial')]
    allp = uniq + adv
    print('unique rich hunks', len(uniq), 'adversarial', len(adv), flush=True)
    d = closer_dist()
    tot = collections.defaultdict(collections.Counter)
    with Pool(int(os.environ.get('NP', '8')), initializer=init, initargs=(d,)) as pl:
        for idx, src, c in pl.imap_unordered(work, [(i, p, i) for i, p in enumerate(allp)], chunksize=64):
            g = 'adversarial' if src == 'adversarial' else 'natural'
            tot[g].update(c); tot['all'].update(c)
            tot['src=' + src].update(c)
    out = {}
    for g, c in tot.items():
        n = c['n']; sn = c['slip_n'] - c['slip_still_valid']
        o = {'calls': n}
        for k in ('valid', 'i_changed', 'ii_changed', 'b1_fires', 'b2_fires', 'census_flags', 'vllm_wrong'):
            o[k] = {'k': c[k], 'rate': c[k] / n, 'wilson95': wilson(c[k], n)}
        o['synthetic_slips'] = {'n': sn, 'still_valid': c['slip_still_valid']}
        for k in ('slip_detected', 'slip_gt_in_cands', 'slip_unique', 'slip_site_on_target', 'slip_max_cut_correct'):
            o['synthetic_slips'][k] = {'k': c[k], 'rate': c[k] / max(sn, 1), 'wilson95': wilson(c[k], sn)}
        o['synthetic_slips']['mean_cands'] = c['slip_ncands'] / max(sn, 1)
        out[g] = o
    json.dump(out, open(os.path.join(HERE, 'out/quotestorm_free_big.json'), 'w'), indent=1)
    for g in ('all', 'natural', 'adversarial'):
        o = out[g]
        print(g, o['calls'], 'i/ii changed', o['i_changed']['k'], o['ii_changed']['k'], 'b1', o['b1_fires']['k'], 'b2', o['b2_fires']['k'],
              'census', o['census_flags']['k'], 'vllm_wrong', o['vllm_wrong']['k'], 'slips', o['synthetic_slips']['n'],
              'det', o['synthetic_slips']['slip_detected']['rate'], 'gt_in', o['synthetic_slips']['slip_gt_in_cands']['rate'],
              'max_cut', round(o['synthetic_slips']['slip_max_cut_correct']['rate'], 4))


if __name__ == '__main__':
    main()
