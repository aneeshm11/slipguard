"""Unit + property tests for gemma_protocol (model-free).  Run: python -m pytest -q tests/  (or python tests/test_protocol.py)"""
import os, sys, random, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gemma_protocol import (D, schema_from_tools, parse_strict, is_valid, first_slip_site, repair_candidates,
                            render_call, census_judge)

TOOLS = [
    {'type': 'function', 'function': {'name': 'edit_file', 'parameters': {'type': 'object', 'properties': {
        'filepath': {'type': 'string'}, 'old_string': {'type': 'string'}, 'new_string': {'type': 'string'},
        'allow_multiple': {'default': False, 'type': 'boolean'}}, 'required': ['filepath', 'old_string', 'new_string']}}},
    {'type': 'function', 'function': {'name': 'write_file', 'parameters': {'type': 'object', 'properties': {
        'filepath': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['filepath', 'content']}}},
    {'type': 'function', 'function': {'name': 'read_file', 'parameters': {'type': 'object', 'properties': {
        'filepath': {'type': 'string'}, 'start_line': {'nullable': True, 'type': 'integer'},
        'end_line': {'nullable': True, 'type': 'integer'}}, 'required': ['filepath']}}},
    {'type': 'function', 'function': {'name': 'run_command', 'parameters': {'type': 'object', 'properties': {
        'command': {'type': 'string'}}, 'required': ['command']}}},
]
S = schema_from_tools(TOOLS)


def call(*pairs, name='edit_file'):
    return render_call(name, [(k, v, 'str' if isinstance(v, str) else 'bare') for k, v in pairs])


def test_valid_basic():
    t = call(('filepath', 'a.py'), ('new_string', 'x = `y`'), ('old_string', 'x = 1'))
    assert is_valid(t, S)
    assert first_slip_site(t, S) is None
    assert repair_candidates(t, S) == []
    t2 = call(('filepath', 'a.py'), ('start_line', 3), ('end_line', None), name='read_file')
    assert is_valid(t2, S), t2


def test_adversarial_literal_is_identity():
    # new_string literally ends with the slip signature, call is valid -> never touched
    t = call(('filepath', 'a.py'), ('new_string', 'msg = "`,old_string:'), ('old_string', 'x'))
    assert is_valid(t, S)
    assert first_slip_site(t, S) is None and repair_candidates(t, S) == []


def test_backtick_slip_new_first():
    t = 'call:edit_file{filepath:' + D + 'a.py' + D + ',new_string:' + D + 'x = 2`,old_string:' + D + 'x = 1' + D + '}'
    assert not is_valid(t, S)
    s = first_slip_site(t, S)
    assert s is not None and s.key == 'new_string' and s.next_key == 'old_string' and s.run == '`'
    assert t[s.content_start:s.cut_positions()[0]] == 'x = 2'
    cands = repair_candidates(t, S)
    texts = {c.text('edit_file') for c in cands}
    assert call(('filepath', 'a.py'), ('new_string', 'x = 2'), ('old_string', 'x = 1')) in texts
    ok, why, args = census_judge(t, S)
    assert not ok


def test_mixed_run_and_quote_slip():
    t = 'call:edit_file{filepath:' + D + 'a.py' + D + ',new_string:' + D + 'sql = f"P"`,old_string:' + D + 'sql = 1' + D + '}'
    s = first_slip_site(t, S)
    assert s.run == '"`' and len(s.cut_positions()) == 3
    cands = repair_candidates(t, S)
    vals = sorted(c.pairs[1][1] for c in cands)
    assert vals == ['sql = f"P', 'sql = f"P"', 'sql = f"P"`'], vals


def test_end_slip():
    t = 'call:edit_file{filepath:' + D + 'a.py' + D + ',old_string:' + D + 'a' + D + ',new_string:' + D + 'b`}'
    assert not is_valid(t, S)
    ok, why, _ = census_judge(t, S)
    assert ok  # the lenient census parser silently accepts new_string='b`'
    s = first_slip_site(t, S, finished=True)
    assert s is not None and s.kind == 'end' and s.run == '`'
    assert first_slip_site(t, S, finished=False) is None
    cands = repair_candidates(t, S)
    assert call(('filepath', 'a.py'), ('old_string', 'a'), ('new_string', 'b')) in {c.text('edit_file') for c in cands}


def test_bare_key_slip():
    t = 'call:edit_file{filepath:' + D + 'a.py' + D + ',old_string:' + D + 'a' + D + ',new_string:' + D + 'b",allow_multiple:true}'
    s = first_slip_site(t, S, finished=True)
    assert s is not None and s.next_key == 'allow_multiple'
    cands = repair_candidates(t, S)
    assert call(('filepath', 'a.py'), ('old_string', 'a'), ('new_string', 'b'), ('allow_multiple', True)) in {c.text('edit_file') for c in cands}


def test_two_slips():
    t = 'call:edit_file{filepath:' + D + 'a.py' + D + ',new_string:' + D + 'b`,old_string:' + D + 'a`}'
    cands = repair_candidates(t, S, finished=True)
    assert call(('filepath', 'a.py'), ('new_string', 'b'), ('old_string', 'a')) in {c.text('edit_file') for c in cands}


def test_empty_closer():
    t = 'call:edit_file{filepath:' + D + 'a.py' + D + ',new_string:' + D + ',old_string:' + D + 'a' + D + '}'
    s = first_slip_site(t, S)
    assert s is not None and s.run == '' and s.cut_positions() == [s.content_start]
    cands = repair_candidates(t, S)
    assert call(('filepath', 'a.py'), ('new_string', ''), ('old_string', 'a')) in {c.text('edit_file') for c in cands}


def test_write_file_and_filepath_slip():
    t = 'call:write_file{content:' + D + 'print(1)\n`,filepath:' + D + 'a.py' + D + '}'
    s = first_slip_site(t, S)
    assert s is not None and s.next_key == 'filepath'
    t = 'call:edit_file{filepath:' + D + 'src/a.py`,new_string:' + D + 'b' + D + ',old_string:' + D + 'a' + D + '}'
    s = first_slip_site(t, S)
    assert s is not None and s.key == 'filepath'


def _rand_payload(rng):
    alpha = ['`', '``', '```', '"', "'", '\\"', '"""', "'''", ',', ':', '}', '{', '[', ']', ',old_string:', ',new_string:',
             '`,old_string:', '",filepath:', ',allow_multiple:true', '}', 'x', ' ', '\n', 'def f():', 'return', '`}', '\\n']
    return ''.join(rng.choice(alpha) for _ in range(rng.randint(0, 12)))


def test_property_valid_calls_never_altered(n=20000, seed=0):
    rng = random.Random(seed)
    for _ in range(n):
        keys = ['filepath', 'new_string', 'old_string']
        rng.shuffle(keys)
        pairs = [(k, _rand_payload(rng)) for k in keys]
        if rng.random() < 0.3:
            pairs.insert(rng.randint(0, 3), ('allow_multiple', rng.random() < 0.5))
        t = call(*pairs)
        assert is_valid(t, S), t
        assert first_slip_site(t, S) is None
        assert repair_candidates(t, S) == []


def test_property_injected_slip_recoverable(n=5000, seed=1):
    """inject a look-alike closer in place of the closing delimiter of a non-final string argument:
    the ground truth must be among the minimal repair candidates whenever the call becomes invalid."""
    rng = random.Random(seed)
    miss = inv = 0
    for _ in range(n):
        keys = ['filepath', 'new_string', 'old_string']
        rng.shuffle(keys)
        pairs = [(k, _rand_payload(rng)) for k in keys]
        gt = call(*pairs)
        j = rng.randrange(len(pairs) - 1)
        L = rng.choice(['`', '"', '\\"', '"""', ''])
        txt = 'call:edit_file{' + ','.join(
            f'{k}:{D}{v}{L if i == j else D}' for i, (k, v) in enumerate(pairs)) + '}'
        if is_valid(txt, S):
            continue
        inv += 1
        texts = {c.text('edit_file') for c in repair_candidates(txt, S, max_cost=3)}
        if gt not in texts:
            miss += 1
    # random payloads can contain D-free structure that makes another parse cheaper; must be rare
    assert miss / max(inv, 1) < 0.05, (miss, inv)


def test_pathological_runs_bounded():
    import time
    from gemma_protocol import LAST_REPAIR_INCOMPLETE
    junk = ('"' * 300) + ',old_string:' + D + ('x`,new_string:' * 40) + ('"' * 200) + ',allow_multiple:true' + D + '}'
    t = 'call:edit_file{filepath:' + D + 'a.py' + D + ',new_string:' + D + 'y' + junk
    t0 = time.time()
    c = repair_candidates(t, S, finished=True, max_cost=3)
    s = first_slip_site(t, S, finished=True)
    assert time.time() - t0 < 10, time.time() - t0
    if s is not None:
        assert len(s.cut_positions()) <= 8


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_') and callable(f):
            f(); print('ok', k)
