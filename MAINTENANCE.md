# Maintenance

## Owners and contact
* **Maintainer:** aneeshm11 (GitHub). Contact, bugs and data errata: the repository's issue tracker.
  Security problems in slipguard or TranscriptLab: the repository's private security reporting (`SECURITY.md`).
* **Response targets:** privacy or takedown requests 7 days; security reports acknowledged within 7 days; errata
  30 days.

## Checks that ship with the repository
There is no hosted CI. These are the checks a maintainer, or anyone, runs before tagging a version (all CPU):

| check | command | what it guards |
|---|---|---|
| registrations and frozen code | `python tools/verify_preregs.py --root .` | each pre-registration and frozen analysis file matches the hash recorded at its freeze. Files changed by the export and files withheld are tied to their frozen hashes (`FROZEN_EXPORT_PINS.json`, `WITHHELD.json`) |
| results page | `python tools/make_results_md.py --root . --out RESULTS.md --check` | every value on `RESULTS.md` is read from its result file |
| paper numbers | `python release/build_numbers.py --strict` | every number the paper cites resolves to its source file#key |
| library | `slipguard verify` | the shipped proxy, quarantine renderer and audit code are byte-identical to the evaluated code; conformance smoke |
| CLI | `transcriptlab verify`, then `python -m unittest discover -s transcriptlab/tests` | the frozen runner and analysis files; 16 CLI tests |
| re-analysis | `bash tools/reproduce_level1.sh` | the frozen analyses re-run on the released records give the released results (`tools/LEVEL1_RESULTS.md`) |
| headline re-derivation | `python notebooks/reproduce_numbers.py` | headline values recomputed from the raw registered records |

`VERIFY_LOG.md` records the last run of these commands on this tree, in a clean environment.

## Versioning
* Semantic versions for slipguard and TranscriptLab, with a CHANGELOG entry per release. PNC versions are tagged
  (`MANIFEST.json` → `version`), and every file is sha256-pinned in its manifest.
* A new Gemma chat template is checked against the shipped parser with `slipguard verify` and the conformance
  inputs. If the grammar changes, the parser gets a new minor version.

## Errata and takedowns
* **Data errata** (a wrong label, a wrong licence, missed personal data): open an issue. The fix ships in the next
  patch version; the record keeps its id.
* **Takedown requests** (from a rights holder or a person): the record is removed in a new version within 7 days. Only
  its id and hash are kept. The privacy build and the results page are re-run, and any changed statistic is noted.
* **Upstream licence changes:** records whose repository becomes unlicensed become pointers (id and hash, no text).

## Contributing
* A new runtime or parser path: add it to the conformance inputs and report its per-class outcome. It must run on
  CPU.
* A new model for TranscriptLab: `transcriptlab run` with `--format` and `--tokenizer` (see `transcriptlab/README.md`).
* Numbers in contributed analyses must come from a result file (see `tools/make_results_md.py`), not from prose.
