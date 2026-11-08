# slipguard · TranscriptLab · PNC

**slipguard (a library) stops Gemma 4 agents from imitating their own corrupted tool calls. TranscriptLab (a
benchmark) measures how much any model does it. PNC (a dataset) is the corpus of real agent episodes behind both.**

Gemma 4 writes tool calls in its own notation, with `<|"|>` delimiting strings. When the model closes a string with a
look-alike character, usually a backtick, the parsers in vLLM, SGLang and llama.cpp read on. They return a well-formed
call with the wrong arguments; the agent framework stores that call in the history, and the chat template renders it
back to the model as a clean example. The model then copies it. In the agent harness released with Google's Gemma 4
Developer Agent challenge (Gemma-4-31B, 4-bit QAT), this produced 1.76 malformed tool calls per episode over eight
fresh replicates (2.47 in the first two), and about 5–6% of episodes got stuck repeating them (49 of 904; first two
replicates 14 of 226).

## Two tools and one dataset: which is which

This repository is named after the library, but it holds all three resources. They are separate: install or download
only the one you need.

| | **slipguard** | **TranscriptLab** | **PNC** |
|---|---|---|---|
| kind | Python library | benchmark (a Python CLI plus frozen runners) | dataset (corpus) |
| what it does | protects a Gemma 4 agent: refuses or repairs broken tool calls, quarantines them in the history, audits checkpoints | measures how much one corrupted past action changes a model's next tool call | 1,181 Gemma-4-31B agent episodes on SWE-bench (41,290 turns): requests, raw generations, parsed calls, tool results, test grades |
| use it if | you run a Gemma 4 agent | you want to test a model, Gemma or not | you study agent trajectories or tool-call failures |
| works with | Gemma 4 only | any model served with raw completions | — |
| get it | `pip install "slipguard[proxy-frozen,adk] @ git+https://github.com/aneeshm11/slipguard#subdirectory=slipguard"` (not on PyPI; `INSTALL.md`) | `pip install "transcriptlab[run] @ git+https://github.com/aneeshm11/slipguard#subdirectory=transcriptlab"`, run inside a checkout with PNC | the Kaggle dataset (https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc) |
| needs | nothing else (core is stdlib-only) | this repository and PNC | — |
| docs | `slipguard/README.md`; `USER_GUIDE.md` §1–3 | `transcriptlab/README.md`; `USER_GUIDE.md` §4 | `DATASHEET.md`; `USER_GUIDE.md` §5 |

How they fit together: TranscriptLab's test states are cut from PNC episodes, and TranscriptLab is how the paper
measures the history effect that slipguard's quarantine removes. slipguard does not need TranscriptLab or PNC to run.

## Start here

1. **Read the paper:** `paper/WRITEUP.md` (the Kaggle Writeup; its two figures and their scripts are in `figures/`).
2. **Check the numbers, no GPU:** open the Kaggle notebook (https://www.kaggle.com/code/cassinicraft/slipguard-reproduce-numbers). It re-derives 12 released values from the raw
   records in about a minute. Locally: `python notebooks/reproduce_numbers.py` (`REPRODUCE.md`).
3. **Get the corpus:** the Kaggle dataset (https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc, ≈ 3.3 GB) is this repository with PNC's episodes and
   contexts already in `data/pnc/`, plus the wheels and the discovery snippets. Download it as a complete checkout, or
   copy its `data/pnc/` into a clone (`USER_GUIDE.md` §4). One exception: Kaggle decompresses `.gz` files, so the
   weight audit's four `*.jsonl.gz` packs are stored there uncompressed. Install slipguard from the wheel in
   `release/package/wheels/` or from GitHub, not from that copy's `slipguard/` folder.
4. **Protect a Gemma 4 agent:** the Quickstart below, then `USER_GUIDE.md` §1 (repair proxy, history guard or strict
   parser).
5. **Choose a checkpoint:** audit it before serving (`USER_GUIDE.md` §3).
6. **Measure your own model:** run TranscriptLab on it (`USER_GUIDE.md` §4).
7. **Check any number:** `RESULTS.md` gives its file and registration status; `LIMITATIONS.md` says what the evidence
   does not show.

## Results, measured on public data

These are slipguard's effects. Rows marked *TranscriptLab* were measured with the benchmark; the others in the
challenge's agent harness or with slipguard's conformance and repair suites. Every row except two is decided by a pre-registered analysis (`PREREGISTRATIONS.md`). The exceptions: the
known-intent row is a deterministic result of the frozen conformance suite, and the pooled 92% is a pre-specified
descriptive estimate, computed after the outcomes were known (a logged deviation). Values are read from the result
files; `RESULTS.md` gives each one's file and status. End-to-end rows are Gemma-4-31B in the challenge harness.

| failure | stock | with slipguard |
|---|---|---|
| Malformed tool calls per agent episode (Google's 4-bit QAT checkpoint) | 1.76 (8 fresh replicates); first 2 replicates: 2.47 | **0.37** (0.21× [0.13, 0.35]); first 2: **0.27** (0.11× [0.06, 0.22]) |
| Episodes stuck in a malformed-call loop | 49 of 904; first 2: 14 of 226 | **3 of 904**; first 2: **0 of 226** |
| Tasks solved, 8 fresh replicates | 393 of 904 | **394 of 904**: non-inferior at −3 pp (difference +0.11 pp [−2.21, +2.43]) |
| Malformed tool calls per episode on the checkpoint the audit picks (cyankiwi AWQ), 6 fresh replicates | 0.50 | **0.29** (0.59× [0.36, 0.99]) |
| Malformed tool calls per episode under stock vLLM: Google QAT vs the audit's pick | 1.91 (Google QAT, 10 replicates) | **0.41** (AWQ, 2 replicates; 0.22× [0.11, 0.39]); 6 fresh AWQ replicates: **0.50** (0.26× [0.15, 0.44]) |
| Malformed tool calls per episode, one proxy component alone (4 of the 8 fresh replicates) | 1.56 | quarantine only **0.66**; IPD only **0.37**; full proxy **0.29** |
| Malformed tool calls per episode on the QAT weights' AWQ and NVFP4 exports (audit-flagged) | 3.81 and 4.85 | **0.19** and **0.27** |
| Same, on unquantized bf16 weights (not flagged) | 0.42 | 0.45: no measurable change |
| Wrong call delivered on ill-formed turns of known intent (all PNC turns; mostly `key=value` drift) | 188–216 of 218 | **0** (the strict parser refuses all 218) |
| Exact intent recovered on the 393 detectable injected slips | 0% (best baseline 69.0%) | **90.6%** (6.9% delivered silently wrong; see below) |
| Malformed next edit after one laundered call (TranscriptLab; 300 states × 3 runs pooled) | 20.0% (original history 0.9%) | quarantine as the proxy does it (recovered call, P8a) removes **92%** [86, 98] of the excess (runs: 98%, 93%, 86%) |
| Malformed next edit after one laundered call (TranscriptLab, registered run), by served checkpoint | 19.7% (Google QAT) | **10.3%** (AWQ served in float16; 12.0% served in bf16 like QAT); 0 of 300 with quarantine (P8a) |

**What these numbers do not say.**
- Most of the end-to-end gain is the ending of runaway loops (exploratory). In the first two replicates, the share of
  episodes with any malformed call fell only from 30.5% to 21.7%. The proxy does not end every loop: 3 of 904 fresh
  proxy episodes still got stuck.
- The eight fresh replicates show a smaller cut (0.21×) than the first two (0.11×), outside its predicted range
  (0.07–0.18). The registered rule tests the point ratio (≤ 0.30); the CI's upper end, 0.35, is above it.
- Resolve is non-inferior at −3 pp, not improved: the CI still allows a drop of up to 2.2 points, and it does not show
  a gain.
- Malformed-call counts cannot see a silently wrong repair. On the 393 detectable injected slips, IPD delivers 6.9%
  silently wrong calls (stock parser 1.1%); over all 600 injected slips, including those no parser can detect, 20.4%
  (stock 15.5%). End to end, the solved-task test is the only check against this.
- The audit-pick result compares AWQ with 10 QAT replicates, paired by task across runs, not by seed; 6 fresh AWQ
  replicates reproduce it (0.26×). On the AWQ checkpoint the proxy's cut is smaller than on QAT and only just
  significant (0.59× [0.36, 0.99], p 0.045); the first 2 AWQ replicates had missed the predicted cut (0.77× [0.44, 1.47]).
- All 113 end-to-end tasks come from four repositories: fastapi 61, rich 46, requests 5, httpx 1.
- Several registered predictions and checks failed. Examples: quarantine's removal fell below 90% in two of three reruns, and a 2-hour overload soak failed its timeout gates; slipguard's verified streaming is silent until a call is valid.
- The audit's flags predict end-to-end malformed calls across six checkpoints (PREREG_E_audit): flagged ones delivered
  1.9–4.8 per episode, unflagged ones 0.34–0.47. The gains are where the audit flags: on unquantized bf16 weights the
  proxy made no measurable difference.
- Everything is in `LIMITATIONS.md`.

## Quickstart

**No GPU?** These run on a CPU in seconds:
- `slipguard audit transcripts.jsonl --tools tools.json` flags laundered calls in your own logs (core install, standard
  library only; `USER_GUIDE.md` §2).
- `python notebooks/reproduce_numbers.py` re-derives released values from the raw records: 8 checks with this
  repository alone, all 12 inside the Kaggle dataset (`REPRODUCE.md`, Level 0). The same run as a Kaggle notebook:
  https://www.kaggle.com/code/cassinicraft/slipguard-reproduce-numbers.
- `python notebooks/quickstart.py` loads PNC and runs the strict parser and the audit on a sample.

**The evaluated configuration** (GPU; the repair proxy in front of stock vLLM 0.19.1):

```bash
pip install "slipguard[proxy-frozen,adk] @ git+https://github.com/aneeshm11/slipguard#subdirectory=slipguard"   # not on PyPI; or the wheel: see INSTALL.md
# [proxy-frozen] pins vLLM 0.19.1's CUDA build (several GB). Evaluated weights: Google's 4-bit QAT checkpoint;
# the audit recommends cyankiwi/gemma-4-31B-it-AWQ-4bit instead (USER_GUIDE.md §3). If the Hugging Face download is
# refused, accept the model's terms on its page and set HF_TOKEN.
vllm serve google/gemma-4-31b-it-qat-w4a16-ct --served-model-name gemma-4-31b --max-model-len 32768 \
    --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 --port 8000
slipguard proxy --backend http://127.0.0.1:8000/v1 --served gemma-4-31b --model-dir <local model dir> --logdir logs/ --port 8420
# --model-dir: a local directory with the checkpoint's tokenizer, chat_template.jinja and generation_config.json
# agents use http://127.0.0.1:8420/fullp/v1 as their OpenAI base URL
```

Other paths (history guard only, strict parser in vLLM, checkpoint audit, TranscriptLab on your model, PNC) are in
`USER_GUIDE.md`.

## Documentation

| file | for |
|---|---|
| `paper/WRITEUP.md` | the paper (the Kaggle Writeup) |
| `INSTALL.md` | installing from GitHub, a checkout or the wheels |
| `USER_GUIDE.md` | which component to use, and how |
| `RESULTS.md` | every headline result, read from its file, with registration status |
| `REPRODUCE.md` | integrity checks (seconds), re-analysis (minutes, CPU), re-generation (GPU) |
| `PREREGISTRATIONS.md` | the frozen registrations, verdicts (including failures), deviations, `tools/verify_preregs.py` |
| `LIMITATIONS.md` | what the evidence does not show |
| `SECURITY.md` | security-relevant parser defects, described by class only; how to obtain the withheld inputs |
| `DATASHEET.md` | PNC: collection, licences, intended uses |
| `MAINTENANCE.md` | versions, support, how results are kept in sync |

## Licence and citation

Code: Apache-2.0. Annotations and documentation: CC BY 4.0. Corpus text keeps each repository's licence (GPL
repositories excluded). slipguard is unofficial and not affiliated with Google. Cite with `CITATION.cff`.
