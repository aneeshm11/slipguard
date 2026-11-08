"""Shared loaders for PREREG_E_audit and PREREG_E_comp (frozen with both, 2026-11-07, before any of their episodes).
Uses PREREG_E's frozen analysis/prereg_analysis.py unchanged (load_proxy, load_arm, boot_paired, boot_ratio, mcnemar, B).
A run is identified by (prefix, replicate k, half h, arm): runs/<prefix><k>s<h>_H_<arm>, proxy logs logs/proxy_<prefix><k>s<h>."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


F = _load('prereg_frozen', HERE / 'prereg_analysis.py')
HALF = {h: [t for t in open(E / f'configs/eligible_113_half{h}.txt').read().split() if t] for h in (0, 1)}
TASKS = [t for t in open(E / 'configs/eligible_113.txt').read().split() if t]


def run_dir(prefix, k, h, arm):
    return E / f'runs/{prefix}{k}s{h}_H_{arm}'


def complete(prefix, k, arms):
    for h in (0, 1):
        for arm in arms:
            p = run_dir(prefix, k, h, arm) / 'per_task.jsonl'
            if not p.exists():
                return False
            done = {json.loads(l)['id'] for l in open(p) if l.strip()}
            if not set(HALF[h]) <= done:
                return False
    return True


def prefix_set(prefix, arms, first, last):
    """largest complete prefix first..K of replicates (the registered stopping rule)."""
    st = {k: complete(prefix, k, arms) for k in range(first, last + 1)}
    K = first - 1
    while K + 1 <= last and st[K + 1]:
        K += 1
    return st, list(range(first, K + 1))


def load_rep(prefix, k, arms):
    by = F.load_proxy([str(E / f'logs/proxy_{prefix}{k}s{h}') for h in (0, 1)])
    return {arm: F.load_arm('+'.join(str(run_dir(prefix, k, h, arm)) for h in (0, 1)), by) for arm in arms}


def episodes(spec, reps):
    """spec: list of (label, prefix, arm). -> {task: {k: {label: episode}}} for replicates where every label has a
    non-infra episode; excluded (task, k, reason) listed."""
    out, excl = {t: {} for t in TASKS}, []
    for k in reps:
        cache = {}
        for label, prefix, arm in spec:
            if (prefix, k) not in cache:
                arms = sorted({a for _, p, a in spec if p == prefix})
                cache[(prefix, k)] = load_rep(prefix, k, arms)
        for t in TASKS:
            row = {}
            for label, prefix, arm in spec:
                ep = cache[(prefix, k)][arm].get(t)
                row[label] = ep[0] if ep else None
            if any(v is None for v in row.values()):
                excl.append([t, k, 'missing']); continue
            if any(v['infra_error'] for v in row.values()):
                excl.append([t, k, 'infra']); continue
            out[t][k] = row
    return {t: v for t, v in out.items() if v}, excl


def tmeans(P, label, key):
    return {t: sum(r[label][key] for r in v.values()) / len(v) for t, v in P.items()}


def contrast(XA, XB, seed):
    """A vs B over tasks present in both (A = treatment): ratio A/B (boot_ratio, seed 1), diff A - B (boot_paired)."""
    ts = [t for t in TASKS if t in XA and t in XB]
    a = [XA[t] for t in ts]; b = [XB[t] for t in ts]
    if not ts:
        return {'n_tasks': 0}
    return {'n_tasks': len(ts), 'A_mean': round(sum(a) / len(a), 4), 'B_mean': round(sum(b) / len(b), 4),
            'ratio_A_over_B': F.boot_ratio(b, a, seed=1),
            'diff_A_minus_B': F.boot_paired([x - y for x, y in zip(a, b)], seed=seed)}


def counts(P, label):
    eps = [r[label] for v in P.values() for r in v.values()]
    return {'stuck': [sum(e['stuck'] for e in eps), len(eps)], 'resolved': [sum(e['resolved'] for e in eps), len(eps)]}


def holm(pvals):
    """Holm step-down adjusted p-values (same order as input)."""
    m = len(pvals); order = sorted(range(m), key=lambda i: pvals[i]); adj = [0.0] * m; run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * pvals[i])); adj[i] = round(run, 5)
    return adj


def spearman(x, y):
    def ranks(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for q in range(i, j + 1):
                r[o[q]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y); n = len(x); mx = sum(rx) / n; my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / den, 4) if den else None
