# PREREG_v2.11b — a second masked-corpus run: is the v2.11 P1 drop masking or run-to-run noise? (descriptive)

Written by the PI on 2026-11-08 after PREREG_v2.11's verdict (MASKING CHANGES THE RESULT; P1 16.7% vs 19.7%, McNemar
p = 0.022) and before any v2.11b job. Freeze time and sha256s are in PROGRESS.md.
**This registration does not change v2.11's verdict, which stands as registered.**

## 1. Why
- v2.11's exploratory checks found that 5 of its 9 net P1 losses are on states whose prompts did not change. Also, vLLM sampling under fixed seeds is not reproducible: only 665 of 1,028 unchanged-prompt generations were byte-identical.
- One masked run cannot separate masking from noise. A second run, with the same masked corpus, seeds and server arguments and a fresh server, gives a second draw.
- This informs the release note and the user's decision on masking.
- GPU 4 is free. E_audit/E_comp are capped at 4 lanes, all in use.

## 2. Run (R-MASK2)
Identical to v2.11's run_masked_r2.sh except the output directory (experiments/transcriptlab_cli/run_v211b_masked) and the analysis output.
- **CLI:** transcriptlab 0.1.3. For this registered gemma4 path the CLI's commands are unchanged from 0.1.2: the request adapter applies only to new models, and `--corpus` is given the manifest file.
- **Server:** GPU 4, :8384, C1's server arguments, a fresh process.

## 3. Analysis (descriptive only; no verdict; experiments/v211b/pool_v211b.py, frozen with this document)
- **(i)** analyze_v211_masked.py, unchanged, on the second run, giving the same fields as v2.11. Its "verdict" field is printed but labelled "replicate (not a registered verdict)".
- **(ii)** pool_v211b.py: P1 counts on the 43 affected and the 257 unaffected states for four runs:
  - masked run 1 and masked run 2;
  - C1 and v2.8 (unmasked, same seeds).
  The v2.7 seed sets' overall P1 (20.0%, 20.3%; unmasked, other seeds) enters as a range reference only.
- **(iii)** Pooled P1 rates: masked (2 runs, 600 state-draws) vs unmasked same-seed (C1 + v2.8, 600).
- **(iv)** Run-to-run range of P1 over the four unmasked runs (C1 19.7%, v2.8 19.3%, v2.7 seed sets 20.0% and 20.3%).

## 4. Pre-specified reading
| outcome | reading |
|---|---|
| Masked run 2's P1 within the unmasked runs' range (19.3–20.3%) and its affected-state P1 within C1/v2.8's (16–17 of 43) | v2.11's drop is consistent with run-to-run noise |
| Run 2's P1 ≤ 17.0% again | the drop replicates, and masking plausibly lowers P1 by about 3 pp |
| Otherwise | inconclusive |

In every case the release documents both masked runs.

## 5. Predictions
Masked run 2 P1 ≈ 18–19%; copying ≈ +16–18 pp.
