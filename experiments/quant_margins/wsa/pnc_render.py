"""Exact prompt rendering for the PUBLIC PNC corpus (data/pnc): the corpus' own chat template, vLLM 0.19.1-faithful
message handling (string contents -> text parts as configured, tool-call arguments JSON -> dicts, reasoning mirrored),
tools from the context manifests. Validated against the logged prompt_tokens (see validate())."""
import json, os, re, glob
from functools import lru_cache

PNC = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc')
TOK_DIR = os.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), 'gemma-4-31b-it-qat-w4a16-ct')
TEMPLATE = open(os.path.join(PNC, 'chat_template.jinja')).read()
SCHEMA_DIR = {'S1': 'P-swebench-31b-S1-v1', 'S2': 'P-swebench-31b-S2-v1'}
EDIT = {'S1': {'tool': 'edit_file', 'path': 'file_path', 'old': 'old_string', 'new': 'new_string', 'fixed': {}},
        'S2': {'tool': 'str_replace_editor', 'path': 'path', 'old': 'old_str', 'new': 'new_str', 'fixed': {'command': 'str_replace'}}}
D = '<|"|>'; DQ = 52


@lru_cache(1)
def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(TOK_DIR)


@lru_cache(4)
def tools(schema):
    return json.load(open(os.path.join(PNC, 'contexts', SCHEMA_DIR[schema], 'manifest.json')))['tools']


def fix_messages(msgs, parts='system'):
    out = []
    for i, m in enumerate(msgs):
        m = json.loads(json.dumps(m))
        if m.get('role') == 'assistant':
            r = m.get('reasoning', m.get('reasoning_content'))
            if r is not None:
                m['reasoning'] = r; m['reasoning_content'] = r
            if m.get('tool_calls'):
                for t in m['tool_calls']:
                    f = t.get('function', {}); a = f.get('arguments')
                    if isinstance(a, str):
                        try: f['arguments'] = json.loads(a) if a else {}
                        except Exception: f['arguments'] = {}
            elif 'tool_calls' in m:
                m.pop('tool_calls')
        if isinstance(m.get('content'), str) and (parts == 'all' or (parts == 'system' and m.get('role') == 'system')):
            m['content'] = [{'type': 'text', 'text': m['content']}]
        out.append(m)
    return out


def render(messages, schema, parts='system'):
    return tokenizer().apply_chat_template(fix_messages(messages, parts), tools=tools(schema), add_generation_prompt=True,
                                           tokenize=False, enable_thinking=True, chat_template=TEMPLATE)


def encode(text):
    return tokenizer()(text, add_special_tokens=False).input_ids


def lookalike_ids():
    v = tokenizer().get_vocab()
    return sorted(i for t, i in v.items() if re.fullmatch(r'▁?[`"\'\\]+,?', t))


def episodes():
    return sorted(glob.glob(os.path.join(PNC, 'episodes', '*.jsonl')))
