# PREREG_v2.12 — TranscriptLab on a Llama-family model (Hermes-3-Llama-3.1-8B), via the released CLI

Written by the PI on 2026-11-08 (freeze time and sha256s in PROGRESS.md), before any v2.12 job.

## 1. Why
- **Coverage gap.** The leaderboard (paper Table 3) covers Gemma 4, Qwen3/3.5/3.8, gpt-oss and Devstral (Mistral), but no Llama-family model. Meta's own Llama-3.1-8B-Instruct is gated, so we use NousResearch/Hermes-3-Llama-3.1-8B: ungated, rev 896ea440, Llama-3.1 weights fine-tuned for the hermes tool format.
- **CLI generality.** This also exercises the released CLI on a model family that was never used in development.

## 2. Pre-checks (CPU, done before freezing)
- `transcriptlab run --format hermes --model hermes3-8b --tokenizer <dir> --no-thinking --dry-run`: 1,200 jobs, frozen code 16/16.
- A 3-state render through the frozen prep step: the model's official tool_use chat template, ChatML turns, `<tool_call>` JSON, tool role with `<tool_response>`, the P1L laundered call followed by the missing-argument error. About 12k tokens per prompt.

## 3. Run (R-LLAMA)
- **Server:** vLLM 0.19.1 on GPU 4 after PREREG_v2.11's run, gated by the user's rule (free for 10 min). Model dir models/community/NousResearch_Hermes-3-Llama-3.1-8B, served name hermes3-8b, serve_vllm.sh defaults (max-model-len 32768). Raw /v1/completions only.
- **Command:**

  ```bash
  transcriptlab run --format hermes --base … --model hermes3-8b --tokenizer <dir> --no-thinking --pool A1 \
      --arms P0,P1,P6,P8a --out experiments/transcriptlab_cli/run_v212_hermes3
  ```

  Then one resume pass, then `transcriptlab report`, which runs X's frozen analyze.py.
- **Corpus:** the registered (unmasked) PNC, as for every other leaderboard row.

## 4. Verdict (experiments/v212/analyze_v212.py, frozen with this document; reads the report's analysis.json)
- **HISTORY-SENSITIVE** iff the 95% CI lower bound of copying RD(P1L − P0) or of imitation RD(P6 − P0) is above 0. This is the paper's Table 3 rule (descriptive, unadjusted).
- Otherwise **NOT HISTORY-SENSITIVE (not detected)**.
- Reported alongside: both RDs with CIs, quarantine removal, error counts.

## 5. Predictions (before data)
| endpoint | prediction | basis |
|---|---|---|
| copying | ≈ 0 pp [−2, +3] | no non-Gemma model copied: 0 of 7 |
| imitation | +2 pp [−1, +6] | Qwen3-8B +4.7 |
| verdict | uncertain (p ≈ 0.4 of HISTORY-SENSITIVE) | |

## 6. What gets written
- One leaderboard row in RESULTS.md and the docs.
- Paper Table 3 only if the word budget allows after the E_audit/E_comp fills.
- A null is reported as a null.
