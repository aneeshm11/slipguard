# User guide

This repository has three parts. Pick the path that matches what you are doing.

| you are... | start here | time |
|---|---|---|
| running a Gemma 4 agent and want fewer corrupted tool calls | [1. Protect an agent](#1-protect-a-gemma-4-agent) | 5 min |
| checking whether your existing transcripts are affected | [2. Audit transcripts](#2-check-whether-your-transcripts-are-affected) | 1 min |
| choosing a quantized Gemma 4 checkpoint to serve | [3. Audit a checkpoint](#3-choose-a-checkpoint) | minutes, GPU |
| evaluating a model (any family) for history contagion | [4. Run TranscriptLab](#4-measure-a-model-with-transcriptlab) | 1,200 generations |
| training or evaluating on agent trajectories | [5. Use PNC](#5-use-the-pnc-corpus) | — |
| reviewing the paper's claims | `REPRODUCE.md`, `RESULTS.md`, `PREREGISTRATIONS.md`, `LIMITATIONS.md` | seconds to minutes |

**Background in one paragraph.** Gemma 4 writes tool calls in its own notation, with `<|"|>` delimiting string values.
When the model closes a string with a look-alike, usually a backtick, stock parsers read on. They return a
well-formed call with the wrong arguments; the agent framework stores that call in the history, and the chat template
renders it back to the model as a clean example. The model then imitates it. In the challenge's own harness
(Gemma-4-31B, 4-bit QAT) this produced 1.76 malformed calls per episode over eight fresh replicates (2.47 in the first
two), and about 5–6% of episodes got stuck in loops of them. slipguard removes the corruption where it enters and where
it persists.

---

## 1. Protect a Gemma 4 agent

Three options. They combine.

| option | what it does | when to use | evaluated how |
|---|---|---|---|
| **Repair proxy** (`slipguard proxy`) | Sits between your agent and vLLM. Repairs look-alike string closers using the model's own likelihood. Quarantines corrupted history (recovered call plus an explicit error, the P8a form). | You serve with vLLM and can add a hop. **This is the evaluated configuration.** | End to end in the challenge harness (Gemma-4-31B QAT): in 8 fresh replicates 1.76 → 0.37 malformed calls per episode (0.21× [0.13, 0.35]), stuck episodes 49 → 3 of 904, tasks solved 393 vs 394 of 904 (non-inferior at −3 pp); first 2 replicates 2.47 → 0.27, stuck 14 → 0 of 226. On the audit's AWQ pick (6 fresh replicates): 0.50 → 0.29 (0.59× [0.36, 0.99]). Its P8a quarantine on TranscriptLab: 92% [86, 98] of the excess removed (300 states × 3 runs pooled; runs 98%, 93%, 86%; the released-CLI rerun 85%) |
| **History guard** (`slipguard.history`, ADK/LiteLLM hooks) | Cleans the message list before every model call. Quarantines with a *sanitized* re-render of the call (the P8b form), not the recovered call. | You cannot change the server, or you use another OpenAI-compatible backend. | TranscriptLab, registered run 1 only: P8b removes 98% [88, 110] of the excess (PREREG_v2 C6; no rerun). Not run end to end (`LIMITATIONS.md` §9, §15) |
| **Strict parser plugin** (`--tool-call-parser gemma4_strict`) + patched template | Delivers a call only when it is strictly valid; the rest becomes content. The template closes the thought when thinking is off. | You want fail-loud behaviour inside vLLM. | Conformance: 0 wrong calls on the 218 ill-formed PNC turns of known intent (mostly `key=value` drift; built-ins: 188–216 wrong). 1-hour load soak: 0 protocol-corrupt deliveries in 918 calls. Not run end to end (`LIMITATIONS.md` §9, §11). |

Commands are in `slipguard/README.md` ("Three 5-minute tasks"). The short version:

```bash
pip install "slipguard[proxy-frozen,adk] @ git+https://github.com/aneeshm11/slipguard#subdirectory=slipguard"   # not on PyPI; or the wheel: see INSTALL.md
vllm serve google/gemma-4-31b-it-qat-w4a16-ct --served-model-name gemma-4-31b --max-model-len 32768 \
    --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 --port 8000
slipguard proxy --backend http://127.0.0.1:8000/v1 --served gemma-4-31b --model-dir <local model dir> \
                --logdir logs/ --port 8420
# point the agent's OpenAI base URL at http://127.0.0.1:8420/fullp/v1
slipguard verify      # checks that the shipped proxy is byte-identical to the evaluated one
```

**Before you run it.**
- **Weights.** The end-to-end evaluation served Google's 4-bit QAT checkpoint, `google/gemma-4-31b-it-qat-w4a16-ct`.
  The weight audit recommends `cyankiwi/gemma-4-31B-it-AWQ-4bit` (§3); the evaluated runs served it with
  `--dtype bfloat16` and a text-only `--hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'`.
  If a Hugging Face download (weights or tokenizer) is refused, accept the model's terms on its page and set `HF_TOKEN`.
- **`--model-dir`** is a local directory with the checkpoint's tokenizer, `chat_template.jinja` and
  `generation_config.json`. Start the stock `vllm serve` first; the proxy fronts it.
- **Install size.** `[proxy-frozen]` pins `vllm==0.19.1`, vLLM's CUDA build (torch and `nvidia-*` wheels, several GB);
  even `pip install --dry-run` downloads them. The resolver picks current versions of the other packages; to reproduce
  the evaluated set exactly, add the pins given in `slipguard/README.md` (transformers 5.13.1, google-adk 1.36.1,
  LiteLLM 1.104.0).
- **Engine.** `slipguard proxy` runs the evaluated (frozen) engine by default, which imports vLLM 0.19.1. With only
  `slipguard[proxy]` installed, pass `--engine lite`, a derived engine that is not the evaluated one. The proxy
  listens on port 8420 by default; its routes are `pass`, `base`, `order`, `quar`, `ipd`, `fullp` (evaluated) and
  `full_order`.
- **Install from a writable checkout.** `pip install ./slipguard` builds inside the source tree. The release wheels
  (`slipguard-0.1.2`, `transcriptlab-0.1.3`) are attached to the release dataset (https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc), not to the
  repository.

**What to expect.**
- Most of the end-to-end gain comes from ending runaway loops (exploratory). In the first two replicates, the share of
  episodes with at least one malformed call fell less, 30.5% → 21.7%. Not every loop ends: 3 of 904 fresh proxy episodes still got
  stuck (49 without the proxy).
- The fresh replicates' cut (0.21× [0.13, 0.35]) is smaller than the first replicates' (0.11×).
- First slips still happen: the proxy repairs them; it does not prevent them.
- A slip in an argument *name* (e.g. `start_line"`) passes through the proxy unrepaired. Use the strict parser if you
  need those refused.
- Solved tasks are non-inferior at −3 pp: 393 (stock) vs 394 (proxy) of 904 episode pairs, +0.11 pp [−2.21, +2.43].
  The CI still allows a drop of up to 2.2 points. No gain in solved tasks is claimed.
- Malformed-call counts cannot see a silently wrong repair. On the 393 detectable injected slips IPD delivers 6.9%
  silently wrong calls (stock parser 1.1%); over all 600 injected slips 20.4% (stock 15.5%), because a slip that yields
  a valid call is silently wrong for every text-based method. The solved-task test is the only end-to-end check on this.
- On the checkpoint the audit recommends (the AWQ pick, §3), the proxy still cuts malformed calls, by less: in 6 fresh
  replicates 0.50 → 0.29 per episode (0.59× [0.36, 0.99], p 0.045; registered PREREG_E_awq2), and stuck episodes
  5 → 1 of 678. The first 2 AWQ replicates had shown no significant cut (0.41 → 0.32, 0.77× [0.44, 1.47]).
- See `LIMITATIONS.md` §2–3.

**Streaming clients: allow a long read timeout.** The proxy and the strict plugin send nothing until a tool call is verified. Under heavy load, a long tool-call turn can be silent for minutes; in our overload soak, at about 3 tokens/s per request, some exceeded 600 s (`LIMITATIONS.md` §11).

**Do not use fail-loud alone with ADK.** In ADK a text-only answer ends the turn. Pair the strict parser with the proxy
or the history guard.

**The vLLM plugin runs inside vLLM's Python.** `slipguard plugin-path vllm` prints a file in *slipguard's* environment,
and that file imports `slipguard.parse`. Install slipguard into the environment (or container) that runs `vllm serve`,
or `--tool-parser-plugin` fails to import and `gemma4_strict` is unknown. Serve with both `--tool-call-parser
gemma4_strict` and `--reasoning-parser gemma4_strict` (`LIMITATIONS.md` §15). `slipguard[vllm]` has no upper bound on
vLLM; the plugin was tested in vLLM 0.19.1, 0.24.0 and 0.31–0.33.

## 2. Check whether your transcripts are affected

```bash
slipguard audit transcripts.jsonl --tools tools.json --json   # one JSON line per conversation (OpenAI-format messages)
# tools.json: your tool declarations (a JSON list, or an object with a "tools" list, e.g. a PNC context manifest.json).
# Without --tools the malformed-call check is skipped (a warning says so); --require-tools makes that an error.
```

It reports, per conversation and without modifying anything:
- `malformed_call`: a historical call that quarantine would fix (unknown tool, missing or undeclared keys, leaked
  look-alike closer, special token in a value);
- `raw_call_in_content`: raw tool-call markup returned as assistant text;
- `control_text`: control-token text in a tool result or call argument;
- `serialized_result`: ADK/LiteLLM's JSON-string form of a tool result;
- `thinking_off_gap`: a conversation ending in a tool result while thinking is off, which needs the patched
  template.

Use `--tools` if your conversations do not carry the tool declarations, and `--thinking` if they ran with thinking on.
`slipguard audit --help` gives the accepted line formats and the exit codes (non-zero when it finds a problem, so it can
gate a pipeline). `slipguard parse` and `slipguard check` exit 1 when the input has a protocol error.

## 3. Choose a checkpoint

```bash
slipguard audit-weights --endpoint http://HOST:PORT/v1 --served-name NAME --pnc <PNC dir> --tokenizer <model dir> \
    --records mine.records.jsonl --reference bf16.records.jsonl --out report.json
```

It measures how far the checkpoint's margin for the true string delimiter falls short of bf16, at 454 held-out string
ends from PNC. You do not need to serve bf16 yourself: the bf16 reference records for Gemma-4-31B and E4B ship in
`experiments/quant_margins/wsa/out/audit_sweep_{31b,e4b}_bf16.records.jsonl`.
- Across the 15 checkpoints we audited, Google's QAT 31B release lost 5.13 nats; its unquantized QAT weights lost 5.51,
  and its AWQ and NVFP4 exports more (below). The community cyankiwi AWQ 4-bit checkpoint
  (`cyankiwi/gemma-4-31B-it-AWQ-4bit`, an export of the bf16 weights) lost only 0.02.
- Serving the AWQ checkpoint instead of QAT cut contagion after a laundered call from 19.7% to 10.3% in a registered
  test, and to 12.0% when AWQ was served in bf16 like QAT.
- End to end in the challenge harness (registered), serving the AWQ pick under stock vLLM cut delivered malformed calls
  per episode from 1.91 (QAT, 10 replicates) to 0.41 (2 replicates; 0.22× [0.11, 0.39]; PREREG_E_awq). Six fresh AWQ
  replicates reproduce it: 0.50, 0.26× [0.15, 0.44] (PREREG_E_awq2 S4). Both comparisons pair tasks across runs, not
  seeds.
- Caveats: about half of the margins are censored lower bounds; and whether the audit's flags predict end-to-end
  malformed calls on other checkpoints is being tested (PREREG_E_audit, running and blind; analysed once at its cutoff,
  Nov 8 14:00 UTC; `LIMITATIONS.md` §2, §6).
- Checkpoint choice and slipguard combine. On TranscriptLab states, quarantine (P8a) removed the rest of the contagion
  on the AWQ checkpoint (0 of 300). End to end, the proxy still cut malformed calls on AWQ, by less than on QAT: 0.50 →
  0.29 per episode in 6 fresh replicates (0.59× [0.36, 0.99], registered).
- **Avoid exports of the QAT weights.** The damage is in the QAT-trained weights, so their AWQ and NVFP4 re-quantizations
  are damaged too (6.0 and 7.4 nats). Exports from the bf16 weights are not (cyankiwi AWQ 0.02; nvidia NVFP4 1.36).
  Audit any checkpoint you plan to serve.

## 4. Measure a model with TranscriptLab

TranscriptLab needs the repository and the PNC corpus. The GitHub repository ships only PNC's metadata in
`data/pnc/` (manifest, licence, task list, grades, chat template). The episodes and contexts (≈ 3 GB) are in the
Kaggle dataset (https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc), which is this repository with `data/pnc/` complete: download it and use it as
your checkout, or copy its `data/pnc/episodes/`, `contexts/` and `episode_meta/` next to `data/pnc/MANIFEST.json` in
a clone, or point `PNC_ROOT` at its `data/pnc/`. Run TranscriptLab inside the repository, or
set `TRANSCRIPTLAB_ROOT=<repository root>`.

```bash
pip install "./transcriptlab[run]"   # from a checkout; or transcriptlab[run] @ git+https://github.com/aneeshm11/slipguard#subdirectory=transcriptlab
export TRANSCRIPTLAB_ROOT=<repository root>       # contains data/pnc/ (or set PNC_ROOT=<unpacked PNC dataset>)
transcriptlab estimate --pool A1 --arms P0,P1,P6,P8a           # cost first
transcriptlab run --base http://HOST:PORT/v1 --model NAME --tokenizer HF_ID --pool A1 --arms P0,P1,P6,P8a --out runs/NAME
transcriptlab report runs/NAME --root "$TRANSCRIPTLAB_ROOT"
```

- **Install.** TranscriptLab is a separate package from slipguard. `[run]` installs vLLM 0.19.1 (its CUDA build),
  although the runner uses only vLLM's Gemma 4 parser and the reference judge, on the CPU; the model under test is
  served separately.
- **Root.** Commands find the repository from `--root`, else `$TRANSCRIPTLAB_ROOT`, else by searching upward from the
  current directory. Pass `--root` when you work outside the checkout, so that another tree above you is not used.
- **Gated tokenizers.** `--tokenizer HF_ID` downloads from Hugging Face; for a gated model, accept its terms and set
  `HF_TOKEN`.
- **Formats.** `gemma4` (default), `hermes`, `qwen3_coder`, `harmony` and `mistral`.
- **What it reports:**
  - *copying*: one corrupted past call plus the framework's error, P1 − P0;
  - *imitation* ("induction" in the registrations and analysis files): the same call plus its original success response,
    P6 − P0;
  - *removal by quarantine*: P8a.
  - Every rate is unconditional, per state: the share of states whose next call is a malformed edit.
- **Reading the result.** A model needs a history guard when either risk difference's 95% CI has its lower bound
  above 0. The current leaderboard (13 configurations, 5 tool formats) is in the paper's Table 3 and `RESULTS.md`.
- **How it works.** The runner and analysis are frozen; `transcriptlab verify` checks their hashes. The CLI only
  selects states and writes the job list.

## 5. Use the PNC corpus

PNC holds 1,181 Gemma-4-31B agent episodes (41,290 turns) on SWE-bench tasks. The episodes are in the Kaggle dataset
(https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc, ≈ 3 GB; already in its `data/pnc/`), not in the GitHub repository (see §4). Each turn
has:
- the exact request;
- the raw generation;
- the parsed calls and tool results.

SWE-bench grades are attached for 1,167 episodes. The datasheet (`DATASHEET.md`) gives the collection process,
licences (GPL repositories excluded) and intended uses.

```python
import json
ep = [json.loads(l) for l in open("data/pnc/episodes/<file>.jsonl")]   # one line per turn (after unpacking the dataset)
turn = ep[0]
print(turn["request"]["messages"][-1], turn["schema"])
```

## Getting help

- Questions and bugs: GitHub issues.
- Security problems: see `SECURITY.md`.
- Known limits: `LIMITATIONS.md`.
