import os, json
os.environ.pop('HF_HUB_OFFLINE', None)
from huggingface_hub import HfApi, hf_hub_download
api = HfApi(); cd = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/data/hubprobe')
for r in ['mistralai/Devstral-Small-2-24B-Instruct-2512', 'openai/gpt-oss-20b', 'Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8']:
    mi = api.model_info(r, files_metadata=True)
    files = {s.rfilename: round((s.size or 0) / 1e9, 2) for s in mi.siblings}
    print('==', r, 'license', (mi.card_data or {}).get('license') if mi.card_data else None, 'gated', mi.gated, 'total GB', round(sum(files.values()), 1))
    print('   files:', {k: v for k, v in files.items() if v > 0.01 or not k.endswith('.safetensors')})
    for fn in ('config.json', 'params.json'):
        if fn in files:
            p = hf_hub_download(r, fn, cache_dir=cd); c = json.load(open(p))
            print('   ', fn, {k: c[k] for k in list(c)[:40] if k in ('architectures', 'model_type', 'text_config', 'quantization_config', 'num_hidden_layers', 'dim', 'n_layers', 'vocab_size', 'max_position_embeddings', 'torch_dtype', 'dtype', 'quantization')} if fn == 'config.json' else {k: c[k] for k in c if k in ('dim', 'n_layers', 'vocab_size', 'quantization', 'vision_encoder', 'max_seq_len', 'max_position_embeddings')})
