# PREREG_v2.11 result: masked released corpus vs the registered TranscriptLab run (C1)
Run 2026-11-08 04:13–05:04 UTC on GPU 4 via run_masked_r2.sh (deviation 1: the corpus argument). Analysis ran once, at 05:04:27.
Files:
- analysis: experiments/contagion/out/confirmatory/v211_masked_analysis.json
- run: experiments/transcriptlab_cli/run_v211_masked/

## Registered verdict: **MASKING CHANGES THE RESULT**
The failing condition is (c), the P1 McNemar.

| | masked CLI run | C1 (registered) |
|---|---|---|
| copying RD(P1 − P0), B = 2000 task-cluster bootstrap | **+15.0 pp [10.9, 19.5]** | +18.3 [13.6, 23.2] (this analysis's recomputation: [13.7, 23.4]) |

- **(a) passes:** the masked copying point is inside C1's registered CI [13.61, 23.16].
- **(c) fails:** P1, masked vs C1, is 16.7% vs 19.7%: RD −3.0 pp [−5.4, −0.7], discordant 11 (C1 only) vs 2 (masked only), exact McNemar two-sided p = 0.022.

Arm rates (n = 300 states each):

| arm | masked | C1 |
|---|---|---|
| P0 | 1.7% | 1.3% |
| P1 | 16.7% | 19.7% |
| P6 | 7.7% | 9.0% |
| P8a | 2.7% | — |

- Imitation RD(P6 − P0): +6.0 pp [3.0, 9.5] (C1 +7.7 [4.3, 11.6]).
- Quarantine removal (not gated): 0.93 [0.78, 1.09] (C1 0.98 [0.88, 1.10]).

## Descriptive (registered as descriptive)
| | masked | C1 | v2.8 (unmasked CLI rerun) |
|---|---|---|---|
| P1 on the 43 affected states | 13/43 | 17/43 | 16/43 |
| P1 on the 257 unaffected states | 37/257 | 42/257 | 42/257 |

Judged disagreement vs C1 (all four arms):

| | affected (172 jobs) | unaffected (1,028 jobs) |
|---|---|---|
| masked vs C1 | 10 | 19 |
| v2.8 vs C1 (pre-data smoke) | 9 | 21 |

## Exploratory (after the verdict; labelled; does not change the verdict)
- **Prompts:** prompt token counts differ from v2.8 on exactly 172 jobs (43 states × 4 arms) and are equal on the other 1,028.
- **Sampling:** seeds and sampling parameters are equal on all 1,200 jobs.
- **Server:** arguments identical to v2.8 apart from the port; the chat template is byte-identical (sha256 ae53464b…).
- **Run-to-run noise:** on the 1,028 jobs with unchanged prompts, only 665 outputs are byte-identical to v2.8 (vLLM batching is not deterministic under fixed seeds).
- **Reading:**
  - 5 of the 9 net P1 losses are on states whose prompts did not change, so run-to-run noise contributes at least part of the drop. The affected-state disagreement (10/172) is the same as an unmasked rerun's (9/172).
  - This does not overturn the registered verdict. With one masked run we cannot separate masking from noise, and the registered test says P1 moved.

## What this changes (PREREG_v2.11 §5)
- **LIMITATIONS and the release state which corpus reproduces which number:**
  - the registered numbers come from PNC v1.0 (unmasked; not released, for privacy);
  - the released v1.1 (masked) gives copying +15.0 pp [10.9, 19.5], P1 16.7%, removal 0.93 [0.78, 1.09].
- **The paper's claims survive in kind:** Gemma copies the laundered call, and quarantine removes most of the excess. The point estimate on the released corpus is about 3 pp lower.

## Addendum: PREREG_v2.11b, a second masked run (descriptive; registered before the run; 06:33 UTC)
- Files: experiments/contagion/out/confirmatory/v211b_masked_analysis.json, v211b_pooled.json; run experiments/transcriptlab_cli/run_v211b_masked/.
- **Masked run 2:**
  - P1 18.0% [13.8, 22.6]; copying +16.7 pp [12.2, 21.3]; imitation +7.7 pp [4.3, 11.5]; removal 0.92 [0.78, 1.06].
  - P1 vs C1: −1.7 pp [−4.0, +0.7], McNemar p = 0.27. As a replicate check (not a verdict) both of v2.11's conditions hold.
- **Pre-specified reading: INCONCLUSIVE.** 18.0% is neither within the unmasked range (19.3–20.3%) nor ≤ 17.0%.

| P1 | masked 1 | masked 2 | C1 | v2.8 |
|---|---|---|---|---|
| 43 affected states | 13 | 13 | 17 | 16 |
| 257 unaffected states | 37 | 41 | 42 | 42 |

Pooled (2 masked runs vs C1 + v2.8):

| | masked | unmasked |
|---|---|---|
| affected | 26/86 | 33/86 |
| unaffected | 78/514 | 84/514 |
| all | 17.3% | 19.5% |

- **Reading (descriptive):**
  - On the masked states the drop replicates (13 and 13 vs 17 and 16).
  - On the unchanged states run 1's drop did not (41 vs 42, 42); that part was noise.
  - So masking plausibly lowers P1 a little on the states it changes: about 1–3 pp overall, copying +15.0 and +16.7 pp vs +18.3 registered.
- **v2.11's registered verdict (MASKING CHANGES THE RESULT) stands.**
