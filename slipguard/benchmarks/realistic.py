"""Parser cost on REALISTIC agent traffic: every model turn of the PNC corpus (natural Gemma 4 trajectories), parsed by
a runtime's built-in Gemma 4 parsers or by slipguard's plugin, inside that runtime's own server-path objects.

    <env python> benchmarks/realistic.py --pnc <PNC dir> --tokenizer <Gemma 4 dir> --suite <C's conformance dir>
        --impl builtin|slipguard --out OUT.jsonl [--stride K]

Per turn (one record each):
  ns_ms        non-streaming: reasoning split + tool-call extraction, exactly as the server does it (parser objects
               constructed per request, as the server does). Token ids are computed OUTSIDE the timer.
  st_ms        streaming: per-token deltas from the Gemma tokenizer fed through the server's streaming parser path
               (vLLM 0.19: serving.py's reasoning -> tool handoff; >= 0.24: DelegatingParser.parse_delta); only the
               parser calls are timed (the server's own string accumulation is not).
  st_max_ms    the longest single parser call in the stream = the worst event-loop stall of that turn.
  llm_s        the turn's logged generation wall time (PNC timing.llm_seconds); gen_tokens from the proxy log.
The prompt ended inside an open thought for most turns (template prefill): as in the conformance harness, the text
is given to every parser with the '<|channel>thought\\n' prefix.
"""
from __future__ import annotations

import glob
import json
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


PNC, TOK, SUITE, IMPL, OUT = _arg("--pnc"), _arg("--tokenizer"), _arg("--suite"), _arg("--impl"), _arg("--out")
STRIDE = int(_arg("--stride", "1"))
TIMEOUT = float(_arg("--timeout", "300"))
sys.path.insert(0, os.path.join(SUITE, "diff"))
sys.path.insert(0, os.path.join(HERE, "..", "src"))


class Timeout(BaseException):
    pass


def _alarm(*_):
    raise Timeout()


def main():
    import logging
    logging.disable(logging.WARNING)
    import vllm
    from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
    from vllm.tokenizers import get_tokenizer
    from fastdelta import deltas as _deltas
    ver = vllm.__version__.split("+")[0]
    vt = tuple(int(x) for x in ver.split(".")[:2])
    tok = get_tokenizer(TOK)
    if IMPL == "slipguard":
        from vllm.reasoning.abs_reasoning_parsers import ReasoningParserManager
        from vllm.tool_parsers.abstract_tool_parser import ToolParserManager
        from slipguard.integrations import plugin_path
        ToolParserManager.import_tool_parser(plugin_path("vllm"))
        ReasoningParserManager.import_reasoning_parser(plugin_path("vllm"))
        tname = rname = "gemma4_strict"
    else:
        tname = rname = "gemma4"
    tools = {}
    for s in ("S1", "S2"):
        m = json.load(open(os.path.join(PNC, "contexts", f"P-swebench-31b-{s}-v1", "manifest.json")))
        t = m["tools"]
        tools[s] = t if isinstance(t, list) else t.get(f"tools_{s}") or t.get(s) or list(t.values())[0]
    reqs = {s: ChatCompletionRequest(model="m", messages=[{"role": "user", "content": "x"}], tools=tools[s],
                                     tool_choice="auto", chat_template_kwargs={"enable_thinking": True})
            for s in tools}
    if vt >= (0, 24):
        from vllm.parser.parser_manager import ParserManager
        try:
            PCLS = ParserManager.get_parser(tool_parser_name=tname, reasoning_parser_name=rname, enable_auto_tools=True,
                                            model_name="m", tokenizer=tok)
        except TypeError:
            PCLS = ParserManager.get_parser(tool_parser_name=tname, reasoning_parser_name=rname, enable_auto_tools=True,
                                            model_name="m")

        def make(req):
            try:
                return PCLS(tok, req.tools, chat_template_kwargs={"enable_thinking": True})
            except TypeError:
                return PCLS(tok, req.tools)

        def nonstream(text, ids, req):
            p = make(req)
            _, _, tcs = p.parse(text, req, enable_auto_tools=True, model_output_token_ids=ids)
            return len(tcs or [])

        def stream(ds, req):
            p = make(req)
            mx = tot = 0.0
            n = len(ds)
            for k, (dt, tid) in enumerate(ds):
                t0 = time.perf_counter()
                p.parse_delta(dt, [tid], req, None, finished=(k == n - 1))
                e = time.perf_counter() - t0
                tot += e
                mx = max(mx, e)
            return tot, mx
    else:
        from vllm.reasoning.abs_reasoning_parsers import ReasoningParserManager
        from vllm.tool_parsers.abstract_tool_parser import ToolParserManager
        if IMPL == "builtin":
            sys.path.insert(0, os.path.join(SUITE, "diff"))
            from vllm.reasoning.gemma4_reasoning_parser import Gemma4ReasoningParser as RP
            from vllm.tool_parsers.gemma4_tool_parser import Gemma4ToolParser as TP
        else:
            RP = ReasoningParserManager.get_reasoning_parser(rname)
            TP = ToolParserManager.get_tool_parser(tname)

        def nonstream(text, ids, req):
            rp, tp = RP(tok), TP(tok, req.tools)
            _, content = rp.extract_reasoning(text, req)
            info = tp.extract_tool_calls(content if content is not None else "", req)
            return len(info.tool_calls) if info.tools_called else 0

        def stream(ds, req):
            """vLLM 0.19.1 serving.py: reasoning phase until is_reasoning_end(delta ids), then the tool parser."""
            t0 = time.perf_counter()
            rp, tp = RP(tok), TP(tok, req.tools)
            tot = mx = time.perf_counter() - t0
            prev, prev_ids, in_tools, added = "", [], False, False
            cprev = ""
            for dt, tid in ds:
                cur, cur_ids = prev + dt, prev_ids + [tid]
                if not in_tools:
                    t0 = time.perf_counter()
                    dm = rp.extract_reasoning_streaming(prev, cur, dt, prev_ids, cur_ids, [tid])
                    ended = rp.is_reasoning_end([tid])
                    e = time.perf_counter() - t0
                    tot += e
                    mx = max(mx, e)
                    if ended:
                        in_tools = True
                        ctext = (dm.content if dm is not None and dm.content else "")
                        cprev, cdelta = "", ctext
                        t0 = time.perf_counter()
                        tp.extract_tool_calls_streaming(cprev, ctext, cdelta, [], [], [tid], req)
                        e = time.perf_counter() - t0
                        tot += e
                        mx = max(mx, e)
                        cprev = ctext
                else:
                    ctext = cprev + dt
                    t0 = time.perf_counter()
                    tp.extract_tool_calls_streaming(cprev, ctext, dt, [], [], [tid], req)
                    e = time.perf_counter() - t0
                    tot += e
                    mx = max(mx, e)
                    cprev = ctext
                prev, prev_ids = cur, cur_ids
            return tot, mx

    files = sorted(glob.glob(os.path.join(PNC, "episodes", "*.jsonl")))
    signal.signal(signal.SIGALRM, _alarm)
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            try:
                done.add(json.loads(line)["id"])
            except Exception:  # noqa: BLE001
                pass
    k = 0
    with open(OUT, "a") as fo:
        for f in files:
            for line in open(f):
                k += 1
                if (k - 1) % STRIDE:
                    continue
                d = json.loads(line)
                tid_ = f"{d['episode_id']}#{d['turn_index']}"
                if tid_ in done:
                    continue
                raw = d.get("raw_completion") or ""
                text = raw if raw.startswith("<|channel>") or "<channel|>" not in raw else "<|channel>thought\n" + raw
                req = reqs[d["schema"]]
                ids = tok.encode(text, add_special_tokens=False)
                ds = _deltas(lambda x: tok.decode(x, skip_special_tokens=False), ids)
                msg = (d.get("response") or {}).get("message") or {}
                calls = msg.get("tool_calls") or []
                argsz = []
                for c in calls:
                    a = (c.get("function") or {}).get("arguments") or ""
                    try:
                        ad = json.loads(a) if isinstance(a, str) else a
                    except ValueError:
                        ad = {}
                    argsz.append({"name": (c.get("function") or {}).get("name"), "chars": len(a),
                                  "n_args": len(ad) if isinstance(ad, dict) else None,
                                  "max_value": max((len(v) for v in (ad or {}).values() if isinstance(v, str)), default=0)})
                rec = {"id": tid_, "chars": len(text), "tokens": len(ids), "logged_calls": len(calls), "calls": argsz,
                       "llm_s": (d.get("timing") or {}).get("llm_seconds"),
                       "gen_tokens": (d.get("proxy") or {}).get("gen_tokens")}
                signal.setitimer(signal.ITIMER_REAL, TIMEOUT)
                try:
                    t0 = time.perf_counter()
                    rec["n_calls"] = nonstream(text, ids, req)
                    rec["ns_ms"] = round((time.perf_counter() - t0) * 1000, 4)
                    tot, mx = stream(ds, req)
                    rec["st_ms"], rec["st_max_ms"] = round(tot * 1000, 4), round(mx * 1000, 4)
                    rec["status"] = "ok"
                except Timeout:
                    rec["status"] = "timeout"
                except Exception as e:  # noqa: BLE001
                    rec["status"] = f"exception: {type(e).__name__}: {str(e)[:120]}"
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                fo.write(json.dumps(rec) + "\n")
                fo.flush()


if __name__ == "__main__":
    main()
