"""T-F1..T-F3: the shipped frozen files are the frozen ones (sha, AST, JSON); hygienic loading; E's quarantine
self-test passes on the shipped copy."""
import sys

from slipguard._frozen import FrozenIntegrityError, load_e, manifest, verify_shipped
from slipguard.verify import check_frozen


def test_shipped_files_match_manifest():
    rows = verify_shipped()
    assert rows and all(r["ok"] for r in rows)


def test_only_public_export_changes_and_only_main():
    r = check_frozen()
    assert r["ok"]
    assert sorted(r["changed_by_public_export"]) == sorted([
        "_frozen/endtoend/proxy/e2e_proxy.py", "_frozen/endtoend/proxy/VENDOR_B.txt",
        "_frozen/endtoend/configs/channel_prior.json", "_vendor/gemmaproto/gen.py"])
    rows = {x["file"]: x for x in r["outside_main_identical"]}
    assert list(rows) == ["_frozen/endtoend/proxy/e2e_proxy.py"]
    assert rows["_frozen/endtoend/proxy/e2e_proxy.py"]["differs_only_in"] == ["main"]
    assert rows["_frozen/endtoend/proxy/e2e_proxy.py"]["ok"]


def test_e_shas_equal_the_freeze_list():
    for row in manifest()["files"]:
        if row["owner"] == "E":
            assert row["source_sha256"] == row["owner_sha256"]
            if not row["changed"]:
                assert row["shipped_sha256"] == row["owner_sha256"]


def test_loader_is_hygienic_and_selftest_passes(capsys):
    before = {k: sys.modules.get(k) for k in ("gemma_protocol", "quarantine_renderer")}
    e = load_e()
    assert {k: sys.modules.get(k) for k in before} == before
    e.quarantine_renderer._selftest()
    assert "SELFTEST OK" in capsys.readouterr().out


def test_integrity_error_type():
    assert issubclass(FrozenIntegrityError, RuntimeError)
