"""QuoteStorm copy-task contexts with KNOWN intent: the official system prompt + official tool declarations + a user
message that shows the exact old/new text of one payload and asks for a single edit_file call.
The model's call is compared to the ground truth (filepath, old_string, new_string)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ctx0 = json.loads(open(os.path.join(HERE, 'data/replay_first_edit.jsonl')).readline())
system = ctx0['messages'][0]
assert system['role'] == 'system'
tools = json.load(open(os.path.join(HERE, 'data/tools_official.json')))
USER = ('Apply exactly this change to the file {fp} with a single edit_file call.\n'
        'Replace this text (everything between the marker lines; the marker lines themselves are not part of it):\n'
        '-----BEGIN OLD-----\n{old}\n-----END OLD-----\n'
        'with this text:\n'
        '-----BEGIN NEW-----\n{new}\n-----END NEW-----\n'
        'Copy both blocks character for character.')
n = 0
with open(os.path.join(HERE, 'data/quotestorm_ctx.jsonl'), 'w') as fo:
    for l in open(os.path.join(HERE, 'data/quotestorm.jsonl')):
        p = json.loads(l)
        msgs = [system, {'role': 'user', 'content': USER.format(fp=p['filepath'], old=p['old'], new=p['new'])}]
        fo.write(json.dumps({'id': 'qs:%d' % p['qid'], 'qid': p['qid'], 'src': p['src'], 'messages': msgs, 'tools': tools,
                             'gt': {'filepath': p['filepath'], 'old_string': p['old'], 'new_string': p['new']}}) + '\n')
        n += 1
print('contexts', n)
