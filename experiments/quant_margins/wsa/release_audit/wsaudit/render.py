"""Exact PNC prompt rendering (vLLM 0.19.1-faithful): the corpus chat template, system content as text parts, tool-call
arguments JSON -> dicts, reasoning mirrored. All paths are arguments; nothing host-specific."""
import json, os, re


class PNCRenderer:
    EDIT = {'S1': {'tool': 'edit_file', 'path': 'file_path', 'old': 'old_string', 'new': 'new_string'},
            'S2': {'tool': 'str_replace_editor', 'path': 'path', 'old': 'old_str', 'new': 'new_str'}}
    SCHEMA_DIR = {'S1': 'P-swebench-31b-S1-v1', 'S2': 'P-swebench-31b-S2-v1'}

    def __init__(self, pnc_dir, tokenizer_dir):
        from transformers import AutoTokenizer
        self.pnc = pnc_dir
        self.tok = AutoTokenizer.from_pretrained(tokenizer_dir)
        self.template = open(os.path.join(pnc_dir, 'chat_template.jinja')).read()
        self._tools = {}

    def tools(self, schema):
        if schema not in self._tools:
            self._tools[schema] = json.load(open(os.path.join(self.pnc, 'contexts', self.SCHEMA_DIR[schema], 'manifest.json')))['tools']
        return self._tools[schema]

    @staticmethod
    def _fix(msgs):
        out = []
        for m in msgs:
            m = json.loads(json.dumps(m))
            if m.get('role') == 'assistant':
                r = m.get('reasoning', m.get('reasoning_content'))
                if r is not None:
                    m['reasoning'] = r; m['reasoning_content'] = r
                if m.get('tool_calls'):
                    for t in m['tool_calls']:
                        f = t.get('function', {}); a = f.get('arguments')
                        if isinstance(a, str):
                            try:
                                f['arguments'] = json.loads(a) if a else {}
                            except Exception:
                                f['arguments'] = {}
                elif 'tool_calls' in m:
                    m.pop('tool_calls')
            if m.get('role') == 'system' and isinstance(m.get('content'), str):
                m['content'] = [{'type': 'text', 'text': m['content']}]
            out.append(m)
        return out

    def render(self, messages, schema):
        return self.tok.apply_chat_template(self._fix(messages), tools=self.tools(schema), add_generation_prompt=True,
                                            tokenize=False, enable_thinking=True, chat_template=self.template)

    def encode(self, text):
        return self.tok(text, add_special_tokens=False).input_ids

    def lookalike_ids(self):
        v = self.tok.get_vocab()
        return sorted(i for t, i in v.items() if re.fullmatch(r'▁?[`"\'\\]+,?', t))

    def turn(self, episode_id, turn_index):
        with open(os.path.join(self.pnc, 'episodes', episode_id + '.jsonl')) as f:
            for l in f:
                t = json.loads(l)
                if t.get('record_type') == 'turn' and t['turn_index'] == turn_index:
                    return t
        raise KeyError((episode_id, turn_index))
