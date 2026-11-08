"""slipguard targets for workstream C's differential conformance harness (diff/worker.run_cases).

    python conformance/gg_targets.py CASES.jsonl OUT.jsonl SHARD NSHARDS --suite <C's conformance dir> \
        [--tokenizer <Gemma 4 tokenizer dir>] [--targets a,b] [--stream-max-chars N]

Targets
  gg.completion      slipguard.parse.parse_completion (whole completion, strict; ParseError = loud)
  gg.extract         slipguard.parse.extract (per-call runtime semantics; errors = loud, calls before them kept)
  gg.repair          extract(..., repair=True) with the case's tools (opt-in text repair; informational)
  gg.stream          slipguard.parse.StreamParser(mode="per_call") fed per-token deltas (needs --tokenizer)
  gg.vllmNNN.server  the vLLM plugin through vLLM NNN's own server-path objects (0.19: reasoning parser ->
                     tool parser, as serving.py does; >= 0.24: ParserManager.get_parser(...).parse)
  gg.vllmNNN.stream  the vLLM plugin, one token per delta (0.19: reasoning streaming -> tool streaming;
                     >= 0.24: DelegatingParser.parse_delta)
The plugin is loaded exactly as `vllm serve --tool-parser-plugin/--reasoning-parser-plugin` loads it.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


SUITE = _arg("--suite")
TOKENIZER = _arg("--tokenizer")
if SUITE:
    sys.path.insert(0, os.path.join(SUITE, "diff"))
    sys.path.insert(0, SUITE)

from slipguard.parse import ParseError, StreamParser, extract, parse_completion  # noqa: E402


class GGEnv:
    def __init__(self):
        self.targets = {"gg.completion": self.t_completion, "gg.extract": self.t_extract, "gg.repair": self.t_repair}
        self.tok = None
        if TOKENIZER:
            from transformers import AutoTokenizer
            self.tok = AutoTokenizer.from_pretrained(TOKENIZER)
            self.targets["gg.stream"] = self.t_stream
        try:
            import vllm  # noqa: F401
        except ImportError:
            return
        self._init_vllm()

    def describe(self):
        return f"slipguard targets={sorted(self.targets)}"

    # -- helpers -------------------------------------------------------------------------------------------
    def ids(self, text):
        return self.tok.encode(text, add_special_tokens=False)

    def deltas(self, ids):
        from fastdelta import deltas as _deltas   # C's O(n) incremental detokenisation (vLLM's scheme)
        return _deltas(lambda x: self.tok.decode(x, skip_special_tokens=False), ids)

    # -- in-process API ------------------------------------------------------------------------------------
    def t_completion(self, case):
        try:
            pc = parse_completion(case["text"], in_thought=case.get("in_thought", False))
        except ParseError as e:
            return {"calls": [], "error": f"ParseError:{e.code}", "loud": True}
        return {"calls": [{"name": c.name, "arguments": c.arguments} for c in pc.calls],
                "content": "".join(pc.content) or None, "reasoning": pc.thought}

    def t_extract(self, case):
        ex = extract(case["text"], case.get("tools"), in_thought=case.get("in_thought", False), parse_thought=True)
        out = {"calls": [{"name": c.name, "arguments": c.arguments} for c in ex.calls], "content": ex.content,
               "reasoning": ex.thought}
        if ex.errors:
            out.update({"loud": True, "error": f"ParseError:{ex.errors[0].code}"})
        return out

    def t_repair(self, case):
        """Opt-in text-only repair (informational: an exact repair of ill-formed input is a strictness POLICY in C's
        rules, a wrong one a defect)."""
        tools = case.get("tools")
        ex = extract(case["text"], tools, in_thought=case.get("in_thought", False), parse_thought=True,
                     repair=bool(tools))
        out = {"calls": [{"name": c.name, "arguments": c.arguments} for c in ex.calls], "content": ex.content,
               "reasoning": ex.thought, "repaired": len(ex.repairs)}
        if ex.errors and not ex.repairs:
            out.update({"loud": True, "error": f"ParseError:{ex.errors[0].code}"})
        return out

    def t_stream(self, case):
        sp = StreamParser(mode="per_call", in_thought=case.get("in_thought", False))
        calls, content, thought = [], [], []
        evs = []
        for dt, _ in self.deltas(self.ids(case["text"])):
            evs.extend(sp.feed(dt))
        evs.extend(sp.finish())
        for ev in evs:
            if ev[0] == "call_end":
                calls.append({"name": ev[2].name, "arguments": ev[2].arguments})
            elif ev[0] == "content":
                content.append(ev[1])
            elif ev[0] == "thought":
                thought.append(ev[1])
        out = {"calls": calls, "content": "".join(content) or None, "reasoning": "".join(thought) or None}
        if sp.errors:
            out.update({"loud": True, "error": f"ParseError:{sp.errors[0].code}"})
        return out

    # -- vLLM plugin ---------------------------------------------------------------------------------------
    def _init_vllm(self):
        import vllm
        from vllm.tool_parsers.abstract_tool_parser import ToolParserManager
        from vllm.reasoning.abs_reasoning_parsers import ReasoningParserManager
        from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
        from slipguard.integrations import plugin_path
        if self.tok is None:
            raise SystemExit("--tokenizer is required for the vLLM targets")
        from vllm.tokenizers import get_tokenizer      # vLLM's cached tokenizer, as the server (and C's harness) use
        self.tok = get_tokenizer(TOKENIZER)
        path = plugin_path("vllm")
        ToolParserManager.import_tool_parser(path)          # what --tool-parser-plugin does
        ReasoningParserManager.import_reasoning_parser(path)  # what --reasoning-parser-plugin does
        self.TP = ToolParserManager.get_tool_parser("gemma4_strict")
        self.RP = ReasoningParserManager.get_reasoning_parser("gemma4_strict")
        self.CCR = ChatCompletionRequest
        ver = vllm.__version__.split("+")[0]
        tag = "vllm0" + ver.split(".")[1].zfill(2)
        self.vtag = tag
        self.ParserManager = None
        if tuple(int(x) for x in ver.split(".")[:2]) >= (0, 24):   # 0.24+: serving composes a DelegatingParser
            from vllm.parser.parser_manager import ParserManager
            self.ParserManager = ParserManager
        self.targets[f"gg.{tag}.server"] = self.t_vllm_server
        self.targets[f"gg.{tag}.stream"] = self.t_vllm_stream

    def request(self, tools, think=False):
        kw = dict(model="m", messages=[{"role": "user", "content": "x"}], tools=tools or None, tool_choice="auto")
        try:
            return self.CCR(**kw, chat_template_kwargs={"enable_thinking": think})
        except Exception:  # noqa: BLE001
            return self.CCR(**kw)

    def _delegating(self, req):
        pm = self.ParserManager
        try:
            cls = pm.get_parser(tool_parser_name="gemma4_strict", reasoning_parser_name="gemma4_strict",
                                enable_auto_tools=True, model_name="m", tokenizer=self.tok)
        except TypeError:
            cls = pm.get_parser(tool_parser_name="gemma4_strict", reasoning_parser_name="gemma4_strict",
                                enable_auto_tools=True, model_name="m")
        try:
            p = cls(self.tok, req.tools, chat_template_kwargs={"enable_thinking": False})
        except TypeError:
            p = cls(self.tok, req.tools)
        if hasattr(p, "adjust_request"):
            req = p.adjust_request(req)
        return p, req

    @staticmethod
    def _calls(tcs):
        from worker import args_from_json
        out = []
        for tc in tcs or []:
            fn = getattr(tc, "function", tc)
            out.append({"name": fn.name, "arguments": args_from_json(fn.arguments)})
        return out

    def t_vllm_server(self, case):
        text = case["text"]
        req = self.request(case.get("tools"), think=case.get("in_thought", False))
        if case.get("in_thought"):
            text = "<|channel>thought\n" + text
        if self.ParserManager is None:   # vLLM 0.19: serving.py runs the reasoning parser, then the tool parser
            rp = self.RP(self.tok)
            tp = self.TP(self.tok, req.tools)
            req = tp.adjust_request(rp.adjust_request(req))
            reasoning, content = rp.extract_reasoning(text, req)
            info = tp.extract_tool_calls(content if content is not None else "", req)
            if info.tools_called:
                return {"calls": self._calls(info.tool_calls), "content": info.content, "reasoning": reasoning}
            return {"calls": [], "content": content, "reasoning": reasoning}
        p, req = self._delegating(req)
        reasoning, content, tcs = p.parse(text, req, enable_auto_tools=True, model_output_token_ids=self.ids(text))
        return {"calls": self._calls(tcs), "content": content, "reasoning": reasoning}

    def t_vllm_stream(self, case):
        text = case["text"]
        req = self.request(case.get("tools"), think=case.get("in_thought", False))
        if case.get("in_thought"):
            text = "<|channel>thought\n" + text
        ids = self.ids(text)
        ds = self.deltas(ids)
        acc, content, reasoning = {}, [], []

        def take(dm):
            if dm is None:
                return
            if dm.content:
                content.append(dm.content)
            if getattr(dm, "reasoning", None):
                reasoning.append(dm.reasoning)
            for tc in dm.tool_calls or []:
                slot = acc.setdefault(tc.index, {"name": None, "args": ""})
                fn = tc.function
                if fn is not None:
                    if fn.name:
                        slot["name"] = fn.name
                    if fn.arguments:
                        slot["args"] += fn.arguments

        if self.ParserManager is None:
            rp = self.RP(self.tok)
            tp = self.TP(self.tok, req.tools)
            req = tp.adjust_request(rp.adjust_request(req))
            prev, prev_ids, ctext, in_tools = "", [], "", False
            # a generation that ends on a stop token carries that token's id in its last delta (its text is not
            # output): <|tool_response> after a tool call, else <turn|>. vLLM 0.19 has no other end-of-stream signal.
            stop = self.tok.convert_tokens_to_ids("<|tool_response>" if "<|tool_call>" in text else "<turn|>")
            for dt, tid in list(ds) + [("", stop)]:
                cur, cur_ids = prev + dt, prev_ids + [tid]
                if not in_tools:
                    dm = rp.extract_reasoning_streaming(prev, cur, dt, prev_ids, cur_ids, [tid])
                    if dm is not None:
                        if getattr(dm, "reasoning", None):
                            reasoning.append(dm.reasoning)
                        if dm.content:
                            in_tools = True   # serving.py: reasoning ended -> tool phase starts with this content
                            new = dm.content
                            take(tp.extract_tool_calls_streaming("", new, new, [], [], [tid], req))
                            ctext = new
                    if rp._phase == "content":
                        in_tools = True
                else:
                    new = ctext + dt
                    take(tp.extract_tool_calls_streaming(ctext, new, dt, [], [], [tid], req))
                    ctext = new
                prev, prev_ids = cur, cur_ids
        else:
            p, req = self._delegating(req)
            for k, (dt, tid) in enumerate(ds):
                take(p.parse_delta(dt, [tid], req, None, finished=(k == len(ds) - 1)))
        from worker import args_from_json
        calls = [{"name": s["name"], "arguments": args_from_json(s["args"] or "{}")} for _, s in sorted(acc.items())]
        return {"calls": calls, "content": "".join(content) or None, "reasoning": "".join(reasoning) or None,
                "n_tokens": len(ids)}


def main():
    import logging
    logging.disable(logging.WARNING)
    cases_path, out_path, shard, nshards = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    only = set(_arg("--targets").split(",")) if _arg("--targets") else None
    stream_max = int(_arg("--stream-max-chars", "3000"))
    from worker import run_cases   # C's per-case loop (timeouts, classification, fingerprints)
    run_cases(GGEnv(), cases_path, out_path, shard, nshards, only, stream_max, lean="--lean" in sys.argv,
              stream_sample=float(_arg("--stream-sample", "1.0")))


if __name__ == "__main__":
    main()
