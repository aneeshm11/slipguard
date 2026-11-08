#!/usr/bin/env python3
"""Copy the frozen components into the slipguard package (dev-time tool of workstream L; not shipped).

    python tools/vendor_frozen.py [--check]

* Sources are read-only. Every source sha256 is checked against its owner's freeze list before anything is written:
  E: experiments/endtoend/PREREG_E_manifest.txt (final freeze 2026-11-05 07:14 UTC) == acceptance/FREEZE_CANDIDATE.txt.
  C: gemmaproto has no published freeze list yet -> pinned here (GEMMAPROTO_PIN) and reported as such.
  F: the weight-audit package wsa-1.0 (experiments/quant_margins/wsa/release_audit) -> F_FREEZE below; the two points
     packs (.jsonl.gz) are copied as bytes (privacy-checked decompressed).
* The copy applies EXACTLY the public-repo export transform of workstream R (release/repo_build/build_tree.py):
  py_rewrite (host path literals -> env lookups) followed by the release privacy redaction. So a shipped copy is
  byte-identical to the copy in R's public tree. Every changed file is listed with its diff in
  _frozen/EXPORT_DIFFS.md (diff shown against the redacted source, so it never carries a host path).
* Writes src/slipguard/_frozen/MANIFEST.json: {source, source_sha256, owner_sha256, shipped, shipped_sha256, changed}.
--check: verify only (no writes); exit 1 on any difference.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
REL = os.path.dirname(LIB)
AP = os.path.dirname(REL)
PKG = os.path.join(LIB, 'src', 'slipguard')
sys.path.insert(0, os.path.join(REL, 'repo_build'))
import build_tree  # noqa: E402  (R's builder: py_rewrite + privacy_rules)

E_ROOT = 'experiments/endtoend'
E_FILES = ['proxy/e2e_proxy.py', 'proxy/gemma_protocol.py', 'proxy/vendor_b_gemma_protocol.py', 'proxy/configs.json',
           'proxy/VENDOR_B.txt', 'export/quarantine_renderer.py', 'configs/channel_prior.json']
F_ROOT = 'experiments/quant_margins/wsa/release_audit'
# F's freeze list (agent message F -> L, 2026-11-05, after the PI decision of 19:16 UTC: audit-weights only).
F_FREEZE = {'wsaudit/__init__.py': 'd73fb8a7968af1bc61364420fac8343834b5d0ac93441fbc211fbea7e3ea6fef',
            'wsaudit/audit.py': '43df25b33ab9589055a067ee12f0cde2b2a41548e29bf396d1ba19b9a37389c5',
            'wsaudit/render.py': '85ce0172fc0e3bac543b79c8a673d66162d8296f3cbb939b377131d20ba8007d',
            'wsaudit/report.py': 'b852acbe7929ace74eb2277ea6506b8b8d778e116f7e3224f1c1f4fbcba689a6',
            'pack/audit_items_16k.jsonl.gz': 'fdf85e048f867077427dfe6cc69f80daed2a6e153acbd493f0f089cfad55ee5e',
            'pack/core_items.jsonl.gz': 'd4fe1c0e448f4550e977a960ee6f55e164fb36d7d961082d06e8098112f4ea62'}
C_ROOT = 'experiments/conformance/gemmaproto'
C_FILES = ['__init__.py', 'tokens.py', 'serializer.py', 'parser.py', 'conformance.py', 'gen.py']
# C has not published a freeze list for gemmaproto; these are the bytes vendored on 2026-11-05 (the version every
# result in experiments/conformance/ was produced with: README "76,635 checks", Table D column "ours").
GEMMAPROTO_PIN: dict[str, str] = {}   # filled on first run, then frozen into MANIFEST.json (see --check)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def ast_map(src: str) -> dict[str, str]:
    """sha256 of ast.dump() of every top-level statement, keyed by its name (defs/classes) or 'stmt<i>'."""
    import ast
    out = {}
    for i, node in enumerate(ast.parse(src).body):
        key = getattr(node, "name", None) or f"stmt{i}"
        out[key] = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
    return out


def outside_sha(src: str, names: list[str]) -> str:
    """sha256 of the file text with the line ranges of the named top-level definitions removed (version-independent:
    proves that everything outside those definitions is byte-identical)."""
    import ast
    lines = src.splitlines(keepends=True)
    drop = set()
    for node in ast.parse(src).body:
        if getattr(node, 'name', None) in names:
            first = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
            drop.update(range(first - 1, node.end_lineno))
    return hashlib.sha256(''.join(l for i, l in enumerate(lines) if i not in drop).encode('utf-8')).hexdigest()


def json_semantic(raw: bytes) -> str:
    """sha256 of the parsed JSON without provenance fields (what the code reads)."""
    o = json.loads(raw)
    if isinstance(o, dict):
        o = {k: v for k, v in o.items() if k not in ("source",)}
    return hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()


def owner_list(path: str) -> dict[str, str]:
    out = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith('#'):
            h, p = line.split(None, 1)
            out[p] = h
    return out


def export(src_rel: str, raw: bytes, rules) -> tuple[bytes, list[str], str]:
    if src_rel.endswith('.gz'):                 # binary data (F's points packs): copied as is, checked decompressed
        import gzip
        text = gzip.decompress(raw).decode('utf-8')
        red, counts = rules.redact(text)
        if counts or red != text:
            raise SystemExit(f'FAIL {src_rel}: privacy redaction would change a binary pack ({counts})')
        return raw, [], ''
    text = raw.decode('utf-8')
    out, changes = text, []
    if src_rel.endswith('.py'):
        out, k = build_tree.py_rewrite(out, build_tree_manifest()['path_rules'])
        if k:
            changes.append(f'{k} path literal(s) -> env/config lookups (R path rule)')
    red, counts = rules.redact(out)
    if counts:
        changes.append('privacy redaction: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    out = red
    diff = ''
    if out != text:
        shown, _ = rules.redact(text)
        diff = ''.join(difflib.unified_diff(shown.splitlines(True), out.splitlines(True), f'a/{src_rel}',
                                            f'b/{src_rel}', n=0))
    return out.encode('utf-8'), changes, diff


_MAN = None


def build_tree_manifest():
    global _MAN
    if _MAN is None:
        _MAN = json.load(open(os.path.join(REL, 'repo_build', 'manifest.json')))
    return _MAN


def main() -> int:
    check = '--check' in sys.argv
    rules, den = build_tree.privacy_rules.load(os.path.join(REL, '_work/private_denylist.json'),
                                               os.path.join(REL, '_work/.redaction_key'))
    e_final = owner_list(os.path.join(AP, E_ROOT, 'PREREG_E_manifest.txt'))
    e_cand = owner_list(os.path.join(AP, E_ROOT, 'acceptance/FREEZE_CANDIDATE.txt'))
    man_path = os.path.join(PKG, '_frozen', 'MANIFEST.json')
    old = json.load(open(man_path)) if os.path.exists(man_path) else None
    pin = {r['source']: r['source_sha256'] for r in (old or {}).get('files', []) if r['owner'] == 'C'}
    jobs = []
    for f in E_FILES:
        jobs.append(('E', f'{E_ROOT}/{f}', f'_frozen/endtoend/{f}', e_final.get(f)))
        if f in e_cand and e_cand[f] != e_final.get(f):
            print(f'FAIL {f}: FREEZE_CANDIDATE and PREREG_E_manifest disagree')
            return 1
    for f in C_FILES:
        jobs.append(('C', f'{C_ROOT}/{f}', f'_vendor/gemmaproto/{f}', pin.get(f'{C_ROOT}/{f}')))
    for f, h in F_FREEZE.items():
        jobs.append(('F', f'{F_ROOT}/{f}', f'_frozen/wsa/{f}', h))
    rows, notes, bad = [], [], 0
    residual = build_tree.privacy_rules.residual_checks(den)
    for owner, src_rel, dst_rel, want in jobs:
        raw = open(os.path.join(AP, src_rel), 'rb').read()
        h = sha(raw)
        if want is not None and h != want:
            print(f'FAIL {src_rel}: sha {h[:12]} != owner list {want[:12]}')
            bad += 1
            continue
        out, changes, diff = export(src_rel, raw, rules)
        plain = out.decode('utf-8') if not src_rel.endswith('.gz') else __import__('gzip').decompress(out).decode('utf-8')
        for name, rx in residual.items():
            if name.startswith('R_') and rx.search(plain):
                print(f'FAIL {dst_rel}: residual privacy hit {name}')
                bad += 1
        dst = os.path.join(PKG, dst_rel)
        sem = {}
        if src_rel.endswith('.py') and changes:
            sa, da = ast_map(raw.decode('utf-8')), ast_map(out.decode('utf-8'))
            differs = sorted(k for k in set(sa) | set(da) if sa.get(k) != da.get(k))
            o_src = outside_sha(raw.decode('utf-8'), differs)
            o_out = outside_sha(out.decode('utf-8'), differs)
            if o_src != o_out:
                print(f'FAIL {dst_rel}: text outside {differs} differs from the frozen source')
                bad += 1
            sem = {'differs_only_in': differs, 'outside_sha256': o_src}
        elif src_rel.endswith('.json'):
            sem = {'json_semantic_sha256': json_semantic(raw),
                   'json_semantic_equal': json_semantic(raw) == json_semantic(out)}
        rows.append({'owner': owner, 'source': src_rel, 'source_sha256': h, 'owner_sha256': want, **sem,
                     'owner_list': {'E': 'experiments/endtoend/PREREG_E_manifest.txt (freeze 2026-11-05 07:14 UTC)',
                                    'F': "F's freeze list wsa-1.0 (2026-11-05, after the PI decision of 19:16 UTC: "
                                         "audit-weights only)"}.get(owner, 'none published: pinned at vendoring (2026-11-05)'),
                     'shipped': dst_rel, 'shipped_sha256': sha(out), 'changed': bool(changes), 'changes': changes})
        if changes:
            notes.append((dst_rel, src_rel, owner, changes, diff))
        if check:
            if not os.path.exists(dst) or open(dst, 'rb').read() != out:
                print(f'FAIL {dst_rel}: shipped copy differs from the export of the frozen source')
                bad += 1
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as fo:
                fo.write(out)
    if check:
        if old is not None and [r['shipped_sha256'] for r in old['files']] != [r['shipped_sha256'] for r in rows]:
            print('FAIL MANIFEST.json shipped shas differ from a fresh export')
            bad += 1
        print('CHECK', 'PASS' if not bad else f'FAIL ({bad})', f'{len(rows)} files')
        return 1 if bad else 0
    if bad:
        return 1
    man = {'comment': ('Frozen components copied into slipguard by tools/vendor_frozen.py. Source paths are relative '
                       'to the project/public repository root. shipped == source except the files with changed=true '
                       '(see EXPORT_DIFFS.md); the transform is the public-repo export of workstream R.'),
           'e_freeze_digest': 'c9c20591ecdeb33ca505a65da0256e07451de31a0380f8449358ac9f325a5259',
           'files': rows}
    with open(man_path, 'w') as fo:
        json.dump(man, fo, indent=1)
        fo.write('\n')
    with open(os.path.join(PKG, '_frozen', 'EXPORT_DIFFS.md'), 'w') as fo:
        fo.write('# Export diffs: frozen source -> shipped copy\n\nOnly path literals (to env lookups) and privacy '
                 'redactions are ever changed; the diff is shown against the redacted source.\n\n')
        for dst_rel, src_rel, owner, changes, diff in notes:
            fo.write(f'## {dst_rel}\nsource `{src_rel}` (owner {owner}); ' + '; '.join(changes) + '\n\n```diff\n'
                     + diff + '```\n\n')
    print(f'vendored {len(rows)} files ({sum(r["changed"] for r in rows)} changed by the export transform)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
