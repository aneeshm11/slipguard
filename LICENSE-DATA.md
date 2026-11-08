# Data licence (CC BY 4.0)

The **data, annotations, corpus structure, documentation and statistics** in this repository are licensed under the
**Creative Commons Attribution 4.0 International License (CC BY 4.0)**:
https://creativecommons.org/licenses/by/4.0/legalcode

The **code** is licensed separately under the Apache License, Version 2.0 (see `LICENSE`).

## What CC BY 4.0 covers (data paths)

- `data/` -- the PNC corpus metadata, manifests and licence files (the full corpus ships as the Kaggle/Hugging Face
  dataset);
- `conformance/` -- the public conformance cases, repros and summaries;
- `experiments/**/out/`, `experiments/**/results*.json` and the other released result and analysis JSON/MD files;
- `figures/` -- the figures and their underlying `figure_data*.json`;
- `RESULTS.md`, `DATASHEET.md`, `croissant.json`, `PREREGISTRATIONS.md`, `LIMITATIONS.md`, `REPRODUCE.md`,
  `RESOURCE_CARD.md`, `paper/WRITEUP.md` and the other top-level documentation;
- the registration documents under `paper/protocol_theory/prereg/` and `experiments/**/PREREG_*`.

## What is **not** CC BY 4.0

- Everything under a `src/`, `tools/`, `notebooks/`, `release/` path, every `*.py`, `*.sh`, `*.jinja` file, and the
  `slipguard/` and `transcriptlab/` packages: **Apache-2.0** (`LICENSE`).
- Third-party repository text embedded in PNC tool outputs, QuoteStorm payloads and PNC-derived conformance inputs:
  **its own upstream SPDX licence** (per-repository identifiers in `data/pnc/MANIFEST.json#licenses`; see `NOTICE` and
  `DATASHEET.md`). Non-permissive text is referenced by pointer, not redistributed.
- Gemma 4 chat templates and Gemma model outputs: Apache-2.0 per the model cards, subject to the Gemma 4 Terms of Use
  (`NOTICE`).

When reusing the CC BY 4.0 data, attribute the authors as given in `CITATION.cff`.
