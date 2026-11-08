"""Synthetic-fixture test of analysis/prereg_analysis.py (no real outcome data is read: blinding)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

E = Path(__file__).resolve().parents[1]
PY = sys.executable
n_ok = 0


def check(c, m):
    global n_ok
    assert c, m
    n_ok += 1


def call(name, ok=True):
    return {'name': name, 'ok_emitted': ok, 'ok_delivered': ok, 'id': 'x', 'args': {}}


def rec(task, t, calls, tool_results=(), raw='', hist=(), n_tools=10, branch=None, replay=None):
    r = {'t': t, 'task': task, 'status': 200, 'n_tools': n_tools, 'calls': list(calls), 'tool_results': [list(x) for x in tool_results],
         'raw': raw, 'hist': [list(h) for h in hist], 'prompt_tokens': 1000, 'gen_tokens': 100, 'latency_s': 1.0}
    if branch is not None:
        r['branch'] = branch
    if replay is not None:
        r['replay'] = replay
    return r


def make_run(root, name, cfg, per_task, recs):
    d = root / 'runs' / name
    d.mkdir(parents=True)
    (d / 'run_cfg.json').write_text(json.dumps({'cfg': cfg, 'tag': name}))
    (d / 'per_task.jsonl').write_text(''.join(json.dumps(p) + '\n' for p in per_task))
    lg = root / 'logs' / f'proxy_{root.name}'
    lg.mkdir(parents=True, exist_ok=True)
    with open(lg / f'proxy_{cfg}.jsonl', 'a') as f:
        for r in recs:
            f.write(json.dumps({**r, 'task': f'{name}/{cfg}:{r["task"]}'}) + '\n')
    return d


with tempfile.TemporaryDirectory(dir=str(E / 'tmp')) as td:
    root = Path(td) / 'syn'
    root.mkdir()
    MP = ['edit_file', 'error', 'MissingParameters', 'h']
    base_recs = [
        rec('t1', 1, [call('edit_file', False)]), rec('t1', 2, [call('edit_file', False)], [MP]), rec('t1', 3, [call('submit_patch')], [MP]),
        rec('t2', 1, [call('read_file')]), rec('t2', 2, [call('edit_file')], [['read_file', 'ok', None, 'h']]),
        rec('t2', 3, [], [['edit_file', 'ok', None, 'h']]),
        rec('t3', 1, [call('edit_file', False)]), rec('t3', 2, [], [MP], raw='<channel|>call:read_file{x}<tool_call|>'),
    ]
    full_recs = [rec('t1', 1, [call('edit_file')]), rec('t2', 1, [call('edit_file')]), rec('t3', 1, [call('edit_file')])]
    pt = lambda t, res: {'id': t, 'resolved': res, 'error': '', 'agent_s': 100.0}  # noqa: E731
    make_run(root, 'synA_base', 'base', [pt('t1', True), pt('t2', False), pt('t3', False)], base_recs)
    make_run(root, 'synA_fullp', 'fullp', [pt('t1', True), pt('t2', True), pt('t3', False)], full_recs)
    (root / 'tasks.txt').write_text('t1\nt2\nt3\n')
    out = root / 'pop.json'
    subprocess.run([PY, str(E / 'analysis/prereg_analysis.py'), 'population', '--label', 'syn',
                    '--base', str(root / 'runs/synA_base'), '--fullp', str(root / 'runs/synA_fullp'),
                    '--proxy-logs', str(root / 'logs' / 'proxy_syn'), '--tasks', str(root / 'tasks.txt'), '--out', str(out)], check=True)
    r = json.loads(out.read_text())
    y1, y2 = r['co_primary']['Y1'], r['co_primary']['Y2']
    check(abs(y1['base_mean'] - 1.0) < 1e-9 and y1['fullp_mean'] == 0 and y1['diff_fullp_minus_base']['mean_diff'] == -1.0, f'Y1 {y1}')
    # Y2 base: t1 = 2 malformed calls (their MissingParameters results are not double counted) ; t3 = 1 malformed + 1 unparsed turn
    check(abs(y2['base_mean'] - 4 / 3) < 1e-3, f'Y2 {y2}')
    # 3 tasks with diffs (-2, 0, -1): resampling all zeros has p = 1/27 > 2.5%, so the CI touches 0 -> rule must say False
    check(y1['ratio_fullp_over_base']['ratio'] == 0.0 and y1['diff_fullp_minus_base']['ci95'] == [-2.0, 0.0]
          and r['co_primary']['success_Y1_reduction_ge_70pct_ci_excludes_0'] is False, 'success rule respects the CI')
    rr = r['secondary']['resolved']['replicate1']
    check(rr['base'][0] == 1 and rr['fullp'][0] == 2 and rr['discordant'] == [0, 1], f'resolve {rr}')
    check(r['secondary']['first_applied_edit']['base']['reached'][0] == 1, f"first applied edit {r['secondary']['first_applied_edit']}")
    # ---- branches
    plan = {'branches': {t: {'b': 1, 'onset': 'injected'} for t in ('t1', 't2')}}
    (root / 'plan.json').write_text(json.dumps(plan))
    def brec(task, i, ok, fid='ok'):
        return rec(task, i, [call('edit_file', ok)], branch={'i': i, 'b': 1}, replay={'fidelity': fid} if i <= 1 else None)
    make_run(root, 'synB_base', 'base', [pt('t1', False), pt('t2', False)],
             [brec('t1', 0, True), brec('t1', 1, False), brec('t1', 2, False), brec('t1', 3, False),
              brec('t2', 0, True), brec('t2', 1, False), brec('t2', 2, False)])
    make_run(root, 'synB_quar', 'quar', [pt('t1', True), pt('t2', False)],
             [brec('t1', 0, True), brec('t1', 1, False), brec('t1', 2, True), brec('t1', 3, True),
              brec('t2', 0, True), brec('t2', 1, False, fid='mismatch'), brec('t2', 2, True)])
    out2 = root / 'br.json'
    subprocess.run([PY, str(E / 'analysis/prereg_analysis.py'), 'branches', '--label', 'syn', '--plan', str(root / 'plan.json'),
                    '--arm', f'base={root}/runs/synB_base', '--arm', f'quar={root}/runs/synB_quar',
                    '--proxy-logs', str(root / 'logs' / 'proxy_syn'), '--out', str(out2)], check=True)
    b = json.loads(out2.read_text())
    check(b['n_branch_points'] == 1 and b['excluded_fidelity_or_infra'] == ['0:t2'], f"fidelity exclusion {b['n_branch_points']} {b['excluded_fidelity_or_infra']}")
    check(b['post_onset']['base']['post_onset_malformed_mean'] == 2.0 and b['post_onset']['quar']['post_onset_malformed_mean'] == 0.0,
          f"post-onset {b['post_onset']}")
print(f'ALL {n_ok} CHECKS PASSED')
