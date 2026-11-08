"""Per-task wheel sets for the official Docker harness (makes the public tasks gradable).

Problem: swegemma injects EVERY <16 MB wheel of `wheels_dir` (newest version per package) into the container's
site-packages. With the public wheels only 43/129 gold patches pass (pydantic needs typing_inspection, starlette
1.x breaks older fastapi snapshots, ...); adding PyPI test deps breaks rich tasks (pytest plugins such as
inline_snapshot import `rich` from site-packages before the workspace is on sys.path).

Fix (selection logic ported from the main-track scorer replica, /harness/work/scripts/scorer_env.py,
read-only): per task, a wheel set that
  * excludes the package under test (the workspace is importable through setup.py's workspace_paths.pth),
  * restricts test-only plugins to the repos that need them (ONLY_FOR),
  * keeps the image's own pytest stack (pytest/pytest-timeout/pluggy/iniconfig are not re-injected),
  * picks the NEWEST version allowed by the snapshot's own pyproject dependencies (+ transitive Requires-Dist),
  * applies the replica's gold-derived calibration pins (old pygments / werkzeug+flask for a few tasks).
Identical selections share one directory (wheelsets/<sha>/, symlinks into wheels_pool/), and the harness tar cache
is keyed by the selection hash. Routing: common.CUR_TASK (contextvar) -> resolve_wheels_dir.
"""
from __future__ import annotations
import os  # added by the repo export (paths are env/config driven)

import hashlib
import json
import re
import tarfile
import threading
import tomllib
import zipfile
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

E2E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))
COMP = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/comp'))
POOL = E2E / 'wheels_pool'
SETS = E2E / 'wheelsets'
TAG = 'cp313'
OWN = {'fastapi/fastapi': 'fastapi', 'Textualize/rich': 'rich', 'psf/requests': 'requests', 'encode/httpx': 'httpx'}
ONLY_FOR = {'pytest_httpbin': {'psf/requests'}, 'httpbin': {'psf/requests'}, 'flasgger': {'psf/requests'},
            'brotlicffi': {'psf/requests', 'encode/httpx'}, 'brotli': {'encode/httpx'}, 'zstandard': {'encode/httpx'},
            'inline_snapshot': {'fastapi/fastapi'}, 'dirty_equals': {'fastapi/fastapi'}}
IMAGE_KEEP = {'pytest', 'pytest_timeout', 'pluggy', 'iniconfig'}
CALIBRATION = {  # from the main-track replica (found by grading gold patches)
    'rich_3064': {'pygments': '2.15.1'}, 'rich_3130': {'pygments': '2.15.1'}, 'rich_3296': {'pygments': '2.16.1'},
    'rich_3469': {'pygments': '2.18.0'}, 'rich_3782': {'pygments': '2.19.2'}, 'rich_4070': {'pygments': '2.19.2'},
    'rich_4079': {'pygments': '2.20.0'},
    'requests_6589': {'werkzeug': '2.3.8', 'flask': '2.3.3'}, 'requests_6592': {'werkzeug': '2.3.8', 'flask': '2.3.3'},
    'requests_6629': {'werkzeug': '2.3.8', 'flask': '2.3.3'},
}
_norm = lambda n: re.sub(r'[-_.]+', '_', n).lower()  # noqa: E731
_lock = threading.Lock()
_POOL_IDX = None
_PUBLIC = None
_CACHE: dict[str, Path] = {}


def _fits(w: Path) -> bool:
    py, abi, plat = w.name[:-4].split('-')[-3:]
    if plat != 'any' and 'linux' not in plat:
        return False
    if abi == 'abi3':
        return int(py.split('.')[0][2:]) <= int(TAG[2:])
    return any(t.startswith('py3') for t in py.split('.')) or TAG in py.split('.')


def pool():
    global _POOL_IDX, _PUBLIC
    if _POOL_IDX is None:
        _PUBLIC = {w.name for w in (COMP / 'wheels').glob('*.whl')}
        idx: dict[str, list] = {}
        for w in sorted(POOL.glob('*.whl')):
            if not _fits(w):
                continue
            name, ver = w.name.split('-')[:2]
            idx.setdefault(_norm(name), []).append((Version(ver), w))
        _POOL_IDX = idx
    return _POOL_IDX


def pyproject_of(task_id: str) -> dict:
    cache = SETS / '_pyproject' / f'{task_id}.json'
    if cache.exists():
        return json.loads(cache.read_text())
    data = {}
    with tarfile.open(COMP / 'snapshots' / f'{task_id}.tgz') as tf:
        for m in tf:
            if m.name in ('./pyproject.toml', 'pyproject.toml'):
                try:
                    data = tomllib.loads(tf.extractfile(m).read().decode())
                except Exception:  # noqa: BLE001
                    data = {}
                break
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, default=str))
    return data


def _poetry_to_pep440(spec) -> str:
    spec = spec if isinstance(spec, str) else (spec or {}).get('version', '')
    m = re.fullmatch(r'\^(\d+)(\.\d+)?(\.\d+)?', spec.strip())
    return f'>={spec.strip()[1:]},<{int(m.group(1)) + 1}' if m else ('' if spec.strip() == '*' else spec)


def select(task_id: str, repo: str) -> dict[str, Path]:
    idx = pool()
    own = OWN.get(repo)
    sel: dict[str, Path] = {}
    for name, opts in idx.items():
        if name == own or name in IMAGE_KEEP or (name in ONLY_FOR and repo not in ONLY_FOR[name]):
            continue
        public = [(v, w) for v, w in opts if w.name in _PUBLIC]
        if public:
            sel[name] = max(public)[1]
        elif name != 'pygments':
            sel[name] = max(opts)[1]
    data = pyproject_of(task_id)
    reqs = list(data.get('project', {}).get('dependencies', []))
    reqs += [n + _poetry_to_pep440(s) for n, s in data.get('tool', {}).get('poetry', {}).get('dependencies', {}).items()
             if n != 'python']
    queue, seen = list(reqs), set()
    while queue:
        try:
            req = Requirement(queue.pop(0))
        except Exception:  # noqa: BLE001
            continue
        key = _norm(req.name)
        if key in seen or key == own or key in IMAGE_KEEP or (req.marker and not req.marker.evaluate({'extra': ''})):
            continue
        seen.add(key)
        options = [(v, w) for v, w in idx.get(key, []) if req.specifier.contains(v, prereleases=True)
                   and not (key in ONLY_FOR and repo not in ONLY_FOR[key])]
        if options:
            best = max(options)[1]
            sel[key] = best
            with zipfile.ZipFile(best) as z:
                meta = next(n for n in z.namelist() if n.endswith('.dist-info/METADATA'))
                queue += [ln.split(':', 1)[1].strip() for ln in z.read(meta).decode(errors='replace').splitlines()
                          if ln.startswith('Requires-Dist:')]
    for name, ver in CALIBRATION.get(task_id, {}).items():
        hit = [w for v, w in idx.get(name, []) if str(v) == ver]
        if hit:
            sel[name] = hit[0]
    return sel


def wheel_dir(task_id: str, repo: str) -> Path:
    """Selection directory for a task. Creation is atomic across processes (build in a temp dir, rename)."""
    import os
    import shutil
    import time
    with _lock:
        if task_id in _CACHE:
            return _CACHE[task_id]
        sel = select(task_id, repo)
        sha = hashlib.sha1('\n'.join(sorted(p.name for p in sel.values())).encode()).hexdigest()[:12]
        d = SETS / sha
        if not (d / '.complete').exists():
            tmp = SETS / f'.tmp_{sha}_{os.getpid()}_{threading.get_ident()}'
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            for p in sel.values():
                (tmp / p.name).symlink_to(p)
            (tmp / 'selection.json').write_text(json.dumps(sorted(p.name for p in sel.values()), indent=0))
            (tmp / '.complete').write_text('ok')
            try:
                os.rename(tmp, d)
            except OSError:  # another process won the race (or a stale partial dir exists)
                shutil.rmtree(tmp, ignore_errors=True)
                for _ in range(300):
                    if (d / '.complete').exists():
                        break
                    time.sleep(0.1)
                if not (d / '.complete').exists():
                    raise RuntimeError(f'wheel set {d} incomplete')
        (SETS / '_index').mkdir(parents=True, exist_ok=True)
        (SETS / '_index' / f'{task_id}.txt').write_text(sha)
        _CACHE[task_id] = d
        return d


def install(cur_task_var, tasks_by_id: dict) -> None:
    """Route swegemma's wheel resolution through the per-task sets; key the unpacked-wheel tar cache by content."""
    import swegemma.harness.container_setup as cs
    orig_resolve, orig_build = cs.resolve_wheels_dir, cs._build_unpacked_wheels_tar

    def resolve(config=None):
        tid = cur_task_var.get()
        t = tasks_by_id.get(tid.split(':')[-1]) if tid else None
        return wheel_dir(t.instance_id, t.repo) if t is not None else orig_resolve(config)

    def build(selected_wheels, cache_name, marker_name):
        h = hashlib.sha1('\n'.join(sorted(Path(w).name for w in selected_wheels)).encode()).hexdigest()[:10]
        return orig_build(selected_wheels, f'{cache_name}_{h}', marker_name)

    cs.resolve_wheels_dir = resolve
    cs._build_unpacked_wheels_tar = build
