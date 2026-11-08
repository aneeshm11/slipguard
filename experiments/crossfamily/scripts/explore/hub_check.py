import os, json
os.environ.pop('HF_HUB_OFFLINE', None); os.environ.pop('TRANSFORMERS_OFFLINE', None)
from huggingface_hub import HfApi
api = HfApi()
try:
    who = api.whoami(); print('whoami:', who.get('name'), '| orgs:', [o.get('name') for o in who.get('orgs', [])][:5])
except Exception as e:
    print('whoami failed:', type(e).__name__, str(e)[:120])
for q in ['Devstral-Small', 'Devstral']:
    try:
        ms = list(api.list_models(author='mistralai', search=q, sort='lastModified', direction=-1, limit=12))
        print('search', q, [(m.id, str(m.last_modified)[:10] if getattr(m, 'last_modified', None) else None) for m in ms])
    except Exception as e:
        print('search failed', q, repr(e)[:150])
repos = ['Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8', 'Qwen/Qwen3-Coder-30B-A3B-Instruct', 'mistralai/Devstral-Small-2507',
         'mistralai/Devstral-Small-2505', 'openai/gpt-oss-20b', 'meta-llama/Llama-3.1-8B-Instruct']
for r in repos:
    try:
        mi = api.model_info(r, files_metadata=True)
        size = sum((s.size or 0) for s in mi.siblings) / 1e9
        files = [s.rfilename for s in mi.siblings]
        tmpl = [f for f in files if 'template' in f or f in ('tokenizer_config.json', 'tekken.json', 'params.json', 'chat_template.json')]
        print(json.dumps({'repo': r, 'size_GB': round(size, 1), 'gated': getattr(mi, 'gated', None), 'license': (mi.card_data or {}).get('license') if mi.card_data else None,
                          'last_modified': str(mi.last_modified)[:10], 'n_files': len(files), 'template_files': tmpl[:8],
                          'library': getattr(mi, 'library_name', None), 'tags': [t for t in (mi.tags or []) if t.startswith(('base_model', 'license'))][:4]}))
    except Exception as e:
        print(json.dumps({'repo': r, 'error': type(e).__name__ + ': ' + str(e)[:200]}))
