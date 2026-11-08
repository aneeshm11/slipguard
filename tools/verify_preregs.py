#!/usr/bin/env python3
"""Check every pre-registration and its frozen code against the hashes recorded at freeze time.

    python tools/verify_preregs.py [--root ROOT] [--json OUT.json] [--pins FILE] [--withheld FILE]

Two kinds of check:
  1. DOCUMENTS: each registration document's sha256 at freeze. Some documents were amended *append-only* after the
     freeze (a dated "Deviations"/"Amendment" section at the end, each entry saying whether it was decided before or
     after seeing data). For those, the registered hash is the hash of the first N bytes, and the check reports
     PREFIX-OK plus what was appended.
  2. MANIFESTS and FROZEN CODE: hash files written at freeze time ("<sha>  <path>" lines; md5 for the cross-family
     manifest), and the files frozen with PREREG_v2.7 and later (hashes in V27_CODE below). Each listed file is
     re-hashed. A mismatch is reported, never hidden; expected mismatches (append-only logs, files re-frozen with a
     logged reason) are explained in KNOWN below and in PREREGISTRATIONS.md.

Both tree layouts work. The released (public) repository adds two lists, which are consulted only when the plain check
fails (so they are inert on the project tree, which has neither):
  * FROZEN_EXPORT_PINS.json: files whose public copy had to differ from the frozen file (host-path literals -> env
    lookups, privacy redaction, pseudonymisation), with the frozen and the exported sha256. Such a file is
    "OK (exported with edits)" when the frozen hash is the registered one and the file hashes to the exported one.
  * WITHHELD.json: files that cannot be public, with the hash each manifest recorded. A missing file listed there with
    the registered hash is "WITHHELD (listed)", an explained entry, not a mismatch.
A file that is absent and not listed is MISSING; a file that is present with another hash is MISMATCH.
Exit status 0 only if every problem is explained. Standard library only."""
import argparse, hashlib, json, os, sys

# (id, path, sha256 recorded at freeze [full], frozen-prefix length in bytes or None, UTC freeze time)
DOCS = [
    ('PREREG_v1', 'paper/protocol_theory/prereg/PREREG_v1.md', '53e34f1fc0c061e8d67bb559b2458419154159608f9e63cadae8eb9bcbecee38', None, '2026-11-04 11:47:06'),
    ('E_PREDICTIONS_v1', 'paper/protocol_theory/prereg/E_PREDICTIONS_v1.md', '182365c95726d5b30319ac757a7859db1782ea59edadc4bf8431e4bf160ca8af', None, '2026-11-04 11:56:08'),
    ('X prereg', 'experiments/crossfamily/prereg.md', 'md5:6435db4804805d617f53df27e6f57eff', None, '2026-11-04 12:15'),
    ('PREREG_v2', 'paper/protocol_theory/prereg/PREREG_v2.md', '5da75e6170243f838fe0fe1dcb4250a21b8132fc97161e22d149f46fae0d73ac', None, '2026-11-04 14:46:45'),
    ('PREREG_v2.1', 'paper/protocol_theory/prereg/PREREG_v2.1_thinkingOFF.md', 'bb3696da3772d0c7ac67eae9f7f76162dbff11ca357161c34e3c5ca53fb44839', None, '2026-11-04 16:14:17'),
    ('PREREG_v2.2', 'paper/protocol_theory/prereg/PREREG_v2.2_thoughtSuppressed.md', 'ec9164ffa833f351618c3eb7ec69aa2e471e096307de7f5fd61e6c72e07f09d3', None, '2026-11-04 17:37:23'),
    ('X prereg_ext', 'experiments/crossfamily/prereg_ext.md', '0843ebd7c912b380134a800efefc9e121d59308dfbf4116f34fbc706a011cfdc', None, '2026-11-04 18:51'),
    ('PREREG_v2.3', 'paper/protocol_theory/prereg/PREREG_v2.3_onsetTransplant.md', '7111525f15d76787280b78e6b55494a00edb64c3456a1214f7aebfcdd0ee67cb', None, '2026-11-05 07:07:28'),
    ('PREREG_E', 'experiments/endtoend/PREREG_E.md', '20fa38602f745431575442024076611b7ac8f597df2b3c9961d89d3a7c791c0c', None, '2026-11-05 07:14'),
    ('PREREG_v2.4', 'paper/protocol_theory/prereg/PREREG_v2.4_injectedSlipRepair.md', 'e7af894ba355a03a5fb7b023c3c7ad860a5e8c3d666a4ab80e6ff6c7ea102090', None, '2026-11-05 11:07:17'),
    ('F ANALYSIS_PLAN', 'experiments/quant_margins/wsa/ANALYSIS_PLAN.md', 'c67d049a0649246b40f738f27c7706dac353d6207f28a1e082769bbb03982ceb', 6443, '2026-11-05 12:41'),
    ('F ANALYSIS_PLAN_addendum', 'experiments/quant_margins/wsa/ANALYSIS_PLAN_addendum.md', 'b332186fd362c33cdceb054f614270dc673525b03d93e1d066bf75c6ec6b898d', None, '2026-11-05 13:50'),
    ('PREREG_v2.5', 'paper/protocol_theory/prereg/PREREG_v2.5_stackGain.md', '50f8a39505e752e7fd528415c7593fe898af1bdfb61fdd89d35fea37cf51d75f', None, '2026-11-05 14:00:57'),
    ('F SWEEP_PLAN', 'experiments/quant_margins/wsa/SWEEP_PLAN.md', '7faf0172890c8aaa520adb1a03e91210028082935593db676097b92081a79c98', 4108, '2026-11-05 14:16'),
    ('PREREG_v2.6', 'paper/protocol_theory/prereg/PREREG_v2.6_auditBehaviour.md', 'ed19a6d07734afe795f63e7c9c5b6c3d1285d21deff828557ca28b1e333520f6', None, '2026-11-05 17:37:48'),
    ('PREREG_v2.5b', 'paper/protocol_theory/prereg/PREREG_v2.5b_stackGainE4B.md', 'c78e7512485a6f3e98e2fd71f319638aa72ff10f2eb5f6deedc89415a94ffb7d', None, '2026-11-05 21:09:59'),
    ('PREREG_v2.7', 'paper/protocol_theory/prereg/PREREG_v2.7_robustness.md', '3bc5b4a8f8a242b613265cd072183a39e09eefa17283216940367e860f469c29', None, '2026-11-06 13:32:39'),
    ('PREREG_v2.8', 'paper/protocol_theory/prereg/PREREG_v2.8_cli.md', 'c69d54a519b9e727323b38b6bdc7f9984d49e0d630122ac84679e7e568d8df98', None, '2026-11-06 17:30:46'),
    ('PREREG_E_ext', 'experiments/endtoend/PREREG_E_ext.md', 'cc4cc803dfa2de2444e766a8f864448177dee2653d24ffc61349da03f1de3056', None, '2026-11-06 17:54:21'),
    ('PREREG_v2.9', 'paper/protocol_theory/prereg/PREREG_v2.9_gemma_coverage.md', '565f3017602856a54535eb29733acc7db0ba4ac2520169e2d8571c0b9e916e58', None, '2026-11-06 17:56:22'),
    ('PREREG_v2.10', 'paper/protocol_theory/prereg/PREREG_v2.10_audit_breadth.md', '06b3ee6cd48eb3dec2dce9fa9f681f28ef63a6c8c95cf7264cb5e95fbf9827f0', None, '2026-11-06 17:59:10'),
    ('PREREG_E_awq', 'experiments/endtoend/PREREG_E_awq.md', '33d430ea8580f861cf2ce72d01d48c4c339750669f05703734cbcee57ec1f403', None, '2026-11-06 19:56:34'),
    ('PREREG_E_awq2', 'experiments/endtoend/PREREG_E_awq2.md', '7e7cc12df52c19e60c7ba92e3180454ddb7289dc9cee4d37da8840e18d598160', None, '2026-11-07 06:57:35'),
    ('PREREG_E_audit', 'experiments/endtoend/PREREG_E_audit.md', '90005d2f99a84f96297ccfb237bbe52895cd6fe41740e6fa9dd75dd801ff519c', None, '2026-11-07 07:12:07'),
    ('PREREG_E_comp', 'experiments/endtoend/PREREG_E_comp.md', '4d1acb426fb01490d9f9994405aef0f5dbc1d8568b83eddebc70b747474dc245', None, '2026-11-07 07:12:07'),
    ('PREREG_v2.11', 'paper/protocol_theory/prereg/PREREG_v2.11_masked_corpus.md', '50c2f0a320eaa4d0bb5cef419895064afbd7aba285e8c8bd4c7d3ecd0ef5acb9', None, '2026-11-07 21:55'),
    ('PREREG_v2.12', 'paper/protocol_theory/prereg/PREREG_v2.12_llama_family.md', '06caf31d298280f009c39943d84e454d6c264c9e57fee1444f3e574cb5f9d42f', None, '2026-11-08 00:14'),
    ('PREREG_v2.11b', 'paper/protocol_theory/prereg/PREREG_v2.11b_masked_replicate.md', 'f5f97848e3c2a30276f8544e727940919b553e690b9bb0a969efb412edf702aa', None, '2026-11-08 05:38'),
    ('PREREG_v2.13', 'paper/protocol_theory/prereg/PREREG_v2.13_llama3_hermes2pro.md', '9714ee69d404fcf72eef4bfb912dc42b151375f29f3ae4a49fb2144d7348cb10', None, '2026-11-08 06:36'),
    ('PREREG_v2.14', 'paper/protocol_theory/prereg/PREREG_v2.14_bf16_cli.md', '8ed7bccb117dc0443bef3fd492e43f5c12417d2575a471c8f2acbffb46ce95df', None, '2026-11-08 09:40'),
    ('PREREG_v2.15', 'paper/protocol_theory/prereg/PREREG_v2.15_audit_predicts_copying.md', 'efd6399be79b908196894f22026631ef415ea1f1fcf00bdac896ef1334aca7e5', None, '2026-11-08 09:45'),
    ('PREREG_v2.16', 'paper/protocol_theory/prereg/PREREG_v2.16_qat_weights.md', '080b6ecf05085fcd4c3407d32d65d33a4ec004f02f640a8c3039b2ad6d840098', None, '2026-11-08 11:20'),
]
# hash manifests written at freeze time: (id, manifest path, base dir the listed paths are relative to, algorithm)
MANIFESTS = [
    ('A confirmatory + v2.6 + bf16 scripts', 'experiments/contagion/out/confirmatory_script_hashes_v1.txt', 'experiments/contagion', 'sha256'),
    ('A v2.1/v2.2 scripts', 'experiments/contagion/out/v21_v22_script_hashes.txt', 'experiments/contagion', 'sha256'),
    ('A v2.3 scripts', 'experiments/contagion/out/onset_v23_script_hashes.txt', 'experiments/contagion', 'sha256'),
    ('X scripts as registered (md5)', 'experiments/crossfamily/data/prereg_hashes.md5', 'experiments/crossfamily', 'md5'),
    ('X discovery run snapshot (md5)', 'experiments/crossfamily/scripts/discovery/SNAPSHOT.md5', 'experiments/crossfamily/scripts', 'md5'),
    ('X PREREG_v2 run snapshot', 'experiments/crossfamily/scripts/v2_frozen/SHA256SUMS', 'experiments/crossfamily/scripts/v2_frozen', 'sha256'),
    ('X prereg_ext run snapshot', 'experiments/crossfamily/scripts/ext_frozen/SHA256SUMS', 'experiments/crossfamily/scripts/ext_frozen', 'sha256'),
    ('E code (PREREG_E)', 'experiments/endtoend/PREREG_E_manifest.txt', 'experiments/endtoend', 'sha256'),
    ('B v2.4 battery', 'experiments/intent_decoding/v24/FREEZE_MANIFEST.txt', 'experiments/intent_decoding/v24', 'sha256'),
    ('B v2.5 stack', 'experiments/intent_decoding/v25/FREEZE_MANIFEST_v25.txt', 'experiments/intent_decoding/v25', 'sha256'),
]
V27_CODE = [  # frozen with PREREG_v2.7 (13:32:39), v2.8 (17:30:46), E_ext (17:54:21), v2.9 (17:56:22), v2.10 (17:59:10),
              # E_awq (19:56:34) on Nov 6; E_awq2 (06:57:35), E_audit + E_comp (07:12:07) on Nov 7 -- hashes in PROGRESS.md
    ('experiments/contagion/scripts/analyze_v27_robustness.py', 'f68bc12dd6aaab1bba12eb94c6b6a664debe403b08b0d3cf5d836983c288fdb1'),
    ('experiments/soak/soak_drive.py', 'e229d4e4e1f716a4b2bbec4703b6246a9255accf33b6a2c76e4f9569ad749a3d'),
    ('experiments/soak/soak_analyze.py', 'f446092912181bc94c01c8547c30f5a51ec12b7811b2aef887060f19a1b36bcd'),
    ('experiments/contagion/scripts/analyze_v28_cli.py', 'c6c01aec47ec14ddbe521942934fcce03d304c739eeebae14c57a3a5d8f86045'),
    ('experiments/v28/run_cli.sh', 'a5a913d9cfa565a9df8617d4b805acf78dc35b3c5ea0fbb00e75db6149f98f43'),
    ('experiments/endtoend/analysis/prereg_E_ext_analysis.py', 'c61e66e1b842e575c66a2cd4526fbfcef6ea808be38b4b784009f175cfd8c192'),
    ('experiments/endtoend/ext/dispatch_ext.sh', '88c6ed5145b2cff731b56f960cac563ec637dce20bc1c6020645583309611bbf'),
    ('experiments/contagion/scripts/analyze_v29_coverage.py', '545a43444bea5c719897cfe4d170ceb47d5c7d57bff06d67db6cfa76efdcfe07'),
    ('experiments/v29/run_cov.sh', 'e73558f9c15cd24cb07a3a7dee64f85a69cfbd28e65254205c3f0842952c4b48'),
    ('experiments/v210/analyze_v210.py', 'd0f041185d42654f5e8f0fabe876f2e4a850ae6a990d0de0fcc9b202c2d4dd67'),
    ('experiments/v210/run_audits.sh', '4becb3c9254c398f93ea7273a3f6954d09f5e7f7ca8914ccd72839c47115105e'),
    ('experiments/v210/chain_gpu6.sh', 'cb69a03c9b02d12fdc8e8a6d2463d34bdb153047eca856420caed4f4fa5852a4'),
    ('experiments/endtoend/analysis/prereg_E_awq_analysis.py', 'ce96049efc90f1817b97d5bace10c7ee09e6c385a9020b424a41a485f4cede44'),
    ('experiments/endtoend/ext/run_awq.sh', '4029fcc4e4409e754ae0746aadf76a01ee5aa63e81b0afb4951bde52fbf61e34'),
    # E_awq2 (2026-11-07 06:57:35); prereg_analysis.py and run_population.sh are also in PREREG_E's manifest
    ('experiments/endtoend/analysis/prereg_E_awq2_analysis.py', 'dbc7e8b2301c18ff439133f5f13f28c01b4f6cfa10fed7577262350206b6b195'),
    ('experiments/endtoend/ext/dispatch_awq2.sh', 'faa381ee9fc95648c45451d0742896bf28c36511b1cb5e50b79f726861712b89'),
    ('experiments/endtoend/analysis/prereg_analysis.py', '1f8fca3ad11295dbff74c57feda4781a3a979d7e2b46db7feb4d328246dfbf76'),
    ('experiments/endtoend/run_population.sh', 'ef09af67b5b38f556cc6b68e9b8e0feff5cdb9e9e9a412f437f644ed19f05127'),
    # E_audit + E_comp (2026-11-07 07:12:07)
    ('experiments/endtoend/analysis/prereg_E_audit_analysis.py', '13a27cc367d4d7ad8bc21983b036d8d0f4848496a7ba06fa70157b36dcdd8c85'),
    ('experiments/endtoend/analysis/prereg_E_comp_analysis.py', '9175d26229d741436b4e2bd1c72863cee886b7536dea39eb9ab8fc2f550821c9'),
    ('experiments/endtoend/analysis/prereg_cov_common.py', 'e4f7affa603f1a155bf38fa67903712ece923150e7b1627eb68a6aea4f66218b'),
    ('experiments/endtoend/ext/dispatch_q.sh', '199456d530d72361f599baa2bb3b8110ae4ac0bd4d49225d6bcc4d8c6987ee94'),
    ('experiments/endtoend/ext/queue_single.txt', '425ba58479fa81b633dd8252746bb462a0eb8b8f517a5280232dbf8fbe1f5f5b'),
    ('experiments/endtoend/ext/queue_tp.txt', 'fbebb550a291b298e6daca9d2d3653c4bbff848f494c4201399569cb82010bed'),
    ('experiments/endtoend/run_population_qi.sh', '33459c10222ffbad607313398b8b5c626e8c1f96764d344870c3e529bfbf513a'),
    ('tools/dl_eaudit.sh', 'cd7f6041efca1cfcc3daaa04bd65b96e61c80ab3d4c3bd0a1d4da383afe1a5af'),
]
_XDEV = ('development copy. Registered runs executed from frozen snapshots (scripts/discovery/SNAPSHOT.md5, '
         'scripts/v2_frozen/, scripts/ext_frozen/), checked below; the discovery snapshot equals the registered md5 '
         'except the changes logged in experiments/crossfamily/PREREG_DEVIATIONS.md (12:17Z format_cpu fixed-point '
         'report, 12:25Z run_qwen hardening, 12:30Z analyze reference line; all before any GPU job or descriptive only)')
KNOWN = {  # path -> explanation of an expected mismatch (see PREREGISTRATIONS.md, "Audit of the hashes")
    'experiments/crossfamily/scripts/analyze.py': _XDEV, 'experiments/crossfamily/scripts/format_cpu.py': _XDEV,
    'experiments/crossfamily/scripts/qwenproto.py': _XDEV, 'experiments/crossfamily/scripts/run_qwen.py': _XDEV,
    'experiments/crossfamily/scripts/discovery/analyze.py': 'the logged 12:30Z descriptive reference line',
    'experiments/endtoend/PREREG_DEVIATIONS.md': 'append-only log (listed in the manifest; verified pre-unblinding 2026-11-06 00:01 UTC)',
    'experiments/endtoend/RUNBOOK.md': 'append-only log (listed in the manifest; verified pre-unblinding 2026-11-06 00:01 UTC)',
    'experiments/endtoend/export/quarantine_renderer.py': ('re-frozen by E on 2026-11-04 at 18:48 and 19:05 UTC '
        '(13e28567 -> 6b08b6e9 -> 5ca5c62c, the current file); 0 render differences on all 1,476 discovery + 4 smoke '
        'renders; recorded in experiments/contagion/out/confirmatory_script_hashes_v1.txt'),
    'experiments/intent_decoding/v25/stack_runner.py': ('operational fix 2026-11-05 15:05 UTC before any v2.5 outcome '
        'was opened (PREREG_DEVIATIONS.md, B entries for v2.5, item 6); new sha d3440af4 recorded there'),
}


def h(path, algo='sha256', n=None):
    d = hashlib.new(algo)
    with open(path, 'rb') as f:
        d.update(f.read() if n is None else f.read(n))
    return d.hexdigest()


# ---- public-tree lists (FROZEN_EXPORT_PINS.json, WITHHELD.json); {} when absent, e.g. on the project tree ----
def load_list(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        return json.load(open(path)).get('files', {})
    except (OSError, ValueError, AttributeError):
        return {}


class Lists:
    def __init__(self, root, pins_path, withheld_path):
        self.root = root
        self.pins = load_list(pins_path)
        self.withheld = load_list(withheld_path)

    def rel(self, fp):
        return os.path.relpath(fp, self.root).replace(os.sep, '/')

    def exported_ok(self, fp, want, algo='sha256'):
        """fp is the public copy of a frozen file whose frozen hash is `want`."""
        rec = self.pins.get(self.rel(fp))
        if not rec:
            return False
        frozen = rec.get('frozen_md5' if algo == 'md5' else 'frozen_sha256')
        return frozen == want and h(fp) == rec.get('exported_sha256')

    def exported_prefix_ok(self, fp, want, n):
        """fp is the public copy of a document whose frozen first-n-bytes hash is `want`."""
        rec = self.pins.get(self.rel(fp))
        pre = (rec or {}).get('frozen_prefix') or {}
        return bool(rec) and pre.get('bytes') == n and pre.get('sha256') == want and h(fp) == rec.get('exported_sha256')

    def withheld_status(self, cands, want, algo='sha256'):
        """(listed, hash matches, reason) for the first candidate path that WITHHELD.json lists."""
        for c in cands:
            rec = self.withheld.get(self.rel(c))
            if rec:
                return True, rec.get('md5' if algo == 'md5' else 'sha256') == want, rec.get('reason', 'withheld')
        return False, False, ''


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default='.'); ap.add_argument('--json', default='')
    ap.add_argument('--pins', default=None, help='FROZEN_EXPORT_PINS.json (default: ROOT/FROZEN_EXPORT_PINS.json if present; "" = none)')
    ap.add_argument('--withheld', default=None, help='WITHHELD.json (default: ROOT/WITHHELD.json if present; "" = none)')
    a = ap.parse_args()
    R = lambda p: os.path.join(a.root, p)  # noqa: E731
    L = Lists(a.root, R('FROZEN_EXPORT_PINS.json') if a.pins is None else a.pins,
              R('WITHHELD.json') if a.withheld is None else a.withheld)
    out = {'documents': [], 'manifests': [], 'v27_code': []}
    for pid, p, want, n, t in DOCS:
        rec = {'id': pid, 'path': p, 'frozen_utc': t}
        algo = 'md5' if want and want.startswith('md5:') else 'sha256'
        want_h = want[4:] if algo == 'md5' else want
        if not os.path.exists(R(p)):
            listed, match, why = L.withheld_status([R(p)], want_h, algo)
            rec['status'] = (f'WITHHELD (listed in WITHHELD.json: {why})' if match else
                             'WITHHELD-HASH-DIFFERS (listed in WITHHELD.json with another hash)' if listed else 'MISSING')
        elif want is None:
            rec['status'] = 'RECORDED-PREFIX-ONLY'; rec['sha256_now'] = h(R(p))
        elif algo == 'md5':
            rec['status'] = 'OK' if h(R(p), 'md5') == want_h else ('OK (exported with edits: FROZEN_EXPORT_PINS.json)' if L.exported_ok(R(p), want_h, 'md5') else 'MISMATCH')
        elif n is None:
            now = h(R(p)); rec['sha256_now'] = now
            rec['status'] = 'OK' if now == want else ('OK (exported with edits: FROZEN_EXPORT_PINS.json)' if L.exported_ok(R(p), want) else 'MISMATCH')
        else:
            ok = h(R(p), 'sha256', n) == want
            size = os.path.getsize(R(p))
            rec['status'] = (f'PREFIX-OK (first {n} of {size} bytes; {size - n} bytes appended after the freeze)' if ok else
                             'PREFIX-OK (exported with edits: FROZEN_EXPORT_PINS.json)' if L.exported_prefix_ok(R(p), want, n) else 'MISMATCH')
        out['documents'].append(rec)
    for mid, mp, base, algo in MANIFESTS:
        if not os.path.exists(R(mp)):
            listed, match, why = L.withheld_status([R(mp)], None)
            out['manifests'].append({'id': mid, 'manifest': mp, 'status': 'WITHHELD (listed)' if listed else 'MISSING'}); continue
        ok = bad = miss = exported = withheld = 0; bads = []; last = {}; superseded = 0
        for line in open(R(mp), encoding='utf-8'):
            line = line.rstrip('\n')
            if not line or line.startswith('#'): continue
            parts = line.split(None, 1)
            if len(parts) != 2 or not all(c in '0123456789abcdef' for c in parts[0]): continue
            want, rel = parts[0], parts[1].split('  (')[0].strip()
            if rel in last: superseded += 1  # re-frozen later in the same manifest: the last entry governs
            last[rel] = want
        for rel, want in last.items():
            cands = [os.path.normpath(os.path.join(R(b), rel)) for b in (base, os.path.dirname(mp), 'experiments', 'release/lib/src', 'slipguard/src', '.')]
            fp = next((c for c in cands if os.path.exists(c)), None)
            if fp is None:
                listed, match, why = L.withheld_status(cands, want, algo)
                if match:
                    withheld += 1; bads.append({'path': rel, 'status': 'WITHHELD', 'known': f'listed in WITHHELD.json: {why}'}); continue
                miss += 1
                bads.append({'path': rel, 'status': 'MISSING', 'known': '', 'note': 'listed in WITHHELD.json with another hash' if listed else ''})
                continue
            if h(fp, algo) == want: ok += 1
            elif L.exported_ok(fp, want, algo): ok += 1; exported += 1
            else:
                bad += 1
                key = os.path.relpath(fp, a.root)
                bads.append({'path': key, 'status': 'MISMATCH', 'known': KNOWN.get(key, '')})
        out['manifests'].append({'id': mid, 'manifest': mp, 'ok': ok, 'mismatch': bad, 'missing': miss, 'exported_with_edits': exported,
                                 'withheld': withheld, 'superseded_entries': superseded, 'details': bads})
    for p, want in V27_CODE:
        if not os.path.exists(R(p)):
            listed, match, why = L.withheld_status([R(p)], want)
            st = f'WITHHELD (listed: {why})' if match else ('WITHHELD-HASH-DIFFERS' if listed else 'MISSING')
        elif h(R(p)) == want:
            st = 'OK'
        elif L.exported_ok(R(p), want):
            st = 'OK (exported with edits)'
        else:
            st = 'MISMATCH'
        out['v27_code'].append({'path': p, 'status': st})
    for r in out['documents']:
        print(f"{r['status'][:60]:<62} {r['id']:<26} {r['frozen_utc']}")
    for m in out['manifests']:
        if m.get('status'):
            print(f"manifest {m['id']:<40} {m['status']}"); continue
        print(f"manifest {m['id']:<40} ok {m.get('ok', 0):>3} (exported with edits {m.get('exported_with_edits', 0):>2})  mismatch {m.get('mismatch', 0):>2}  missing {m.get('missing', 0):>2}  withheld {m.get('withheld', 0):>2}")
        for d in m.get('details', []):
            print(f"    {d['status']:<9} {d['path']}  {d.get('known', '') or d.get('note', '')}")
    for r in out['v27_code']:
        print(f"{r['status']:<9} {r['path']}")
    # exit status: 0 only if every document matches (fully, on its frozen prefix, or through its recorded export edits),
    # no file is missing unless WITHHELD.json lists it with the registered hash, and every mismatch has a documented
    # explanation in KNOWN; otherwise 1
    docs = out['documents']
    bad = [r for r in docs if not r['status'].startswith(('OK', 'PREFIX-OK', 'WITHHELD ('))]
    bad += [d for m in out['manifests'] for d in m.get('details', []) if d['status'] == 'MISSING' or (d['status'] == 'MISMATCH' and not d.get('known'))]
    bad += [m for m in out['manifests'] if m.get('status') == 'MISSING']
    bad += [r for r in out['v27_code'] if not r['status'].startswith(('OK', 'WITHHELD ('))]
    det = [d for m in out['manifests'] for d in m.get('details', [])]
    v27 = out['v27_code']
    summary = {
        'documents': {'n': len(docs), 'ok': sum(r['status'] == 'OK' for r in docs), 'prefix_ok': sum(r['status'].startswith('PREFIX-OK (first') for r in docs),
                      'exported_with_edits': sum('exported with edits' in r['status'] for r in docs),
                      'withheld': sum(r['status'].startswith('WITHHELD (') for r in docs), 'missing': sum(r['status'] == 'MISSING' for r in docs),
                      'mismatch': sum(r['status'] in ('MISMATCH', 'WITHHELD-HASH-DIFFERS (listed in WITHHELD.json with another hash)') for r in docs)},
        'manifest_entries': {'ok': sum(m.get('ok', 0) for m in out['manifests']),
                             'exported_with_edits': sum(m.get('exported_with_edits', 0) for m in out['manifests']),
                             'withheld': sum(m.get('withheld', 0) for m in out['manifests']),
                             'mismatch_explained': sum(d['status'] == 'MISMATCH' and bool(d.get('known')) for d in det),
                             'mismatch_unexplained': sum(d['status'] == 'MISMATCH' and not d.get('known') for d in det),
                             'missing': sum(d['status'] == 'MISSING' for d in det),
                             'manifests_missing': sum(m.get('status') == 'MISSING' for m in out['manifests'])},
        'frozen_code_v27': {'n': len(v27), 'ok': sum(r['status'] == 'OK' for r in v27), 'exported_with_edits': sum(r['status'] == 'OK (exported with edits)' for r in v27),
                            'withheld': sum(r['status'].startswith('WITHHELD (') for r in v27), 'missing': sum(r['status'] == 'MISSING' for r in v27),
                            'mismatch': sum(r['status'] not in ('OK', 'OK (exported with edits)', 'MISSING') and not r['status'].startswith('WITHHELD (') for r in v27)},
        'lists': {'FROZEN_EXPORT_PINS.json': len(L.pins), 'WITHHELD.json': len(L.withheld)},
        'unexplained_problems': len(bad)}
    out['summary'] = summary
    if a.json:
        json.dump(out, open(a.json, 'w'), indent=1)
    sd, sm, sv = summary['documents'], summary['manifest_entries'], summary['frozen_code_v27']
    print(f"\ndocuments {sd['ok'] + sd['prefix_ok'] + sd['exported_with_edits'] + sd['withheld']}/{sd['n']} "
          f"({sd['ok']} OK, {sd['prefix_ok']} by frozen prefix, {sd['exported_with_edits']} exported with edits, {sd['withheld']} withheld; "
          f"{sd['missing']} missing, {sd['mismatch']} mismatch) | manifest entries: {sm['ok']} OK ({sm['exported_with_edits']} exported with edits), "
          f"{sm['withheld']} withheld (listed), {sm['mismatch_explained']} mismatch with a logged reason, {sm['mismatch_unexplained']} unexplained, "
          f"{sm['missing']} missing | frozen code v2.7+: {sv['ok'] + sv['exported_with_edits']}/{sv['n']} OK "
          f"({sv['exported_with_edits']} exported with edits), {sv['withheld']} withheld, {sv['missing']} missing, {sv['mismatch']} mismatch")
    print(f"{'PASS' if not bad else 'FAIL'}: {len(bad)} unexplained problem(s)")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
