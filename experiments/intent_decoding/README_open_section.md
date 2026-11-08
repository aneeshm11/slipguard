
## 6. Open issues and limitations (honest list)
1. **Structure, not content.**
   - IPD restores the intended protocol structure; it does not fix JSON-string-mode content (literal `\n` / `\"`
     escapes inside raw strings).
   - The harness's "unescaped" fallback sometimes applies such edits anyway.
   - Forcing `<|"|>` at a drifted opener ((i+)) does pull the regenerated value back to raw mode.
2. **(i) regenerates the suffix.** The re-emitted arguments can differ from the original suffix, which was produced
   in a corrupted state. It can occasionally add a benign duplicate key, which is census-clean but strict-invalid.
3. **Forced edits.** Where the model chose another tool, E1 forces `edit_file`. Natural-only results and the unforced
   natural-next-call analysis are reported separately.
4. **E4B fails differently.**
   - Its failures are mostly opener drift, Python-kwarg drift (`filepath="x"`), JSON quoted-key slips and runaway
     strings; it has few closer slips.
   - IPD's census reduction on E4B is therefore lower than on 31B. Opt-in `kwarg`/`qkey` rules exist (`(i++)`,
     `extend_residual.py`) but are not part of the deployed default.
   - E4B makes essentially no copy-task slips (0/262).
5. **G1 selection.**
   - The retry-derived intent matches retry.new_string == payload-without-closer. The gold cut is the whole run for
     219/229 records and partial for 10 (composite runs).
   - T1/(ii) on G1 use an assumed tail; only resuming decoders are evaluated on the real lost tail.
6. **12B not run.** :8301 is workstream A's lane; the gold slips come from 31B (E4B rarely slips).
7. **Composite closers are intrinsically ambiguous** (P4). The disjoint prior has never seen some of them, and
   τ-abstention trades coverage for precision.
8. **Concurrency budget.** Prefix pins count toward the ≤32 in-flight cap per server, which limited throughput.
9. **E4B ON** has 1,197 of 1,200 samples: 3 contexts lost their second sample at a restart.
10. **Arms 11/12 are onset comparisons.**
    - Exemplar ON: the first 87 records carry the full inline head-to-head; after the 15:53 restart the rest carry
      onset + (i) only.
    - Exemplar OFF: the first 27 records carry the full inline head-to-head; the rest are onset-only.
    - The July runs never had the inline head-to-head; they have (i)/(ii).
    - All four arms completed before the lane hand-back (18:13 UTC): exemplar ON 600/600, exemplar OFF 599/600,
      July ON 600/600, July OFF 595/600 samples. Missing samples are second samples lost at restarts (item 14).
11. **Guard trigger.** At 15:52 UTC the :8302 guard (KV > 90% twice) stopped three jobs. They resumed at ≤32 in
    flight, and no sample was lost beyond in-flight work.
12. **G1R stopping rule.** G1R was stopped at 417 samples (about 105 of 229 states) once the gold set reached
    ≥ 500 natural slips: G1 229 + G1R 290 = 519. These are the first states in corpus order, not a random subset.
13. **"Thinking OFF" still produces a thought.** With `enable_thinking=False` (June template), the 31B still opens a
    thought channel in 583/587 OFF call samples. The median thought is 682 characters, against 952 with thinking ON.
    So ON and OFF differ in the template's thinking flag and in thought length, not in whether a thought is present.
    The replayed histories come from thinking-ON runs: 298/300 OFF contexts render earlier thoughts into the history
    (the OFF prompt itself has no `<|think|>` flag). The model emits a thought in 579/583 samples of those contexts,
    and in 4/4 samples of the two contexts without one.
    The July template behaves the same way with thinking OFF: 584/588 call samples, median 685 characters. PREREG_v2.1
    describes A's thinking-OFF battery as emitting the call with no thought. In B's replays, `enable_thinking=False`
    alone did not suppress the thought.
14. **Lost samples.** The June OFF and July OFF replays each have 595 of 600 samples (300 contexts × 2). A restart
    resumes by (context, seed), so a context whose first sample was already written loses its in-flight second
    sample. The paired onset comparisons use per-context rates over the samples present.
15. **Discovery prompts are 1 token short of the logged prompts.** System content was passed as a string instead
    of text parts, which drops one space before the tool declarations (§3.1). This holds for all 600 gate contexts.
    It affects every June-template discovery replay (E1, arms 11/12, G1, G1R). It does not affect the confirmatory
    runner.
16. **G1 seeds are not reproducible.** `rs279.py` drew each record's seed from Python's salted `hash(id)`, so the
    exact G1 samples cannot be regenerated. The statistics stand. The proxy-equivalence replay of G1 (§8.3) uses
    sha256-based seeds and reproduces the 227/229 exact-intent result.
17. **vLLM parser hang.** vLLM 0.19.1's `_parse_gemma4_array` can loop forever on some malformed arrays. One fresh live
    proxy sample triggered it inside B's census judge. The proxy-equivalence analysis installs the same no-progress
    patch that workstreams A and E use. The discovery analyses completed without hitting it.
