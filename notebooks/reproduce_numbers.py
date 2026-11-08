#!/usr/bin/env python3
"""Re-derive the writeup's headline results from the released raw records and compare them with the released results
(RESULTS.md's source files). CPU only, standard library only, no network, about a minute.

    python notebooks/reproduce_numbers.py [REPO_ROOT]          # default: auto-detect (checkout, $TRANSCRIPTLAB_ROOT, /kaggle/input/*)
    PNC_ROOT=<dir with MANIFEST.json and episodes/>             # if the PNC dataset is attached separately

A check is EXACT when the recomputed value equals the released one:
* counts are equal;
* k/n rates have the same n and k;
* other values agree at the precision the released file stores, at least 3 decimals.

Output: OUT_DIR/l2_checks.json (default ./reproduced). Exit code 1 if any check disagrees.
"""
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def exactness(v, n, ref):
    if v is None or ref is None:
        return None
    if float(v).is_integer() and float(ref).is_integer():
        return 'count' if int(v) == int(ref) else None
    if n and 0 <= v <= 1 and abs(v * n - round(v * n)) < 1e-9 and 0 <= ref <= 1:
        return 'count-exact' if round(v * n) == round(ref * n) else None
    s = repr(float(ref))
    dec = len(s.split('.')[1]) if '.' in s and 'e' not in s else 0
    return 'stored-precision' if dec >= 3 and round(v, dec) == ref else None


def main():
    rc = load_module(os.path.join(HERE, 'recompute.py'), 'recompute')
    root = rc.find_repo(sys.argv[1] if len(sys.argv) > 1 else None)
    pnc = rc.find_pnc(root)
    out_dir = os.environ.get('OUT_DIR', os.path.join(os.getcwd(), 'reproduced'))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    rows, skipped = [], []
    for fn in rc.CHECKS:
        try:
            res = fn(root, pnc)
        except FileNotFoundError as e:
            skipped.append({'check': fn.__name__, 'why': str(e)})
            continue
        for label, v, n, ref_file, ref_path in res:
            ref = rc.reference(root, ref_file, ref_path)
            ex = exactness(v, n, ref)
            rows.append({'check': fn.__name__, 'quantity': label, 'recomputed': v, 'n': n, 'released': ref,
                         'released_at': f"{os.path.relpath(ref_file, root) if os.path.isabs(ref_file) else ref_file}#{ref_path}",
                         'status': 'EXACT' if ex else 'DIFF', 'exact': ex})
    n_exact = sum(r['status'] == 'EXACT' for r in rows)
    n_diff = sum(r['status'] == 'DIFF' for r in rows)
    complete = not skipped
    # a skipped check GROUP (one per missing dataset part) would have produced one or more values, so values run and
    # groups skipped are reported separately -- never as one fraction that mixes the two units
    l2 = {'repo_root': os.path.basename(os.path.abspath(root)), 'pnc_found': pnc is not None, 'n_checks': len(rows), 'n_exact': n_exact,
          'n_checks_released_files': len(rows), 'n_exact_released_files': n_exact, 'n_ok_released_files': n_exact,
          'n_skipped': len(skipped), 'skipped_groups': [s['check'] for s in skipped], 'n_diff': n_diff, 'complete': complete,
          'skipped': skipped, 'rows': rows}
    with open(os.path.join(out_dir, 'l2_checks.json'), 'w') as f:
        json.dump(l2, f, indent=1)
    # WP-release (WP_CODE_CHANGES H1): report checks RUN vs SKIPPED, so a partial run never looks like full success.
    print(f'headline results re-derived from raw released records: {len(rows)} check(s) run, {n_exact} exact; '
          f'{len(skipped)} check group(s) skipped ({time.time() - t0:.1f} s)')
    for r in rows:
        v = f"{r['recomputed']:.4f}" if isinstance(r['recomputed'], float) else str(r['recomputed'])
        ref = f"{r['released']:.4f}" if isinstance(r['released'], float) else str(r['released'])
        print(f"  {r['quantity']:46s} {v:>10s}  released {ref:>10s}  {r['status']}{' (' + r['exact'] + ')' if r['exact'] else ''}")
    for s in skipped:
        print(f"  skipped {s['check']}: {s['why']}")
    if skipped:
        parts = ', '.join(s['check'] for s in skipped)
        print(f'INCOMPLETE: {len(skipped)} check(s) skipped because dataset parts are not attached ({parts}); '
              'attach PNC (PNC_ROOT) and the discovery snippets of the release dataset for the full set')
    print(f'outputs in {out_dir}')
    # exit 1 on any disagreement; 3 when the run is incomplete (parts missing); 0 only when every check ran and is exact
    sys.exit(1 if n_diff else (3 if skipped else (0 if rows else 1)))


if __name__ == '__main__':
    main()
