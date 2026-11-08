# Installing slipguard and transcriptlab (no PyPI release)

Neither package is on PyPI (the names `slipguard` and `transcriptlab` were free when checked on 2026-11-06; nothing is
published). Install from the repository or from the wheels shipped with the release dataset.

**From the repository** (pip ≥ 21.3):

```bash
pip install "slipguard @ git+https://github.com/aneeshm11/slipguard#subdirectory=slipguard"                      # core, stdlib only
pip install "slipguard[proxy-frozen,adk] @ git+https://github.com/aneeshm11/slipguard#subdirectory=slipguard"    # the evaluated proxy + ADK hooks
pip install "transcriptlab[run] @ git+https://github.com/aneeshm11/slipguard#subdirectory=transcriptlab"
```

**From a checkout:** `pip install ./slipguard` and `pip install ./transcriptlab` (add extras the same way, e.g.
`pip install "./slipguard[proxy-frozen,adk]"`). pip builds these in place (it writes `build/` and `*.egg-info` into the
package directory), so run it from a writable clone, not a read-only checkout.

`pip install --dry-run "./slipguard[proxy-frozen]"` still downloads several GB of wheels (vLLM 0.19.1 is a CUDA build).

**From the wheels** in the release dataset (`https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc`, folder `release/package/wheels/`; offline). They are
not in this repository:

```bash
pip install slipguard-0.1.2-py3-none-any.whl          # core
pip install "slipguard-0.1.2-py3-none-any.whl[proxy-frozen,adk]"   # extras are fetched from PyPI
pip install transcriptlab-0.1.3-py3-none-any.whl
```

Both wheels are pure Python (`py3-none-any`) and have no required dependencies; the extras pull third-party packages
(see each package's README). Check the wheels against `release/package/wheels/SHA256SUMS`. After installing,
`slipguard verify` and `transcriptlab verify` check the shipped frozen code against its recorded hashes.
