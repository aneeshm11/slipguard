"""Markdown table of the per-arm pilot metrics (from pilot_metrics.py output). Usage: metrics_table.py analysis/<tag>_metrics.json"""
import json
import sys


def ci(x):
    return '' if not x else f' [{x[0]:.2f}, {x[1]:.2f}]'


def rate(d, key='wilson'):
    if not d or d.get('rate') is None:
        return f"{d.get('k', 0)}/{d.get('n', 0)}" if d else '—'
    return f"{d['k']}/{d['n']} = {d['rate']:.3f}{ci(d.get(key))}"


d = json.load(open(sys.argv[1]))
rows = [('resolved (denominator: gold-gradable pilot tasks)', lambda a: rate(a['resolved'])),
        ('malformed calls, emitted (slips) [task-cluster boot]', lambda a: rate(a['malformed_total_emitted'], 'task_cluster_boot')),
        ('malformed calls, delivered [task-cluster boot]', lambda a: rate(a['malformed_total_delivered'], 'task_cluster_boot')),
        ('edit_file malformed, delivered [task-cluster boot]', lambda a: rate(a['edit_malformed_delivered'], 'task_cluster_boot')),
        ('onset hazard P(slip | no earlier slip) [boot]', lambda a: rate(a['onset_hazard_emitted'], 'task_cluster_boot')),
        ('post-onset P(slip | >=1 earlier slip) [boot]', lambda a: rate(a['post_onset_slip_rate'], 'task_cluster_boot')),
        ('sessions with >=1 slip', lambda a: f"{a['sessions_with_any_slip']['k']}/{a['sessions_with_any_slip']['n']}{ci(a['sessions_with_any_slip']['wilson'])}"),
        ('wasted calls / session [boot]', lambda a: f"{a['wasted_calls_per_session']['mean']}{ci(a['wasted_calls_per_session']['boot95'])} (total {a['wasted_calls_per_session']['total']})"),
        ('unparsed tool-call turns / session [boot]', lambda a: f"{a['unparsed_turns_per_session']['mean']}{ci(a['unparsed_turns_per_session']['boot95'])}"),
        ('sessions killed by protocol failure', lambda a: f"{a['sessions_killed_by_protocol']['k']}/{a['sessions_killed_by_protocol']['n']}{ci(a['sessions_killed_by_protocol']['wilson'])}"),
        ('sessions reaching a valid edit', lambda a: f"{a['reached_valid_edit']['k']}/{a['reached_valid_edit']['n']}{ci(a['reached_valid_edit']['wilson'])}"),
        ('time to first valid edit: median turns [boot]', lambda a: f"{a['time_to_first_valid_edit']['median_turns']}{ci(a['time_to_first_valid_edit']['boot95_turns'])}" if a.get('time_to_first_valid_edit') else '—'),
        ('time to first valid edit: median seconds [boot]', lambda a: f"{a['time_to_first_valid_edit']['median_seconds']}{ci(a['time_to_first_valid_edit']['boot95_seconds'])}" if a.get('time_to_first_valid_edit') else '—'),
        ('agent turns / session [boot]', lambda a: f"{a['agent_turns']['mean_per_session']}{ci(a['agent_turns']['boot95'])}"),
        ('wall s / session [boot]', lambda a: f"{a['wall_s']['mean']}{ci(a['wall_s']['boot95'])}"),
        ('IPD repairs (total) / quarantine actions (total)', lambda a: f"{a['ipd_repair']['total']} / {a['quarantine']['total']}"),
        ('IPD rejected (literal, not a slip) / stop false alarms', lambda a: f"{a['ipd_rejected']['total']} / {a['ipd_no_repair']['total']}"),
        ('submitted patch', lambda a: f"{a['submitted']['k']}/{a['submitted']['n']}")]
arms = list(d['arms'])
print('| metric | ' + ' | '.join(arms) + ' |')
print('|---|' + '---|' * len(arms))
for name, f in rows:
    cells = []
    for a in arms:
        try:
            cells.append(f(d['arms'][a]))
        except Exception:  # noqa: BLE001
            cells.append('—')
    print(f'| {name} | ' + ' | '.join(cells) + ' |')
print()
for p in d['paired']:
    print(f"- {p['contrast']}: n={p['n_common']}, resolve diff {p['resolve_diff_B_minus_A']} (only A {p['resolve_A_only']}, only B "
          f"{p['resolve_B_only']}, McNemar p={p['mcnemar_exact_p']}); delivered-malformed calls/session diff "
          f"{p['delivered_bad_calls_diff_B_minus_A']['mean']}{ci(p['delivered_bad_calls_diff_B_minus_A']['boot95'])}; wasted calls diff "
          f"{p['wasted_calls_diff_B_minus_A']['mean']}{ci(p['wasted_calls_diff_B_minus_A']['boot95'])}; turns diff "
          f"{p['agent_turns_diff_B_minus_A']['mean']}{ci(p['agent_turns_diff_B_minus_A']['boot95'])}")
