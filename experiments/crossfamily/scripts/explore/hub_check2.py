import os, json
os.environ.pop('HF_HUB_OFFLINE', None)
from huggingface_hub import HfApi
api = HfApi()
try:
    who = api.whoami(); print('whoami ok, user:', who.get('name'))
except Exception as e:
    print('whoami failed:', type(e).__name__)
for q in ['Devstral']:
    ms = list(api.list_models(author='mistralai', search=q, sort='lastModified', limit=20))
    print('search', q, [(m.id, str(getattr(m, 'last_modified', '') or '')[:10]) for m in ms])
for r in ['meta-llama/Llama-3.1-8B-Instruct']:
    try:
        p = api.hf_hub_download(r, 'config.json', cache_dir=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/crossfamily/data/hubprobe'))
        print('gated access OK for', r)
    except Exception as e:
        print('gated access FAILED for', r, type(e).__name__, str(e)[:160])
