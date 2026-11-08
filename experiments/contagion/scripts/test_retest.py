"""Test-retest (UPGRADE_PLAN §P0-A1): 100 gate contexts x {P0, P1} re-run (a) with the SAME per-context seed
(reproducibility of the serving stack) and (b) with NEW seeds (sampling reliability). Outcome per context: malformed next
edit (unconditional) and the next tool name. Reports agreement, Cohen's kappa, and the rates in each run.
usage: test_retest.py out.json"""
import os  # added by the repo export (paths are env/config driven)
import json, sys, math, collections
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
ids = [x.strip() for x in open(f'{D}/data/ids_gate300.txt') if x.strip()][:100]


def load(fs):
    R = {}
    for f in fs:
        try:
            for l in open(f):
                d = json.loads(l)
                if not d.get('error'): R[(d['id'], d['pathway'], d['k'])] = d
        except FileNotFoundError: pass
    return R


def y(d):
    j = d.get('judge') or {}
    return int(j.get('name') == 'edit_file' and bool(j.get('malformed'))), (j.get('name') or ('<no call>' if not d.get('opened_call') else '<unparsed>'))


def kappa(pairs):
    n = len(pairs)
    if n == 0: return None
    po = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n; pb = sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else None


def wilson(k, n, z=1.96):
    if n == 0: return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4), n]


M = f'{D}/out/main'
orig = load([f'{M}/r31b_old_{x}.jsonl' for x in ('a', 'b', 'A', 'B', 'G')])
res = {'n_contexts': len(ids)}
for tag, f in (('same_seed', f'{M}/r31b_retest_sameseed.jsonl'), ('new_seed', f'{M}/r31b_retest_newseed.jsonl')):
    rt = load([f]); out = {}
    for arm in (('P0', 0), ('P1', 1)):
        pairs, tool_agree, text_identical, n = [], 0, 0, 0
        for i in ids:
            a, b = orig.get((i,) + arm), rt.get((i,) + arm)
            if not a or not b: continue
            ya, ta = y(a); yb, tb = y(b); n += 1
            pairs.append((ya, yb)); tool_agree += (ta == tb)
            text_identical += ((a.get('s1_text'), a.get('s2_text')) == (b.get('s1_text'), b.get('s2_text')))
        out[f'{arm[0]}k{arm[1]}'] = {'n': n, 'malformed_agreement': wilson(sum(p == q for p, q in pairs), n), 'kappa_malformed': kappa(pairs),
                                     'next_tool_agreement': wilson(tool_agree, n), 'byte_identical_generation': wilson(text_identical, n),
                                     'rate_original': wilson(sum(p for p, _ in pairs), n), 'rate_retest': wilson(sum(q for _, q in pairs), n)}
    res[tag] = out
json.dump(res, open(sys.argv[1], 'w'), indent=1); print(json.dumps(res, indent=1)[:2500])
