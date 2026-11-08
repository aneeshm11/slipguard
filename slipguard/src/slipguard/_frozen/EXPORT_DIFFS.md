# Export diffs: frozen source -> shipped copy

Only path literals (to env lookups) and privacy redactions are ever changed; the diff is shown against the redacted source.

## _frozen/endtoend/proxy/e2e_proxy.py
source `experiments/endtoend/proxy/e2e_proxy.py` (owner E); 1 path literal(s) -> env/config lookups (R path rule)

```diff
--- a/experiments/endtoend/proxy/e2e_proxy.py
+++ b/experiments/endtoend/proxy/e2e_proxy.py
@@ -726 +726 @@
-    ap.add_argument('--model-dir', default='models/gemma-4-31b-it-qat-w4a16-ct')
+    ap.add_argument('--model-dir', default=os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct'))
```

## _frozen/endtoend/proxy/VENDOR_B.txt
source `experiments/endtoend/proxy/VENDOR_B.txt` (owner E); privacy redaction: host_path_repo 1

```diff
```

## _frozen/endtoend/configs/channel_prior.json
source `experiments/endtoend/configs/channel_prior.json` (owner E); privacy redaction: host_path_repo 1

```diff
```

