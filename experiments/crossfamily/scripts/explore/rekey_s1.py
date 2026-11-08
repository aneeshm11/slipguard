import copy, json


def rekey(msgs, tools):
    tools = copy.deepcopy(tools); msgs = copy.deepcopy(msgs)
    for t in tools:
        f = t['function']
        if f['name'] == 'edit_file':
            pr = f['parameters']['properties']
            f['parameters']['properties'] = {('file_path' if k == 'filepath' else k): v for k, v in pr.items() if k != 'allow_multiple'}
            f['parameters']['required'] = [('file_path' if k == 'filepath' else k) for k in f['parameters']['required']]
    for m in msgs:
        for tc in m.get('tool_calls') or []:
            if tc['function']['name'] == 'edit_file':
                a = json.loads(tc['function']['arguments'])
                tc['function']['arguments'] = json.dumps({('file_path' if k == 'filepath' else k): v for k, v in a.items() if k != 'allow_multiple'}, ensure_ascii=False)
    return msgs, tools

