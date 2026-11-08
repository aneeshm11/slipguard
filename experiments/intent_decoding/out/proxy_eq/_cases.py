import os  # added by the repo export (paths are env/config driven)
import json, sys
sys.dont_write_bytecode = True
sys.argv = ["x", "offline"]; sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), "experiments/intent_decoding"))
import proxy_equivalence as PE
EGP, EPX = PE.load_e()
engine = EPX.Engine(PE.MODEL_DIR_JUNE)
BGP = PE.BGP
ids = ['ctx-aab682aa86', 'ctx-2c674f86e3', 'ctx-62d17f0b9b', 'ctx-311005d2c5']
ctx = {}
for i, l in enumerate(open(PE.CTX)):
    if i >= 600: break
    c = json.loads(l); ctx[c['id']] = c
for l in open(PE.GATE):
    r = json.loads(l)
    if r.get('status') != 'call' or r['id'] not in ids: continue
    schemas = EGP.tool_schemas(ctx[r['id']]['tools'])
    G = r['A_text'] + PE.TC_START + r['call'] + (PE.TC_END if r['finished'] else '')
    reasoning, content, calls = engine.parse(G)
    raw = EGP.CALL_RE.findall(G)
    a = json.loads(calls[0]['arguments']) if calls else {}
    cls = EGP.classify_args(calls[0]['name'], a, schemas) if calls else None
    if cls and not cls['ok'] and raw:
        a2 = EGP.intent_parse_args(raw[0][1], schemas['edit_file']['properties'])
        if EGP.classify_args('edit_file', a2, schemas)['ok']: a = a2
    ip = r.get('i_plus') or r.get('i_nc')
    ref = BGP.parse_strict(ip['text']).args() if ip and ip.get('valid') else {}
    print('=====', r['id'])
    for k in ('filepath', 'new_string', 'old_string'):
        pv, rv = a.get(k), ref.get(k)
        same = pv == rv
        print(f'  {k}: same={same}', '' if same else f'\n     proxy tail={repr((pv or "")[-60:])}\n     ref   tail={repr((rv or "")[-60:])}\n     proxy head={repr((pv or "")[:50])}\n     ref   head={repr((rv or "")[:50])}')
