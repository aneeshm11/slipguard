# PREREG_v2.11 — does masking e-mail addresses in the released PNC change TranscriptLab's result?

Written by the PI on 2026-11-07 (freeze time and sha256s in PROGRESS.md), before any v2.11 job.

## 1. Why
The release-hygiene review (R4) found real developer e-mail addresses in PNC. The released copy masks them as `<email>`:
- release/package/pnc_v1.1_masked/, MANIFEST sha256 f64aebfa…;
- report: release/package/PNC_MASKING_REPORT.md.

43 of the 300 A1 TranscriptLab states contain a masked address. The registered TranscriptLab results used the unmasked states. A user who reruns the benchmark on the released corpus renders 172 of the 1,200 prompts differently (43 states × 4 arms). This check shows whether that changes the benchmark's result.

## 2. Run (R-MASK)
- **Released CLI:** release/transcriptlab 0.1.2, with PREREG_v2.8's arguments plus the masked corpus:

  ```bash
  transcriptlab run --base http://127.0.0.1:<port>/v1 --model gemma-4-31b --tokenizer <QAT-ct dir> --pool A1 \
      --arms P0,P1,P6,P8a --corpus <masked copy> --meta tmp/wp_pnc/meta_S1_masked.jsonl \
      --out experiments/transcriptlab_cli/run_v211_masked --python env_gemma
  ```

  The meta file is the registered meta_S1.jsonl with contexts_file re-pointed at the masked copy. Byte offsets are valid, because changed lines are space-padded. Then one resume pass, then `transcriptlab report`.
- **Server:** Gemma-4-31B QAT-ct, vLLM 0.19.1, C1's server arguments (serve_vllm.sh defaults + `--max-num-seqs 64` + gemma4 parsers), on GPU 4 once the user's gate holds for 10 minutes.
- **Seeds:** the registered per-state seeds (md5 of the state id), the same as C1 and v2.8.

## 3. Analysis (experiments/contagion/scripts/analyze_v211_masked.py, frozen with this document)
- **Statistics:** copied verbatim from analyze_v27_robustness.py (f68bc12d), via analyze_v28_cli.py: judge indicator, task-cluster bootstrap B = 2000 (seed 20261106), exact McNemar.
- **Comparator:** C1 (out/main/rC31b_v2.jsonl). Registered: copying +18.33 pp [13.61, 23.16].
- **Verdict:** **MASKING DOES NOT CHANGE THE RESULT** iff both hold:
  - (a) the masked run's copying RD point lies inside C1's registered 95% CI [0.1361, 0.2316];
  - (c) the two-sided exact McNemar for P1, masked vs C1, has p ≥ 0.05.
  - Otherwise **MASKING CHANGES THE RESULT**, with the failing condition named.
- **Not gated, reported:** quarantine removal. v2.8 showed it is the least stable score: 0.85 on an unmasked rerun with the same seeds.
- **Descriptive:**
  - on the 43 affected states: P1 and P0 counts, masked vs C1 vs the v2.8 unmasked CLI run (run_v28);
  - on the 257 unaffected states: the same, as a reference for run-to-run noise.

## 4. Predictions
- Copying ≈ +18 pp, inside the CI.
- P1 McNemar p ≥ 0.05.
- On the affected states, the masked-vs-C1 disagreement is no larger than on the unaffected ones (vLLM noise only).

## 5. What gets written
- If MASKING DOES NOT CHANGE THE RESULT: one sentence in the datasheet and docs: "the released corpus masks e-mail addresses; rerunning TranscriptLab on it gives copying X [CI] (registered +18.3)".
- If it changes the result: the numbers go into LIMITATIONS, and the release documents which corpus version reproduces which number.
