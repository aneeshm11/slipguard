"""prereg_ext preparation (benchmark extension; derived from v2_prepare.py; no outcome is read): from A's confirmatory
pools build the id lists (first 300 of S1_A1 in rank order, halves H1/H2; first 300 of S1_B1 for the census tier) and
pre-render, for each extension model, the battery prompts (A1 x P0, P1L, P1N, P5, P6, P8a) and the census prompts
(B1 x C0) with prep_prompts_ext.py (text prompts for HF-template formats, token ids for harmony / mistral).
usage: ext_prepare.py <pools_dir> <out_dir> [models=gpt-oss-20b,qwen3-coder-30b,devstral-24b,qwen3.8-27b] [workers=8]
  pools_dir: experiments/contagion/data/confirmatory/pools (POOLS_MANIFEST.json, S1_A1.jsonl, S1_B1.jsonl)
  writes <out_dir>/ids_A1.txt, ids_A1_H1.txt, ids_A1_H2.txt, ids_B1.txt, prompts_<mk>.jsonl, v2_prepare_manifest.json
"""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTAGION = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
PY = os.path.join(os.environ.get('TRANSCRIPTLAB_ENVS', 'envs/'), 'env_gemma/bin/python')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main():
    pools, od = sys.argv[1], sys.argv[2]
    models = (sys.argv[3] if len(sys.argv) > 3 else 'gpt-oss-20b,qwen3-coder-30b,devstral-24b,qwen3.8-27b').split(',')
    workers = sys.argv[4] if len(sys.argv) > 4 else '8'
    os.makedirs(od, exist_ok=True)
    pm = json.load(open(os.path.join(pools, 'POOLS_MANIFEST.json')))
    cm = pm['S1']['corpus_manifest']
    if not os.path.isabs(cm):
        cm = os.path.join(CONTAGION, cm)
    a1 = [json.loads(line) for line in open(os.path.join(pools, 'S1_A1.jsonl'))]
    b1 = [json.loads(line) for line in open(os.path.join(pools, 'S1_B1.jsonl'))] if os.path.exists(os.path.join(pools, 'S1_B1.jsonl')) else []
    assert [r['rank'] for r in a1] == list(range(1, len(a1) + 1)), 'A1 not in rank order'
    a1 = a1[:300]; b1 = b1[:300]
    ids = {'A1': [r['context_id'] for r in a1], 'A1_H1': [r['context_id'] for r in a1 if r['rank'] <= 150],
           'A1_H2': [r['context_id'] for r in a1 if 150 < r['rank'] <= 300], 'B1': [r['context_id'] for r in b1]}
    for k, v in ids.items():
        open(os.path.join(od, f'ids_{k}.txt'), 'w').write('\n'.join(v) + ('\n' if v else ''))
    info = {'pools_dir': pools, 'pools_manifest_sha256': sha(os.path.join(pools, 'POOLS_MANIFEST.json')),
            'S1_A1_sha256': sha(os.path.join(pools, 'S1_A1.jsonl')), 'corpus_manifest': cm, 'corpus_manifest_sha256': sha(cm),
            'n': {k: len(v) for k, v in ids.items()}, 'models': {}}
    for mk in models:
        parts = []
        for tag, idf, arms in (('extA1', 'ids_A1.txt', 'P0,P1L,P1N,P5,P6,P8a'), ('extB1', 'ids_B1.txt', 'C0')):
            if not ids['A1' if tag == 'extA1' else 'B1']:
                continue
            outp = os.path.join(od, f'prompts_{mk}_{tag}.jsonl')
            subprocess.run([PY, os.path.join(HERE, 'prep_prompts_ext.py'), '--manifest', cm, '--mk', mk, '--out', outp,
                            '--ids', os.path.join(od, idf), '--arms', arms, '--set', tag, '--workers', workers], check=True)
            parts.append([json.loads(line) for line in open(outp)])
        # interleave: A1 context i (6 arms), B1 context i, B1 context 300 + i
        bat = parts[0] if parts else []; cen = parts[1] if len(parts) > 1 else []
        by_idx = {}
        for r in bat:
            by_idx.setdefault(r['idx'], []).append(r)
        merged = []
        for i in range(max(len(ids['A1']), (len(cen) + 1) // 2 if cen else 0)):
            merged += by_idx.get(i, [])
            for j in (i, len(ids['A1']) + i):
                if j < len(cen):
                    merged.append(cen[j])
        if len(cen) > 2 * len(ids['A1']):
            merged += cen[2 * len(ids['A1']):]
        with open(os.path.join(od, f'prompts_{mk}.jsonl'), 'w') as f:
            for r in merged:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        info['models'][mk] = {'jobs': len(merged), 'render_errors': sum(1 for r in merged if r.get('error')),
                              'prompts_sha256': sha(os.path.join(od, f'prompts_{mk}.jsonl'))}
    json.dump(info, open(os.path.join(od, 'ext_prepare_manifest.json'), 'w'), indent=1)
    print(json.dumps(info, indent=1))


if __name__ == '__main__':
    main()
