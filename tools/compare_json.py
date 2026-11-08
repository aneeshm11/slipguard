#!/usr/bin/env python3
"""Compare a re-computed analysis output with the released result file (standard library only).

    compare_json.py RELEASED NEW [--released-key A/B] [--mc REGEX] [--mc-tol X] [--ignore REGEX] [--show N] [--report OUT.json]
    compare_json.py --wsa-check CHECK_WSA_SUMMARY.json [--mc-tol X] [--report OUT.json]

Both files are loaded (``.json``: one document; ``.jsonl``: a list of the line documents) and compared recursively.
NaN equals NaN; int 1 equals float 1.0 (as after ``json.load``). Prints ONE line, ``RESULT<TAB>detail``:

  IDENTICAL         equal after loading (minus any ``--ignore`` keys, which the detail names).
  POINTS-IDENTICAL  every difference is a numeric leaf whose path matches ``--mc`` (the row's declared bootstrap /
                    Monte-Carlo quantities: CI bounds, bootstrap p-values) and, with ``--mc-tol``, is at most that
                    far from the released value. Everything else, incl. every point estimate, is equal.
  DIFFERENT         anything else; the detail lists the first differing paths.

``--released-key`` compares NEW with a subtree of RELEASED (path segments joined by '/').
``--wsa-check`` classifies the JSON summary printed by slipguard/dev/check_wsa.py (it compares the shipped audit
code with F's sweep reports itself): no mismatches -> IDENTICAL if its max CI-bound difference is 0, else
POINTS-IDENTICAL (bootstrap stream; at most ``--mc-tol`` nats if given); any mismatch -> DIFFERENT.
Exit status: 0 for IDENTICAL / POINTS-IDENTICAL, 1 for DIFFERENT, 2 for unreadable input.
"""
import argparse
import json
import math
import re
import sys


def load(path):
    with open(path, encoding='utf-8') as f:
        if path.endswith('.jsonl'):
            return [json.loads(line) for line in f if line.strip()]
        return json.load(f)


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def diff(a, b, path='', out=None):
    """-> list of (path, kind, released, new); kind in value / type / missing_in_new / extra_in_new / length."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            p = f'{path}/{k}'
            if k not in b:
                out.append((p, 'missing_in_new', a[k], None))
            else:
                diff(a[k], b[k], p, out)
        for k in b:
            if k not in a:
                out.append((f'{path}/{k}', 'extra_in_new', None, b[k]))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, 'length', len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f'{path}[{i}]', out)
    elif num(a) and num(b):
        if not (a == b or (isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b))):
            out.append((path, 'value', a, b))
    elif type(a) is not type(b) and not (num(a) and num(b)):
        out.append((path, 'type', a, b))
    elif a != b:
        out.append((path, 'value', a, b))
    return out


def short(v, n=60):
    s = json.dumps(v, default=str)
    return s if len(s) <= n else s[:n - 3] + '...'


def subtree(doc, key):
    for seg in [s for s in key.split('/') if s]:
        doc = doc[int(seg)] if isinstance(doc, list) else doc[seg]
    return doc


def drop_ignored(doc, rx, path=''):
    if isinstance(doc, dict):
        return {k: drop_ignored(v, rx, f'{path}/{k}') for k, v in doc.items() if not rx.search(f'{path}/{k}')}
    if isinstance(doc, list):
        return [drop_ignored(v, rx, f'{path}[{i}]') for i, v in enumerate(doc)]
    return doc


def classify(released, new, mc=None, mc_tol=None, show=4):
    d = diff(released, new)
    if not d:
        return 'IDENTICAL', '', d
    rx = re.compile(mc) if mc else None

    def is_mc(e):
        p, kind, a, b = e
        return (rx is not None and kind == 'value' and num(a) and num(b) and rx.search(p)
                and (mc_tol is None or abs(a - b) <= mc_tol))
    mc_d = [e for e in d if is_mc(e)]
    other = [e for e in d if not is_mc(e)]
    if not other:
        mx = max(abs(a - b) for _, _, a, b in mc_d)
        return 'POINTS-IDENTICAL', (f'{len(mc_d)} bootstrap/MC leaves differ (max |diff| {mx:.4g}), '
                                    f'e.g. {mc_d[0][0]}: {short(mc_d[0][2])} -> {short(mc_d[0][3])}; '
                                    f'all other leaves equal'), d
    first = '; '.join(f'{p} [{k}] {short(a)} -> {short(b)}' for p, k, a, b in other[:show])
    return 'DIFFERENT', f'{len(other)} non-MC differences (+{len(mc_d)} MC): {first}', d


def wsa_check(summary, mc_tol=None):
    mm = summary.get('mismatches') or []
    mx = summary.get('max_ci_bound_diff_nats', 0.0) or 0.0
    n = sum(r.get('checkpoints', 0) for r in (summary.get('reports') or {}).values())
    if mm or not summary.get('reports'):
        return 'DIFFERENT', f'{len(mm)} mismatches, e.g. {short(mm[:2], 200)}'
    if mc_tol is not None and mx > mc_tol:
        return 'DIFFERENT', f'CI bounds differ by {mx:.4f} nats > tolerance {mc_tol}'
    if mx == 0:
        return 'IDENTICAL', f'{n} checkpoint rows: every summary field, point, FLAG/SEVERE and CI bound equal'
    return 'POINTS-IDENTICAL', (f'{n} checkpoint rows: every summary field, median-deficit point and FLAG/SEVERE equal; '
                                f'CI bounds differ by <= {mx:.4f} nats (one RNG stream in sweep_report.py vs '
                                f'per-comparison reseed in the shipped compare())')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('released', nargs='?')
    ap.add_argument('new', nargs='?')
    ap.add_argument('--released-key', default='')
    ap.add_argument('--mc', default='', help='regex over leaf paths: declared bootstrap / Monte-Carlo quantities')
    ap.add_argument('--mc-tol', type=float, default=None)
    ap.add_argument('--ignore', default='', help='regex over key paths removed from BOTH documents before comparing')
    ap.add_argument('--show', type=int, default=4)
    ap.add_argument('--wsa-check', default='')
    ap.add_argument('--report', default='')
    a = ap.parse_args()
    try:
        if a.wsa_check:
            res, detail = wsa_check(load(a.wsa_check), a.mc_tol)
            d = []
        else:
            if not (a.released and a.new):
                ap.error('RELEASED and NEW are required')
            rel, new = load(a.released), load(a.new)
            if a.released_key:
                rel = subtree(rel, a.released_key)
            if a.ignore:
                rx = re.compile(a.ignore)
                rel, new = drop_ignored(rel, rx), drop_ignored(new, rx)
            res, detail, d = classify(rel, new, a.mc or None, a.mc_tol, a.show)
            if a.ignore:
                detail = (detail + '; ' if detail else '') + f'ignored keys matching {a.ignore!r}'
    except (OSError, ValueError, KeyError, IndexError) as e:
        print(f'DIFFERENT\tunreadable input: {type(e).__name__}: {e}')
        return 2
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump({'result': res, 'detail': detail, 'n_differences': len(d),
                       'differences': [{'path': p, 'kind': k, 'released': x, 'new': y} for p, k, x, y in d[:500]]},
                      f, indent=1, default=str)
    print(f'{res}\t{detail}')
    return 0 if res in ('IDENTICAL', 'POINTS-IDENTICAL') else 1


if __name__ == '__main__':
    sys.exit(main())
