"""PREREG_v2 prompt builder: pre-render every (context, arm) prompt for one Qwen model from generic context records
(workstream P's public-corpus contexts; schema per experiments/contagion/CONTEXT_SCHEMA.md).

A context record needs at least {id, messages (OpenAI chat format, tool-call arguments as JSON strings), tools (OpenAI
tool declarations)}; optional: temperature, top_p, cluster (attempt / task id used for cluster bootstrap). Eligibility
(k_usable >= 1: the most recent prior edit call valid, successful, single, answered) is computed by arms_v2 with the
schema profile derived from the declared tools (S0 / S1 file_path / S2 str_replace_editor) and the harness profile.
Output records have the same shape as prep_prompts.py, so run_qwen.py and analyze.py (--contexts) take them unchanged.
usage: prep_prompts_v2.py (--contexts ctx.jsonl | --manifest <P corpus manifest.json>) --mk <model_key> --out data/v2/prompts_<mk>.jsonl
                          [--ids ids.txt] [--arms P0,P1L,P1N,P5,P6,P8a] [--harness adk] [--set v2] [--workers 8]
                          [--default_temp 0.2 --default_top_p 0.95]
"""
import argparse
import hashlib
import json
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def seed_of(cid):
    return int(hashlib.md5(cid.encode()).hexdigest()[:8], 16) % (2 ** 31 - 8)


_W = {}


def _init(ctx_path, mk, harness, manifest):
    import arms_v2 as A2
    _W.update(A2=A2, mk=mk, harness=harness, recs={})
    if manifest:
        recs, H = A2.load_p_corpus(manifest); _W['harness'] = H
    else:
        recs = [json.loads(line) for line in open(ctx_path)]
    for r in recs:
        _W['recs'][r['id']] = r


def _render(job):
    A2 = _W['A2']; mk = _W['mk']
    import qwenproto as qp
    try:
        rec = _W['recs'][job['id']]
        meta, (msgs, tools) = A2.context_from_record(rec, _W['harness'])
        if meta['k_usable'] < 1 and job['arm'] not in ('P0', 'C0'):
            return {**job, 'error': 'render:not_eligible_k_usable_0'}
        prompt, info = A2.build_prompt(msgs, tools, meta['prior'], job['arm'], mk, _W['harness'])
        info = {k: v for k, v in info.items() if k in ('p1n_outcome', 'slip_key', 'diff_patch', 'missing', 'quarantine_actions', 'p1n_args')}
        return {**job, 'task': meta['task'], 'temp': meta['temp'] if meta['temp'] is not None else job['dt'],
                'top_p': meta['top_p'] if meta['top_p'] is not None else job['dp'], 'seed': seed_of(job['id']),
                'n_prompt': qp.n_tokens(prompt, mk), 'prompt': prompt, 'info': info, 'tools': tools, 'schema': meta['schema']}
    except Exception as e:  # noqa: BLE001
        return {**job, 'error': 'render:' + repr(e)[:300]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--contexts', default=''); ap.add_argument('--manifest', default='')
    ap.add_argument('--mk', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--ids', default=''); ap.add_argument('--arms', default='P0,P1L,P1N,P5,P6,P8a')
    ap.add_argument('--harness', default='adk'); ap.add_argument('--set', default='v2'); ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--default_temp', type=float, default=0.2); ap.add_argument('--default_top_p', type=float, default=0.95)
    a = ap.parse_args()
    assert bool(a.contexts) != bool(a.manifest), 'give exactly one of --contexts / --manifest'
    if a.ids:
        ids = [x.strip() for x in open(a.ids) if x.strip()]
    elif a.manifest:
        import arms_v2 as A2
        ids = [r['id'] for r in A2.load_p_corpus(a.manifest)[0]]
    else:
        ids = [json.loads(line)['id'] for line in open(a.contexts)]
    arms = a.arms.split(',')
    jobs = [{'id': cid, 'arm': arm, 'set': a.set, 'idx': i, 'dt': a.default_temp, 'dp': a.default_top_p}
            for i, cid in enumerate(ids) for arm in arms]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    n_err = 0
    with Pool(a.workers, initializer=_init, initargs=(a.contexts, a.mk, a.harness, a.manifest)) as pool, open(a.out, 'w') as fo:
        for r in pool.imap(_render, jobs, chunksize=4):
            r.pop('dt', None); r.pop('dp', None)
            n_err += int('error' in r)
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')
    json.dump({'model': a.mk, 'n_jobs': len(jobs), 'n_contexts': len(ids), 'arms': arms, 'render_errors': n_err,
               'source': a.manifest or a.contexts, 'source_md5': hashlib.md5(open(a.manifest or a.contexts, 'rb').read()).hexdigest(),
               'harness': 'manifest' if a.manifest else a.harness},
              open(a.out.replace('.jsonl', '.manifest.json'), 'w'), indent=1)
    print(a.mk, 'jobs', len(jobs), 'contexts', len(ids), 'render errors', n_err, flush=True)


if __name__ == '__main__':
    main()
