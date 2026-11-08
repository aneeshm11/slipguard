"""Record the serving details of one run: /v1/models, the server's non-default args, vLLM version and KV cache (from the
server log), prompt + runner sha256. usage: write_manifest.py <mk> <port> <server_log> <prompts> <runner> <out_json> [gpu]"""
import datetime
import hashlib
import json
import re
import subprocess
import sys

mk, port, logf, prompts, runner, out = sys.argv[1:7]
gpu = sys.argv[7] if len(sys.argv) > 7 else None
models = json.loads(subprocess.run(['curl', '-s', '-m', '5', f'http://127.0.0.1:{port}/v1/models'], capture_output=True, text=True).stdout)
log = open(logf).read()


def grab(p):
    m = re.findall(p, log)
    return m[-1] if m else None


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


man = {'model_key': mk, 'recorded_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
       'endpoint': f'http://127.0.0.1:{port}/v1', 'gpu': gpu, 'v1_models': models, 'server_log': logf,
       'server_non_default_args': grab(r"non-default args: (\{.*\})"), 'vllm_version': grab(r"LLM engine \((v[0-9.]+)\)"),
       'kv_cache': {'available_gib': grab(r"Available KV cache memory: ([0-9.]+) GiB"), 'tokens': grab(r"GPU KV cache size: ([0-9,]+) tokens"),
                    'max_concurrency': grab(r"Maximum concurrency for [0-9,]+ tokens per request: ([0-9.]+)x")},
       'prompts': prompts, 'prompts_sha256': sha(prompts), 'runner': runner, 'runner_sha256': sha(runner)}
json.dump(man, open(out, 'w'), indent=1)
print(json.dumps({k: man[k] for k in ('server_non_default_args', 'vllm_version', 'kv_cache', 'runner_sha256')}))
