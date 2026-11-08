"""CPU smoke test for workstream X (no GPU, no server).

For each Qwen model and N gate contexts x every battery arm:
  1. render the arm's history with the model's own template via vLLM 0.19.1's chat path; prompt token counts;
  2. serializer byte-identity: the replaced call (and, for P0, the last prior edit) as rendered by the template equals
     qwenproto.call_text(...) of the same arguments;
  3. arm integrity: P1L shows the laundered dict (new_string ends in '`,old_string:'), P1N follows the format's
     production parser outcome, P8a shows the recovered (= original) arguments + MalformedToolCall error, P5 shows the
     note, P6 the success response; common prefix with P0 up to the replaced turn;
  4. judge sanity on synthetic generations: the original call -> ok; the laundered call -> malformed; the native slip ->
     production outcome; a P0-history false-positive scan over every rendered historical call (re-parsed with the
     production parser and judged).
usage: smoke.py N out.json
"""
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qwenproto as qp  # noqa: E402
import arms as AR  # noqa: E402

N = int(sys.argv[1]); OUT = sys.argv[2]
META = AR.load_meta()
ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()][:N]
res = {'n_contexts': len(ids), 'models': {}, 'frozen_sha': AR.SHA}
t0 = time.time()


def gen_from(call_txt, fmt):
    """a synthetic generated turn: thought + call (+ end token)"""
    return ('<think>\n' if fmt == 'hermes' else '') + 'ok.\n</think>\n\n' + call_txt


for mk in ('qwen3-8b', 'qwen3-32b', 'qwen3.5-9b'):
    fmt = qp.MODELS[mk]['fmt']
    R = collections.Counter(); ex = {}; ntok = collections.defaultdict(list); fp_scan = collections.Counter()
    for cid in ids:
        meta = META[cid]; ctx = AR.load_context(meta)
        msgs, tools = ctx
        p = meta['prior'][-1]
        orig_args = json.loads(msgs[p['ai']]['tool_calls'][0]['function']['arguments'])
        order = list(orig_args)
        prompts = {}
        for arm in AR.ARMS_BATTERY:
            try:
                pr, info = AR.build_prompt(meta, ctx, arm, mk)
            except Exception as e:  # noqa: BLE001
                R[f'{arm}:render_error'] += 1; ex.setdefault(f'{arm}:render_error', repr(e)[:300]); continue
            prompts[arm] = (pr, info)
            ntok[arm].append(qp.n_tokens(pr, mk))
            if arm == 'P1N':
                R[f'P1N:outcome:{info.get("p1n_outcome")}'] += 1
                if info.get('diff_patch'):
                    R[f'P1N:diff_patch:{info["diff_patch"]}'] += 1
        if 'P0' not in prompts:
            continue
        p0 = prompts['P0'][0]
        # serializer identity on the original call (present in P0's history)
        ct = qp.call_text(fmt, 'edit_file', orig_args, order)
        R['serializer_identity_P0'] += int(ct in p0)
        if ct not in p0:
            ex.setdefault('serializer_miss', ct[:400])
        for arm, (pr, info) in prompts.items():
            if arm == 'P0':
                continue
            # common prefix with P0 (in characters) vs the position of the replaced call in P0
            cp = 0
            for a_, b_ in zip(p0, pr):
                if a_ != b_:
                    break
                cp += 1
            pos = p0.find(ct)
            R[f'{arm}:prefix_reaches_replaced_turn'] += int(pos >= 0 and cp >= p0.rfind('<|im_start|>assistant', 0, pos))
            if arm in ('P1L', 'P6', 'P8a'):
                vm, _, _ = AR.build_messages(meta, ctx, arm, fmt, mk)
                a2 = json.loads(vm[p['ai']]['tool_calls'][0]['function']['arguments'])
                ct2 = qp.call_text(fmt, 'edit_file', a2, list(a2))
                R[f'{arm}:serializer_identity'] += int(ct2 in pr)
                if arm in ('P1L', 'P6'):
                    R[f'{arm}:laundered_value_shown'] += int(isinstance(a2.get('new_string'), str) and a2.get('new_string', '').endswith('`,old_string:')
                                                             or isinstance(a2.get('old_string'), str) and a2.get('old_string', '').endswith('`,new_string:'))
                    # history fixed point: the rendered corrupted call re-parses (production parser) to the same dict
                    rp = qp.parse_nonstream(ct2, qp.PROD_PARSER[fmt], tools, mk)
                    R[f'{arm}:history_reparse_same'] += int(bool(rp['calls']) and rp['calls'][0]['args'] == a2)
                    j = qp.judge(gen_from(ct2, fmt), fmt, tools, mk)
                    R[f'{arm}:judge_copy_malformed'] += int(j['malformed'])
                if arm == 'P8a':
                    R['P8a:recovered_equals_original'] += int(a2 == orig_args)
                    R['P8a:malformed_error_shown'] += int('MalformedToolCall' in pr)
            if arm == 'P5':
                R['P5:note_shown'] += int(AR.AV.P5_NOTE in pr)
            if arm == 'P1N':
                raw = info['p1n_raw']
                j = qp.judge(gen_from(raw, fmt), fmt, tools, mk)
                R[f'P1N:judge_native_slip_malformed'] += int(j['malformed'])
                R[f'P1N:raw_or_call_in_prompt'] += int(raw in pr or info.get('p1n_outcome') != 'loud')
        # judge sanity: original call -> ok
        j0 = qp.judge(gen_from(ct, fmt), fmt, tools, mk)
        R['judge_original_ok'] += int(not j0['malformed'])
        if j0['malformed']:
            ex.setdefault('judge_original_flags', j0['flags'])
        # false-positive scan over all historical calls of P0 (re-rendered, re-parsed, judged)
        for m in msgs:
            for tc in m.get('tool_calls') or []:
                a = json.loads(tc['function']['arguments'])
                t = qp.call_text(fmt, tc['function']['name'], a, list(a))
                j = qp.judge(gen_from(t, fmt), fmt, tools, mk)
                fp_scan['calls'] += 1; fp_scan['flagged'] += int(j['malformed'])
                fp_scan['args_roundtrip'] += int(j.get('name') == tc['function']['name'])
                if j['malformed']:
                    fp_scan['flag:' + ','.join(j['flags'])] += 1
                    ex.setdefault('fp_example_' + ','.join(j['flags']), t[:600])
                st = qp.strict_parse(t, fmt, tools)
                fp_scan['strict_ok'] += int(st['ok'])
                if not st['ok']:
                    fp_scan['strict:' + str(st.get('code'))] += 1
    res['models'][mk] = {'checks': dict(sorted(R.items())), 'examples': ex, 'history_call_scan': dict(fp_scan),
                         'prompt_tokens': {a: {'mean': round(sum(v) / len(v)), 'max': max(v)} for a, v in ntok.items() if v}}
    print(mk, json.dumps(res['models'][mk]['checks']), json.dumps(dict(fp_scan)), f'{time.time() - t0:.0f}s', flush=True)
json.dump(res, open(OUT, 'w'), indent=1)
