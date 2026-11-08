"""Model-free tests of intent_decode's pure helpers (prior, cut choice, continuation, prompt_logprobs guard)."""
import os, sys, math, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gemma_protocol import D, TC_END, schema_from_tools, first_slip_site
from intent_decode import ChannelPrior, NoPrior, pick_cut, closer_at, _continuation, Server, MAX_PROMPT_LOGPROBS_TOKENS
from test_protocol import TOOLS, S


def test_prior_monotone_and_smoothed():
    p = ChannelPrior({'`': 100, '"': 10, '': 2})
    assert p.logp('`') > p.logp('"') > p.logp('') > p.logp('"`') > p.logp('"""`')
    assert p.logp(' ` ') == p.logp('`')            # whitespace gap is not part of the closer
    tot = sum(math.exp(p.logp(c)) for c in ('`', '"', ''))
    assert tot < 1.0                                # mass left for unseen strings
    assert NoPrior().logp('anything') == 0.0


def test_prior_from_logs():
    ft = ChannelPrior.from_log_slips('ft_edit')
    base = ChannelPrior.from_log_slips('base_edit')
    assert ft.N > 400 and base.N > 3000
    assert ft.logp('`') > ft.logp('"`')


def test_pick_cut_rules():
    lls = [-27.1, -30.1, -31.8]                     # smoke case: content x = "a | x = "a" | x = "a"`
    closers = ['"`', '`', '']
    pr = ChannelPrior({'`': 320, '"': 58, '\\"': 69, '': 17})
    assert pick_cut(lls, closers, 'lik', pr) == 0
    assert pick_cut(lls, closers, 'nc', pr) == 1    # noisy channel recovers the intended x = "a"
    assert pick_cut(lls, closers, 'max', pr) == 0


def test_closer_at_and_continuation():
    t = 'call:edit_file{filepath:' + D + 'a.py' + D + ',new_string:' + D + 'x = "a"`,old_string:' + D + 'y' + D + '}'
    s = first_slip_site(t, S, True)
    assert [closer_at(s, k) for k in range(len(s.cut_positions()))] == ['"`', '`', '']
    assert _continuation(s, S['edit_file']) == ',old_string:' + D
    t2 = 'call:edit_file{filepath:' + D + 'a.py' + D + ',old_string:' + D + 'a' + D + ',new_string:' + D + 'b`}'
    s2 = first_slip_site(t2, S, True)
    assert _continuation(s2, S['edit_file']) == '}' + TC_END
    t3 = 'call:edit_file{filepath:' + D + 'a.py' + D + ',old_string:' + D + 'a' + D + ',new_string:' + D + 'b",allow_multiple:true}'
    s3 = first_slip_site(t3, S, True)
    assert _continuation(s3, S['edit_file']) == ',allow_multiple:'


def test_prompt_logprobs_guard():
    async def go():
        srv = Server('http://127.0.0.1:9', 'x', conc=1)
        try:
            await srv.complete(list(range(MAX_PROMPT_LOGPROBS_TOKENS + 1)), 1, prompt_logprobs=0)
            return False
        except ValueError:
            return True
        finally:
            await srv.close()
    assert asyncio.run(go())




def test_extension_rules_opt_in():
    from gemma_protocol import first_violation, first_kwarg_site, first_qkey_site, is_valid
    kw = 'call:edit_file{filepath="a.py",new_string="x",old_string="y"}'
    assert first_violation(kw, S, True, ('closer', 'opener')) is None or first_violation(kw, S, True, ('closer', 'opener')).kind != 'kwarg'
    st = first_kwarg_site(kw, S)
    assert st is not None and st.kind == 'kwarg' and kw[:st.colon_end].endswith('filepath') and st.force == ':' + D
    qk = 'call:edit_file{filepath:' + D + 'a.py' + D + ',new_string:' + D + 'x\\n", "old_string": "y"' + D + '}'
    s2 = first_qkey_site(qk, S)
    assert s2 is not None and s2.next_key == 'old_string' and s2.run == '"'
    v = 'call:edit_file{filepath:' + D + 'a.py' + D + ',new_string:' + D + 'msg = \'x", "old_string": y\'' + D + ',old_string:' + D + 'z' + D + '}'
    assert is_valid(v, S) and first_kwarg_site(v, S) is None and first_qkey_site(v, S) is None   # guard on valid calls


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_') and callable(f):
            f(); print('ok', k)
