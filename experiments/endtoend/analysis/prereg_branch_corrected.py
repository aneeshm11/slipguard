"""PRE-OUTCOME WRAPPER (written 2026-11-06 ~00:25 UTC, before any branch outcome was looked at; NOT in the frozen manifest).
Runs the FROZEN analysis/prereg_analysis.py `branches` (sha 1f8fca3a...) unchanged, replacing only its fidelity input:
every replayed proxy record's replay.fidelity is set from the corrected trace-based check
(analysis/branch_fidelity_corrected.py: frozen normaliser + 'budget_warning' key removed + 64-hex container ids masked;
tool name/status/error type must match; prefixes cut by the 40-call cap fail). A branch point is excluded if ANY arm
mismatches (frozen rule). Writes <out> and <out>.fidelity.json (per branch point and arm, frozen flag and corrected).
Usage: prereg_branch_corrected.py branches --label L --group plan=P,base=D,quar=D,ipd=D,fullp=D [--group ...]
       --proxy-logs LOGS... --out OUT.json"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


F = _load('prereg_frozen', HERE / 'prereg_analysis.py')
C = _load('fid_corrected', HERE / 'branch_fidelity_corrected.py')


def corrected_map(groups):
    """run-dir name -> (plan entries, arm, verdict per task) using the corrected check on the traces."""
    by_rundir = {}
    for g in groups:
        kv = dict(x.split('=', 1) for x in g.split(','))
        plan = json.load(open(kv.pop('plan')))['branches']
        for arm, rd in kv.items():
            verdict = {}
            for tid, br in plan.items():
                k = sum(len(r['calls']) for r in br['responses'][:br['b']])
                orig = C.tool_results(C.E / 'runs' / br['source']['session'].split('/')[0] / 'traces' / f'trace_{tid}.json')[:k]
                tp = Path(rd) / 'traces' / f'trace_{tid}.json'
                if not tp.exists():
                    verdict[tid] = 'mismatch'
                    continue
                rep = C.tool_results(tp)[:k]
                ok = len(rep) == len(orig) == k and all(a[0] == b[0] and C.norm(a[1]) == C.norm(b[1]) for a, b in zip(orig, rep))
                verdict[tid] = 'ok' if ok else 'mismatch'
            by_rundir[Path(rd).name] = (arm, verdict)
    return by_rundir


def main():
    argv = sys.argv[1:]
    groups = [argv[i + 1] for i, x in enumerate(argv) if x == '--group']
    out = argv[argv.index('--out') + 1]
    cmap = corrected_map(groups)
    frozen_flags = {}
    orig_load = F.load_proxy

    def load_proxy(dirs):
        by = orig_load(dirs)
        for key, recs in by.items():
            rundir = key.split('/')[0]
            if rundir not in cmap:
                continue
            arm, verdict = cmap[rundir]
            tid = key.split(':')[-1]
            fz = any((r.get('replay') or {}).get('fidelity') == 'mismatch' for r in recs if r.get('replayed'))
            frozen_flags[f'{rundir}:{tid}'] = {'arm': arm, 'frozen_flag': 'mismatch' if fz else 'ok', 'corrected': verdict.get(tid, 'mismatch')}
            for r in recs:
                if r.get('replayed'):
                    r['replay'] = {**(r.get('replay') or {}), 'fidelity': 'ok' if verdict.get(tid) == 'ok' else 'mismatch'}
        return by

    F.load_proxy = load_proxy
    sys.argv = [sys.argv[0]] + argv
    F.main()
    Path(out + '.fidelity.json').write_text(json.dumps(frozen_flags, indent=0))
    from collections import Counter
    print('fidelity (per branch x arm): frozen', dict(Counter(v['frozen_flag'] for v in frozen_flags.values())),
          'corrected', dict(Counter(v['corrected'] for v in frozen_flags.values())))


if __name__ == '__main__':
    main()
