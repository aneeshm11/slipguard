"""CPU smoke test for the benchmark-extension models (prereg_ext.md) on context records with an S1/S0 schema.
Per model and context, every arm (P0, P1L, P1N, P5, P6, P8a) is built (arms_v2) and rendered by the model's own
production path (vLLM 0.19.1: HF chat template / harmony / mistral); checks:
  render ok; prompt tokens; history-call byte identity (the replaced call, and P0's original call, appear in the
  prompt exactly as the format's history serializer writes them); P1N stack outcome; judge sanity on synthetic
  generations in the model's EMIT format (original call ok; laundered call malformed; native slip per format);
  judge false positives over every historical call re-emitted in the model's format.
usage: smoke_ext.py <manifest.json> N out.json [models=qwen3.8-27b,qwen3-coder-30b,gpt-oss-20b,devstral-24b]"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qwenproto as qp  # noqa: E402
import arms_v2 as A2  # noqa: E402
import fmt_ext as fe  # noqa: E402

man, N, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
MKS = (sys.argv[4] if len(sys.argv) > 4 else 'qwen3.8-27b,qwen3-coder-30b,gpt-oss-20b,devstral-24b').split(',')
recs, H = A2.load_p_corpus(man)
recs = recs[:N]
res = {'manifest': man, 'n_contexts': len(recs), 'models': {}}


def synth_gen(mk, call_emit):
    fmt = qp.MODELS[mk]['fmt']
    if fmt == 'harmony':
        return '<|channel|>analysis<|message|>ok<|end|><|start|>assistant' + call_emit
    if fmt == 'mistral':
        return call_emit
    if not qp.thinking(mk):
        return call_emit
    return 'ok\n</think>\n\n' + call_emit


for mk in MKS:
    fmt = qp.MODELS[mk]['fmt']; variant = qp.MODELS[mk].get('xml_variant')
    R = collections.Counter(); ex = {}; ntok = collections.defaultdict(list)
    for rec in recs:
        meta, (msgs, tools) = A2.context_from_record(rec, H)
        if meta['k_usable'] < 1:
            R['skip_not_eligible'] += 1; continue
        prof = qp.profile_from_tools(tools)
        p = meta['prior'][-1]
        orig = json.loads(msgs[p['ai']]['tool_calls'][0]['function']['arguments'])
        for arm in A2.ARMS:
            try:
                vm, info = A2.make_variant(msgs, meta['prior'], arm, tools, fmt, H, mk)
                text, ids = qp.render_any(vm, tools, mk)
            except Exception as e:  # noqa: BLE001
                R[f'{arm}:render_error'] += 1; ex.setdefault(f'{arm}:render_error', repr(e)[:300]); continue
            R[f'{arm}:rendered'] += 1
            ntok[arm].append(len(ids) if ids is not None else qp.n_tokens(text, mk))
            if arm == 'P0':
                ct = qp.call_text(fmt, 'edit_file', orig, list(orig), variant=variant, form='history')
                R['P0:history_call_identity'] += int(ct in text)
                if ct not in text:
                    ex.setdefault('P0_identity_miss', ct[:300])
                j = qp.judge(synth_gen(mk, qp.call_text(fmt, 'edit_file', orig, list(orig), variant=variant, form='emit')), fmt, tools, mk)
                R['judge_original_ok'] += int((not j['malformed']) and j['is_edit'])
                if j['malformed'] or not j['is_edit']:
                    ex.setdefault('judge_original', j)
                for mm in msgs:  # false-positive scan
                    for tc in mm.get('tool_calls') or []:
                        a = json.loads(tc['function']['arguments'])
                        jj = qp.judge(synth_gen(mk, qp.call_text(fmt, tc['function']['name'], a, list(a), variant=variant, form='emit')), fmt, tools, mk)
                        R['hist_calls'] += 1; R['hist_flagged'] += int(jj['malformed'])
                        if jj['malformed']:
                            ex.setdefault('fp_' + ','.join(jj['flags']), json.dumps(a)[:200])
            if arm in ('P1L', 'P6', 'P8a'):
                a2 = json.loads(vm[p['ai']]['tool_calls'][0]['function']['arguments'])
                ct2 = qp.call_text(fmt, 'edit_file', a2, list(a2), variant=variant, form='history')
                # mistral_common re-serialises argument JSON; compare on the parsed rendering when not verbatim
                R[f'{arm}:history_call_identity'] += int(ct2 in text)
                if arm == 'P8a':
                    R['P8a:recovered_equals_original'] += int(a2 == orig)
                else:
                    j = qp.judge(synth_gen(mk, qp.call_text(fmt, 'edit_file', a2, list(a2), variant=variant, form='emit')), fmt, tools, mk)
                    R[f'{arm}:laundered_copy_judged_malformed'] += int(j['malformed'])
            if arm == 'P1N':
                R['P1N:outcome:' + str(info.get('p1n_outcome'))] += 1
                j = qp.judge(synth_gen(mk, info['p1n_raw']), fmt, tools, mk)
                R['P1N:native_slip_judged_malformed'] += int(j['malformed'])
    res['models'][mk] = {'fmt': fmt, 'checks': dict(sorted(R.items())), 'examples': ex,
                         'prompt_tokens': {a: {'mean': round(sum(v) / len(v)), 'max': max(v)} for a, v in ntok.items() if v}}
    print(mk, json.dumps(res['models'][mk]['checks']), json.dumps(res['models'][mk]['prompt_tokens']), flush=True)
json.dump(res, open(OUT, 'w'), indent=1, default=str)
