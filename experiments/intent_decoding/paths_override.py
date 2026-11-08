"""Path shim after the user moved the main-track tree from /harness to <competition-logs> (~18:12 UTC,
2026-11-04; read-only use approved).  replay_utils.py and mine_logs.py hard-code the old path and are left unedited:
`import paths_override` (after sys.path has this directory) re-points them in memory and verifies the June-5 template
md5 d6c5bd0d1e797798f3a598dd7fd7f020.  The frozen confirm/ package reads P's manifest template and is unaffected."""
import hashlib, os
OLD, NEW = '/harness', '<competition-logs>'
JUNE_MD5 = 'd6c5bd0d1e797798f3a598dd7fd7f020'


def _moved(p):
    return NEW + p[len(OLD):] if p.startswith(OLD) and not os.path.exists(p) else p


def apply():
    import replay_utils
    replay_utils.TEMPLATES['june'] = _moved(replay_utils.TEMPLATES['june'])
    md5 = hashlib.md5(open(replay_utils.TEMPLATES['june'], 'rb').read()).hexdigest()
    assert md5 == JUNE_MD5, f'June template md5 {md5} != {JUNE_MD5}'
    replay_utils._TPL_CACHE.pop('june', None)
    return replay_utils.TEMPLATES['june']


def patch_mine_logs(mod):
    """call with the imported mine_logs module before mining (one-off miner; not imported here)."""
    mod.ROOT = _moved(mod.ROOT)
    return mod.ROOT


JUNE_TEMPLATE_PATH = apply()
