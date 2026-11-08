"""Decoder head-to-head analysis (P0-B), paired on identical samples.
usage: python analyze_h2h.py <replay.jsonl> [--tau 2] [--gold ctx.jsonl]   (inline arms read from rec['h2h'])
Arms and delivery policies (what reaches the harness):
  1_lenient       vLLM-0.19.1-lenient parse of the emitted call (status quo)
  2_fail_loud     only strictly valid calls, otherwise a loud error
  3_T1_text_only  valid -> as is; else the longest-closer reading if complete & schema-valid; else loud
  4_i_max         rollback/resume, whole-run cut; residual invalid -> loud
  5_IPD           rollback/resume, noisy-channel cut + opener rule (i+); residual invalid -> loud
  6_ii_tau        valid -> as is; else MAP repair if margin >= tau; else loud
  7_retry_x2      valid -> as is; else first strictly valid of two resamples; else loud
  8_greedy        T=0 re-decode, lenient delivery
  9_forbid        forbid-trigger constrained decoding (fires only at slip sites), lenient delivery
 10_grammar_CD    grammar-constrained decoding emulation, lenient delivery (always grammatical)
Metrics: delivered-malformed (census criterion on the delivered call), loud (nothing delivered), silent corruption
(delivered, accepted by the runtime, but strict-invalid or carrying look-alike+key text), clean; with --gold: exact
intent, edit-applies (old_string occurs exactly once in the pre-patch file), edit-correct (result == gold result).
"""
import json, os, sys, collections, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gemma_protocol import (schema_from_tools, is_valid, repair_candidates, parse_strict, runtime_view)
from stats import wilson

S = schema_from_tools(json.load(open(os.path.join(HERE, 'data/tools_official.json'))))
ARMS = ['1_lenient', '2_fail_loud', '3_T1_text_only', '4_i_max', '5_IPD', '6_ii_tau', '7_retry_x2', '7b_retry_x2_lenient', '8_greedy',
        '9_forbid', '9b_forbid_strict', '10_grammar_CD']


def W(k, n):
    return {'k': k, 'n': n, 'rate': (k / n) if n else None, 'wilson95': wilson(k, n)}


def t1_text_only(text, finished):
    if finished and is_valid(text, S):
        return text
    cands = repair_candidates(text, S, finished=finished)
    name = parse_strict(text).name
    for c in cands:
        if all(site is not None and cp == site.cut_positions()[0] for (k, cp, cl), site in zip(c.cuts, c.sites)):
            return c.text(name)
    return None


def deliveries(r, tau=2.0, h=None):
    """arm -> (text or None, finished, policy) ; policy 'strict' = deliver only if strictly valid."""
    base, fin = r['call'], r['finished']
    out = {'1_lenient': (base, fin, 'lenient'), '2_fail_loud': (base, fin, 'strict')}
    t1 = t1_text_only(base, fin)
    out['3_T1_text_only'] = (t1, True, 'strict')
    im = r.get('i_max')
    if im == 'same':
        im = r.get('i_nc')
    out['4_i_max'] = (im['text'], im['finished'], 'strict') if im else (base, fin, 'strict')
    ip = r.get('i_plus') or r.get('i_nc')
    out['5_IPD'] = (ip['text'], ip['finished'], 'strict') if ip else (base, fin, 'strict')
    ii = r.get('ii')
    if not r['base']['strict_valid'] and fin and 'ii' not in r:
        pass                                    # (ii) not run on this sample (onset-only segment): arm absent
    elif r['base']['strict_valid'] or not ii or not ii.get('cands'):
        out['6_ii_tau'] = (base, fin, 'strict')
    else:
        adj = [c['ll'] + c['prior'] for c in ii['cands']]
        order = sorted(range(len(adj)), key=lambda i: -adj[i])
        margin = adj[order[0]] - adj[order[1]] if len(adj) > 1 else math.inf
        out['6_ii_tau'] = ((ii['cands'][order[0]]['text'], True, 'strict') if margin >= tau else (None, False, 'strict'))
    A = dict(r.get('h2h') or {})
    if h:
        A.update(h.get('arms') or {})
    if not A:
        A = None
    if A is not None:
        if r['base']['strict_valid']:
            out['7_retry_x2'] = (base, fin, 'strict')
        elif 'retry' in A:
            out['7_retry_x2'] = (A['retry']['final_text'], True, 'strict')
        if r['base']['strict_valid']:
            out['7b_retry_x2_lenient'] = (base, fin, 'lenient')
        elif 'retry' in A:
            t = A['retry']['tries'][-1]
            out['7b_retry_x2_lenient'] = ((A['retry']['final_text'], True, 'lenient') if A['retry']['final_text'] else
                                          (t['text'], t['finished'], 'lenient'))
        if 'greedy' in A:
            out['8_greedy'] = (A['greedy']['final_text'], A['greedy']['finished'], 'lenient')
        if r.get('site') is None:
            out['9_forbid'] = (base, fin, 'lenient')
        elif 'forbid' in A:
            out['9_forbid'] = (A['forbid']['final_text'], A['forbid']['finished'], 'lenient')
        if r.get('site') is None:
            out['9b_forbid_strict'] = (base, fin, 'lenient')
        elif 'forbid2' in A:
            out['9b_forbid_strict'] = (A['forbid2']['final_text'], A['forbid2']['finished'], 'lenient')
        if r['base']['strict_valid']:
            out['10_grammar_CD'] = (base, fin, 'lenient')
        elif 'grammar' in A:
            out['10_grammar_CD'] = (A['grammar']['final_text'], A['grammar']['finished'], 'lenient')
    return out


def metrics(text, finished, policy, gold=None, file_text=None):
    if text is None:
        m = {'delivered': False, 'malformed': False, 'silent': False, 'clean': False}
    else:
        v = runtime_view(text, finished, S)
        if policy == 'strict' and not v['strict_valid']:
            m = {'delivered': False, 'malformed': False, 'silent': False, 'clean': False}
        else:
            m = {'delivered': True, 'malformed': not v['census_ok'], 'silent': v['silent_corruption'],
                 'clean': v['strict_valid'] and not v['leak_text']}
    if gold is not None:
        args = parse_strict(text).args() if (m['delivered'] and text is not None and parse_strict(text).ok) else {}
        if m['delivered'] and not args and text is not None:
            from gemma_protocol import census_judge
            _, _, args = census_judge(text, S)
        m['exact_intent'] = bool(m['delivered'] and args.get('filepath') == gold['filepath'] and
                                 args.get('old_string') == gold['old_string'] and args.get('new_string') == gold['new_string'])
        if file_text is not None:
            o, n = args.get('old_string'), args.get('new_string')
            ok = bool(m['delivered'] and isinstance(o, str) and isinstance(n, str) and o and file_text.count(o) == 1
                      and args.get('filepath') == gold['filepath'])
            m['edit_applies'] = ok
            m['edit_correct'] = bool(ok and file_text.replace(o, n, 1) == file_text.replace(gold['old_string'], gold['new_string'], 1))
    return m


def summarize(replay, tau=2.0, gold_ctx=None, h2h=None):
    recs = [json.loads(l) for l in open(replay)]
    recs = [r for r in recs if r.get('status') == 'call' and r.get('tool') == 'edit_file']
    H = {}
    if h2h and os.path.exists(h2h):
        for l in open(h2h):
            d = json.loads(l)
            if d.get('status') == 'ok':
                k = (d['id'], d['seed'], d.get('sample', 0))
                if k in H:
                    H[k]['arms'].update(d.get('arms') or {})      # merge arms from several passes
                else:
                    H[k] = d
    G, F = {}, {}
    if gold_ctx:
        for l in open(gold_ctx):
            d = json.loads(l)
            G[d['id']] = d
    rows = []
    for r in recs:
        g = G.get(r['id'])
        ft = None
        if g and g.get('file_sha'):
            if g['file_sha'] not in F:
                F[g['file_sha']] = open(os.path.join(HERE, 'data/gold_copy_files', g['file_sha'] + '.txt')).read()
            ft = F[g['file_sha']]
        dl = deliveries(r, tau, H.get((r['id'], r['seed'], r.get('sample', 0))))
        rows.append({'id': r['id'], 'slip': r.get('site') is not None, 'forced': bool(r.get('forced')),
                     'rich': (g or {}).get('rich'),
                     'arms': {a: metrics(t, f, p, g['gt'] if g else None, ft) for a, (t, f, p) in dl.items()}})
    # an arm that ran on only part of the samples (onset-only segments after a restart) is excluded from this file's
    # tables entirely, so that every reported arm is paired on the same samples
    partial = {}
    for a in ARMS:
        npres = sum(a in x['arms'] for x in rows)
        if 0 < npres < len(rows):
            partial[a] = npres
            for x in rows:
                x['arms'].pop(a, None)
    res = {'replay': os.path.basename(replay), 'tau': tau, 'n_samples': len(rows), 'arms_excluded_partial': partial,
           'n_contexts': len({x['id'] for x in rows}), 'n_slips': sum(x['slip'] for x in rows),
           'n_forced': sum(x['forced'] for x in rows)}
    keys = ['malformed', 'silent', 'clean'] + (['exact_intent'] if gold_ctx else []) + \
           (['edit_applies', 'edit_correct'] if any('edit_applies' in m for x in rows for m in x['arms'].values()) else [])
    for subset in ('all', 'slips', 'natural', 'forced', 'rich', 'rich_slips'):
        sel = [x for x in rows if subset == 'all' or (subset == 'slips' and x['slip']) or
               (subset == 'natural' and not x['forced']) or (subset == 'forced' and x['forced']) or
               (subset == 'rich' and x['rich']) or (subset == 'rich_slips' and x['rich'] and x['slip'])]
        if not sel:
            continue
        tab = {}
        for a in ARMS:
            ss = [x for x in sel if a in x['arms']]
            if not ss:
                continue
            n = len(ss)
            tab[a] = {k: W(sum(bool(x['arms'][a].get(k)) for x in ss), n) for k in keys}
            tab[a]['loud'] = W(sum(not x['arms'][a]['delivered'] for x in ss), n)
        res[subset] = tab
    return res


def show(res, subsets=('all', 'slips')):
    for subset in subsets:
        if subset not in res:
            continue
        print(f"== {res['replay']} [{subset}] samples={res['n_samples']} contexts={res['n_contexts']} slips={res['n_slips']} "
              f"forced={res['n_forced']} tau={res['tau']}")
        for a, t in res[subset].items():
            f = lambda d: f"{d['k']}/{d['n']}={100*(d['rate'] or 0):.1f}%"
            extra = ''.join(f"  {k} {f(t[k])}" for k in ('exact_intent', 'edit_applies', 'edit_correct') if k in t)
            print(f"  {a:15s} malformed {f(t['malformed'])}  silent {f(t['silent'])}  loud {f(t['loud'])}  clean {f(t['clean'])}{extra}")


if __name__ == '__main__':
    rp = sys.argv[1]
    tau = float(sys.argv[sys.argv.index('--tau') + 1]) if '--tau' in sys.argv else 2.0
    gold = sys.argv[sys.argv.index('--gold') + 1] if '--gold' in sys.argv else None
    show(summarize(rp, tau, gold), ('all', 'slips', 'rich_slips') if gold else ('all', 'slips'))
