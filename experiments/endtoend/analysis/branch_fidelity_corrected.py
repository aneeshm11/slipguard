"""PRE-OUTCOME CORRECTION of the branch replay-fidelity check (2026-11-06; NOT part of the frozen manifest; frozen code
is imported unchanged). The frozen proxy hashes each replayed tool result after normalising volatile parts; it masks the
VALUE of the harness's "budget_warning" annotation but not its PRESENCE. The registered 40-call branch cap makes the
harness add that annotation from call 30 on, where the 50-call source episode had none, so every prefix with >= 30
calls fails the hash although the tool output is identical. This check compares, for each branch point and arm, the
replayed prefix tool results with the source episode's, step by step from the harness traces, using the frozen
normaliser (gemma_protocol.tool_output_hash) after removing the "budget_warning" key and masking 64-hex Docker container
ids (sandbox-instance identifiers, like the tmp paths/addresses the frozen normaliser already masks); nothing else.
Status and error type must match as in the frozen check. Prefixes longer than the 40-call cap fail (BudgetExceeded). Output: {branch_task: {'arm': ok|mismatch, ...}}.
usage: branch_fidelity_corrected.py <plan.json> <out.json> <arm>=<run_dir> [...]"""
import os  # added by the repo export (paths are env/config driven)
import ast
import json
import sys
from pathlib import Path

E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))
sys.path.insert(0, str(E / 'proxy'))
import gemma_protocol as gp  # noqa: E402
import re  # noqa: E402
CID = re.compile(r'\b[0-9a-f]{64}\b')


def tool_results(trace_path):
    d = json.load(open(trace_path))
    out = []
    for s in d['steps']:
        if s.get('source') != 'agent' or not s.get('tool_calls'):
            continue
        calls = ast.literal_eval(s['tool_calls']) if isinstance(s['tool_calls'], str) else s['tool_calls']
        obs = s.get('observation')
        obs = ast.literal_eval(obs) if isinstance(obs, str) else obs
        contents = obs if isinstance(obs, list) else [obs]
        for k, c in enumerate(calls):
            o = contents[k] if k < len(contents) else None
            out.append((c.get('function_name'), o.get('content') if isinstance(o, dict) else o))
    return out


def norm(content):
    txt = content if isinstance(content, str) else json.dumps(content, sort_keys=True, default=str)
    st, et = None, None
    try:
        obj = json.loads(txt)
        if isinstance(obj, dict):
            obj.pop('budget_warning', None)
            st, et = obj.get('status'), obj.get('error_type')
            txt = json.dumps(obj, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        pass
    txt = CID.sub('<CID>', txt)
    return st, et, gp.tool_output_hash(txt)


def main():
    plan = json.load(open(sys.argv[1]))['branches']
    arms = dict(a.split('=', 1) for a in sys.argv[3:])
    res = {}
    for tid, br in plan.items():
        k = sum(len(r['calls']) for r in br['responses'][:br['b']])   # prefix executions reported in replayed requests
        src_run = E / 'runs' / br['source']['session'].split('/')[0]
        orig = tool_results(src_run / 'traces' / f'trace_{tid}.json')[:k]
        res[tid] = {'n_prefix_tool_results': k}
        for arm, rd in arms.items():
            tp = Path(rd) / 'traces' / f'trace_{tid}.json'
            if not tp.exists():
                res[tid][arm] = 'missing'
                continue
            rep = tool_results(tp)[:k]
            ok = len(rep) == len(orig) == k and all(a[0] == b[0] and norm(a[1]) == norm(b[1]) for a, b in zip(orig, rep))
            res[tid][arm] = 'ok' if ok else 'mismatch'
    Path(sys.argv[2]).write_text(json.dumps(res, indent=0))
    from collections import Counter
    print({arm: dict(Counter(v[arm] for v in res.values())) for arm in arms})


if __name__ == '__main__':
    main()
