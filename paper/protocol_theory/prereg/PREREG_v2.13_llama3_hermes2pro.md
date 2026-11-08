# PREREG_v2.13 — a second Llama-tokenizer model: Hermes-2-Pro-Llama-3-8B via the released CLI 0.1.3

Written by the PI on 2026-11-08 after PREREG_v2.12's verdict and before any v2.13 job. Freeze time and sha256s are in PROGRESS.md.

## 1. Why
v2.12 found that Hermes-3-Llama-3.1-8B is HISTORY-SENSITIVE, but by retries rather than copies: 0 of 28 malformed edits copy the laundered call. That is one model. This registration asks two questions on a second Llama-tokenizer hermes model with a different base and fine-tune (NousResearch/Hermes-2-Pro-Llama-3-8B, rev f798274b, Llama-3 base):
- does the pattern hold?
- does CLI 0.1.3's request adapter work on another tokenizer?

GPU 4 is free; E_audit/E_comp are capped at 4 lanes, all in use.

## 2. Run
- **Identical to v2.12's run_llama_r2.sh** except the model dir, served name (hermes2pro-8b), output dir (experiments/transcriptlab_cli/run_v213_hermes2pro) and verdict output.
- **Command:** `transcriptlab run --format hermes --no-thinking --pool A1 --arms P0,P1,P6,P8a`; one resume pass; `transcriptlab report`.
- **Server:** vLLM 0.19.1 on GPU 4 :8384, serve_vllm.sh defaults, `--max-num-seqs 64`.
- **Corpus:** the registered (unmasked) PNC, as for every leaderboard row.
- **Guard (lesson from v2.12):** if more than 5% of the first pass's records are errors, the runner stops before the
  resume pass, report and verdict. The run is then NOT RUN, with the cause logged.
- **Pre-checks before freezing (CPU only):** a CLI dry run, and a 3-state render through the frozen prep step.

## 3. Verdict
experiments/v212/analyze_v212.py, reused unchanged. HISTORY-SENSITIVE iff the CI lower bound of copying RD or of imitation RD is above 0 (the Table 3 rule).

## 4. Pre-specified descriptive endpoint
The share of malformed P1L edits that are verbatim copies of the laundered call, from the frozen analysis's copy_check.

## 5. Predictions
| endpoint | prediction | basis |
|---|---|---|
| verdict | HISTORY-SENSITIVE (p ≈ 0.6) | |
| copying RD | +4 pp [0, +9] | |
| imitation RD | +4 pp [+1, +8] | |
| copy share | ≤ 10% | Hermes-3: 0/28 |

## 6. What gets written
- One docs leaderboard row (RESULTS, LIMITATIONS §5).
- Paper: only within the existing Table 3 footnote if the budget allows.
- A null is reported as a null.
