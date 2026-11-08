"""(1) S0 equivalence: arms_v2.make_variant == the discovery construction (A's frozen make_variant / E's quarantine /
X's native_variant) on the 300 gate contexts, for every arm.
(2) S1 smoke: the same contexts re-keyed to workstream P's schema edit_file(file_path, old_string, new_string)
(declaration + every historical edit call; allow_multiple dropped from the declaration and calls) -> profile S1,
prior analysis, every arm builds and renders for the three Qwen models, serializer identity, the judge flags the
laundered call and not the original, P1N stack outcome, P8a recovers the original call, judge false positives on all
re-rendered historical calls.
usage: check_arms_v2.py N out.json"""
import collections
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import qwenproto as qp  # noqa: E402
import arms as AR  # noqa: E402
import arms_v2 as A2  # noqa: E402

N = int(sys.argv[1]); OUT = sys.argv[2]
META = AR.load_meta()
ids = [x.strip() for x in open(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')) if x.strip()][:N]
res = {'S0_equivalence': collections.Counter(), 'S1': {}}
ex = {}


def rekey(msgs, tools):
    tools = copy.deepcopy(tools); msgs = copy.deepcopy(msgs)
    for t in tools:
        f = t['function']
        if f['name'] == 'edit_file':
            pr = f['parameters']['properties']
            f['parameters']['properties'] = {('file_path' if k == 'filepath' else k): v for k, v in pr.items() if k != 'allow_multiple'}
            f['parameters']['required'] = [('file_path' if k == 'filepath' else k) for k in f['parameters']['required']]
    for m in msgs:
        for tc in m.get('tool_calls') or []:
            if tc['function']['name'] == 'edit_file':
                a = json.loads(tc['function']['arguments'])
                tc['function']['arguments'] = json.dumps({('file_path' if k == 'filepath' else k): v for k, v in a.items() if k != 'allow_multiple'}, ensure_ascii=False)
    return msgs, tools


for cid in ids:
    meta = META[cid]; msgs, tools = AR.load_context(meta)
    # (1) S0 equivalence on messages, per arm (fmt matters only for P1N)
    for fmt, mk in (('hermes', 'qwen3-8b'), ('xml', 'qwen3.5-9b')):
        for arm in A2.ARMS:
            if arm != 'P1N' and fmt == 'xml':
                continue
            v1, _, i1 = AR.build_messages(meta, (msgs, tools), arm, fmt, mk)
            v2, i2 = A2.make_variant(msgs, meta['prior'], arm, tools, fmt, 'adk', mk)
            same = json.dumps(v1, sort_keys=True) == json.dumps(v2, sort_keys=True)
            res['S0_equivalence'][f'{arm}:{fmt}:{"same" if same else "DIFF"}'] += 1
            if not same:
                ex.setdefault(f'S0diff:{arm}:{fmt}', cid)
    # (2) S1 smoke
    m1, t1 = rekey(msgs, tools)
    prof = qp.profile_from_tools(t1)
    prior = A2.analyse_prior(m1, t1, A2.HARNESS['adk'])
    R = res['S1'].setdefault('common', collections.Counter())
    R['profile_' + str(prof)] += 1
    R['prior_positions_match_A'] += int([(p['ai'], p['ti']) for p in prior] == [(p['ai'], p['ti']) for p in meta['prior']])
    R['k_usable_ge_1'] += int(A2.k_usable(prior) >= 1)
    p = prior[-1]
    orig = json.loads(m1[p['ai']]['tool_calls'][0]['function']['arguments'])
    for mk in ('qwen3-8b', 'qwen3.5-9b'):
        fmt = qp.MODELS[mk]['fmt']; RR = res['S1'].setdefault(mk, collections.Counter())
        for arm in A2.ARMS:
            try:
                vm, info = A2.make_variant(m1, prior, arm, t1, fmt, 'adk', mk)
                pr = qp.render(vm, t1, mk)
            except Exception as e:  # noqa: BLE001
                RR[f'{arm}:error'] += 1; ex.setdefault(f'S1err:{arm}:{mk}', repr(e)[:300]); continue
            RR[f'{arm}:rendered'] += 1
            if arm in ('P1L', 'P6', 'P8a'):
                a2 = json.loads(vm[p['ai']]['tool_calls'][0]['function']['arguments'])
                ct2 = qp.call_text(fmt, 'edit_file', a2, list(a2))
                RR[f'{arm}:serializer_identity'] += int(ct2 in pr)
                gen = ('<think>\n' if fmt == 'hermes' else '') + 'ok\n</think>\n\n' + ct2
                j = qp.judge(gen, fmt, t1, mk)
                if arm == 'P8a':
                    RR['P8a:recovered_equals_original'] += int(a2 == orig)
                    RR['P8a:judge_ok'] += int(not j['malformed'])
                else:
                    RR[f'{arm}:judge_malformed'] += int(j['malformed'] and j['is_edit'])
                    RR[f'{arm}:missing_file_path_not_reported'] += int('file_path' not in (info.get('missing') or []))
            if arm == 'P1N':
                RR['P1N:outcome:' + str(info.get('p1n_outcome'))] += 1
            if arm == 'P0':
                ct = qp.call_text(fmt, 'edit_file', orig, list(orig))
                RR['P0:serializer_identity'] += int(ct in pr)
                gen = ('<think>\n' if fmt == 'hermes' else '') + 'ok\n</think>\n\n' + ct
                j = qp.judge(gen, fmt, t1, mk)
                RR['P0:original_judged_ok'] += int(not j['malformed'] and j['is_edit'] and j.get('fp') == orig.get('file_path'))
                for mm in m1:  # false positives on every historical call
                    for tc in mm.get('tool_calls') or []:
                        a = json.loads(tc['function']['arguments'])
                        t = qp.call_text(fmt, tc['function']['name'], a, list(a))
                        jj = qp.judge(('<think>\n' if fmt == 'hermes' else '') + 'ok\n</think>\n\n' + t, fmt, t1, mk)
                        RR['hist_calls'] += 1; RR['hist_flagged'] += int(jj['malformed'])
res['S0_equivalence'] = dict(res['S0_equivalence'])
res['S1'] = {k: dict(v) for k, v in res['S1'].items()}
res['examples'] = ex
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps(res, indent=1)[:4000])
