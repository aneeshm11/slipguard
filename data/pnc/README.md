# PNC: a public corpus of natural Gemma 4 agent trajectories on SWE-bench

PNC holds natural, unedited agent trajectories of `google/gemma-4-31b-it-qat-w4a16-ct` (thinking on, the checkpoint's
default sampling) solving SWE-bench tasks with a small, generic tool-calling harness. Every model turn is recorded
with the exact request, the raw generated text (including the native `<|tool_call>…<tool_call|>` protocol), the calls
exactly as vLLM 0.19.1's gemma4 parser delivered them, and the tool results that went back to the model. The corpus
was built as the confirmation set for a pre-registered study of the Gemma 4 tool-call protocol (string delimiters,
look-alike closers and history re-rendering). It contains no data from any private competition.

## Contents
| path | what |
|---|---|
| `episodes/<instance_id>__<schema>.jsonl` | one line per model turn (chat request) of one episode |
| `episode_meta/<episode_id>.json` | per-episode metadata: image and digest, repository state, end reason, timings, final patch, optional grading log reference |
| `tasks.json` | task population, sampling procedure, run order, images |
| `contexts/P-swebench-31b-{S1,S2}-v1/` | replay contexts in a fixed schema: `manifest.json`, `contexts.jsonl` (requests whose response's first call is the edit tool), `raw_texts.jsonl`, `outcomes.jsonl`, `requests.jsonl` (every request), `chat_template.jinja` |
| `grading.jsonl` | optional SWE-bench grading of the final patches (official eval scripts and parsers) |
| `chat_template.jinja` | the checkpoint's chat template used for every request |
| `MANIFEST.json` | sha256 of every file; model, server, proxy and harness provenance; sampling; seeds; tasks; images; licenses |

Keys: `episode_id = <instance_id>__<schema>`; `turn_index` = 0-based request index within the episode;
`split` = `verified` (SWE-bench Verified sample) or `swebench_test_ext` (SWE-bench full test split, non-Verified);
`schema` = `S1` (`bash`, `read_file`, `edit_file`, `write_file`, `submit`) or `S2` (`execute_bash`,
`str_replace_editor`, `finish`).

## How it was made
See `experiments/pnc/README.md` in the project repository (harness, prompts, proxy, budgets, masking, sampling,
seeds, task sampling, provenance). In short: one SWE-bench instance container per episode (network off, 4 GB),
50 tool calls or 45 minutes per episode, observation masking above 22k prompt tokens (tool calls never modified),
temperature 1.0 / top-p 0.95 / top-k 64, thinking budget 4,096 tokens, vLLM 0.19.1 rendering and parsing through a
faithful protocol proxy.

## Privacy
This is the public release copy (version 1.1-masked). Developer e-mail addresses that came from upstream source files the agent read (copyright headers, author lists, package and git metadata), and every other e-mail address in the records (test fixtures, mailing lists), are masked as the literal `<email>` in every text field (39,775 occurrences; Python decorators such as `@pytest.mark.parametrize` are unchanged). The rule, the scope and the counts are in `MANIFEST.json` → `privacy`. No other personal data was found by the scan; names of upstream authors in copyright and license headers are kept, as those licenses require attribution. Token counts and `proxy.prompt_sha` describe the original unmasked text. To request removal of any further content, contact the maintainer via the Kaggle dataset page.

## Licenses
Our annotations and corpus structure: CC BY 4.0. Code: Apache-2.0. Third-party content keeps its license (see
`LICENSE.md` and `MANIFEST.json`: per-repository SPDX identifiers). GPL-licensed repositories were excluded.

## Known limitations
- Natural trajectories of one model and one harness; tool-output texts and prompts are ours (generic).
- Episodes ran on up to three H100 servers with the same checkpoint and flags; `episode_meta.server` records which.
- Sampling is seeded per request, but vLLM is not batch-invariant, so re-running does not reproduce outputs bitwise.
- Masked (older) tool outputs do not show their original status; `contexts.jsonl` carries `history_tool_status`.
