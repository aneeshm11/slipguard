"""Shared helpers: historical tool_call arguments must be dicts for the Gemma-4 chat template."""
import os  # added by the repo export (paths are env/config driven)
import json


def fix_msgs(msgs):
    out = []
    for m in msgs:
        m = dict(m)
        if m.get('tool_calls'):
            tcs = []
            for t in m['tool_calls']:
                t = json.loads(json.dumps(t)); f = t.get('function', {})
                if isinstance(f.get('arguments'), str):
                    try:
                        f['arguments'] = json.loads(f['arguments'])
                    except Exception:
                        f['arguments'] = {}
                if not isinstance(f.get('arguments'), dict):
                    f['arguments'] = {}
                tcs.append(t)
            m['tool_calls'] = tcs
        out.append(m)
    return out


# ---------------------------------------------------------------------------------------------- template selection
# 'june' = the main-track chat template that PRODUCED the logs (log-faithful; primary for the head-to-head);
# 'july' = the current HF template (2026-07-09, md5 f016bd4b...), which the tokenizer dir ships; arm 12.
TEMPLATES = {'june': os.path.join(os.environ.get('TRANSCRIPTLAB_DISCOVERY_ROOT', '(data holder only)'), 'work/models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja'),
             'july': os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja')}
_TPL_CACHE = {}


def template_text(name):
    if name not in _TPL_CACHE:
        _TPL_CACHE[name] = open(TEMPLATES[name]).read()
    return _TPL_CACHE[name]


def render_prompt(tok, messages, tools, think, template=None):
    """template=None -> the tokenizer's own template (E4B/12B use their shipped template)."""
    kw = {}
    if template:
        kw['chat_template'] = template_text(template)
    return tok.apply_chat_template(fix_msgs(messages), tools=tools, add_generation_prompt=True, tokenize=False,
                                   enable_thinking=bool(think), **kw)


# ---------------------------------------------------------------------------------------------- exemplar immunization
EXEMPLAR_ARGS = {'filepath': 'NOTES.md', 'old_string': '## Notes\n',
                 'new_string': '## Notes\n\nVerify every change with `python -m pytest -x -q`'}


def with_exemplar(messages):
    """P0-B arm 11: one synthetic CLEAN edit_file exchange (harness format: call + success response) inserted right after
    the first user message. Its new_string ends with a backtick -- the hardest closing case -- correctly closed."""
    out, done = [], False
    for m in messages:
        out.append(m)
        if not done and m.get('role') == 'user':
            done = True
            cid = 'exemplar-call-0'
            out.append({'role': 'assistant', 'content': '', 'tool_calls': [
                {'type': 'function', 'id': cid, 'function': {'name': 'edit_file', 'arguments': json.dumps(EXEMPLAR_ARGS)}}]})
            diff = ('--- a/NOTES.md\n+++ b/NOTES.md\n@@ -1 +1,3 @@\n ## Notes\n+\n'
                    '+Verify every change with `python -m pytest -x -q`\n')
            out.append({'role': 'tool', 'tool_call_id': cid, 'content': json.dumps(
                {'status': 'ok', 'filepath': 'NOTES.md', 'occurrences': 1, 'strategy': 'exact', 'diff': diff,
                 'is_truncated': False})})
    return out
