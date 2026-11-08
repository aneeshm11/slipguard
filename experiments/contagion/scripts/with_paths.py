"""Run one of A's scripts with the main-track data paths that the user moved on 2026-11-04 at about 18:12 UTC
(/harness -> <competition-logs>). Points variants.ROOT (main-track logs, read-only) and
gemma_protocol.OLD_TEMPLATE (June template) at the new location in-process, checks that both exist and that the
template is the June one (md5 d6c5bd0d...), then runs the target script unchanged (runpy). Frozen files are not edited.
usage: with_paths.py <script.py> <its arguments>"""
import sys, os, runpy, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OLD, NEW = '/harness', '<competition-logs>'
import gemma_protocol as gp
import variants as V
if not os.path.exists(gp.OLD_TEMPLATE):
    gp.OLD_TEMPLATE = gp.OLD_TEMPLATE.replace(OLD, NEW, 1)
if not os.path.isdir(V.ROOT):
    V.ROOT = V.ROOT.replace(OLD, NEW, 1)
assert os.path.isdir(V.ROOT), V.ROOT
assert hashlib.md5(open(gp.OLD_TEMPLATE, 'rb').read()).hexdigest() == 'd6c5bd0d1e797798f3a598dd7fd7f020', gp.OLD_TEMPLATE
print('data paths:', V.ROOT, '|', gp.OLD_TEMPLATE, flush=True)
target = os.path.abspath(sys.argv[1]); sys.argv = sys.argv[1:]
runpy.run_path(target, run_name='__main__')
