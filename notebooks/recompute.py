"""Re-derive the writeup's headline results from the RELEASED raw records (stdlib only, no research code imported).

Each check:
* recomputes one value from raw records, e.g. the judge verdict of every generation of a registered run;
* reads the released result for the same quantity from the file that RESULTS.md cites;
* reports both.

`reproduce_numbers.py` compares them.

Layouts:
* the repository root, a checkout or the Kaggle dataset that bundles it;
* the PNC dataset, either inside it (data/pnc) or attached separately (`$PNC_ROOT`, /kaggle/input/*).
"""
import glob
import json
import os

C = 'experiments/contagion/out/'
REG = C + 'confirmatory/confirm_v2_all_full.json'
BF16 = C + 'confirmatory/bf16_core_all.json'


def find_repo(arg=None):
    cands = [arg, os.environ.get('TRANSCRIPTLAB_ROOT'), os.getcwd()]
    cands += [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    cands += sorted(glob.glob('/kaggle/input/*')) + sorted(glob.glob('/kaggle/input/*/*')) + sorted(glob.glob('/kaggle/input/*/*/*')) + sorted(glob.glob('/kaggle/input/*/*/*/*'))
    for c in cands:
        if c and os.path.isfile(os.path.join(c, REG)):
            return c
    raise SystemExit('repository not found: pass its root, set TRANSCRIPTLAB_ROOT, or attach the repository dataset on Kaggle')


def find_pnc(repo):
    cands = [os.environ.get('PNC_ROOT'), os.path.join(repo, 'data', 'pnc')]
    cands += sorted(glob.glob('/kaggle/input/*')) + sorted(glob.glob('/kaggle/input/*/*')) + sorted(glob.glob('/kaggle/input/*/*/*')) + sorted(glob.glob('/kaggle/input/*/*/*/*')) + sorted(glob.glob('/kaggle/input/*/data/pnc')) + sorted(glob.glob('/kaggle/input/*/*/*/data/pnc'))
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'MANIFEST.json')) and os.path.isdir(os.path.join(c, 'episodes')):
            return c
    return None


def reference(root, rel, path):
    """the released value at file#path (RESULTS.md's source); list indices allowed (`.../RD_P1_P0/0`)"""
    d = json.load(open(rel if os.path.isabs(rel) else os.path.join(root, rel)))
    for k in path.split('/'):
        d = d[int(k)] if isinstance(d, list) else d[k]
    return d


def _records(root, rel):
    with open(os.path.join(root, rel)) as f:
        return [json.loads(line) for line in f if line.strip()]


def _rate(rs, arm, k, tier=None):
    """unconditional P(next call is a malformed edit), first record per state (as the frozen analyses count)"""
    seen = {}
    for r in rs:
        if r['pathway'] == arm and r['k'] == k and (tier is None or r.get('tier') == tier) and not r.get('error'):
            seen.setdefault(r['id'], r)
    hits = 0
    for r in seen.values():
        j = r.get('judge') or {}
        hits += bool(j.get('is_edit', j.get('name') == 'edit_file')) and bool(j.get('malformed'))
    return hits / len(seen), len(seen)


def transcriptlab_confirmatory(root, pnc=None):
    """TranscriptLab on 300 public PNC states, Gemma-4-31B 4-bit (registered battery, PREREG_v2): RESULTS.md rows
    'copying', 'induction; dose k=4' and 'quarantine removal'."""
    rs = _records(root, C + 'main/rC31b_v2.jsonl')
    p0, p1 = _rate(rs, 'P0', 0), _rate(rs, 'P1', 1)
    p6, p6k4, p8 = _rate(rs, 'P6', 1, 'A1'), _rate(rs, 'P6', 4), _rate(rs, 'P8a', 1)
    return [
        ('31B copying: P0 rate', p0[0], p0[1], REG, '31B/full/C1/uncond/base'),
        ('31B copying: P1 rate', p1[0], p1[1], REG, '31B/full/C1/uncond/arm'),
        ('31B copying: RD P1 - P0', p1[0] - p0[0], p1[1], REG, '31B/full/C1/uncond/RD'),
        ('31B induction: RD P6 - P0', p6[0] - p0[0], p6[1], REG, '31B/full/C2/uncond/RD'),
        ('31B induction dose: k=4 rate', p6k4[0], p6k4[1], REG, '31B/C3/uncond/rates/k=4'),
        ('31B quarantine removal (P8a)', (p1[0] - p8[0]) / (p1[0] - p0[0]), p8[1], REG, '31B/full/C5/uncond/removal'),
    ]


def bf16_row(root, pnc=None):
    """the same battery on bf16 weights: RESULTS.md row '31B bf16: copying and induction'"""
    rs = _records(root, C + 'main/rCbf16_v2.jsonl')
    p0, p1, p6 = _rate(rs, 'P0', 0), _rate(rs, 'P1', 1), _rate(rs, 'P6', 1)
    return [('31B bf16 copying: RD P1 - P0', p1[0] - p0[0], p1[1], BF16, 'uncond/RD_P1_P0/0'),
            ('31B bf16 induction: RD P6 - P0', p6[0] - p0[0], p6[1], BF16, 'uncond/RD_P6_P0/0')]


def pnc_corpus(root, pnc):
    """the corpus itself: episodes, turns, graded and resolved, recounted from the episode files"""
    if pnc is None:
        raise FileNotFoundError('PNC dataset not attached (set PNC_ROOT or attach it on Kaggle)')
    eps = sorted(glob.glob(os.path.join(pnc, 'episodes', '*.jsonl')))
    turns = 0
    for f in eps:
        with open(f) as fh:
            turns += sum(1 for line in fh if line.strip())
    conf = 'slipguard/results/conformance_pnc/RESULTS.json' if os.path.isdir(os.path.join(root, 'slipguard')) else 'release/lib/results/conformance_pnc/RESULTS.json'
    return [('PNC episodes', len(eps), None, os.path.join(pnc, 'MANIFEST.json'), 'n_episodes'),
            ('PNC model turns (= the conformance run inputs)', turns, None, conf, 'stream_vs_server/gg.vllm019/n')]


def discovery_released(root, pnc=None):
    """size of the released discovery split (snippets + pointers) against its build summary"""
    base = next((b for b in (os.path.join(root, 'release', 'package', 'v1.0'), root) if os.path.isdir(os.path.join(b, 'corpus', 'discovery'))), None)
    if base is None:
        raise FileNotFoundError('release package (corpus/discovery) not attached')
    n_snip = sum(1 for _ in open(os.path.join(base, 'corpus/discovery/slips_snippets.jsonl')))
    n_ptr = sum(1 for _ in open(os.path.join(base, 'corpus/discovery/pointers.jsonl')))
    summ = os.path.join(base, 'corpus/discovery/build_summary.json')
    return [('discovery snippets', n_snip, None, summ, 'released_records'),
            ('discovery pointer rows', n_ptr, None, summ, 'pointer_only')]


CHECKS = (transcriptlab_confirmatory, bf16_row, pnc_corpus, discovery_released)
