# Reproducing the results

There are three levels of reproduction. The first two need only a CPU and no model weights; the third needs GPUs.

| level | what it shows | needs | time |
|---|---|---|---|
| 0. Integrity | the registrations, frozen code and released results are what the paper cites | Python 3.10+, standard library | seconds |
| 1. Re-analysis | the frozen analyses, re-run on the released run records, give the released results | CPU | minutes |
| 2. Re-generation | new model generations give results within the registered intervals | vLLM, Gemma 4 weights, GPUs | hours |

Paths are relative to the repository root. The two trees give slightly different counts, so each "verified result"
names its tree:
- **public tree**: this repository as released (the library at `slipguard/`; files the export had to edit are listed
  with their frozen hashes in `FROZEN_EXPORT_PINS.json`, files that cannot be public in `WITHHELD.json`);
- **project tree**: the data holder's working tree (the library at `release/lib/`), on which the analyses ran.

The tools detect the layout themselves. Public-tree values were checked on 2026-11-07 on the public export with the
files of the Nov 7 registrations added (PREREG_E_awq2, E_audit, E_comp and their result files); every row is re-run on
the final export and logged in `VERIFY_LOG.md`.

## Level 0: integrity (CPU, seconds)

| command | checks | verified result, public tree | project tree, if different |
|---|---|---|---|
| `sha256sum -c --quiet TREE_MANIFEST.sha256` | every shipped file against the export's manifest | exit 0, no output | (public tree only) |
| `python tools/verify_preregs.py --root .` | each registration document and frozen code file against the hash recorded at its freeze | `PASS: 0 unexplained problem(s)`, exit 0. The last lines tally it: 25/25 documents (13 of them through their recorded export edits); 173 manifest entries match (83 through export edits: host paths, privacy redactions and the withheld-material / competition-text redactions), 47 are withheld with their hashes listed, 8 differ for logged reasons (`PREREGISTRATIONS.md`); 26/26 files frozen with PREREG_v2.7 and later | 25/25 documents (23 byte-identical, 2 by frozen prefix); 220 manifest entries and 26/26 later frozen files match; the same 8 differ for logged reasons; exit 0 |
| `python tools/make_results_md.py --root . --out RESULTS.md --check` | every headline value is read from its result file; none is typed by hand | 63 results, 0 unresolved, UP TO DATE (`RESULTS.md` is regenerated from this tree at export, so its hash table lists the files shipped here) | same: 52 results, 0 unresolved |
| `python release/build_numbers.py --strict` | every number in the paper against its source file#key | paper gate PASS, 0 blocking (paper v2.2 of 2026-11-07: 163 OK, 26 qualitative/derived, 31 text, 3 node; refreshed at the final export). On this public tree, which ships the clean Writeup (`paper/WRITEUP.md`, no source comments), the shipped gate checks the READMEs only (`strict gate: PASS -- paper (none)`); the paper master's source comments were gated against this tree at export (0 blocking: 169 OK, 32 qualitative/derived, 41 text, 4 node; `VERIFY_LOG.md`) | same counts |
| `slipguard verify` | the shipped proxy, quarantine renderer and audit code are byte-identical to the frozen evaluated code | `VERIFY PASS`, `"ok": true` (files changed by the export are matched through their recorded edits) | `"ok": true` |
| `transcriptlab verify --root .` | TranscriptLab's frozen runner and analysis files | 4/4 match (as recorded in `FROZEN_EXPORT_PINS.json`). Pass `--root`: without it the tool searches upward from the current directory | 4/4 match |
| `python notebooks/reproduce_numbers.py .` | re-derives released values from the raw records: 8 headline estimates (TranscriptLab C1, C2, C3 and C5 on 31B; the bf16 row) and 4 corpus counts | **8/8 exact** with this repository alone; **10/10** with the PNC dataset attached (`PNC_ROOT=<dir>`: adds the episode and turn counts); **12/12** with PNC and the discovery snippets of the release dataset (`release/package/v1.0/corpus/discovery/slips_snippets.jsonl` and `pointers.jsonl`). It skips a check whose input is absent and says so; read the printed count | 12/12 exact |

None of the 12 checks of `reproduce_numbers.py` re-derives an end-to-end value: the end-to-end run records are not
released (Level 1 below).

## Level 1: re-analysis from released run records (CPU, about 20 minutes)

```bash
bash tools/reproduce_level1.sh          # OUT=<scratch dir> to choose where outputs go; nothing is written elsewhere
```

The script re-runs every registered (and labelled exploratory) analysis from its frozen script on the released run
records, writing only into a scratch directory. It then compares each output with the released result file
(`tools/compare_json.py`).

**Result on the project tree (`tools/LEVEL1_RESULTS.md`; full run 2026-11-06, plus rows `e_ext`, `e_awq` and `e_awq2`
run on 2026-11-07 after their registered analyses):**
- **24 identical.** PREREG_v2 (with sensitivity and the Qwen arm), v2.3, v2.4, v2.5, v2.5b, v2.6, v2.7 (with the pooled
  retest and the soak), v2.8, v2.9, v2.10 (with the audits re-scored from records), PREREG_E_ext, PREREG_E_awq,
  PREREG_E_awq2, both weight-sweep reports, the cross-family decisions and extension, the bf16 row, and the two
  exploratory end-to-end analyses.
- **8 identical except bootstrap CIs.**
  - The 7 PREREG_E end-to-end rows: their frozen script seeds some bootstraps with Python's per-process string hash.
    The 31B re-run CIs fall inside the range found over all 1,000 possible seeds (see "Known non-determinism").
  - The shipped weight-audit re-score: CI bounds within 0.031 nats.
- **0 different.**
- **8 not run, with reasons:**
  - three scripts write to a hard-coded path that is the released file;
  - three need main-track contexts that are not released;
  - one manual evaluation;
  - the GPU-only weight repair.

**Result on this public tree** (a clean copy of this repository with the PNC dataset at `data/pnc/`; 2026-11-06,
`VERIFY_LOG.md`): **19 identical, 1 identical except bootstrap CIs** (the shipped weight-audit re-score), **0 different,
0 failed, 19 not run.** Of the 19 not-run rows, 9 are end-to-end rows (the 7 registered PREREG_E rows and the two
exploratory end-to-end analyses). Their run records (`experiments/endtoend/runs/`, `logs/`, `plans/`) contain the
competition's task text, its sample prompt and repository code, so they are not redistributed here; the script reports
these rows as NOT RUN with that reason. Their registered outputs are released in `experiments/endtoend/analysis/`, and
the rows re-run only on the project layout (result above). That public-tree run predates the `e_ext`, `e_awq` and
`e_awq2` rows becoming runnable. They need the same run records, so on this tree the same guard reports them NOT RUN
too (checked on 2026-11-07 on the public export for `e_pop31`, `e_ext`, `e_awq`, `e_awq2`, `ex_dist` and `ex_boot`).
With the `e_awq2` row, the public tally of the 2026-11-06 run becomes 19 identical, 1 identical except bootstrap CIs
and 20 not run (12 of them end-to-end), of 40 rows. The exported scripts find the repository root
through `TRANSCRIPTLAB_ROOT`, which `reproduce_level1.sh` sets; when running a frozen script by hand from its own
directory, set `TRANSCRIPTLAB_ROOT=<repository root>`. Interpreters: set `PY_G` / `PY_A` (see the script header), or
`TRANSCRIPTLAB_ENVS=<dir with env_gemma/ and env_agentpaper/>`.

**Warning.** Several frozen analysis scripts default their output to the released result file. Never run them by hand
without an explicit `--out` into a scratch directory; `reproduce_level1.sh` does this for you. The script also sets
`PYTHONDONTWRITEBYTECODE=1`, so no bytecode lands in frozen directories.

## Level 2: new generations (GPU)

- **TranscriptLab on any model** (1,200 generations; prints its cost first):

  ```bash
  transcriptlab run --base http://HOST:PORT/v1 --model NAME --tokenizer HF_ID --pool A1 --arms P0,P1,P6,P8a --out runs/NAME
  transcriptlab report runs/NAME --root .
  ```

  It needs the PNC dataset (`USER_GUIDE.md` §4). For Gemma-4-31B 4-bit on vLLM 0.19.1, this is the registered C1 battery; seeds are fixed per state. Expect the
  copying RD within the registered interval (+18.3 pp [13.6, 23.2]), not identical generations: vLLM sampling is not
  bit-reproducible across GPUs and batch sizes.
- **End to end:**
  1. Serve the QAT checkpoint (`google/gemma-4-31b-it-qat-w4a16-ct`) with `vllm serve` (vLLM 0.19.1, gemma4 tool and
     reasoning parsers; `USER_GUIDE.md` §1 has the command).
  2. Start `slipguard proxy` in front of it.
  3. Run the challenge harness on the 113 eligible tasks, base vs `fullp` routes (`experiments/endtoend/RUNBOOK.md`).
  4. Analyse with `prereg_analysis.py population`.

  About 6–8 GPU-hours per replicate on one 80 GB GPU.
- **Weight audit of your checkpoint:**

  ```bash
  slipguard audit-weights --endpoint http://HOST:PORT/v1 --served-name NAME --pnc <PNC dir> --tokenizer <model dir> \
      --records mine.records.jsonl --reference bf16.records.jsonl --out report.json
  ```

  About 454 string ends; minutes.

## Known non-determinism

- **Generations.** TranscriptLab samples at temperature 1.0 with a per-state seed shared by all arms (common random numbers);
  the end-to-end harness samples at 0.2 with per-request seeds shared by the two arms of a replicate.
  vLLM output can still differ across hardware and batch composition. The released run records are the reference.
- **Most analyses** fix their bootstrap seeds in the code. Re-running them on the same records gives identical numbers.
- **PREREG_E's end-to-end analysis is the exception** (`experiments/endtoend/analysis/prereg_analysis.py`, frozen). It
  seeds the bootstrap of each paired difference with `hash(key) % 1000`. Python randomises string hashes per process, so
  a re-run reproduces the point estimates and ratio CIs exactly, but the difference CIs and bootstrap p-values only up to
  Monte-Carlo error.
  - The later end-to-end registrations (PREREG_E_ext, PREREG_E_awq, PREREG_E_awq2, and the still-running E_audit and
    E_comp) call its functions with explicit integer seeds, so they are not affected: Level 1 reproduces E_ext, E_awq
    and E_awq2 exactly.
  - `EXPLORATORY_bootseed.py` evaluates the frozen bootstrap at all 1,000 possible seeds, without modifying the frozen
    code. Output: `EXPLORATORY_bootseed.json`.
  - **Exact reproduction.** Seeds 92 / 319 / 491 / 513 reproduce the released Y1 interval; seeds 216, 353, 436, 780 and
    882 reproduce Y2; seeds 523 / 647 / 49 reproduce the quarantine / IPD / fullp branch contrasts.
  - **Range over all seeds.** The Y1 difference CI is [−3.69 to −3.54, −1.07 to −0.98] (released [−3.60, −1.03]).
    p = 0 at every seed.
  - **Verdicts.** Every registered verdict that uses these CIs holds at all 1,000 seeds: the co-primary success rule,
    and the ≥50% rule for quarantine, IPD and fullp.
