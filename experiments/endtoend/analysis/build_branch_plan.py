"""Branch-at-onset plan builder (closed loop). From a RECORDED base episode set (official harness, proxy cfg base):
for every completed episode with an edit_file call, the replay prefix = all requests up to and including the first
edit_file turn of the root agent (b). Onset = that call: NATURAL if it was emitted malformed, otherwise INJECTED with
workstream A's P1 corruption (contagion/scripts/variants.py: the first of new_string/old_string in emitted key order is
closed with a backtick instead of <|"|>; the vLLM 0.19.1 parse of that text is delivered; the raw text is kept so the
shipped quarantine can recover it). Natural onsets are taken first, then injected ones (seeded sample) up to --n.

Usage: build_branch_plan.py --run runs/<tag>_H_base --proxy-logs logs/proxy_<tag> --n 100 --seed 20261105 --out plans/<name>.json
"""
import os  # added by the repo export (paths are env/config driven)
import argparse
import json
import random
import sys
import time
from pathlib import Path

E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))
sys.path.insert(0, str(E / 'proxy'))
import gemma_protocol as gp  # noqa: E402

D = gp.D


def fmt_value(v):  # == contagion/scripts/gemma_protocol.py::fmt_value
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return D + v + D
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return '{' + ','.join(f'{k}:{fmt_value(x)}' for k, x in v.items()) + '}'
    if isinstance(v, list):
        return '[' + ','.join(fmt_value(x) for x in v) + ']'
    return str(v)


def raw_args(args, order, slip_key=None, closer='`'):  # == contagion/scripts/gemma_protocol.py::raw_args
    parts = []
    for k in order:
        if k not in args:
            continue
        v = args[k]
        if k == slip_key and isinstance(v, str):
            parts.append(f'{k}:{D}{v}{closer}')
        else:
            parts.append(f'{k}:{fmt_value(v)}')
    return ','.join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='append', required=True, help='recorded base run dir(s) (official harness, cfg base); repeatable')
    ap.add_argument('--proxy-logs', action='append', required=True, help='repeatable')
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--seed', type=int, default=20261105)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    import importlib
    ep = importlib.import_module('e2e_proxy')
    ep._install_array_hang_patch()
    from vllm.tool_parsers.gemma4_tool_parser import _parse_gemma4_args
    natural, injected, skipped = [], [], {}
    for run_s in a.run:
        run = Path(run_s)
        rc = json.loads((run / 'run_cfg.json').read_text())
        prefix = f"{rc.get('tag', run.name)}/{rc['cfg']}:"
        done = {json.loads(l)['id']: json.loads(l) for l in open(run / 'per_task.jsonl')}
        recs = {}
        for pl in a.proxy_logs:
            for f in Path(pl).glob(f"proxy_{rc['cfg']}.jsonl"):
                for line in open(f):
                    r = json.loads(line)
                    if r.get('task', '').startswith(prefix):
                        recs.setdefault(r['task'][len(prefix):], []).append(r)
        for tid, rs in sorted(recs.items()):
            rs.sort(key=lambda r: r['t'])
            if tid not in done:
                skipped[f'{run.name}:{tid}'] = 'episode not completed'
                continue
            b = next((i for i, r in enumerate(rs) if any(c['name'] == 'edit_file' for c in r.get('calls') or [])), None)
            if b is None:
                skipped[f'{run.name}:{tid}'] = 'no edit_file call'
                continue
            if any(r.get('status') != 200 for r in rs[:b + 1]):
                skipped[f'{run.name}:{tid}'] = 'proxy error before the onset'
                continue
            responses = []
            for r in rs[:b + 1]:
                segs = gp.CALL_RE.findall(r.get('raw') or '')
                calls = [{'id': c['id'], 'name': c['name'], 'args': c['args'], 'ok_emitted': c['ok_emitted']} for c in r.get('calls') or []]
                raw_by_id = {c['id']: segs[k][1] for k, c in enumerate(calls) if k < len(segs) and segs[k][0] == c['name']}
                responses.append({'raw': r['raw'], 'calls': calls, 'raw_args': raw_by_id, 'finish': r.get('finish'),
                                  'usage': {'prompt_tokens': r.get('prompt_tokens'), 'completion_tokens': r.get('gen_tokens')},
                                  'tool_results': r.get('tool_results'), 'n_msgs': r.get('n_msgs'), 'n_tools': r.get('n_tools')})
            onset = next(c for c in responses[b]['calls'] if c['name'] == 'edit_file')
            entry = {'task': tid, 'b': b, 'responses': responses, 'onset_call_id': onset['id'],
                     'source': {'run': str(run), 'session': prefix + tid, 'n_turns_recorded': len(rs)}}
            if not onset['ok_emitted']:
                entry.update(onset='natural', onset_args=onset['args'], onset_raw_args=responses[b]['raw_args'].get(onset['id'], ''))
                natural.append(entry)
            else:
                args = onset['args']
                order = list(args.keys())  # emitted order (vLLM's parser keeps it; json keeps it)
                slip_key = next((k for k in order if k in ('new_string', 'old_string')), None)
                if slip_key is None:
                    skipped[f'{run.name}:{tid}'] = 'first edit has no string argument to corrupt'
                    continue
                raw = raw_args(args, order, slip_key=slip_key, closer='`')
                corrupted = _parse_gemma4_args(raw)
                if corrupted == args or gp.classify_args('edit_file', corrupted, {'edit_file': {'properties': {
                        'filepath': {}, 'old_string': {}, 'new_string': {}, 'allow_multiple': {}},
                        'required': ['filepath', 'old_string', 'new_string']}})['ok']:
                    skipped[f'{run.name}:{tid}'] = 'P1 corruption did not produce a malformed call'
                    continue
                entry.update(onset='injected', onset_args=corrupted, onset_raw_args=raw, onset_slip_key=slip_key)
                injected.append(entry)
    rnd = random.Random(a.seed)
    rnd.shuffle(natural)
    rnd.shuffle(injected)
    # natural onsets first, then injected; a plan holds at most one branch point per task (the proxy keys plans by
    # task), so overflow (e.g. 150 points from 113 tasks x 2 replicates) goes to further plans <out>_2.json, ...
    plans, chosen = [{}], []
    for e in natural + injected:
        if len(chosen) >= a.n:
            break
        k = next((i for i, pl in enumerate(plans) if e['task'] not in pl), None)
        if k is None:
            plans.append({})
            k = len(plans) - 1
        plans[k][e['task']] = e
        chosen.append(e)
    outs = []
    for k, pl in enumerate(plans):
        out = Path(a.out) if k == 0 else Path(a.out).with_name(Path(a.out).stem + f'_{k + 1}.json')
        for e in pl.values():
            e['branch_id'] = f"{out.stem}:{e['task']}"
        plan = {'meta': {'created': time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime()), 'source_runs': a.run,
                         'source_proxy_logs': a.proxy_logs, 'n_requested': a.n, 'seed': a.seed, 'plan_index': k + 1,
                         'n_plans': len(plans), 'n_natural': sum(e['onset'] == 'natural' for e in pl.values()),
                         'n_injected': sum(e['onset'] == 'injected' for e in pl.values()), 'skipped': skipped},
                'branches': pl}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, ensure_ascii=False))
        out.with_suffix('.tasks.txt').write_text('\n'.join(sorted(pl)) + '\n')
        outs.append(str(out))
    print(json.dumps({'plans': outs, 'n_branch_points': len(chosen), 'skipped': len(skipped)}))


if __name__ == '__main__':
    main()
