"""Loader for the frozen components shipped inside slipguard (workstream E's proxy freeze, C's gemmaproto, workstream
F's weight audit wsa-1.0).

Every shipped file is checked against MANIFEST.json (sha256) before it is imported; a mismatch raises
:class:`FrozenIntegrityError`. The modules are loaded under private names; ``sys.path`` and any user modules named
``gemma_protocol`` / ``quarantine_renderer`` are saved and restored around the import (the frozen files locate each
other through ``sys.path``; nothing in them is edited).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import threading
from types import ModuleType, SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
E_DIR = os.path.join(HERE, "endtoend")
WSA_DIR = os.path.join(HERE, "wsa")
WSA_FILES = ["_frozen/wsa/wsaudit/__init__.py", "_frozen/wsa/wsaudit/audit.py", "_frozen/wsa/wsaudit/render.py",
             "_frozen/wsa/wsaudit/report.py"]
_LOCK = threading.Lock()
_CACHE: dict[str, ModuleType] = {}


class FrozenIntegrityError(RuntimeError):
    """A shipped frozen file does not match its recorded sha256."""


def manifest() -> dict:
    with open(os.path.join(HERE, "MANIFEST.json"), encoding="utf-8") as f:
        return json.load(f)


def verify_shipped() -> list[dict]:
    """[{shipped, ok, expected, actual}] for every frozen file (shipped bytes vs MANIFEST.json)."""
    rows = []
    for r in manifest()["files"]:
        p = os.path.join(PKG, r["shipped"])
        try:
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        except OSError:
            h = None
        rows.append({"shipped": r["shipped"], "owner": r["owner"], "ok": h == r["shipped_sha256"],
                     "expected": r["shipped_sha256"], "actual": h, "changed_by_export": r["changed"]})
    return rows


def _check(paths: list[str]) -> None:
    bad = [r for r in verify_shipped() if r["shipped"] in paths and not r["ok"]]
    if bad:
        raise FrozenIntegrityError("frozen file(s) modified: " + ", ".join(r["shipped"] for r in bad))


def _load(name: str, path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_e(with_proxy: bool = False) -> SimpleNamespace:
    """E's frozen modules: quarantine_renderer, gemma_protocol (+ e2e_proxy, which needs aiohttp, if asked)."""
    with _LOCK:
        if "gemma_protocol" not in _CACHE:
            _check(["_frozen/endtoend/export/quarantine_renderer.py", "_frozen/endtoend/proxy/gemma_protocol.py",
                    "_frozen/endtoend/proxy/vendor_b_gemma_protocol.py"])
            saved_path = list(sys.path)
            saved = {k: sys.modules.get(k) for k in ("gemma_protocol", "quarantine_renderer")}
            try:
                qr = _load("slipguard._e2e_quarantine_renderer", os.path.join(E_DIR, "export", "quarantine_renderer.py"))
                sys.modules["quarantine_renderer"] = qr     # what gemma_protocol imports
                gp = _load("slipguard._e2e_gemma_protocol", os.path.join(E_DIR, "proxy", "gemma_protocol.py"))
            finally:
                sys.path[:] = saved_path
                for k, v in saved.items():
                    if v is None:
                        sys.modules.pop(k, None)
                    else:
                        sys.modules[k] = v
            _CACHE["quarantine_renderer"], _CACHE["gemma_protocol"] = qr, gp
        if with_proxy and "e2e_proxy" not in _CACHE:
            _check(["_frozen/endtoend/proxy/e2e_proxy.py"])
            saved_path = list(sys.path)
            saved = sys.modules.get("gemma_protocol")
            sys.modules["gemma_protocol"] = _CACHE["gemma_protocol"]   # what e2e_proxy imports
            try:
                px = _load("slipguard._e2e_proxy", os.path.join(E_DIR, "proxy", "e2e_proxy.py"))
            finally:
                sys.path[:] = saved_path
                if saved is None:
                    sys.modules.pop("gemma_protocol", None)
                else:
                    sys.modules["gemma_protocol"] = saved
            assert px.gp is _CACHE["gemma_protocol"]
            _CACHE["e2e_proxy"] = px
        return SimpleNamespace(quarantine_renderer=_CACHE["quarantine_renderer"],
                               gemma_protocol=_CACHE["gemma_protocol"], e2e_proxy=_CACHE.get("e2e_proxy"))


def load_wsa() -> ModuleType:
    """Workstream F's frozen weight-audit package (wsaudit, wsa-1.0), sha-checked, loaded as a private package.
    Its own imports (numpy; httpx and transformers for a live audit) are optional dependencies: slipguard[weights]."""
    with _LOCK:
        if "wsaudit" not in _CACHE:
            _check(WSA_FILES)
            d = os.path.join(WSA_DIR, "wsaudit")
            spec = importlib.util.spec_from_file_location("slipguard._wsaudit", os.path.join(d, "__init__.py"),
                                                          submodule_search_locations=[d])
            mod = importlib.util.module_from_spec(spec)
            sys.modules["slipguard._wsaudit"] = mod
            try:
                spec.loader.exec_module(mod)
            except BaseException:
                for k in [k for k in sys.modules if k == "slipguard._wsaudit" or k.startswith("slipguard._wsaudit.")]:
                    sys.modules.pop(k, None)
                raise
            _CACHE["wsaudit"] = mod
        return _CACHE["wsaudit"]


def paths() -> SimpleNamespace:
    return SimpleNamespace(endtoend=E_DIR, configs_json=os.path.join(E_DIR, "proxy", "configs.json"),
                           channel_prior=os.path.join(E_DIR, "configs", "channel_prior.json"),
                           wsa_packs={"audit16k": os.path.join(WSA_DIR, "pack", "audit_items_16k.jsonl.gz"),
                                      "core": os.path.join(WSA_DIR, "pack", "core_items.jsonl.gz")})
