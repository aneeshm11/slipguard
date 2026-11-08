"""Shared helper for the paper figures: read every plotted value from a cited JSON (fail loudly on a missing key),
record its source as `path#key` with the file's sha256, and write figure_data.json.

No value is typed into a figure script. Derived values (a sum, a unit change) are recorded with the formula and the
labels they come from.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # figures -> draft -> protocol -> paper -> project root
DATA_JSON = HERE / "figure_data.json"

# Okabe-Ito (colour-blind safe). One accent for slipguard across figures.
STOCK = "#6E6E6E"       # stock / built-in / unguarded
GUARD = "#0072B2"       # slipguard (accent)
MID = "#E69F00"         # intermediate step (audit pick)
GEMMA = "#009E73"       # Gemma family (FIG2)
OTHER = "#CC79A7"       # other families (FIG2)
REF = "#000000"         # reference marks


class Sources:
    def __init__(self, figure: str, script: str):
        self.figure, self.script = figure, script
        self.values: list[dict] = []
        self._cache: dict[str, object] = {}
        self._sha: dict[str, str] = {}

    def _load(self, rel: str):
        if rel not in self._cache:
            p = ROOT / rel
            raw = p.read_bytes()
            self._sha[rel] = hashlib.sha256(raw).hexdigest()
            self._cache[rel] = json.loads(raw)
        return self._cache[rel]

    def get(self, label: str, rel: str, key: str):
        """value at `key` ('/'-separated; integers index lists) of the JSON file `rel` (relative to the project root)."""
        x = self._load(rel)
        for part in key.split("/"):
            if isinstance(x, list):
                x = x[int(part)]
            elif isinstance(x, dict):
                if part not in x:
                    raise KeyError(f"{rel}#{key}: missing key {part!r}")
                x = x[part]
            else:
                raise KeyError(f"{rel}#{key}: cannot descend into {type(x).__name__} at {part!r}")
        self.values.append({"label": label, "value": x, "source": f"{rel}#{key}", "file_sha256": self._sha[rel]})
        return x

    def derived(self, label: str, value, formula: str, inputs: list[str]):
        self.values.append({"label": label, "value": value, "derived": formula, "inputs": inputs})
        return value

    def write(self, outputs: list[str] = ()):
        """record the values, plus the sha256 of the figure files (and the script) written by this run."""
        allv = json.loads(DATA_JSON.read_text()) if DATA_JSON.exists() else {"figures": {}}
        outs = {o: hashlib.sha256((HERE / o).read_bytes()).hexdigest() for o in outputs}
        allv["figures"][self.figure] = {"script": self.script, "written_utc": _dt.datetime.now(_dt.timezone.utc)
                                        .strftime("%Y-%m-%dT%H:%M:%SZ"), "outputs_sha256": outs,
                                        "n_values": len(self.values), "values": self.values}
        allv["note"] = ("Every plotted number with its source (`path#key`, relative to the project root, plus the file's "
                        "sha256 at drawing time). Entries with `derived` are arithmetic on the listed inputs.")
        DATA_JSON.write_text(json.dumps(allv, indent=1, ensure_ascii=False) + "\n")
        for v in self.values:
            print(f"{self.figure} | {v['label']} = {v['value']} | {v.get('source') or v['derived']}")
        for o, h in outs.items():
            print(f"{self.figure} | output {o} sha256 {h}")
