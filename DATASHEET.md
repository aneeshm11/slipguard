# Datasheet -- TranscriptLab / slipguard release data (v1.3)

*Structure follows Gebru et al., "Datasheets for Datasets" (2021). Every count here is computed from the released files: PNC from
`data/pnc/MANIFEST.json`, `grading.jsonl` and `episode_meta/`; the other components from their own summary files.*

## 0. At a glance

| component | role | what ships | size | where (v1.0) |
|---|---|---|---|---|
| **PNC** -- public natural corpus | primary data | full trajectories: every request, raw generated text, the calls exactly as vLLM 0.19.1 delivered them, tool results, per-episode metadata, SWE-bench grading | 1,181 episodes, 41,290 model turns, 3.0 GB | Kaggle PNC dataset `https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc`; this repository ships only its metadata (`data/pnc/`: MANIFEST, tasks, grading, template, licence) |
| **discovery** split | secondary | slip-local snippets + labels from the authors' own competition runs; full contexts committed by sha256 only | 8,160 slips (8,107 snippets + 53 pointer rows) | release dataset `release/package/v1.0/corpus/discovery/` (not in this repository; only its `build_summary.json` is here) |
| **replay labels** (discovery) | causal evidence | label-only generation records of the history interventions on discovery contexts (no text) | 25,763 records, 1,204 contexts | release dataset `release/package/v1.0/replay/discovery/` (not in this repository; only its `build_summary.json` is here) |
| **registered run records** (PNC states) | causal evidence | full generation records of the confirmatory batteries on public states (e.g. `rC31b_v2.jsonl`, `rCbf16_v2.jsonl`) | see `REPRODUCE.md` | this repository (`experiments/`) |
| **gold intent** | benchmark | 229 logged slips with retry-derived intent + 290 natural closures re-sampled at the same states | 519 natural slips | counts in this repository (`experiments/intent_decoding/results.json#gold`); the per-slip records derive from the authors' competition runs and are not in v1.0 |
| **QuoteStorm** | stress set | quote-dense payloads | 2,762 payloads + 290 pointer rows | release dataset `release/package/v1.0/quotestorm/` (not in this repository) |
| **conformance (public subset)** | test suite | parser inputs that are safe to publish (see 2.6) | 2,620 cases + 32 repros of the 13,612-input suite | this repository (`conformance/`) |

The release dataset (`release/package/v1.0/`) and the PNC dataset are separate downloads from the GitHub repository
(`https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc`); this repository does not contain their data files.

**Licence rule for every component.** Text ships only when its source has a known permissive licence (MIT, BSD-2/3,
Apache-2.0, ISC, PSF, Unlicense, CC0, ZPL, ...). Everything else ships as a pointer: dataset, task, repository, commit,
path, line span where available, and the sha256 of the withheld text.

## 1. Motivation

* **Purpose.** To measure how tool-calling agents read their own past actions, and to make tool-call failures of
  Gemma 4 measurable, testable and repairable. Concretely, the data supports:
  * history-intervention experiments (TranscriptLab);
  * parser conformance testing;
  * evaluation of repair and constrained decoding;
  * study of natural tool-call slips and of how serving stacks re-render them into the history ("laundering").
* **Creators and funding:** aneeshm11 (independent). No external funding.

## 2. Composition

### 2.1 PNC (primary)
* **What an instance is.** One episode is one agent attempt at one SWE-bench task. It is a sequence of model turns;
  each turn is one chat request with its response.
* **Model and serving.** `google/gemma-4-31b-it-qat-w4a16-ct` (revision 52f3f65b), thinking on. vLLM 0.19.1 with
  `--enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4`, through a faithful protocol proxy
  (`base` configuration: vLLM-identical rendering and parsing, no fixes).
* **Sampling.** The checkpoint's own: temperature 1.0, top-p 0.95, top-k 64. `max_tokens` 8,192, thinking budget 4,096
  tokens. Seeds per episode and per request: `MANIFEST.json` → `sampling.seed_policy`.
* **Harness.** The authors' own Apache-2.0 harness with a generic system prompt; no competition text.
  * One SWE-bench instance container per episode: network off, 4 GB memory, 2 CPU cores.
  * Two tool schemas. **S1:** `bash`, `read_file`, `edit_file`, `write_file`, `submit`. **S2** (OpenHands-style):
    `execute_bash`, `str_replace_editor`, `finish`.
* **Budgets.**
  * 50 tool calls or 45 minutes of wall time per episode, at most 100 model turns.
  * At most 3 consecutive nudges when a response has no delivered call.
  * Bash commands time out after 300 s; tool output is shortened above 10,000 characters.
  * Above 22,000 prompt tokens the oldest tool outputs are masked, down to 16,000 tokens. Tool calls are never modified.

| split | tasks | episodes | model turns | graded | resolved |
|---|---|---|---|---|---|
| `verified` / S1 | 400 SWE-bench Verified tasks, stratified by repository (seed 20261104) | 400 | 13,414 | 400 | 241 (60.2%) |
| `verified` / S2 | 100 of the same 400 tasks with the second schema | 100 | 3,239 | 100 | 66 (66.0%) |
| `swebench_test_ext` / S1 | 681 non-Verified SWE-bench test-split tasks of the same 10 repositories (first 681 of a stratified random order of 1,597 candidates) | 681 | 24,637 | 667 | 192 (28.8% of graded; 28.2% of episodes) |
| **total** | 1,081 distinct tasks | **1,181** | **41,290 turns** | **1,167** | **499** |

* **Repository mix (episodes).**
  * `verified` / S1: django 203, sympy 66, sphinx 38, scikit-learn 28, astropy 19, xarray 19, pytest 17, requests 7,
    seaborn 2, flask 1.
  * `verified` / S2: django 45, sympy 16, sphinx 14, scikit-learn 7, astropy 5, xarray 4, pytest 4, seaborn 2,
    requests 2, flask 1.
  * `swebench_test_ext`: django 263, sympy 132, scikit-learn 84, sphinx 60, pytest 44, xarray 38, astropy 31,
    requests 16, seaborn 8, flask 5.
* **How episodes ended.** 846 submitted and 331 hit the tool-call budget; 2 hit the no-tool-call limit and 2 ran out of
  context.
  * `verified`: 378 submitted, 122 budget stops.
  * `swebench_test_ext`: 468 submitted, 209 budget stops, 2 no-tool-call limits, 2 context stops.
* **Exclusions (operational and licence reasons).**
  * matplotlib: its instance images cannot be unpacked on the rootless container daemon used (operational).
  * pylint: GPL-2.0, excluded before generation (licence).
  * One extension task (`pydata__xarray-5662`) could not start: its first request exceeds the 32,768-token context.
  * Production ended early for a scheduled GPU maintenance stop. The extension split therefore holds the first 681 of
    its 1,597 ordered candidates. The 14 extension episodes that ended after the stop was announced were not graded
    (`attempt_resolved` is null); they are complete trajectories.
  * The Verified part is complete.
* **Grading.** SWE-bench's official evaluation scripts and log parsers, on the final patch of each episode
  (`grading.jsonl`).
* **Licences of the task code.**
  * BSD-3-Clause (astropy, django, seaborn, flask, scikit-learn, sympy); BSD-2-Clause (sphinx); Apache-2.0
    (requests, xarray); MIT (pytest).
  * Per-repository SPDX identifiers are in `MANIFEST.json` → `licenses`.
  * SWE-bench Verified and the SWE-bench test split declare no dataset licence; the SWE-bench project code is MIT.
  * Problem statements are GitHub issue text, redistributed with their URLs as in SWE-bench.
* **Laundered calls.** The harness re-sends every assistant turn exactly as delivered, so malformed calls stay in the
  history as the stock parser delivered them. This is natural, as in every OpenAI-compatible client, and it is what
  the corpus is for.

### 2.2 discovery split (secondary)
* **What it holds.** 8,160 tool-call slips from the authors' own Kaggle competition runs (June-5 chat template, vLLM
  0.19.1, the competition's official harness): 8,107 snippets with text and 53 pointer rows (47 from unlicensed
  repositories, 6 MPL-2.0).
  * 4,239 snippets come from Gemma-4-31B-it QAT.
  * 3,868 come from nine fine-tuned adapters, pseudonymous ids `ft-A..I`.
* **A snippet** is slip-local evidence only:
  * the call as emitted, the delivered arguments and their canonical re-renders;
  * labels, position, the tool's parameter schema, the edited file's last `read_file` output, and the names and
    status of the previous five calls.
* **Not included:** system prompts, user messages, full histories, reasoning, run or adapter names.
* **Excluded:** 250 slips produced under a team member's private system prompt (no consent).
* **Full contexts:** 8,091 redacted contexts are committed by sha256 (root `136d61f7…`, `contexts_commitment.json`).
  Their release is not planned.

### 2.3 Replay labels and run records
* **Discovery replays: labels only.** 25,763 generation records of the history interventions on 1,204 discovery
  contexts (28 frozen batches, `batches.json`).
  * Fields: arm, dose, model, template, thinking, sampling, seed, prompt length, judge verdict, edit / no-edit, and
    copy class.
  * No generated text and no prompts.
  * Contexts are pseudonymous ids. 1,072 are committed by sha256 (root `d379b4ea…`). The split also includes labels
    for 132 contexts whose underlying text is excluded for consent reasons.
* **Confirmatory and later batteries on PNC states: full records.** These include every registered run cited in
  `RESULTS.md`, such as `experiments/contagion/out/main/rC31b_v2.jsonl` and `rCbf16_v2.jsonl`, and the TranscriptLab
  CLI runs in `experiments/transcriptlab_cli/`. Every record that `tools/reproduce_level1.sh` reads for these rows is
  included.
* **End-to-end harness runs: analysis outputs only.** The per-task records, transcripts, patches and proxy logs of
  the end-to-end runs (`experiments/endtoend/runs/`, `logs/`, `plans/`) are not included. They hold the competition's
  task text, its sample system prompt and repository code, and they are not redistributed. The registered analysis outputs (`experiments/endtoend/analysis/*.json`) are included.

### 2.4 Gold intent
* 229 logged base-model slips whose intended `old_string` is recovered from a later clean retry. Fine-tune records
  are excluded. The gold cut is the whole look-alike run in 219 cases and a composite run in 10.
* 290 natural closures re-sampled at the first 105 of the same states.
* In all, 519 natural slips with known intent (`experiments/intent_decoding/results.json` → `gold`).

### 2.5 QuoteStorm
3,052 quote-dense payloads from SWE-rebench, SWE-rebench-V2, SWE-bench-Live, SWE-bench Verified and 600 adversarial
splices.
* 2,762 ship with content: MIT 1,216, Apache-2.0 738, BSD-3-Clause 659, BSD-2-Clause 78, Unlicense 23, ZPL-2.1 19,
  ISC 13, CC0-1.0 8, WTFPL 3, PSF-2.0 2, NCSA 1, AFL-3.0 1, MIT OR Apache-2.0 1.
* 290 ship as pointers:
  * 165 unlicensed or unknown, incl. 112 SWE-bench-Live payloads (no dataset licence);
  * 120 under custom licences;
  * 4 AGPL-3.0;
  * 1 GPL-2.0-or-later.

### 2.6 Conformance suite, public subset
* The suite has 13,573 generated cases and 39 minimal repros. The public subset keeps 2,620 cases and 32 repros
  (`conformance/SUMMARY.json`).
* **Dropped:**
  * cases re-assembled from discovery logs;
  * every case that on any runtime target hung, raised, produced an extra call, or took more than 1 s;
  * control-token-in-string and nested-bracket inputs, and the withheld security repros;
  * cases carrying argument text from a non-permissive source.
* Tool descriptions are removed.
* Each case carries its per-target outcomes and class tags.

## 3. Collection process
* **PNC:** generated 2026-11-04 15:25-22:52 UTC on up to three H100 servers. All servers used the same checkpoint and
  flags; `episode_meta.server` records which one served each episode. Deviations from the plan are logged in
  `experiments/pnc/DEVIATIONS.md`.
* **Discovery split:** the authors' competition runs. Official harness `swegemma` 0.2.11 → google-adk → LiteLLM →
  vLLM 0.19.1, June-5 template.

## 4. Preprocessing and labelling
* **Labels.** Labels come from frozen, hash-pinned judges, not from human annotation.
  * The canonical malformed definition is `DEFINITIONS.md` → M-A v1.
  * The judges' code is listed in the freeze manifests that `tools/verify_preregs.py` checks.
  * No human inter-annotator audit was run for v1.3.
* **Personal data.** PNC tool outputs echo upstream repository files and git output, which contain the e-mail
  addresses of the repositories' developers. **These developer e-mail addresses are masked as `<email>` in the
  released corpus**, and the same mask (same rule) is applied to the PNC- and discovery-derived run records and
  conformance inputs in this repository. The corpus metadata in `data/pnc/` is byte-identical to the released corpus
  (sha256-pinned in `MANIFEST.json`): its only address-like strings are synthetic URL credentials inside SWE-bench test
  node ids in `grading.jsonl`, left unchanged so grading stays joinable with SWE-bench. No other personal data was
  found: a corpus-wide scan finds 0 local usernames, hostnames, host IPs or secret/key patterns.
* **Effect of the masking on results (PREREG_v2.11).**
  * The paper's registered TranscriptLab numbers were produced on the unmasked corpus (v1.0, not released). 43 of the 300
    A1 states contain a masked address.
  * Rerun on this released corpus: copying +15.0 pp [10.9, 19.5] (registered +18.3 [13.6, 23.2]) and P1 16.7% (registered
    19.7%). The pre-registered check therefore says masking changes the result: P1 McNemar p = 0.022.
  * A second masked run (PREREG_v2.11b, descriptive) gave copying +16.7 pp [12.2, 21.3] and P1 18.0%. On the 43 masked
    states P1 was lower in both masked runs (13/43 each, vs 17 and 16 unmasked), so masking plausibly lowers P1 slightly
    on the states it changes.
  * See `LIMITATIONS.md` §7.
* **Redaction (repository files).** Every file in this repository passes the release privacy rules:
  * host paths, user and host names and secret-like strings are redacted;
  * discovery identifiers (runs, adapters, logs, contexts) are replaced by the same pseudonyms everywhere.
  The residual gate finds 0 hits on the public tree.

## 5. Uses
* **Intended:**
  * parser conformance and fail-loud testing;
  * repair and constrained-decoding benchmarks (gold intent, QuoteStorm);
  * history-quarantine and contagion studies (PNC, replays);
  * analysis of natural tool-call failures;
  * fuzzing seeds.
* **Out of scope, with warnings:**
  * **Training on PNC trains on stock-stack trajectories.** These contain laundered calls: malformed calls that the
    stock parser delivered and that were re-rendered into the history as if well-formed. A model fine-tuned on them
    learns exactly the copying behaviour the paper measures. Filter or quarantine those turns first: the judge
    labels and `slipguard.history` identify them.
  * **Training on PNC trains on SWE-bench Verified and SWE-bench test tasks:** their issues, code and the agent's
    patches. Any model trained on PNC is contaminated for those benchmarks. Do not report SWE-bench results for such a
    model without saying so.
  * Estimating leaderboard or resolve-rate effects from the discovery split: it is observational and confounded.
  * Reproducing a competition team's strategy, or re-identifying redacted people, hosts or runs.

## 6. Distribution
* **Channels:** the Kaggle dataset https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc and the GitHub repository
  https://github.com/aneeshm11/slipguard. No DOI.
* **Licences:** code Apache-2.0 (`LICENSE`); labels, documentation and statistics CC BY 4.0 (`LICENSE-DATA.md`);
  third-party text under its upstream SPDX licence. For PNC the licence is recorded **per repository** in
  `data/pnc/MANIFEST.json#licenses.repositories_spdx` (records carry the repository, from which the licence follows);
  QuoteStorm records carry a per-record licence; the conformance inputs drawn from discovery argument text keep only
  permissive-licence records but do not carry a per-case SPDX identifier. Pointers for everything non-permissive. See
  `NOTICE`.
* **Security.** Inputs and reproduction reports for the four security-relevant parser defect classes (injection from
  strings, quadratic slowdown, recursion crash, infinite-loop hang) are withheld from v1.0 and added in v1.x after the
  fixes (see `SECURITY.md` and `WITHHELD.json#security_withheld`).

## 7. Maintenance
* **Maintainer and contact:** aneeshm11, through the repository's issue tracker.
* Errata and takedown requests go through the repository's issue tracker or the contact above. Requests are answered
  within 7 days.
* Versions are tagged.
* Adding the discovery contexts that are committed by hash is not planned.

