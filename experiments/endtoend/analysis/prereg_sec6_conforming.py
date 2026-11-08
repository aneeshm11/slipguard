"""POST-UNBLINDING CORRECTION WRAPPER (2026-11-06; not part of the frozen manifest).
The frozen analysis/prereg_analysis.py (sha 1f8fca3a...) flags an episode as an infrastructure failure when its error
starts with 'Sandbox execution error: litellm'. That prefix also covers the proxy's 400 "Input length (N) exceeds model's
maximum context length", which PREREG_E §6 classifies as an OUTCOME ("Context-length errors ... are outcomes, not
failures"). This wrapper imports the frozen module unchanged and only re-classifies those context-length errors as
outcomes; everything else (endpoints, estimators, bootstrap seeds) is the frozen code. Usage: same CLI as the frozen
script (population ...)."""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('prereg_frozen', Path(__file__).with_name('prereg_analysis.py'))
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
_orig = F.episode


def episode(reqs, per_task_rec, after_index=None):
    e = _orig(reqs, per_task_rec, after_index)
    if "exceeds model's maximum context length" in (per_task_rec.get('error') or ''):
        e['infra_error'] = False   # PREREG_E §6: context-length errors are outcomes
    return e


F.episode = episode
if __name__ == '__main__':
    F.main()
