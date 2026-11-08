"""Render-condition wrapper around the FROZEN scripts/run_injection.py (sha256 1aadb39d..., not modified) for
PREREG_v2.1 (thinking-OFF flag) and PREREG_v2.2 (arm set S, arm set H). The condition is applied by replacing
variants.render in-process; run_injection.py then runs unchanged (same generation, budget, judge and seeds).
  --cond ON   discovery render: enable_thinking=true (identity; for checks)
  --cond OFF  PREREG_v2.1: enable_thinking=false (the shipped flag); nothing else changes
  --cond S    PREREG_v2.2 set S: enable_thinking=false and the template's own closed empty thought
              '<|channel>thought\\n<channel|>' (token ids 100, 45518, 107, 101) appended right after the generation prompt,
              unless the template already ended the prompt with it; prior thoughts stay in history as logged
  --cond H    PREREG_v2.2 set H: enable_thinking=true; every assistant message's reasoning removed from the history
  --cond SON  alternative S operationalisation kept available (not the registered choice): enable_thinking=true + the
              same closed empty thought appended
All other arguments go to run_injection.py unchanged. Put 'cond' into every plan job so it is stored in each record.
usage: run_cond.py --cond ON|OFF|S|H|SON <run_injection.py arguments>"""
import sys, os, copy, runpy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import variants as V
PRE = '<|channel>thought\n<channel|>'
_render = V.render


def install(cond):
    """Replace variants.render by the condition's render (idempotent; ON restores the original)."""
    assert cond in ('ON', 'OFF', 'S', 'H', 'SON'), cond

    def render(tok, msgs, tools, subs=(), which='old', think=True):
        if cond == 'H':
            msgs = copy.deepcopy(msgs)
            for m in msgs:
                if m.get('role') == 'assistant':
                    m.pop('reasoning_content', None); m.pop('reasoning', None)
        s = _render(tok, msgs, tools, subs, which, think=(cond in ('ON', 'H', 'SON')))
        if cond in ('S', 'SON') and not s.endswith(PRE):
            s = s + PRE
        return s
    V.render = _render if cond == 'ON' else render


if __name__ == '__main__':
    args = sys.argv[1:]
    i = args.index('--cond'); COND = args[i + 1]; del args[i:i + 2]
    install(COND)
    print('render condition', COND, flush=True)
    sys.argv = [os.path.join(HERE, 'run_injection.py')] + args
    runpy.run_path(os.path.join(HERE, 'run_injection.py'), run_name='__main__')
