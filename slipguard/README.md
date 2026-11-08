# slipguard

**Tool-call hygiene for Gemma 4 agents (unofficial).** slipguard is not affiliated with or endorsed by Google.

This is the **library**: you install it to protect a Gemma 4 agent. The **benchmark** that measures how models react to
corrupted histories is TranscriptLab (`../transcriptlab/`, a separate package), and the **dataset** of agent episodes
is PNC (https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc). slipguard needs neither of them.

**TL;DR**
* **No GPU, one minute:** `slipguard audit transcripts.jsonl --tools tools.json` flags laundered calls in your own agent
  logs (OpenAI-format message lists). Core install, standard library only, CPU.
* **Fail loud in vLLM:** the strict parser plugin, `--tool-call-parser gemma4_strict` (task 1). slipguard must be
  installed in vLLM's own Python environment.
* **Clean an ADK or LiteLLM agent's history:** four lines, `slipguard[adk]` (task 2).
* **Repair in front of vLLM, the evaluated configuration:** `slipguard proxy`, `slipguard[proxy-frozen]` (task 3).
* **Before serving a 4-bit checkpoint:** `slipguard audit-weights` (Weight audit).
* Not on PyPI yet: see Install. Registered results: `RESULTS.md` at the repository root. Numbers here that are not in
  `RESULTS.md` come from this package's own `results/` files, named where they are used.
* To score a model's sensitivity to a corrupted history, use TranscriptLab (`transcriptlab/`, a separate package).

Gemma 4 writes tool calls as `<|tool_call>call:NAME{key:<|"|>value<|"|>,...}<tool_call|>`. Strings are delimited
only by the special token `<|"|>`, and the format has no escape mechanism. In practice the model often closes a
string with a look-alike character, most often a backtick. That slip is a single token. Every runtime parser we
tested accepts it, and other ill-formed calls, without a warning and returns a corrupted call:

* On the 218 ill-formed turns of known intent in the public PNC corpus (mostly `key=value` drift), vLLM's built-in
  parsers deliver a **wrong call** in 188 (vLLM 0.19.1) to 216 (vLLM 0.33) cases. slipguard's strict parser delivers
  none: it refuses all 218 (`RESULTS.md`, conformance on public real inputs). SGLang's and llama.cpp's parsers share
  the defect classes (Conformance, below).

The agent framework then stores the corrupted call, and the chat template writes it back into the next prompt. Gemma
copies what it sees in its history, so one slip makes later slips more likely. We showed this causally with
pre-registered history interventions: on 300 public agent states, one laundered call raises malformed next edits from
1.3% to 19.7% (Gemma-4-31B 4-bit; `RESULTS.md`, TranscriptLab).

slipguard packages the fixes we validated, tailored to Gemma 4:

| module | what it gives you | needs |
|---|---|---|
| `slipguard.parse` | A strict parser: string-opaque, linear-time, streaming. It either returns exactly the calls the model emitted or reports an error. It is never silent. | nothing (stdlib) |
| vLLM plugin | `--tool-call-parser gemma4_strict` and `--reasoning-parser gemma4_strict` tested with vLLM 0.19.1, 0.24.0, 0.31.0, 0.32.0 and 0.33.0. No code change. | vLLM, with slipguard installed **in vLLM's own environment** |
| SGLang shim (experimental) | `--tool-call-parser gemma4_strict` on SGLang through its plugin entry point (`SGLANG_PLUGINS=slipguard`). All 16 classes pass through SGLang 0.5.23's own harness paths; SGLang's gemma4 *reasoning* parser (not replaced) still splits outputs on channel tokens inside strings (`results/conformance_sglang/`). | SGLang |
| `slipguard.repair` | Intent-preserving decoding (IPD), verify-then-repair, as an OpenAI-compatible proxy. This is the evaluated code, shipped frozen. | `slipguard[proxy-frozen]` (default engine, with vLLM 0.19.1) or `slipguard[proxy]` (`--engine lite`), plus a vLLM backend |
| `slipguard.history` | Transcript hygiene for OpenAI message lists: quarantine of malformed calls, control-token neutralization, removal of raw call text. ADK and LiteLLM hooks. | nothing (hooks: ADK / LiteLLM) |
| `slipguard.template` | A patched Gemma 4 chat template. It honours thinking-off after tool results and makes control-token text in tool data inert. It is byte-identical to the official template on every other input. | jinja2 (only for `render`) |
| `slipguard verify` | Re-checks the guarantees on *your* installation. | |
| `slipguard audit-weights` | Weight audit: how firmly a served checkpoint closes code strings with `<|"|>` rather than a look-alike quote (string-end margins on public PNC decision points, top-20 teacher forcing). Workstream F's frozen code (wsa-1.0). See "Weight audit" below. | `slipguard[weights]` (numpy, httpx, transformers) + a vLLM endpoint |
| `slipguard audit` | Scans existing transcripts (OpenAI message lists, JSON/JSONL) for laundered calls, raw call text, control-token text, ADK-serialized results and the thinking-off gap. The laundered-call check needs the tool declarations (`--tools tools.json`, or per conversation); without them it is reported as not checked. | nothing |

## What was evaluated, and what is derived

The registered end-to-end results come from one configuration: **the `frozen` engine with cfg `fullp`** of
`slipguard proxy`, in the challenge's agent harness (ADK, vLLM 0.19.1, Gemma-4-31B 4-bit QAT, 113 public tasks;
`RESULTS.md`, "End to end"):

* malformed tool calls reaching the agent per episode fall from **2.47 to 0.27** (ratio 0.11 [0.06, 0.22], 2
  replicates), and from **1.76 to 0.37** (0.21× [0.13, 0.35]) in 8 fresh replicates;
* in those 8 replicates, stuck episodes (5 or more consecutive malformed calls) fall from 49 to 3 of 904 per arm, and
  solved tasks are non-inferior at −3 pp: 393 (stock) vs 394 (proxy) of 904 task pairs, difference +0.1 pp [−2.2, +2.4].

The repair rule itself (IPD) was tested on 393 detectable injected slips: it recovers the exact intended call in 90.6%
(stock vLLM 0%, greedy re-decoding 69%) and is silently wrong in 6.9%; it changed none of 582 valid first-edit calls
(`RESULTS.md`, "Repair"). The proxy code is workstream E's frozen proxy, shipped unchanged (see "Byte identity" below).

Everything else is **derived**. Each derived piece is tested, but it was not part of the evaluation:

| piece | status | tests |
|---|---|---|
| `--engine lite` (no vLLM on the proxy host, strict final parse) | derived | P1 on the released QuoteStorm payloads: 0/5,524 changed (ipd and fullp; `results/p1_quotestorm_release_payloads.json`); E's suites |
| `--template guarded` / `closure`, `--token-neutralize`, cfg `guard` | derived | T-T1..T-T4 (template identity), P1; token-level: clean prompts give identical ids, hazardous spans gain no control tokens |
| vLLM plugin, `slipguard.parse` | derived; new code | conformance suite (16 bug classes, 5 vLLM versions); differential equality with the executable specification on 100,000+ inputs and all chunkings |
| `slipguard.history` (quarantine = E's frozen renderer) | the renderer is the evaluated one. The ADK and LiteLLM hooks have no raw emission, so they apply its **sanitized** form (P8b), not the recovered call (P8a) that `fullp` and TranscriptLab's P8a arm evaluate. Other transforms derived | no-op property on clean histories; ADK/LiteLLM integration tests |
| provenance ids (`-ggok`, `-ggrepaired`) | derived: they *extend* E's frozen quarantine | calls with `-ggok` ids are passed to the frozen renderer as strictly valid, so it never quarantines them; this fixes the renderer's known false positive on a valid string that literally contains `` `,old_string: `` |
| `slipguard audit-weights` | F's frozen audit code (wsa-1.0, byte-identical, sha-checked) | reproduces F's frozen 12-checkpoint sweep reports from F's records (CPU); F's CPU check: rendered prompt token ids identical to the sweep's for 235/235 + 951/951 pack items; live end-to-end run of the shipped CLI on the QAT 31B checkpoint (12 items, 20 positions): prompt token counts, logged and top-1 tokens and censoring agree with the sweep everywhere, margins within 0.28 nats (F's own repeat runs: 0.44), same flag |
| `gemma4_strict_repair` (text-only repair) | derived (B's relaxed grammar + E's channel prior, both from the frozen files) | development logs: 1,419/1,610 real slips repaired exactly, 0 wrongly (`results/conformance/RESULTS.md`); public PNC turns of known intent: 152 exact, 0 wrong, 66 left loud, after a disclosed post-hoc fix (`RESULTS.md`); repair never changes a valid completion; streaming equals non-streaming |

## Install

slipguard is **not on PyPI yet**. Install it from a checkout of the repository, `pip install ./slipguard` (pip builds
in the source tree, so use a writable clone), or straight from git:
`pip install "slipguard[EXTRAS] @ git+https://github.com/aneeshm11/slipguard#subdirectory=slipguard"`. Below, `pip install
"slipguard[X]"` stands for either form.

For the **evaluated configuration** (the IPD proxy, cfg `fullp`, frozen engine, vLLM 0.19.1) plus the ADK hooks:

```bash
pip install "slipguard[proxy-frozen,adk]"
```

This is the same set as `slipguard[vllm,proxy-frozen,adk]`, because `proxy-frozen` pins `vllm==0.19.1`, which also
serves the model. `vllm==0.19.1` from PyPI is vLLM's **CUDA build**: it pulls torch 2.10, torchvision, torchaudio,
triton, flashinfer and about 20 `nvidia-*-cu12` wheels (several GB), even though the proxy itself runs on CPU. Even
`pip install --dry-run` downloads several GB of these wheels into the pip cache.

The `adk` and `litellm` extras are pinned to the tested ranges: google-adk >= 1.36, < 2, LiteLLM 1.104.x and
`mcp` >= 1.24, < 2. LiteLLM imports `mcp` on every call with tools without declaring it. ADK 2.x no longer brings it,
and LiteLLM 1.108 needs mcp 2, which ADK 1.x excludes. Unpinned, every ADK tool call failed with `No module named 'mcp'`.
In a fresh venv, `pip install "slipguard[adk]"` now resolves google-adk 1.39.1, LiteLLM 1.104.8 and mcp 1.30.0, and the
README snippet, ADK Runner and LiteLLM hook tests pass (8/8). The stack used for
the evaluation was Python 3.12, vLLM 0.19.1, transformers 5.13.1, google-adk 1.36.1 and LiteLLM 1.104.0; add
`google-adk==1.36.1 litellm==1.104.0 transformers==5.13.1` to reproduce it exactly.

Per component:

```bash
pip install slipguard                 # core: parser, history, audit, verify (stdlib only)
pip install "slipguard[proxy-frozen]" # slipguard proxy, default --engine frozen (the evaluated engine): + aiohttp,
                                      #   transformers, jinja2 and vLLM 0.19.1 (vLLM's CUDA build: torch + nvidia wheels)
pip install "slipguard[proxy]"        # slipguard proxy --engine lite only (derived; no vLLM): aiohttp, transformers, jinja2
pip install "slipguard[adk]"          # ADK + LiteLLM hooks (google-adk 1.x, LiteLLM 1.104.x, mcp 1.x)
pip install "slipguard[weights]"      # slipguard audit-weights (numpy, httpx, transformers)
/path/to/vllm-env/bin/python -m pip install slipguard   # the vLLM plugin: slipguard inside vLLM's environment
```

Python 3.10 or newer. `slipguard --version` prints the installed version.

**Which extra gives which proxy engine.** `slipguard proxy` (and `slipguard verify --model-dir`) default to
`--engine frozen`, the evaluated engine, which imports vLLM 0.19.1's Gemma 4 parsers on the proxy host: it needs
`[proxy-frozen]`. With `[proxy]` alone, pass `--engine lite`. If the packages are missing, the command exits with
status 2 and names the extra to install; it does not start.

**The vLLM plugin runs inside vLLM.** vLLM loads the plugin file by path, and the file imports `slipguard.parse`.
Install slipguard (the core package; no extras needed) into the **same Python environment as vLLM**, the venv or
container that runs `vllm serve`: for example `/path/to/vllm-env/bin/python -m pip install ./slipguard`. Otherwise
vLLM logs `No module named 'slipguard'` and `gemma4_strict` is an unknown parser. `slipguard plugin-path` prints this
reminder on stderr (stdout is the path only; `-q` silences it). The `[vllm]` extra installs a vLLM in the tested range
(0.19.1 to 0.33.x) next to slipguard; it does not put slipguard into an existing vLLM environment.

**Model files.** Gemma 4 weights and tokenizers on Hugging Face are gated: accept the licence on the model page and set
`HF_TOKEN` before `vllm serve <HF id>`, `--tokenizer <HF id>` or a download. `--model-dir` is a local directory with
the checkpoint's tokenizer files, `chat_template.jinja` and `generation_config.json` (the weights are not read). The
commands below use `google/gemma-4-31b-it` (bf16) as a placeholder. The end-to-end evaluation served Google's 4-bit
QAT checkpoint (`gemma-4-31b-it-qat-w4a16-ct`); the weight audit's pick is the community cyankiwi AWQ int4 checkpoint
(Weight audit, below).

## Three 5-minute tasks

**Scope.**
* The configuration evaluated end to end, in agent runs, is the **proxy** (task 3: frozen engine, cfg `fullp`, vLLM
  0.19.1 backend).
* The vLLM plugin (task 1) is conformance-tested (5 vLLM versions, every public PNC turn) and smoke-tested on a GPU
  server. It was **not evaluated end to end** in agent runs.
* Fail-loud alone can end an ADK turn: under ADK a text-only answer is final. **ADK users should serve through the
  proxy (task 3)**, or use the plugin's repair mode (`gemma4_strict_repair`) together with the history guard (task 2).

### 1. Make vLLM fail loud instead of executing corrupted calls

Conformance- and smoke-tested, not evaluated end to end. Under ADK, a refused call ends the turn: see Scope above.
Run this in vLLM's own environment, with slipguard installed there (Install, "The vLLM plugin runs inside vLLM").

```bash
P=$(slipguard plugin-path vllm)                        # the slipguard installed in vLLM's environment
vllm serve google/gemma-4-31b-it --enable-auto-tool-choice \
    --tool-parser-plugin "$P" --tool-call-parser gemma4_strict \
    --reasoning-parser-plugin "$P" --reasoning-parser gemma4_strict \
    --chat-template "$(slipguard template-path)"      # optional: the patched template (task 2 explains it)
```

**Per-call delivery** is how slipguard behaves in a server, both streaming and non-streaming:

* A call is delivered only when its own text is a strictly valid call.
* Calls are delivered **up to the first protocol error**. The malformed region, and everything after it, comes back
  **verbatim as message content**. It is never returned as a call.
* A call reaches the client only once its `<tool_call|>` has arrived, and then in one piece. Arguments are never
  streamed partially, and a truncated call is never delivered.
* Streaming and non-streaming deliver the same calls and the same content.
* Strings are opaque. Control tokens inside `<|"|>...<|"|>` are content: no truncation, no deletion, no extra
  calls.

Use `gemma4_strict_schema` to also reject calls that do not match the request's tool schema: undeclared tools or
keys, missing required arguments, wrong primitive types. `gemma4_strict_repair` adds one opt-in, text-only repair of
the first malformed call, for two drift classes only:
* **kwarg drift** on a non-string argument (`start_line=668`): `=` becomes `:`;
* **closer slips** (a string closed by a look-alike run): candidates from workstream B's relaxed grammar, repaired only
  when two cut rules agree (whole run, and the most probable closer under the frozen channel prior).

Everything else stays loud (including a closer that is simply missing: a whitespace-only run is not a look-alike).
On the conformance suite's slips (development logs, `results/conformance/RESULTS.md`) this repaired 1,419 of 1,610
real slips exactly and **none wrongly** (synthetic mutants: 1,029 exact, 0 wrong). A repaired call is never silent: its id ends in
`-ggrepaired`, a warning is logged, and nothing after it is delivered as a call.

**On natural traffic** (the PNC corpus: 41,290 turns of Gemma 4 agent trajectories; `results/natural_traffic.json`) strict parsing refuses 683 turns
(1.65%) whose calls vLLM 0.19.1 had delivered: 161 are slips that the quarantine criterion flags, and in **445 turns
the model wrote `key=value` and vLLM silently dropped that argument** (e.g. `read_file` without its `start_line`).
Repair mode recovers 479 of the 683 (440 kwarg drifts, 39 closer slips); the other 204 stay loud. Delivered calls have ids ending in `-ggok`.
`slipguard.history` uses these suffixes to tell strictly valid calls from laundered ones (a derived extension of the
frozen quarantine).

### 2. Clean an agent's history (Google ADK + LiteLLM)

<!-- verified: tests/test_readme_snippets.py runs this block with a real ADK Runner against a local stub server -->
```python
from google.adk.agents import LlmAgent
from slipguard.integrations.adk import guarded_lite_llm

model = guarded_lite_llm("hosted_vllm/gemma-4-31b", api_base="http://127.0.0.1:8000/v1")   # your vLLM server
# read_file is your own tool, e.g. def read_file(file_path: str) -> str: ...
agent = LlmAgent(name="coder", model=model, tools=[read_file], instruction="You are a careful coding agent.")
```

`read_file` stands for your own tools. `pip install "slipguard[adk]"`.

Before every model call, `HistoryGuard` rewrites the exact message list LiteLLM is about to send:

1. Raw call text left in assistant content is replaced by a short notice.
2. Malformed historical calls are quarantined. This is the frozen renderer: the call is re-rendered as recovered or
   sanitized, and its tool result becomes a `MalformedToolCall` error.
3. Control-token text in tool results and string arguments is made inert. The escape is reversible.

On a clean history it changes nothing; this is tested. The ADK session itself is never modified. Other entry points:

* LiteLLM without ADK: `litellm.callbacks.append(slipguard.integrations.litellm_hook.SlipGuardHook())`. It runs on
  `acompletion` only.
* Any other stack: `new_messages, report = slipguard.history.HistoryGuard().apply(messages, tools)`.

**Auditing existing transcripts.** `slipguard audit transcripts.jsonl --tools tools.json --json`. The laundered-call
check needs the tool declarations, from each conversation's own `tools` or from `--tools`: a JSON list, or an object
with a `tools` list. For PNC, pass the context manifest, e.g. `data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json`.
Without declarations the check cannot run. `audit` then prints a warning and marks each such conversation
`"malformed_call": "not checked (no tool declarations)"`; `--require-tools` makes that exit with status 2.
Exit status: 0 when no `malformed_call`, `raw_call_in_content` or `control_text` finding is present (`serialized_result`
and `thinking_off_gap` are reported but do not fail), 1 otherwise, 2 for `--require-tools` or a usage error
(`slipguard audit --help` lists the input format). `slipguard parse` exits 1 on a protocol error, also with
`--per-call`.

**Thinking off.** The shipped Gemma 4 templates honour `enable_thinking=false` only when a new model turn opens. After
a tool result they add nothing, and the model thinks anyway: in a registered test on 300 states it opened a thought
after a tool response in 98.7% with the stock template and 0.3% with the patched one (`RESULTS.md`, PREREG_v2.5 F3).

A message-list hook cannot add that closure. Serve the patched template instead (task 1, `--chat-template`). The hooks
log a warning when they see this state.

### 3. Serve with intent-preserving repair (the evaluated configuration)

```bash
pip install "slipguard[proxy-frozen]"                   # the proxy's default --engine frozen imports vLLM 0.19.1
vllm serve google/gemma-4-31b-it --port 8000            # stock backend, no slipguard plugin (tested: vLLM 0.19.1)
slipguard proxy --backend http://127.0.0.1:8000/v1 --served google/gemma-4-31b-it \
    --model-dir /path/to/gemma-4-31b-it --logdir ./proxy-logs
# agents use http://127.0.0.1:8420/fullp/v1 as their OpenAI base URL
```

Start the backend first; the proxy fronts it and parses the raw generations itself. `--model-dir` is the local
directory of the served checkpoint's tokenizer, `chat_template.jinja` and `generation_config.json`. Without vLLM on the
proxy host, use `pip install "slipguard[proxy]"` and add `--engine lite` (derived, not evaluated).
`slipguard proxy --help` lists the defaults (port 8420, engine `frozen`) and the cfg routes (`pass`, `base`, `order`,
`quar`, `ipd`, `fullp`, `full_order`).

IPD is **verify-then-repair**:

* The turn is generated to its end. A strictly valid call passes through byte-identical.
* An invalid call is rolled back to the first slip site. A noisy-channel rule chooses where to cut, the real `<|"|>`
  is inserted, and generation resumes.

`fullp` adds quarantine of the history. The proxy logs every request, including raw generations, to `--logdir`.

Derived options (not part of the evaluation; they add a cfg `guard` = `fullp` + the option):
`--template guarded` (closure + text-level neutralization in the template), `--template closure --token-neutralize`
(closure + **token-level** neutralization: the proxy tokenizes untrusted spans with special-token parsing disabled --
the preferred form, since the model sees exactly the original text), `--engine lite` (no vLLM on the proxy host).

## Verify your installation

```bash
slipguard verify                                   # frozen identity + conformance (no model needed)
slipguard verify --model-dir /path/to/gemma-4-31b-it --data <dataset>/release/package/v1.0/quotestorm/payloads.jsonl
                                                   # + P1 through the proxy (engine as for `proxy`; --engine lite works)
```

The QuoteStorm payloads are in the release dataset (`release/package/v1.0/quotestorm/payloads.jsonl`), not in the
repository; without `--data`, the P1 test uses built-in synthetic look-alike payloads.

* **frozen**:
  * every shipped frozen file matches its recorded sha256;
  * the files that the public export changed are byte-identical to the freeze outside the changed definition:
    `e2e_proxy.py` differs only inside `main` (one default path became an environment lookup); the two JSON/text files
    differ only in a provenance field (now repository-relative), and the data the code reads is identical.
* **conformance**:
  * the public minimal repros of 12 bug classes, run through the one-shot, per-call and streaming paths;
  * generated checks for string opacity, termination, linear time and bounded nesting.
* **p1**: workstream B's P1 acceptance test, run through E's real request path (`Proxy.engine_chat`, cfgs `ipd` and
  `fullp`, teacher-forced stub backend). Every strictly valid edit call must come back byte-identical.

## Byte identity ("what was evaluated is what ships")

`slipguard/_frozen/` holds workstream E's frozen proxy files. The final freeze is 2026-11-05 07:14 UTC, manifest digest
`c9c20591…`. The files keep their original layout and are loaded under private module names.

`tools/vendor_frozen.py` builds the copies:

* it checks every source sha256 against E's freeze list before writing anything;
* it applies exactly the public repository's export transform (path literals become environment lookups, plus
  privacy redaction);
* it records the shas and, for changed files, a hash of all text outside the changed definition in
  `_frozen/MANIFEST.json` (checked by `slipguard verify` on any Python version).

Tests T-F1..T-F4:

| test | check |
|---|---|
| T-F1 | shas match |
| T-F2 | `e2e_proxy.py` is byte-identical to the freeze outside `main` |
| T-F3 | channel prior JSON is equal |
| T-F4 | E's own suites pass on the shipped copies (65/65, 34/34, 30/30, quarantine self-test) |

## The patched chat template

`slipguard template-path` returns the official July template (`Published: 2026-07-09`) with two marked patches:

* **P-a**: after a tool result, with thinking off, it emits the closed empty thought `<|channel>thought\n<channel|>`.
  This is the missing mirror of the template's own thinking-on branch.
* **P-b**: control-token text inside tool-call arguments and tool results is rendered as inert text. A U+2060 word
  joiner is inserted after the `<`. The escape is reversible: `slipguard.history.unneutralize_text`.

  Background: the Gemma 4 tokenizer turns the *text* of its special tokens into the special tokens themselves,
  wherever the text appears. So data the agent reads (files, web pages, tool output) can otherwise inject protocol
  structure.

On every input without those two hazards, the patched template is **byte-identical** to the official one:

| test | inputs | result |
|---|---|---|
| T-T1 | the conformance suite's identity sets: 3,000 calls, 1,500 tool results × thinking on/off, 1,500 declarations, all prompt shapes | 0 differences |
| T-T2 | thinking-off prompts after a tool result | exactly the closure is added |
| T-T3 | every input | `patched(messages) == official(neutralize(messages))`, so the template fix and the history fix are the same function |

## Security notes (class level)

* **Untrusted data can carry protocol structure.** Tool results, files and web pages that contain the text of Gemma 4
  control tokens are tokenized into real control tokens by the official template and tokenizer. `slipguard.history`
  and the patched template make such text inert (reversibly). Affected runtimes are described by class only; the
  exact inputs are withheld from this release (see `SECURITY.md` at the repository root).
* **Nothing after a protocol error is executed.** After the first malformed call (or stray protocol token in the
  content), slipguard returns the rest of the completion as content, never as calls. A parser that "resynchronizes"
  after a malformed call can be steered into executing a call that was really part of a string argument of the broken
  call; delivering calls only up to the first error removes that class of injection while keeping streaming and
  non-streaming identical.
* **Strings are opaque.** Inside `<|"|>...<|"|>` every control token is content.
* **Bounded work.** Parsing is linear in the input for any chunking, and nesting is bounded without recursion.

## Conformance

### On public real inputs (PNC: every model turn)

Every model turn of the public PNC corpus (41,290 turns of Gemma 4 agent trajectories: raw generations including the
thinking, each with its episode's tool schema) through the conformance suite's harness and judge, slipguard next to the
parsers that vLLM and transformers ship. The plugin runs inside each vLLM version's own server objects, non-streaming
and one token per delta (`results/conformance_pnc/RESULTS.md`; `conformance/build_pnc_cases.py`, `run_pnc.sh`,
`report_pnc.py`).

| 41,290 turns | slipguard: API, and plugin in vLLM 0.19.1, 0.24.0, 0.31.0, 0.32.0, 0.33.0 (server and stream) | vLLM 0.19.1 built-in (server / stream) | vLLM 0.31.0 / 0.32.0 / 0.33.0 built-in (server / stream) | transformers 5.13 / 5.17 `parse_response` |
|---|---|---|---|---|
| strictly valid turns with calls: exact | 40,417 / 40,417 | 40,417 / 40,406 | 40,406 / 40,406 | 40,417 |
| ill-formed turns (872): surfaced (error, or returned as text) | **872** | 185 / 75 | 5 / 3 | 847 |
| ill-formed turns: a call delivered silently | **0** | 687 / 692 | 865 / 869 | 24 |
| ill-formed turns: call text lost | 0 | 0 / 105 | 2 / 0 | 1 |
| 218 with known intent (retry-derived): delivered exact / **wrong** | 0 / 0 (all surfaced) | 0 / **188** | 1 / **216** | 0 / 0 |

* Known intent: the malformed call is restated by a later clean call of the same episode (a retry). On these 218 turns
  the built-in vLLM parsers deliver a **wrong** call in 188 (0.19.1, 0.24.0) to 216 (0.31.0, 0.32.0, 0.33.0) cases (dropped
  argument, corrupted value, wrong name) and the intended call once at most. vLLM 0.24.0 (not in the table): 33
  surfaced, 777 delivered silently, 62 lost.
* The plugin follows per-call semantics: in 4 turns the strictly valid call *before* a stray control token was
  delivered and everything from that token on was returned as text. Streaming equals non-streaming on all 41,290
  turns for the plugin in every version (built-in: 5 to 40 turns differ per version).
* Opt-in repair (`gemma4_strict_repair`): on the 218 turns with known intent, 152 repaired exactly, **0 wrongly**,
  66 left loud; it also repaired 327 of the other 654 ill-formed turns (not scored: no intent). These numbers come
  after a **post-hoc fix** that this run prompted (before it: 152 / 1 wrong / 65; a missing closer, where a newline was
  cut as a look-alike), so for the repair rule PNC is not a held-out test; details and the pre-fix results are in
  `results/conformance_pnc/`.
* Safety: 0 hangs and 0 exceptions for slipguard. vLLM 0.19.1's built-in streaming parser exceeded the harness's
  15 s budget on one 8,192-token truncated turn (9.1 s of parser time in the quiet benchmark; quadratic).

### On the conformance suite (development logs and synthetic inputs, judged with the suite's own rules)

`conformance/` drives slipguard through the suite's differential harness: 13,612 inputs (grammar fuzz, mutations of
real edit calls, edge cases, real model outputs, 39 minimal repros), each through the Python API (one-shot, per-call,
streaming) and through the vLLM plugin inside vLLM **0.19.1, 0.24.0, 0.31.0, 0.32.0 and 0.33.0**'s own server-path objects
(non-streaming and per-token streaming). Results: `results/conformance/RESULTS.md`.

* **All 16 bug classes pass on every non-streaming path** (E1-E5 slips and drifts, truncated calls, delimiter errors,
  control tokens inside strings, infinite loops, quadratic time, deep nesting, type drift, literals, valid-L1 coverage,
  multiple calls). **On streaming, plugin streaming in vLLM 0.19.1 and 0.31.0-0.33.0 fails one class, quadratic time
  (C8)**; the API stream and the plugin in vLLM 0.24.0 pass all 16. The quadratic-time (C8) and deep-nesting (C9)
  repros are longer than the harness's 3,000-character streaming cap, so the suite run marks them n/a there. Run
  uncapped (`results/conformance/C8_C9_streaming_uncapped.json`), C9 passes on every streaming path. C8 is judged per
  input on wall time (>= 250 ms = defect): the API stream (198 ms) and the plugin in vLLM 0.24 (242 ms) pass, while the
  plugin in vLLM 0.31.0, 0.32.0 and 0.33.0 (449 ms) and 0.19.1 (1,229 ms) exceed it on the 37,755-character payload. That time includes each
  version's per-delta server objects. Plugin streaming scales linearly from vLLM 0.31 on (slope 1.03-1.04, see
  Performance). vLLM 0.19.1's own streaming loop is super-linear for any parser. The built-in streaming parsers on the
  same three inputs take 0.8 to more than 15 s, or fail. On the same suite the built-in parsers show defects in 10 to 13
  of the 16 classes (server and streaming paths): vLLM 11-12 (0.19.1, 0.24.0, 0.27.0, 0.29.0, 0.30.0, 0.31.0, 0.32.0,
  0.33.0), SGLang 13 (0.5.11, 0.5.23), llama.cpp 10 (b8829, b12103).
* 0 hangs and 0 uncaught exceptions on any input, on any path.
* Real model outputs: 1,500/1,500 real clean calls exact; **1,610/1,610 real slips visible** (never returned as a
  call); 0 real raw outputs lost. All 165,336 distinct real valid calls of the logs (265,422 with repetitions) exact.
* The one-shot parser equals the executable specification (GemmaProtocol) on every input, and streaming equals
  one-shot for every chunking tested (100,000+ randomized inputs, 1-character and random chunkings).

## Weight audit (`slipguard audit-weights`)

**Run `slipguard audit-weights` before deploying a 4-bit Gemma 4 checkpoint.** Quantization can shrink the margin
by which the model closes a code string with `<|"|>` instead of a look-alike quote. The audit measures that margin on a
served checkpoint at held-out string ends of public PNC agent turns, in generation-mode teacher forcing with top-20
log-probabilities. It reports the median margin, P(margin < ln 19), the slip probability under the shipped sampler and,
against the same-family bf16 checkpoint, the paired median margin deficit with the pre-registered flag rule. With
`--out`, the report goes to the file and a one-line verdict to stderr.

```bash
slipguard audit-weights --endpoint http://127.0.0.1:8000/v1 --served-name gemma-4-31b \
    --pnc <PNC dir> --tokenizer <model dir> --records qat.records.jsonl \
    --reference bf16.records.jsonl --out report.json      # --conc 1 if the KV cache holds about one 17k context
slipguard audit-weights --from-records qat.records.jsonl --reference bf16.records.jsonl   # re-score on CPU
```

* **It ranks checkpoints.** Workstream F's sweep (`results/weights/sweep_report.json`, sha256 e1cbe5ff) covers 12
  checkpoints served by vLLM 0.19.1; the registered breadth audit (PREREG_v2.10) adds 3 more that could be served, 15
  in all. Google's QAT 31B checkpoint has a median deficit of **5.13 nats** [4.69, 5.56] against 31B bf16 (FLAG). A
  community AWQ int4 checkpoint of the same size (cyankiwi) has **0.02** [-0.18, 0.21] (no flag). The breadth audit
  supports H-QAT: the damage is in the QAT-trained weights, so re-quantizations of them are damaged too (`RESULTS.md`).
* **Censoring caveat.** Margins come from the top-20 log-probabilities. Where `<|"|>` or every look-alike falls outside
  the top 20, only a lower bound is known: that is 55% of string ends for the QAT 31B checkpoint and 47% for cyankiwi
  AWQ (reported as `censored_frac`). Medians and deficits are therefore computed on lower bounds.
* **Registered behavioural validation** (PREREG v2.6; `results/weights/v26_audit_analysis.json`, sha256 a1d63581).
  On 300 public states, serving the audit's pick (the AWQ checkpoint) instead of the QAT checkpoint cuts contagion
  after a laundered slip from **19.7% to 10.3%** [7.0, 13.9]; with AWQ served in bf16 like QAT, to 12.0% (registered
  replication, PREREG_v2.7 D1). On the AWQ checkpoint, quarantine (arm P8a: the frozen renderer with the recovered
  call, as the proxy's `fullp` applies it) removes the rest: **0/300**. Served end to end under stock vLLM, the pick
  cut malformed calls per episode from 1.91 (QAT, 10 replicates) to 0.41 (2 replicates; 0.22× [0.11, 0.39]; tasks
  paired across runs, not seeds; PREREG_E_awq). Checkpoint choice and slipguard are complementary.
* **Status of the shipped copy.** On CPU it reproduces F's frozen sweep reports from F's records
  (`dev/check_wsa.py`): every summary field, every deficit point estimate and every flag. Bootstrap CI bounds are within
  0.03 nats, because F's script drew all checkpoints from one random stream. F's CPU identity check: the rendered
  prompt token ids equal the sweep's for every pack item (235/235, 951/951); the shipped renderer reproduces the
  packs' prompt token counts too. Live end to end (`results/weights/live_e2e_check.json`): `slipguard audit-weights` against
  Google's QAT 31B checkpoint served by vLLM 0.19.1, on the first 12 pack items (20 positions). Prompt token counts,
  logged tokens, top-1 tokens and censoring agree with F's sweep records at every position. Margins differ by at most
  0.28 nats, within the 0.44 nats between F's own two runs of the same checkpoint (4-bit logprobs are not
  bit-reproducible across vLLM runs). The flag on this subset is the same.
* Weight *repair* is not part of slipguard: none of the candidates passed its registered gate.

## Gemma-only by design

The quarantine text and the closure tokens are specific to Gemma 4. In a cross-family test, the quarantine message
caused a *different* protocol failure in another model family (Qwen3-8B).

`HistoryGuard(model=...)` therefore refuses model names that do not look like Gemma 4, unless you pass
`allow_non_gemma=True`. The TranscriptLab benchmark that ships with this library is model-agnostic; slipguard is not.

## Performance

`slipguard.parse` does linear work for any chunking. String bodies and content are scanned with `str.find`, and there
is no recursion. One CPU core, the same inputs and the same process for every column (`benchmarks/run_perf.sh`;
the inputs are the conformance suite's scaling families); "slope" is the least-squares log-log slope over all sizes
(1 = linear, 2 = quadratic):

| input | vLLM | built-in parser | slipguard plugin (same server objects) | slipguard API |
|---|---|---|---|---|
| many_int_keys (non-streaming), 4,000 arguments | 0.19 | 8.0 ms, slope 1.45 | 28 ms, slope 0.97 | 27 ms, slope 1.0 |
| many_int_keys (non-streaming), 4,000 arguments | 0.31 | 38.8 s, slope 1.97 | 39 ms, slope 0.93 | 28 ms, slope 1.0 |
| many_int_keys (non-streaming), 4,000 arguments | 0.33 | 54.2 s, slope 1.98 | 40 ms, slope 0.72 | 27 ms, slope 0.82 |
| many_string_keys (non-streaming), 4,000 arguments | 0.19 | 9.1 ms, slope 1.61 | 19 ms, slope 0.99 | 18 ms, slope 1.01 |
| many_string_keys (non-streaming), 4,000 arguments | 0.31 | 34.1 s, slope 1.96 | 53 ms, slope 0.97 | 18 ms, slope 1.02 |
| many_string_keys (non-streaming), 4,000 arguments | 0.33 | 46.8 s, slope 1.97 | 53 ms, slope 0.96 | 18 ms, slope 1.02 |
| code_with_commas (non-streaming), 16,000 code lines | 0.19 | 3.6 ms, slope 0.96 | 3.1 ms, slope 1.06 | 0.3 ms, slope None |
| code_with_commas (non-streaming), 16,000 code lines | 0.31 | > 60 s (timeout), slope 1.97 | 157 ms, slope 1.06 | 0.3 ms, slope None |
| code_with_commas (non-streaming), 16,000 code lines | 0.33 | 5.5 s, slope 1.48 | 171 ms, slope 1.06 | 0.3 ms, slope None |
| long_string (non-streaming), 4,000,000 chars | 0.19 | 25 ms, slope 1.03 | 24 ms, slope 1.02 | 3.9 ms, slope None |
| long_string (non-streaming), 4,000,000 chars | 0.31 | 3.2 s, slope 1.05 | 2.5 s, slope 1.07 | 3.9 ms, slope None |
| long_string (non-streaming), 4,000,000 chars | 0.33 | 3.2 s, slope 1.05 | 2.5 s, slope 1.07 | 4.0 ms, slope None |
| many_string_keys (streaming), 2,000 arguments | 0.19 | 47.5 s, slope 2.06 | 1.0 s, slope 1.45 | 194 ms, slope 1.02 |
| many_string_keys (streaming), 2,000 arguments | 0.31 | 17.2 s, slope 1.84 | 243 ms, slope 1.04 | 190 ms, slope 0.94 |
| many_string_keys (streaming), 2,000 arguments | 0.33 | 29.3 s, slope 1.88 | 236 ms, slope 1.04 | 191 ms, slope 0.9 |
| code_with_commas (streaming), 6,400 code lines | 0.19 | > 60 s (timeout), slope 1.98 | 40.0 s, slope 1.81 | 1.1 s, slope 1.04 |
| code_with_commas (streaming), 6,400 code lines | 0.31 | > 60 s (timeout), slope 1.9 | 1.3 s, slope 1.03 | 1.0 s, slope 1.04 |
| code_with_commas (streaming), 6,400 code lines | 0.33 | 2.9 s, slope 1.06 | 1.3 s, slope 1.03 | 1.0 s, slope 1.04 |

* The plugin columns run slipguard inside each vLLM version's own server-path objects (request handling, reasoning
  split, tool parsing; the non-streaming server path also tokenizes the output, which dominates the long-string rows).
* vLLM 0.19's streaming loop re-concatenates the whole output at every step for any parser; from 0.24 on, slipguard's
  two parsers declare engine-based streaming and receive per-step deltas, which makes the plugin's streaming linear.
* Full tables and the paper figure spec: `results/PERF.md`; raw data: `results/perf_vllm0{19,31,33}.json`.
* **On realistic traffic the parser is not a bottleneck for either implementation** (`results/PERF_REALISTIC.md`:
  all 41,290 turns of the PNC corpus, vLLM 0.19.1, 0.31.0, 0.32.0 and 0.33.0): the built-in parsers cost 0.002-0.03% of generation time
  non-streaming and 0.05-0.11% streaming, with no single call above 181 ms; slipguard costs 0.003-0.03%, with no
  call above 16 ms. The speed result is therefore a robustness property (no hang, no quadratic blow-up on large or
  many-argument calls), not a throughput claim.
* `slipguard bench parse --max-args 32000 --max-string 16000000` (API only, Python 3.12; the defaults stop at 16,000
  arguments and 4 MB): 32,000 arguments in 0.15 s, a 16 MB string in 0.09 s; streamed in
  4-character deltas 0.43 s and 4.6 s; every slope 1.0.

## Limitations

* **Fail-loud can end an agent turn.** Under ADK, a text-only answer is final. The strict parser therefore trades a
  silently corrupted call (35.5% of laundered calls were executed in a full ADK runner) for a visible stop. Use the
  proxy to repair, or the history guard's notice so the model re-issues the call.
* **Text-only repair is ill-posed in general.** A string may legitimately contain `` `,old_string: ``. slipguard
  therefore never repairs from text alone without reporting it: E's quarantine marks such calls, and `strictly_valid_ids`
  or the `-ggok` ids exempt calls known to be valid. Repair with token-level evidence is the proxy's job.
* **vLLM 0.19 streaming has no end-of-stream signal for parsers.** slipguard finishes on the stop token's id. A stream
  cut by `max_tokens` inside a call returns no content for that call, but `finish_reason` is `length`.
* **Control-token neutralization changes what the model sees on hazardous inputs.** That is the purpose. Prefer the
  token-level form (special-token parsing disabled for untrusted spans) where you control tokenization.

## License

Apache-2.0 (see `LICENSE` and `NOTICE`). Unofficial; not affiliated with Google.
