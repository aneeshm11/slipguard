# Data license (PNC corpus, data/pnc)

- **Our annotations and corpus structure** (record layout, harness texts, tags, manifests, context selections):
  Creative Commons Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/
- **Code** (this directory: harness, scripts, vendored proxy): Apache License 2.0 (see LICENSE).
- **Third-party content inside the records keeps its own license**: repository code shown in tool outputs (per-repository
  SPDX identifiers in data/pnc/MANIFEST.json: BSD-3-Clause, BSD-2-Clause, MIT, Apache-2.0); SWE-bench problem
  statements (public GitHub issues; the SWE-bench HF dataset cards declare no license, the SWE-bench code is MIT);
  model outputs of google/gemma-4-31b-it-qat-w4a16-ct (Apache-2.0 model card).
- pylint-dev/pylint (GPL-2.0) and matplotlib were excluded before generation.

## Privacy
In this public release (version 1.1-masked) developer e-mail addresses from upstream source files are masked as `<email>` (see README.md and MANIFEST.json → `privacy`); no other personal data was found by the scan. To request removal of content, contact the maintainer via the Kaggle dataset page.
