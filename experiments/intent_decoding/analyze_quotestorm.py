"""Analysis of model-scored slips with known ground truth (v2 record format).
  syn <file.jsonl> [more files]  : synthetic QuoteStorm slips (quotestorm_model.py) or self-slips (selfslip.py)
  gen <qsgen.jsonl>              : model-in-the-loop copy task (replay.py --contexts data/quotestorm_ctx.jsonl)
(ii) decision = argmax over candidates of  LL_wctf + [prior] log P_channel(closers)  ; ABSTAIN if margin < tau
(i)  cut rules: nc = local LL + prior ; lik = local LL ; max = whole look-alike run is the closer (no model)
Priors: none | ft_edit (fine-tuned-model logs; disjoint from the synthetic closer source) | base_edit (matched source).
"""
import json, sys, os, collections, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import parse_strict, schema_from_tools, is_valid, D
from intent_decode import ChannelPrior, NoPrior
from stats import wilson

S = schema_from_tools(json.load(open(os.path.join(HERE, 'data/tools_official.json'))))
PRIORS = {'none': NoPrior(), 'ft_edit': ChannelPrior.from_log_slips('ft_edit'),
          'base_edit': ChannelPrior.from_log_slips('base_edit')}
TAUS = (0.0, 0.5, 1.0, 2.0, 3.0, 5.0)


def W(k, n):
    return {'k': k, 'n': n, 'rate': (k / n) if n else None, 'wilson95': wilson(k, n)}


def ii_eval(rows, prior, tau):
    acc = wrong = abst = 0
    for r in rows:
        adj = [r['lls'][i] + sum(prior.logp(c) for c in r['cand_closers'][i]) for i in range(len(r['lls']))]
        order = sorted(range(len(adj)), key=lambda i: -adj[i])
        margin = adj[order[0]] - adj[order[1]] if len(adj) > 1 else math.inf
        if margin < tau:
            abst += 1
        elif order[0] == r['gt_idx']:
            acc += 1
        else:
            wrong += 1
    n = len(rows)
    return {'correct': W(acc, n), 'wrong': W(wrong, n), 'abstain': W(abst, n),
            'precision_when_repairing': W(acc, acc + wrong)}


def cut_eval(rows, rule, prior):
    ok = n = 0
    for r in rows:
        c = r.get('cut')
        if not c or c['gt_k'] < 0:
            continue
        n += 1
        if rule == 'max':
            k = 0
        else:
            adj = [c['lls'][k] + (prior.logp(c['closers'][k]) if rule == 'nc' else 0.0) for k in range(len(c['lls']))]
            k = max(range(len(adj)), key=lambda i: (adj[i], -i))
        ok += k == c['gt_k']
    return W(ok, n)


def syn(paths):
    recs = []
    for p in paths:
        recs += [json.loads(l) for l in open(p)]
    st = collections.Counter(r.get('status') for r in recs)
    rows = [r for r in recs if r.get('status') == 'ok' and 'lls' in r]
    out = {'files': [os.path.basename(p) for p in paths], 'status': dict(st), 'n': len(rows)}

    def evalset(rs):
        o = {'n': len(rs), 'gt_in_candidates': W(sum(r['gt_idx'] >= 0 for r in rs), len(rs)),
             'unique_candidate': W(sum(r['ncands'] == 1 for r in rs), len(rs))}
        for pn, pr in PRIORS.items():
            o[f'ii_prior={pn}'] = {f'tau={t}': ii_eval(rs, pr, t) for t in TAUS}
        o['i_cut'] = {'nc_ft_edit': cut_eval(rs, 'nc', PRIORS['ft_edit']), 'nc_base_edit': cut_eval(rs, 'nc', PRIORS['base_edit']),
                      'lik': cut_eval(rs, 'lik', None), 'max': cut_eval(rs, 'max', None)}
        if any('ftf' in r for r in rs):
            sub = [r for r in rs if 'ftf' in r]
            agree = sum((max(range(len(r['ftf'])), key=lambda i: r['ftf'][i]) == max(range(len(r['lls'])), key=lambda i: r['lls'][i]))
                        for r in sub)
            acc_f = sum(max(range(len(r['ftf'])), key=lambda i: r['ftf'][i]) == r['gt_idx'] for r in sub)
            acc_w = sum(max(range(len(r['lls'])), key=lambda i: r['lls'][i]) == r['gt_idx'] for r in sub)
            diffs = []
            for r in sub:
                for i in range(1, len(r['lls'])):
                    diffs.append(abs((r['ftf'][i] - r['ftf'][0]) - (r['lls'][i] - r['lls'][0])))
            diffs.sort()
            o['wctf_vs_full_tf'] = {'n': len(sub), 'argmax_agree': W(agree, len(sub)), 'full_tf_argmax_correct': W(acc_f, len(sub)),
                                    'wctf_argmax_correct': W(acc_w, len(sub)),
                                    'abs_diff_of_score_differences_median': diffs[len(diffs) // 2] if diffs else None,
                                    'p90': diffs[int(0.9 * (len(diffs) - 1))] if diffs else None}
        return o
    groups = collections.defaultdict(list)
    for r in rows:
        groups['all'].append(r)
        groups['grp=' + r.get('grp', '?')].append(r)
        groups['kind=' + r['kind']].append(r)
        cl = r['closer'] if r['closer'] in ('`', '"', '\\"', '"""', '') else 'other'
        groups['closer=' + repr(cl)].append(r)
    for g, rs in sorted(groups.items()):
        out[g] = evalset(rs)
    return out


def gen(path):
    gt = {}
    for l in open(os.path.join(HERE, 'data/quotestorm_ctx.jsonl')):
        d = json.loads(l)
        gt[d['id']] = (d['gt'], d['src'])
    recs = [json.loads(l) for l in open(path)]
    recs = [r for r in recs if r.get('status') == 'call']
    out = {'n': len(recs)}

    def exact(text, g):
        if not is_valid(text, S):
            return False
        a = parse_strict(text).args()
        return a.get('filepath') == g['filepath'] and a.get('old_string') == g['old_string'] and a.get('new_string') == g['new_string']
    groups = collections.defaultdict(list)
    for r in recs:
        g, src = gt[r['id']]
        grp = 'adversarial' if src.startswith('adversarial') else 'natural'
        ic = r.get('i_nc')
        i_text = ic['text'] if ic else r['call']
        ip = r.get('i_plus')
        ip_text = ip['text'] if ip else i_text
        ii = r.get('ii') or {}
        ii_text = ii.get('text') if ii.get('decision') == 'repair' else r['call']
        row = {'b_valid': r['base']['strict_valid'], 'b_exact': exact(r['call'], g), 'b_census_bad': not r['base']['census_ok'],
               'slip': r.get('site') is not None, 'i_changed': bool(ic and ic['changed']), 'i_valid': is_valid(i_text, S),
               'i_exact': exact(i_text, g), 'ip_exact': exact(ip_text, g), 'ii_changed': ii.get('decision') == 'repair',
               'ii_exact': exact(ii_text, g), 'run': (r.get('site') or {}).get('run')}
        groups[grp].append(row); groups['all'].append(row)
    for grp, rows in groups.items():
        n = len(rows)
        valid = [x for x in rows if x['b_valid']]
        slips = [x for x in rows if x['slip']]
        out[grp] = {'n': n, 'baseline_strict_valid': W(len(valid), n), 'baseline_exact_intent': W(sum(x['b_exact'] for x in rows), n),
                    'baseline_census_malformed': W(sum(x['b_census_bad'] for x in rows), n), 'baseline_slip': W(len(slips), n),
                    'after_i_exact_intent': W(sum(x['i_exact'] for x in rows), n),
                    'after_iplus_exact_intent': W(sum(x['ip_exact'] for x in rows), n),
                    'after_ii_exact_intent': W(sum(x['ii_exact'] for x in rows), n),
                    'false_repair_i_on_valid': W(sum(x['i_changed'] for x in valid), len(valid)),
                    'false_repair_ii_on_valid': W(sum(x['ii_changed'] for x in valid), len(valid)),
                    'slips_recovered_exact_i': W(sum(x['i_exact'] for x in slips), len(slips)),
                    'slips_recovered_exact_ii': W(sum(x['ii_exact'] for x in slips), len(slips)),
                    'slip_runs': collections.Counter(x['run'] for x in slips).most_common(8)}
    return out


if __name__ == '__main__':
    mode = sys.argv[1]
    r = gen(sys.argv[2]) if mode == 'gen' else syn(sys.argv[2:])
    print(json.dumps(r, indent=1, default=str))
