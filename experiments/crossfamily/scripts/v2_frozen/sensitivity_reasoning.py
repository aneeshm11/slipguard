"""Secondary sensitivity analysis (PREREG_DEVIATIONS.md, added after the 8B pilot): re-judge every stored generation
with the LENIENT reasoning split (vLLM 0.31 Qwen3-engine semantics: a '<tool_call>' inside an unclosed '<think>' ends
the reasoning) instead of the registered vLLM 0.19.1 split (no '</think>' -> everything is reasoning -> no call).
Writes <gen>_lenient.jsonl (same records, judge replaced; 'judge_registered' keeps the original) for analyze.py, and
prints the per-arm rate of calls emitted inside an unclosed thought.
usage: sensitivity_reasoning.py out/gen_<mk>.jsonl data/prompts_<mk>.jsonl [more gen/prompt pairs...]"""
import collections
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qwenproto as qp  # noqa: E402


def wilson(k, n, z=1.959964):
    if n == 0:
        return [None, None, None, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0.0, c - h), 4), round(min(1.0, c + h), 4), n]


args = sys.argv[1:]
SUMF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out', 'sensitivity_reasoning_summary.json')
summary = json.load(open(SUMF)) if os.path.exists(SUMF) else {}
for gen_f, pr_f in zip(args[0::2], args[1::2]):
    tools = {}
    for line in open(pr_f):
        r = json.loads(line); tools[(r['id'], r['arm'])] = r['tools']
    out_f = gen_f.replace('.jsonl', '_lenient.jsonl')
    sw = collections.Counter(); n = collections.Counter(); changed = collections.Counter()
    with open(out_f, 'w') as fo:
        for line in open(gen_f):
            d = json.loads(line)
            if d.get('error') or not d.get('judge'):
                continue
            t = tools[(d['id'], d['arm'])]
            jl = qp.judge(d['gen'], d['fmt'], t, d['model'], lenient_reasoning=True)
            js = d['judge']
            arm = d['arm']; n[arm] += 1
            sw[arm] += int(bool(jl.get('call_in_unclosed_reasoning')))
            changed[arm] += int((js.get('name'), js.get('malformed')) != (jl.get('name'), jl.get('malformed')))
            d['judge_registered'] = js; d['judge'] = jl
            fo.write(json.dumps(d, ensure_ascii=False) + '\n')
    summary[gen_f] = {arm: {'n': n[arm], 'call_in_unclosed_reasoning': wilson(sw[arm], n[arm]),
                            'first_call_outcome_changed': changed[arm]} for arm in sorted(n)}
    print(gen_f, json.dumps(summary[gen_f]))
json.dump(summary, open(SUMF, 'w'), indent=1)
