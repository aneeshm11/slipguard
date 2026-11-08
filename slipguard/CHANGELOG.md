# Changelog

## 0.1.2 (2026-11-07)
Fixes from a clean-install review (R4 practitioner, consistency and area-chair reviews). No frozen file changed:
`_frozen/` and everything in `_frozen/MANIFEST.json` are byte-identical, and `slipguard verify` passes.
* **`slipguard proxy` without vLLM no longer crashes with a bare `ModuleNotFoundError`** (step 4.3). The default
  `--engine frozen` (the evaluated engine) imports vLLM 0.19.1's parsers on the proxy host. A missing package is now
  detected before anything is imported or started: exit status 2 and a message naming the fix,
  `pip install "slipguard[proxy-frozen]"`, or `pip install "slipguard[proxy]"` with `--engine lite`. The same check
  covers `--engine lite` (aiohttp, transformers, jinja2), `slipguard verify --model-dir`, the Python API
  (`make_proxy`, `RepairClient`: `slipguard.repair.EngineDependencyError`, an `ImportError`) and a vLLM other than
  0.19.1 that lacks the gemma4 parser modules.
* **The vLLM plugin needs slipguard inside vLLM's own environment** (step 4.7). `slipguard plugin-path` prints that
  reminder on stderr (stdout is still the path only; `-q` silences it). If vLLM loads the plugin where slipguard is not
  importable, the error now names vLLM's interpreter and the `pip install` to run there, instead of
  `No module named 'slipguard'`. Only the plugin's import block changed; its parsing code is unchanged.
* `slipguard --version` (step 4.1). `slipguard proxy --help` shows the defaults (port 8420, engine `frozen`), the cfg
  routes (`pass, base, order, quar, ipd, fullp, full_order`) and which extra gives which engine (step 4.2).
* `slipguard parse --per-call` exits 1 when the output has a protocol error, like `parse` (step 5.3). `parse` and
  `audit` document their exit status and `audit --help` the accepted input format (step 5.5).
* `slipguard audit-weights --out` prints a one-line verdict on stderr (step 4.11); the report is unchanged.
* Packaging: the `[vllm]` extra is bounded to the tested range, `vllm>=0.19.1,<0.34` (step 1.7).
* README:
  * a TL;DR, with `slipguard audit` as the no-GPU entry point;
  * first-screen and "What was evaluated" numbers now match `RESULTS.md`: the registered end-to-end results
    (2.47 -> 0.27 and 1.76 -> 0.37 malformed calls per episode, stuck 49 -> 3 of 904, solved tasks non-inferior) and
    the 218 PNC turns of known intent replace the development-set numbers (P1 0/229,412; 16.6% -> 0.2%; "100% of 1,610
    real slips") that `RESULTS.md` does not contain; other numbers name their `results/` file;
  * Install: not on PyPI; which extra gives which proxy engine; slipguard must be installed in vLLM's environment
    for the plugin; `--dry-run` also downloads several GB; Gemma weights are gated (`HF_TOKEN`); what `--model-dir`
    holds; the evaluated and the audit-picked checkpoints;
  * `verify --data`: the QuoteStorm payloads are in the release dataset (`release/package/v1.0/quotestorm/`)
    (step 4.12);
  * "All 16 bug classes pass on every path" is now "on every non-streaming path"; plugin streaming in vLLM 0.19.1
    and 0.31-0.33 fails C8;
  * weight audit: 15 checkpoints (12 in F's sweep + 3 in PREREG_v2.10; H-QAT supported), censoring 55% / 47%, the
    matched-dtype replication (12.0%) and the end-to-end audit-pick result (1.91 -> 0.41); the 0/300 is quarantine
    with the recovered call (P8a, as in `fullp`), while the ADK/LiteLLM hooks apply the sanitized form (P8b);
  * thinking-off numbers from the registered test (98.7% -> 0.3%, PREREG_v2.5 F3).
* docs/EVIDENCE.md and docs/API.md: version 0.1.2; 19 frozen files (16 byte-identical); the same corrections.

## 0.1.1 (2026-11-06)
Fixes from a blind practitioner review.
* **`[adk]` / `[litellm]` extras pinned to the tested ranges**: google-adk >= 1.36, < 2; LiteLLM 1.104.x; plus
  `mcp` >= 1.24, < 2. An unpinned install resolved google-adk 2.13 + LiteLLM 1.108.1. There, every model call with
  tools failed with `No module named 'mcp'`: LiteLLM imports `mcp` without declaring it, and ADK 2.x no longer brings
  it. LiteLLM 1.108.1 also fails with ADK 1.x's mcp 1.30, because it needs `mcp.types.CacheableResult` (mcp 2); this
  was found in a fresh venv with an intermediate `< 1.109` pin. Verified in fresh venvs: `pip install "slipguard[adk]"` and `pip install "slipguard[litellm]"`, then the
  README snippet, ADK Runner and LiteLLM hook tests.
* **`slipguard audit` no longer skips the malformed-call check silently** when a conversation has no tool
  declarations. It prints a stderr warning, and the `--json` line carries
  `"malformed_call": "not checked (no tool declarations)"` (else `"checked"`). New `--require-tools` exits 2 in that
  case. `--tools` also accepts an object with a `tools` list, e.g. a PNC context `manifest.json`. New test.
* README:
  * `proxy-frozen` installs vLLM 0.19.1's CUDA build (torch and nvidia wheels, several GB), not a CPU wheel;
  * exact tested versions instead of ranges (plugin: vLLM 0.19.1, 0.24.0, 0.31.0, 0.32.0, 0.33.0);
  * the built-in parsers show defects in 10 to 13 of 16 classes (vLLM 11-12, SGLang 13, llama.cpp 10), not "10 to 12";
  * `HistoryGuard.apply` returns `(messages, report)`;
  * the `bench parse` flags behind the quoted sizes.

## 0.1.0 (unreleased, 2026-11)
First release, alongside the TranscriptLab benchmark.
* `slipguard.parse`: resumable linear-time engine (one-shot, streaming, per-call runtime mode), equal to the GemmaProtocol
  executable specification on every tested input and chunking; schema validation modes.
* vLLM plugin (tested with 0.19.1, 0.24.0, 0.31.0, 0.32.0, 0.33.0): tool parsers `gemma4_strict`, `gemma4_strict_schema`; reasoning parser `gemma4_strict`.
* `slipguard.repair`: workstream E's frozen IPD proxy (final freeze 2026-11-05) shipped unchanged; `lite` engine and
  `guard` cfg (derived); `verify()` and an in-process client.
* `slipguard.history`: HistoryGuard (quarantine, raw-call removal, reversible control-token neutralization, native
  tool results opt-in, thinking-off closure for self-rendered prompts); ADK and LiteLLM integrations.
* `slipguard.template`: patched July template (P-a thinking-off closure, P-b neutralization) + renderer.
* `slipguard verify` (frozen identity, conformance, P1), `slipguard audit` (transcript scanner), `slipguard bench`.
* Opt-in text repair: closer slips (consensus of two cut rules; a missing closer -- empty or whitespace-only run --
  stays loud) and kwarg drift on non-string arguments; the rule used is recorded (`repair_rule:<kwarg|closer>`).
* Experimental SGLang shim (plugin entry point).
* `slipguard audit-weights` / `slipguard.weights`: workstream F's frozen weight audit (wsa-1.0) shipped byte-identical
  with its two PNC points packs; extra `slipguard[weights]`. Weight repair is not shipped (no candidate passed its gate).
