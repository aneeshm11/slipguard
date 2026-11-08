"""slipguard.weights: F's frozen weight audit (wsa-1.0) -- shipped bytes, packs, report composition, CLI re-scoring."""
import gzip
import json
import math
import os
import subprocess
import sys

import pytest

from slipguard import weights as W
from slipguard._frozen import WSA_FILES, verify_shipped

F_SHA = {"_frozen/wsa/wsaudit/__init__.py": "d73fb8a7968af1bc61364420fac8343834b5d0ac93441fbc211fbea7e3ea6fef",
         "_frozen/wsa/wsaudit/audit.py": "43df25b33ab9589055a067ee12f0cde2b2a41548e29bf396d1ba19b9a37389c5",
         "_frozen/wsa/wsaudit/render.py": "85ce0172fc0e3bac543b79c8a673d66162d8296f3cbb939b377131d20ba8007d",
         "_frozen/wsa/wsaudit/report.py": "b852acbe7929ace74eb2277ea6506b8b8d778e116f7e3224f1c1f4fbcba689a6",
         "_frozen/wsa/pack/audit_items_16k.jsonl.gz": "fdf85e048f867077427dfe6cc69f80daed2a6e153acbd493f0f089cfad55ee5e",
         "_frozen/wsa/pack/core_items.jsonl.gz": "d4fe1c0e448f4550e977a960ee6f55e164fb36d7d961082d06e8098112f4ea62"}


def test_frozen_wsa_bytes_match_f_freeze_list():
    rows = {r["shipped"]: r for r in verify_shipped()}
    for path, sha in F_SHA.items():
        assert rows[path]["ok"] and rows[path]["actual"] == sha and rows[path]["owner"] == "F"
    assert set(WSA_FILES) <= set(F_SHA)


def test_packs_ship_and_are_path_free():
    n = {}
    for name in W.PACKS:
        p = W.pack_path(name)
        assert os.path.exists(p)
        text = gzip.open(p, "rt").read()
        items = [json.loads(l) for l in text.splitlines()]
        n[name] = (len(items), sum(it["split"] == "heldout" for it in items))
        assert "/" not in "".join(it["episode_id"] for it in items)
        assert all({"episode_id", "turn_index", "schema", "positions", "prompt_tokens"} <= set(it) for it in items)
    assert n == {"audit16k": (235, 235), "core": (951, 458)}


def _records(shift=0.0, n_eps=6):
    """synthetic per-position records in the audit_endpoint format (two string ends per call)."""
    recs = []
    for e in range(n_eps):
        for k, arg in enumerate(("new", "old")):
            m = 12.0 + e + k - shift
            top = [[52, -0.01], [8347, -0.01 - m]] + [[1000 + i, -30.0 - i] for i in range(18)]
            recs.append({"episode_id": f"ep{e}", "turn_index": 1, "item": e, "split": "heldout", "n_prior_bad": 0,
                         "kind": "close", "arg": arg, "pos": 10 + k, "logged": 52, "top": top, "n_prompt": 100,
                         "pLA_T1": 0.0, "pDQ_T1": 1.0, "margin": m, "margin_censored": False, "top1": 52})
    return recs


def test_report_composition_and_flag_rule():
    pytest.importorskip("numpy")
    ref, qat = _records(0.0), _records(4.0)
    rep = W.report(qat, ref)
    assert rep["schema"] == W.SCHEMA == "slipguard.weights.audit/v1"
    assert rep["summary"]["n_string_ends"] == 12 and rep["summary"]["censored_frac"] == 0.0
    assert math.isclose(rep["paired_vs_reference"]["median_deficit"][0], 4.0)
    assert rep["FLAG"] is True and rep["SEVERE"] is False and rep["descriptive_only"] is False
    same = W.report(ref, ref)
    assert same["paired_vs_reference"]["median_deficit"][0] == 0.0 and same["FLAG"] is False
    desc = W.report(qat)                       # no same-family bf16 reference: descriptive only
    assert desc["descriptive_only"] is True and desc["FLAG"] is None and desc["paired_vs_reference"] is None


def test_cli_rescoring_from_records(tmp_path):
    pytest.importorskip("numpy")
    a, b = tmp_path / "qat.jsonl", tmp_path / "bf16.jsonl"
    a.write_text("".join(json.dumps(r) + "\n" for r in _records(4.0)))
    b.write_text("".join(json.dumps(r) + "\n" for r in _records(0.0)))
    env = dict(os.environ)
    src = os.path.join(os.path.dirname(__file__), "..", "src")
    if os.path.isdir(src) and not env.get("SLIPGUARD_TEST_INSTALLED"):
        env["PYTHONPATH"] = os.path.abspath(src) + os.pathsep + env.get("PYTHONPATH", "")
    r = subprocess.run([sys.executable, "-m", "slipguard", "audit-weights", "--from-records", str(a), "--reference", str(b),
                        "--out", str(tmp_path / "rep.json")], capture_output=True, text=True, env=env, timeout=300)
    assert r.returncode == 0, r.stderr
    rep = json.loads((tmp_path / "rep.json").read_text())
    assert rep["FLAG"] is True and math.isclose(rep["paired_vs_reference"]["median_deficit"][0], 4.0)
    # with --out the report goes to the file and a one-line verdict to stderr (0.1.2; stdout stays empty)
    assert r.stdout == "" and "wrote" in r.stderr and "FLAG True" in r.stderr and "median deficit vs reference 4.00" in r.stderr
