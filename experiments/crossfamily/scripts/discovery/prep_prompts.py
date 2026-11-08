"""Build the job plan and pre-render every prompt for one Qwen model (CPU).

Battery: workstream A's 300 gate contexts (contagion/data/ids_gate300.txt, A's random order) x arms
         P0, P1L, P1N, P5, P6, P8a (k = 1).
Census:  the first N Gemma-only first-edit contexts of workstream B's set (intent_decoding/data/
         replay_gemma_first_edit.jsonl, file order; restricted to ids present in A's context index so every context has
         its logged sampling parameters and attempt id), arm C0 = original history. N = 600 (300 for Qwen3-32B).
Order:   interleaved by index (battery context i, census context i, census context 300+i), so a partial run is a
         balanced random subset of both.
Output:  data/prompts_<mk>.jsonl  {id, arm, set, idx, task, temp, top_p, seed, n_prompt, prompt, info}
Held-out tier (secondary, run only after the primary tier): contexts 300-599 of A's random phase-1 order
         (contagion/data/ids_phase1_random600.txt) x arms P0, P1L, P5, P6 -> data/prompts_<mk>_heldout.jsonl.
usage: prep_prompts.py <model_key> <n_census> [n_battery=300] [workers=8] [--heldout]
"""
import hashlib
import json
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
X = os.path.dirname(HERE)
GATE = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_gate300.txt')
BSET = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/intent_decoding/data/replay_gemma_first_edit.jsonl')
PHASE1 = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/data/ids_phase1_random600.txt')
ARMS_HELDOUT = ['P0', 'P1L', 'P5', 'P6']


def seed_of(cid):  # identical to workstream A's per-context seed (common random numbers across arms)
    return int(hashlib.md5(cid.encode()).hexdigest()[:8], 16) % (2 ** 31 - 8)


_W = {}


def _init(mk):
    import arms as AR
    _W['AR'] = AR; _W['mk'] = mk; _W['META'] = AR.load_meta()


def _render(job):
    AR = _W['AR']; mk = _W['mk']; meta = _W['META'][job['id']]
    import qwenproto as qp
    try:
        ctx = AR.load_context(meta)
        prompt, info = AR.build_prompt(meta, ctx, job['arm'], mk)
        n = qp.n_tokens(prompt, mk)
        info = {k: v for k, v in info.items() if k in ('p1n_outcome', 'slip_key', 'diff_patch', 'missing', 'quarantine_actions', 'p1n_raw', 'p1n_args')}
        return {**job, 'task': meta['task'], 'temp': meta['temp'] if meta['temp'] is not None else 0.2,
                'top_p': meta['top_p'] if meta['top_p'] is not None else 0.95, 'seed': seed_of(job['id']),
                'n_prompt': n, 'prompt': prompt, 'info': info, 'tools': ctx[1]}
    except Exception as e:  # noqa: BLE001
        return {**job, 'error': 'render:' + repr(e)[:300]}


def main():
    heldout = '--heldout' in sys.argv
    argv = [x for x in sys.argv if x != '--heldout']
    mk = argv[1]; n_census = int(argv[2])
    n_bat = int(argv[3]) if len(argv) > 3 else 300
    workers = int(argv[4]) if len(argv) > 4 else 8
    import arms as AR
    META = AR.load_meta()
    if heldout:
        ph = [x.strip() for x in open(PHASE1) if x.strip()]
        gate0 = set(x.strip() for x in open(GATE) if x.strip())
        ho = ph[300:600]
        assert not set(ho) & gate0 and len(ho) == 300
        jobs = [{'id': cid, 'arm': arm, 'set': 'heldout', 'idx': 300 + i} for i, cid in enumerate(ho) for arm in ARMS_HELDOUT]
        out = os.path.join(X, 'data', f'prompts_{mk}_heldout.jsonl'); n_err = 0
        with Pool(workers, initializer=_init, initargs=(mk,)) as pool, open(out, 'w') as fo:
            for r in pool.imap(_render, jobs, chunksize=4):
                n_err += int('error' in r)
                fo.write(json.dumps(r, ensure_ascii=False) + '\n')
        print(mk, 'heldout jobs', len(jobs), 'render errors', n_err, flush=True)
        return
    gate = [x.strip() for x in open(GATE) if x.strip()][:n_bat]
    census = []
    for line in open(BSET):
        cid = json.loads(line)['id']
        if cid in META and META[cid]['n_prior_edits'] == 0:
            census.append(cid)
        if len(census) >= n_census:
            break
    assert not set(gate) & set(census)
    assert len(census) <= 2 * len(gate)
    jobs = []
    for i in range(len(gate)):
        jobs += [{'id': gate[i], 'arm': a, 'set': 'battery', 'idx': i} for a in AR.ARMS_BATTERY]
        for j in (i, len(gate) + i):
            if j < len(census):
                jobs.append({'id': census[j], 'arm': 'C0', 'set': 'census', 'idx': j})
    assert len({(j['id'], j['arm']) for j in jobs}) == len(jobs)
    out = os.path.join(X, 'data', f'prompts_{mk}.jsonl')
    n_err = 0
    with Pool(workers, initializer=_init, initargs=(mk,)) as pool, open(out, 'w') as fo:
        for r in pool.imap(_render, jobs, chunksize=4):
            n_err += int('error' in r)
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')
    json.dump({'model': mk, 'n_jobs': len(jobs), 'n_battery_contexts': len(gate), 'n_census_contexts': len(census),
               'render_errors': n_err, 'census_source_md5': hashlib.md5(open(BSET, 'rb').read()).hexdigest(),
               'gate_source_md5': hashlib.md5(open(GATE, 'rb').read()).hexdigest(), 'frozen_sha': AR.SHA},
              open(os.path.join(X, 'data', f'prompts_{mk}.manifest.json'), 'w'), indent=1)
    with open(os.path.join(X, 'data', f'ids_census_{mk}.txt'), 'w') as f:
        f.write('\n'.join(census) + '\n')
    print(mk, 'jobs', len(jobs), 'battery ctx', len(gate), 'census ctx', len(census), 'render errors', n_err, flush=True)


if __name__ == '__main__':
    main()
