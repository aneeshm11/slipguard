"""Read-only cross-check: does the decision-point judge (stop at the first ',old_string:'/',new_string:' and check the
closer) agree with the full vLLM-parse judge on records that were generated to completion?
usage: xcheck_decision_judge.py out.json results1.jsonl [results2.jsonl ...]"""
import json, sys, os, re, collections, math
sys.path.insert(0, os.path.dirname(__file__))
import gemma_protocol as gp
STOP = re.compile(r',(old_string|new_string):')
def w(k, n, z=1.96):
    if n == 0: return None
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(c - h, 4), round(c + h, 4), n]
tab = collections.Counter(); ex = collections.defaultdict(list); n_rec = 0
for f in sys.argv[2:]:
    for l in open(f):
        d = json.loads(l)
        j = d.get('judge') or {}
        if d.get('error') or j.get('name') != 'edit_file' or j.get('decision_point'): continue
        n_rec += 1
        t = d.get('s2_text') or ''
        m = STOP.search(t)
        if not m:
            dec = 'no_stop'  # decision-point run would not have stopped early: falls back to the full judge
        else:
            jd = gp.judge_decision(t[:m.start()], m.group(0))
            dec = 'dp_bad' if jd['malformed'] else 'dp_ok'
        full = 'full_bad' if j.get('malformed') else 'full_ok'
        tab[(dec, full)] += 1
        if (dec, full) in (('dp_ok', 'full_bad'), ('dp_bad', 'full_ok')) and len(ex[(dec, full)]) < 4:
            ex[(dec, full)].append({'id': d['id'], 'arm': f"{d['pathway']}k{d['k']}", 'full_why': j.get('why'), 'tail_at_stop': t[max(0, (m.start() if m else 0) - 80):(m.start() if m else 0) + 20]})
fb = sum(v for (dd, ff), v in tab.items() if ff == 'full_bad'); db = sum(v for (dd, ff), v in tab.items() if dd == 'dp_bad')
out = {'n_full_judged_edits': n_rec, 'table': {f'{a}|{b}': v for (a, b), v in sorted(tab.items())},
       'decision_point_sensitivity_vs_full': w(tab[('dp_bad', 'full_bad')], fb),
       'decision_point_false_positive_rate_on_full_ok': w(tab[('dp_bad', 'full_ok')], sum(v for (dd, ff), v in tab.items() if ff == 'full_ok')),
       'full_bad_without_stop_string': tab[('no_stop', 'full_bad')], 'examples': {f'{a}|{b}': v for (a, b), v in ex.items()}}
json.dump(out, open(sys.argv[1], 'w'), indent=1); print(json.dumps(out, indent=1)[:3000])
