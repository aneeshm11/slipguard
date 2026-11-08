import os  # added by the repo export (paths are env/config driven)
import json, sys, collections
sys.dont_write_bytecode = True
sys.argv = ["x"]; sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "experiments/intent_decoding"))
import proxy_equivalence as PE
EGP, EPX = PE.load_e()
engine = EPX.Engine(PE.MODEL_DIR_JUNE)
items = PE._g1_items()
print('g1 items', len(items))
c = collections.Counter()
for it in items:
    try:
        _, pids = engine.render_ids(EGP.to_conversation(it['messages']), [dict(t) for t in it['tools']], {'enable_thinking': True}, False)
        c['render_ok'] += 1
    except Exception as e:
        c['render_err:' + type(e).__name__] += 1
    c['gen_ends_with_D'] += it['gen'].endswith(PE.D)
    c['temp=' + str(it['temp'])] += 1
print(dict(c))
it = items[0]; print(repr(it['gen'][-200:])); print(it['gold']['filepath'], len(it['gold']['new_string']), len(it['gold']['old_string']))
