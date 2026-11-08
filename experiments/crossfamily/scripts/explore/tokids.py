import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
from transformers import AutoTokenizer
for mk in ['Qwen3-8B', 'Qwen3-32B-FP8', 'Qwen3.5-9B']:
    tok = AutoTokenizer.from_pretrained(fos.path.join(os.environ.get('TRANSCRIPTLAB_MODELS', 'models/'), '{mk}'))
    ids = {s: tok.convert_tokens_to_ids(s) for s in ['<tool_call>', '</tool_call>', '<think>', '</think>', '<|im_end|>', '<|im_start|>', '<|endoftext|>', '<tool_response>', '</tool_response>']}
    print(mk, len(tok), ids)
    for s in ['<parameter=old_string>\n', '\n</parameter>\n', '</function>', '<function=edit_file>', '"new_string": "', '\\"', '`, "old_string": "', '`,old_string:', '</think>\n\n<tool_call>\n']:
        e = tok(s, add_special_tokens=False)['input_ids']
        print('   ', repr(s), e, [tok.decode([i]) for i in e])
