# slipguard API reference (0.1.2)

## `slipguard.parse`
| name | signature | notes |
|---|---|---|
| `parse_call` | `(text, *, allow_ws=True, template="2026-07-09") -> ToolCall` | exactly one call; else `ParseError` |
| `parse_completion` | `(text, *, in_thought=False, allow_ws=True, strict_content=True, template=...) -> ParsedCompletion` | whole completion, all or nothing; same results and errors as the executable specification |
| `extract` | `(text, tools=None, *, validate="syntax"\|"declared"\|"schema", repair=False, in_thought=False, parse_thought=False, ...) -> Extraction` | runtime (per-call) semantics; never raises; `Extraction(calls, content, errors, thought, repairs)` |
| `StreamParser` | `(*, mode="completion"\|"per_call", tools=None, validate=..., repair=False, in_thought=False, parse_thought=True, ...)` | `.feed(chunk)`, `.feed_text(text_so_far)`, `.finish()` -> events; `.errors`, `.repairs`, `.result()` |
| `ParseError` | `.code`, `.pos`, `.message`, `.extra`, `.to_dict()` | 17 codes in `ERROR_CODES`; schema checks raise `SchemaError` (`UNDECLARED_TOOL`, `UNDECLARED_KEY`, `MISSING_REQUIRED`, `TYPE_MISMATCH`) |
| `ToolCall` | `name, arguments, span, key_order, canonical, warnings` | `warnings == ["repaired", "repair_rule:kwarg"\|"repair_rule:closer"]` for a text-repaired call |

Events: `("thought", text)`, `("thought_end", thought)`, `("content", text)`, `("call_start", i, name)`,
`("arg", i, key, value)`, `("call_end", i, ToolCall)`, `("terminator", token)`. In `per_call` mode a call's events are
emitted together, at its end.

## `slipguard.history`
| name | notes |
|---|---|
| `HistoryGuard(quarantine=True, raw_calls=True, neutralize=True, native_tool_results=False, model=None, allow_non_gemma=False).apply(messages, tools, *, raw_by_call_id=None, strictly_valid_ids=None) -> (messages, report)` | pure; identity on clean histories |
| `quarantine`, `raw_calls_in_content`, `native_tool_results`, `neutralize`, `mark_repaired` | the individual transforms, each `(messages, ...) -> (messages, actions)` |
| `neutralize_text`, `unneutralize_text`, `has_control_text`, `SPECIAL_TOKENS` | reversible U+2060 escape of the 24 Gemma 4 special-token spellings |
| `close_thought(prompt_text_or_ids, enable_thinking)`, `needs_closed_thought(...)` | thinking-off closure for self-rendered prompts |

## `slipguard.repair`
| name | notes |
|---|---|
| `verify(text, tools) -> VerifyReport(calls, strict_valid, invalid, plan, audit)` | E's frozen `ipd_scan` |
| `strictly_valid(call_text, tools)` | B's strict guard as vendored in E's freeze |
| `RepairClient(backend, model_dir, *, served, logdir, engine="frozen", template="official").chat(messages, tools, cfg="fullp", **params)` | E's `Proxy.engine_chat` in-process (async) |
| `slipguard proxy ...` | see `slipguard proxy -h` |
| `EVALUATED` | the configuration that carries the measured guarantees |

## `slipguard.template`
`path("guarded"|"closure"|"official")`, `text(...)`, `render(messages, tools=None, *, add_generation_prompt=True, enable_thinking=False, which="guarded")`.

## `slipguard.integrations`
* `plugin_path("vllm")` -- vLLM plugin file (tool parsers `gemma4_strict`, `gemma4_strict_schema`, `gemma4_strict_repair`; reasoning parser `gemma4_strict`).
* `adk.guarded_lite_llm(model, guard=None, **kw)`, `adk.GuardedLiteLLMClient`, `adk.SlipGuardPlugin`.
* `litellm_hook.SlipGuardHook` (register in `litellm.callbacks`; async calls).
* `sglang.register()` (experimental).

## CLI
`slipguard parse|check|proxy|audit|audit-weights|verify|plugin-path|template-path|bench` and `slipguard --version`.
Exit status: `parse` and `check` 1 on a protocol error (`parse --per-call` too, since 0.1.2); `audit` 1 on a
`malformed_call`, `raw_call_in_content` or `control_text` finding, 2 with `--require-tools` when a conversation has no
declarations; `proxy` and `verify --model-dir` 2 when the engine's packages are missing (`slipguard.repair.EngineDependencyError`, an
`ImportError` whose message names `slipguard[proxy-frozen]` or `slipguard[proxy]`). `plugin-path` prints the path on
stdout and, on stderr, the reminder that slipguard must be installed in vLLM's own environment (`-q` to silence). `slipguard.audit.audit_messages(messages, tools=None, enable_thinking=None)` returns the findings of one conversation; without `tools` the malformed-call check does not run (the CLI reports it as `not checked`; `slipguard audit --tools FILE` takes a JSON list or an object with `tools`, `--require-tools` exits 2 when a conversation could not be checked). `HistoryGuard().apply(messages, tools)` returns `(messages, report)`.

## `slipguard.weights` (weight audit; extra `slipguard[weights]`)

Workstream F's frozen package wsa-1.0 (`slipguard/_frozen/wsa/`, sha-checked before import), re-exported:

| name | signature | notes |
|---|---|---|
| `audit_endpoint` | `(base_url, served_name, *, pnc_dir, tokenizer_dir, pack="audit16k", split="heldout", kinds=("close","slip"), conc=2, max_total=None, records_out=None) -> list[dict]` | per-position records from a live vLLM endpoint (token-id prompts, max_tokens 1, temperature 0, logprobs 20); `pack` = `audit16k` (235 held-out items <= 16.4k tokens), `core` (951) or a path |
| `summarize` | `(records) -> dict` | schema `slipguard.weights.audit/v1`: n_string_ends, censored_frac, margin_median_lb, margin_p10_lb, P_m_lt_ln19, E_slip, onset_per_call, n_onset_calls, slip_states_pLA, n_slip_states |
| `compare` | `(records, reference) -> dict` | paired median margin deficit [point, lo, hi], episode-cluster bootstrap (2000, seed 0) |
| `flag` | `(summary, paired=None) -> (FLAG, SEVERE)` | FLAG: P(m < ln 19) >= 0.5% or deficit vs same-family bf16 >= 3 nats; SEVERE: P >= 2% or E_slip >= 1% |
| `report` | `(records, reference=None, *, pack=None) -> dict` | summary + paired + verdict; descriptive only (no verdict) without a same-family bf16 reference |
| `load_records`, `pack_path`, `SCHEMA`, `PACKS` | | |

CLI: `slipguard audit-weights --endpoint URL --served-name NAME --pnc DIR --tokenizer DIR [--pack] [--conc] --records OUT
[--reference REF] [--out report.json]`, or `--from-records RECORDS [--reference REF]` (CPU re-scoring). Weight repair is
not part of the API (no candidate passed its registered gate).
