"""Per-arm end-to-end metrics for a pilot (coordinator's list), with CIs, + paired contrasts + event export.

Inputs: runs/<tag>_{H,C}_{base,full}/ (per_task.jsonl, run_cfg.json, client_calls.jsonl) and logs/proxy_<tag>/.
Definitions (one session = one task attempt in one arm; sub-agent turns of the harness are part of the session;
ADK compaction calls (no tools) are excluded from agent turns):
  slip (emitted malformed)  : the model's raw emission of a call was malformed (repaired by IPD or not)
  delivered malformed       : the call the client received was malformed (SYNTHESIS §5 criterion, all tools)
  onset                     : P(slip | no earlier slip in the session); post-onset: P(slip | >= 1 earlier slip)
  wasted calls              : delivered-malformed calls + tool results with a protocol error type
                              (TypeError/ValueError/MalformedToolCall/UnknownTool/unknown tool name)
  unparsed turn             : response containing a <|tool_call> the parser could not read (no call delivered)
  killed by protocol        : session ended without a submitted patch and its last agent turn was an unparsed turn
                              or delivered a malformed call
  time to first valid edit  : agent turns (and wall seconds since the session's first request) until the first
                              edit_file/write_file whose tool result has status ok
Usage: pilot_metrics.py <tag> [--out analysis/<tag>_metrics.json]
"""
import os  # added by the repo export (paths are env/config driven)
import argparse
import glob
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))
PROTO_ERR = {'TypeError', 'ValueError', 'MalformedToolCall', 'UnknownTool', 'ValidationError', 'JSONDecodeError',
             'MissingParameters', 'UnexpectedArgument'}
ORPHAN = re.compile(r'(?:^|[^>])call:[\w\-\.]+\{')


def unparsed_turn(r):
    """the turn emitted call syntax that produced no delivered call: an opener tag the parser could not read, or call
    text without the <|tool_call> opener (seen after forced thinking-budget ends: 'call:read_file{...}<tool_call|>')"""
    if r.get('unparsed_tool_call'):
        return True
    if r.get('calls'):
        return False
    raw = r.get('raw') or ''
    ans = raw[raw.rfind('<channel|>') + len('<channel|>'):] if '<channel|>' in raw else raw
    return '<tool_call|>' in ans or bool(ORPHAN.search(ans))
ARMS = [('H', 'base'), ('H', 'full'), ('C', 'base'), ('C', 'full')]


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def boot(xs, B=4000, seed=0, stat=None):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    stat = stat or (lambda v: sum(v) / len(v))
    rnd = random.Random(seed)
    bs = sorted(stat([rnd.choice(xs) for _ in xs]) for _ in range(B))
    return round(stat(xs), 4), [round(bs[int(0.025 * B)], 4), round(bs[int(0.975 * B) - 1], 4)]


def median(v):
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def cluster_rate(groups, B=4000, seed=0):
    groups = [(k, n) for k, n in groups if n > 0]
    K, N = sum(k for k, _ in groups), sum(n for _, n in groups)
    if not N:
        return {'k': 0, 'n': 0, 'rate': None, 'wilson': None, 'task_cluster_boot': None}
    rnd = random.Random(seed)
    bs = []
    for _ in range(B):
        s = [rnd.choice(groups) for _ in groups]
        nn = sum(n for _, n in s)
        bs.append(sum(k for k, _ in s) / nn if nn else 0.0)
    bs.sort()
    return {'k': K, 'n': N, 'rate': round(K / N, 4), 'wilson': wilson(K, N),
            'task_cluster_boot': [round(bs[int(0.025 * B)], 4), round(bs[int(0.975 * B) - 1], 4)]}


def proxy_records(tag):
    by = defaultdict(list)
    for f in glob.glob(str(E / f'logs/proxy_{tag}/proxy_*.jsonl')):
        for line in open(f):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get('task'):
                by[r['task']].append(r)
    for v in by.values():
        v.sort(key=lambda r: r['t'])
    return by


def session(reqs):
    """per-session metrics from its proxy records"""
    s = Counter()
    turns = [r for r in reqs if r.get('status') == 200 and r.get('n_tools', 1) != 0]
    s['compaction_calls'] = sum(1 for r in reqs if r.get('status') == 200 and r.get('n_tools', 1) == 0)
    s['req_errors'] = sum(1 for r in reqs if r.get('status') != 200)
    t0 = reqs[0]['t'] if reqs else None
    slipped_before = False
    seq = []          # per call: (slip, delivered_bad, slipped_before)
    events = []
    first_valid_edit = None
    quarantined = set()
    prev_bad = []  # delivered-malformed flags of the previous turn's calls (results arrive in call order)
    for i, r in enumerate(turns):
        # tool results reported in this request belong to the PREVIOUS turn's calls
        res = r.get('tool_results') or []
        for j, tr in enumerate(res):
            name, st, et = tr[0], tr[1], tr[2]
            proto = et in PROTO_ERR or (name is None and st == 'error')
            if proto or (j < len(prev_bad) and prev_bad[j]):
                s['wasted_calls'] += 1
        for j in range(len(res), len(prev_bad)):  # malformed calls without a reported result
            s['wasted_calls'] += prev_bad[j]
        for tr in res:
            name, st, et = tr[0], tr[1], tr[2]
            if name in ('edit_file', 'write_file') and st == 'ok' and first_valid_edit is None:
                first_valid_edit = {'turns': i, 'seconds': round(r['t'] - t0, 1)}
            if et in PROTO_ERR or (name is None and st == 'error'):
                s['protocol_error_results'] += 1
            if st == 'error':
                s['error_results'] += 1
        ev = r.get('events') or []
        rep_tools = Counter(e.get('tool') for e in ev if e['ev'] == 'ipd_repair')
        for e in ev:
            if e['ev'] in ('ipd_repair', 'ipd_rejected', 'posthoc_repair', 'budget_forced_end', 'ipd_no_repair'):
                events.append({'turn': i, **{k: v for k, v in e.items() if k != 'ctx'}, 'ctx': (e.get('ctx') or '')[-80:]})
            s[e['ev']] += 1
        for q in r.get('quarantine') or []:
            if q.get('id') not in quarantined:  # the same historical call is re-quarantined in every later request
                quarantined.add(q.get('id'))
                events.append({'turn': i, 'ev': 'quarantine', **q})
                s['quarantine'] += 1
            s['quarantine_applications'] += 1
        calls = r.get('calls') or []
        prev_bad = [int(not c['ok_delivered']) for c in calls]
        s['agent_turns'] += 1
        s['gen_tokens'] += r.get('gen_tokens') or 0
        s['prompt_tokens'] += r.get('prompt_tokens') or 0
        if unparsed_turn(r):
            s['unparsed_turns'] += 1
        if r.get('finish') == 'length' and not r.get('calls'):
            s['length_no_call_turns'] += 1
        if not calls:
            s['no_call_turns'] += 1
        for c in calls:
            slip = (not c['ok_emitted']) or rep_tools.get(c['name'], 0) > 0
            bad = not c['ok_delivered']
            seq.append((int(slip), int(bad), slipped_before, c['name']))
            slipped_before = slipped_before or slip
            s['calls'] += 1
            s['slips'] += int(slip)
            s['delivered_bad'] += int(bad)
            if c['name'] == 'edit_file':
                s['edit_calls'] += 1
                s['edit_slips'] += int(slip)
                s['edit_delivered_bad'] += int(bad)
    s['delivered_bad_last'] = sum(prev_bad) if turns else 0  # malformed calls of the final turn (no result reported)
    last = turns[-1] if turns else None
    last_bad = bool(last and (unparsed_turn(last) or any(not c['ok_delivered'] for c in last.get('calls') or [])))
    s['last_turn_length_no_call'] = int(bool(last and last.get('finish') == 'length' and not last.get('calls')))
    return s, seq, events, first_valid_edit, last_bad, (turns[-1]['t'] - t0 if turns else None)


def arm_metrics(tag, kind, cfg, by):
    rd = E / f'runs/{tag}_{kind}_{cfg}'
    if not (rd / 'per_task.jsonl').exists():
        return None, None, None
    rc = json.loads((rd / 'run_cfg.json').read_text())
    pref = f"{rc.get('tag', rd.name)}/{'nonudge-' if kind == 'C' else ''}{cfg}:"
    recs = {json.loads(l)['id']: json.loads(l) for l in open(rd / 'per_task.jsonl')}
    ends = {}
    if (rd / 'client_calls.jsonl').exists():
        for l in open(rd / 'client_calls.jsonl'):
            c = json.loads(l)
            ends[c['task'].split(':')[-1]] = c
    per, all_events = {}, []
    for tid, r in recs.items():
        s, seq, events, fve, last_bad, dur = session(by.get(pref + tid, []))
        submitted = r.get('submitted') if kind == 'H' else (ends.get(tid) or {}).get('submitted')
        end = (ends.get(tid) or {}).get('end') if kind == 'C' else None
        killed = (not submitted) and last_bad
        per[tid] = {'resolved': int(r['resolved']), 'submitted': bool(submitted), 'end': end, 'killed_by_protocol': int(killed),
                    'tool_calls_harness': r.get('tool_calls'), 'llm_calls': r.get('llm_calls'), 'wall_s': r.get('wall_s'),
                    's': dict(s), 'seq': seq, 'first_valid_edit': fve, 'error': (r.get('error') or '')[:100]}
        for e in events:
            all_events.append({'arm': f'{kind}-{cfg}', 'task': tid, **e})
    n = len(per)
    k = sum(v['resolved'] for v in per.values())
    g = lambda key: [(v['s'].get(key, 0)) for v in per.values()]  # noqa: E731
    out = {'arm': f'{kind}-{cfg}', 'client': 'official harness' if kind == 'H' else 'no-nudge client', 'proxy_cfg': cfg,
           'n_sessions': n, 'resolved': {'k': k, 'n': n, 'rate': round(k / n, 4) if n else None, 'wilson': wilson(k, n),
                                         'denominator': 'pilot tasks, all gold-gradable in our sandbox (gold resolves, empty patch fails)'}}
    out['malformed_total_emitted'] = cluster_rate([(v['s'].get('slips', 0), v['s'].get('calls', 0)) for v in per.values()])
    out['malformed_total_delivered'] = cluster_rate([(v['s'].get('delivered_bad', 0), v['s'].get('calls', 0)) for v in per.values()])
    out['edit_malformed_emitted'] = cluster_rate([(v['s'].get('edit_slips', 0), v['s'].get('edit_calls', 0)) for v in per.values()])
    out['edit_malformed_delivered'] = cluster_rate([(v['s'].get('edit_delivered_bad', 0), v['s'].get('edit_calls', 0)) for v in per.values()])
    on = [(sum(c[0] for c in v['seq'] if not c[2]), sum(1 for c in v['seq'] if not c[2])) for v in per.values()]
    po = [(sum(c[0] for c in v['seq'] if c[2]), sum(1 for c in v['seq'] if c[2])) for v in per.values()]
    out['onset_hazard_emitted'] = cluster_rate(on)
    out['post_onset_slip_rate'] = cluster_rate(po)
    sess_slip = [int(any(c[0] for c in v['seq'])) for v in per.values()]
    out['sessions_with_any_slip'] = {'k': sum(sess_slip), 'n': n, 'wilson': wilson(sum(sess_slip), n)}
    wasted = [v['s'].get('wasted_calls', 0) + (v['s'].get('delivered_bad_last', 0)) for v in per.values()]
    m, ci = boot(wasted)
    out['wasted_calls_per_session'] = {'mean': m, 'boot95': ci, 'total': sum(wasted),
                                       'definition': 'calls delivered malformed OR whose tool result had a protocol error type '
                                                     '(TypeError/ValueError/MalformedToolCall/UnknownTool/...), counted once per call'}
    m, ci = boot(g('unparsed_turns'))
    out['unparsed_turns_per_session'] = {'mean': m, 'boot95': ci, 'total': sum(g('unparsed_turns'))}
    kp = sum(v['killed_by_protocol'] for v in per.values())
    out['sessions_killed_by_protocol'] = {'k': kp, 'n': n, 'wilson': wilson(kp, n),
                                          'definition': 'no submitted patch and the last agent turn was unparsed call syntax '
                                                        '(incl. call text without the <|tool_call> opener) or delivered a malformed call'}
    kl = sum(1 for v in per.values() if not v['submitted'] and v['s'].get('last_turn_length_no_call'))
    out['sessions_ended_by_length_no_call'] = {'k': kl, 'n': n, 'wilson': wilson(kl, n),
                                               'definition': 'no submitted patch and the last turn hit the length cap without a call '
                                                             '(e.g. thinking re-entered after a forced budget end)'}
    m, ci = boot(g('length_no_call_turns'))
    out['length_no_call_turns_per_session'] = {'mean': m, 'boot95': ci, 'total': sum(g('length_no_call_turns'))}
    fv = [v['first_valid_edit'] for v in per.values()]
    reached = [x for x in fv if x]
    out['reached_valid_edit'] = {'k': len(reached), 'n': n, 'wilson': wilson(len(reached), n)}
    if reached:
        mt, cit = boot([x['turns'] for x in reached], stat=median)
        ms, cis = boot([x['seconds'] for x in reached], stat=median)
        out['time_to_first_valid_edit'] = {'median_turns': mt, 'boot95_turns': cit, 'median_seconds': ms, 'boot95_seconds': cis,
                                           'n_reached': len(reached)}
    for key in ('agent_turns', 'calls', 'gen_tokens', 'ipd_repair', 'ipd_rejected', 'ipd_no_repair', 'posthoc_repair',
                'quarantine', 'quarantine_applications', 'budget_forced_end', 'compaction_calls', 'req_errors', 'error_results'):
        m, ci = boot(g(key))
        out[key] = {'total': sum(g(key)), 'mean_per_session': m, 'boot95': ci}
    m, ci = boot([v['wall_s'] for v in per.values()])
    out['wall_s'] = {'mean': m, 'boot95': ci}
    sub = sum(v['submitted'] for v in per.values())
    out['submitted'] = {'k': sub, 'n': n, 'wilson': wilson(sub, n)}
    if kind == 'C':
        out['episode_end'] = dict(Counter(v['end'] for v in per.values()))
    out['errors'] = dict(Counter(v['error'][:60] for v in per.values() if v['error']))
    return out, per, all_events


def paired(pa, pb, name):
    common = sorted(set(pa) & set(pb))
    b = sum(1 for t in common if pa[t]['resolved'] and not pb[t]['resolved'])
    c = sum(1 for t in common if pb[t]['resolved'] and not pa[t]['resolved'])
    nd = b + c
    p = min(1.0, 2 * sum(math.comb(nd, i) for i in range(0, min(b, c) + 1)) / 2 ** nd) if nd else 1.0
    res = {'contrast': name, 'n_common': len(common), 'resolve_A_only': b, 'resolve_B_only': c,
           'resolve_diff_B_minus_A': round((c - b) / len(common), 4) if common else None, 'mcnemar_exact_p': round(p, 4)}
    for key, get in (('delivered_bad_calls', lambda v: v['s'].get('delivered_bad', 0)),
                     ('slips', lambda v: v['s'].get('slips', 0)),
                     ('wasted_calls', lambda v: v['s'].get('wasted_calls', 0) + v['s'].get('delivered_bad_last', 0)),
                     ('agent_turns', lambda v: v['s'].get('agent_turns', 0)),
                     ('wall_s', lambda v: v['wall_s'])):
        d = [get(pb[t]) - get(pa[t]) for t in common if get(pa[t]) is not None and get(pb[t]) is not None]
        m, ci = boot(d)
        res[f'{key}_diff_B_minus_A'] = {'mean': m, 'boot95': ci}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tag')
    ap.add_argument('--out', default=None)
    ap.add_argument('--cfgs', default='base,full', help="proxy cfgs of the arms (pilots: base,full; pre-registered: base,fullp)")
    ap.add_argument('--kinds', default='H,C', help='H = official harness, C = no-nudge client')
    a = ap.parse_args()
    by = proxy_records(a.tag)
    arms, pers, evs = {}, {}, []
    cfgs = a.cfgs.split(',')
    for kind, cfg in [(k, c) for k in a.kinds.split(',') for c in cfgs]:
        o, p, e = arm_metrics(a.tag, kind, cfg, by)
        if o:
            arms[o['arm']] = o
            pers[o['arm']] = p
            evs += e
    pairs = []
    b0, f0 = cfgs[0], cfgs[-1]
    for x, y in ((f'H-{b0}', f'H-{f0}'), (f'C-{b0}', f'C-{f0}'), (f'H-{b0}', f'C-{b0}'), (f'H-{f0}', f'C-{f0}')):
        if x in pers and y in pers:
            pairs.append(paired(pers[x], pers[y], f'{x} -> {y}'))
    out = {'tag': a.tag, 'arms': arms, 'paired': pairs}
    outp = Path(a.out or E / f'analysis/{a.tag}_metrics.json')
    outp.write_text(json.dumps(out, indent=1, default=str))
    with open(outp.with_name(f'{a.tag}_events.jsonl'), 'w') as f:
        for e in evs:
            f.write(json.dumps(e, default=str) + '\n')
    for arm, o in arms.items():
        print(f"{arm}: n={o['n_sessions']} resolved {o['resolved']['k']}/{o['resolved']['n']} {o['resolved']['wilson']} | "
              f"malformed emitted {o['malformed_total_emitted']['rate']} delivered {o['malformed_total_delivered']['rate']} | "
              f"onset {o['onset_hazard_emitted']['rate']} | wasted/session {o['wasted_calls_per_session']['mean']} | "
              f"killed {o['sessions_killed_by_protocol']['k']} | ipd {o['ipd_repair']['total']} quar {o['quarantine']['total']}")
    for p in pairs:
        print(json.dumps(p))


if __name__ == '__main__':
    main()
