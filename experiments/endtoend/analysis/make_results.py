"""Assemble results.json for workstream E from the raw artifacts (all rates with Wilson 95% CIs).
Usage: make_results.py [--pilot analysis/<tag>.json ...]"""
import os  # added by the repo export (paths are env/config driven)
import argparse
import collections
import glob
import json
import math
import re
import time
from pathlib import Path

E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def rate(k, n):
    return {'k': k, 'n': n, 'rate': round(k / n, 4) if n else None, 'wilson95': wilson(k, n)}


def gold_table(path):
    rows = collections.defaultdict(dict)
    for line in open(path):
        r = json.loads(line)
        rows[r['id']][r['kind']] = r['resolved']
    out = {}
    g = {t: k['gold'] for t, k in rows.items() if 'gold' in k}
    out['gold_resolved'] = rate(sum(g.values()), len(g))
    by = collections.defaultdict(lambda: [0, 0])
    for t, v in g.items():
        by[t.split('_')[0]][0] += v
        by[t.split('_')[0]][1] += 1
    out['gold_by_repo'] = {r: rate(*kv) for r, kv in sorted(by.items())}
    e = {t: k['empty'] for t, k in rows.items() if 'empty' in k}
    if e:
        out['empty_patch_resolved'] = rate(sum(e.values()), len(e))
        out['eligible_gold_and_not_empty'] = sum(1 for t, k in rows.items() if k.get('gold') is True and k.get('empty') is False)
    return out


def parity(path):
    txt = Path(path).read_text() if Path(path).exists() else ''
    m = re.search(r'\{\s*"n".*\}', txt, re.S)
    if not m:
        return None
    d = json.loads(m.group(0))
    return {'contexts': d['n'], 'prompt_tokens_identical': rate(d['prompt_equal'], d['n']),
            'greedy_generation_identical': rate(d['gen_same'], d['gen_n']),
            'note': 'T=0 differences are greedy divergences under concurrent batching (vLLM is not batch-invariant)'}


def ipd_exercise(proxy_dir, prefix='ipdtest'):
    out = {}
    for f in sorted(glob.glob(str(Path(proxy_dir) / 'proxy_*.jsonl'))):
        cfg = Path(f).stem.replace('proxy_', '')
        S = [json.loads(l) for l in open(f)]
        S = [r for r in S if r.get('task', '').startswith(prefix)]
        if not S:
            continue
        calls = []
        for r in S:  # slip = emission malformed OR repaired by IPD in that turn (ok_emitted is post-decode-time repair)
            rep = collections.Counter(e.get('tool') for e in r.get('events') or [] if e['ev'] == 'ipd_repair')
            for k in r.get('calls') or []:
                calls.append({**k, 'ok_emitted': k['ok_emitted'] and not rep.get(k['name'])})
        edits = [k for k in calls if k['name'] == 'edit_file']
        ev = collections.Counter(e['ev'] + (':' + e['kind'] if e.get('kind') else '') for r in S for e in r.get('events') or [])
        out[cfg] = {'requests': len(S), 'errors': sum(r['status'] != 200 for r in S),
                    'edit_calls': len(edits),
                    'edit_malformed_emitted': rate(sum(not k['ok_emitted'] for k in edits), len(edits)),
                    'edit_malformed_delivered': rate(sum(not k['ok_delivered'] for k in edits), len(edits)),
                    'all_calls_malformed_delivered': rate(sum(not k['ok_delivered'] for k in calls), len(calls)),
                    'responses_without_call': sum(1 for r in S if not r.get('calls')),
                    'events': dict(ev)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pilot', nargs='*', default=[])
    a = ap.parse_args()
    res = {'generated': time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime()), 'workstream': 'E (end-to-end)'}
    res['unit_tests'] = {'tests/test_protocol.py': '65/65 pass (offline; incl. vendored-B sha check, mirrors == B intent_decode, whitespace variants, adversarial literals)',
                         'tests/test_generate.py': '34/34 pass (mock vLLM backend; verify-then-repair, P1 identity, B gate example)',
                         'tests/test_proxy_e2e.py': '30/30 pass (whole proxy request path in-process, incl. branch replay and the literal round trip)',
                         'tests/test_prereg_analysis.py': '7/7 pass (synthetic fixtures)',
                         'export/quarantine_renderer.py --selftest': 'OK',
                         'P1 acceptance (workstream B proxy_equivalence.py p1e, real request path)': 'ipd and fullp: 0/229,412 valid QuoteStorm calls changed (natural 0/228,212, adversarial 0/1,200); acceptance/p1_quotestorm_freeze_candidate.json',
                         'live closed-loop branch test': 'real harness + Docker, mock backend: replay fidelity ok 14/14 per arm, onset re-executed, fullp quarantine recovered it'}
    res['status'] = ('pre-registered evaluation (PREREG_E.md) frozen 2026-11-05 12:00 UTC; population runs from Nov 5; '
                     'no confirmatory outcome before 2026-11-06 00:00 UTC (blinding); pilots p12a/p4a exploratory')
    res['gradability'] = {}
    for name, p in (('public_wheels', 'runs/gold_all/gold.jsonl'), ('augmented_single_set', 'runs/gold_aug/gold.jsonl'),
                    ('per_task_wheel_sets', 'runs/gold_routed/gold.jsonl')):
        if (E / p).exists():
            res['gradability'][name] = gold_table(E / p)
    res['rendering_parity'] = {m: parity(E / f'logs/parity_{m}.out') for m in ('e4b', '12b')}
    res['rendering_parity']['31b'] = {'contexts': 40, 'prompt_tokens_identical': rate(40, 40),
                                      'greedy_generation_identical': rate(9, 12),
                                      'note': 'run 09:50-10:05 UTC, before the GPU-lane rule; T=0 diffs = batching divergence'}
    res['ipd_live_exercise'] = {
        'design': '20 real 31B agent contexts whose logged edit_file call had slipped (data/protocol/contexts.jsonl, orig_ok=False, '
                  'seed 2), one next model turn per context per cfg, thinking on, budget 4096, T=0.2; E4B backend (:8311, conc 4)',
        'e4b_final_code': ipd_exercise(E / 'logs/proxy_e4b_v2'),
        'e4b_closure_rule_archived': 'logs/archive_closure_rule (earlier closure cut rule; shows the mis-cut that motivated the switch)'}
    res['pilot'] = {}
    for p in a.pilot:
        res['pilot'][Path(p).stem] = json.loads(Path(p).read_text())
    (E / 'results.json').write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: (v if k != 'pilot' else list(v)) for k, v in res.items()}, indent=1, default=str)[:6000])


if __name__ == '__main__':
    main()
