#!/usr/bin/env python3
"""Residual privacy gate over the PUBLIC part of release/lib and over a built wheel (R's release rules, counts only).

    python tools/privacy_check.py [wheel.whl ...]
Public part = everything except tests/private/, dev/, progress.md, DESIGN.md, __pycache__ (see HANDOFF_R.md).
Also flags disclosure-sensitive payload shapes in public files: control-token text inside JSON test fixtures is
allowed only in src/slipguard/_vendor (C's generators) and the parser/template code (token constants)."""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
REL = os.path.dirname(LIB)
sys.path.insert(0, os.path.join(REL, "scripts"))
import privacy_rules  # noqa: E402

EXCLUDE_DIRS = {"private", "dev", "__pycache__", "scratch"}
EXCLUDE_FILES = {"progress.md", "DESIGN.md"}
_, den = privacy_rules.load(os.path.join(REL, "_work/private_denylist.json"), os.path.join(REL, "_work/.redaction_key"))
checks = {k: v for k, v in privacy_rules.residual_checks(den).items() if k.startswith("R_")}
hits = {}


def scan(name, text):
    for k, rx in checks.items():
        n = len(rx.findall(text))
        if n:
            hits.setdefault(name, {})[k] = n


n = 0
for root, dirs, files in os.walk(LIB):
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    for fn in files:
        if fn in EXCLUDE_FILES and root == LIB:
            continue
        p = os.path.join(root, fn)
        try:
            t = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        n += 1
        scan(os.path.relpath(p, LIB), t)
for w in sys.argv[1:]:
    z = zipfile.ZipFile(w)
    for name in z.namelist():
        try:
            scan(f"{os.path.basename(w)}:{name}", z.read(name).decode("utf-8"))
        except UnicodeDecodeError:
            pass
        n += 1
print(f"scanned {n} files; residual hits: {sum(sum(v.values()) for v in hits.values())}")
for k, v in sorted(hits.items()):
    print(" ", k, v)
sys.exit(1 if hits else 0)
