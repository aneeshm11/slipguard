"""`slipguard verify`: check the guarantees on the INSTALLED package.

  frozen       every shipped frozen file matches MANIFEST.json (sha256); for the files the public export changed
               (one path literal, two provenance fields), every top-level definition except ``main`` has the
               frozen source's AST and the JSON the code reads is identical
  conformance  the parser on C's public minimal repros (12 of the 16 bug classes) + generated checks for the other
               4 (string opacity, termination, linear time, bounded nesting): one-shot, per-call, streaming
  p1           (needs the Gemma 4 model dir) workstream B's P1 acceptance test through E's REAL request path
               (Proxy.engine_chat, cfgs ipd and fullp, teacher-forced stub backend): every strictly valid edit call
               must come back byte-identical. Payloads: the released QuoteStorm payloads (--data payloads.jsonl) or a
               built-in synthetic set with look-alike closers inside the strings.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import random
import time
from typing import Any

from ._frozen import manifest, verify_shipped, PKG


# ------------------------------------------------------------------------------------------------- frozen
def _outside_sha(src: str, names: list[str]) -> str:
    lines = src.splitlines(keepends=True)
    drop: set[int] = set()
    for node in ast.parse(src).body:
        if getattr(node, "name", None) in names:
            first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            drop.update(range(first - 1, node.end_lineno))
    return hashlib.sha256("".join(l for i, l in enumerate(lines) if i not in drop).encode("utf-8")).hexdigest()


def check_frozen() -> dict:
    rows = verify_shipped()
    ast_ok, json_ok = [], []
    for r, m in zip(rows, manifest()["files"]):
        p = os.path.join(PKG, m["shipped"])
        if "outside_sha256" in m:
            # everything outside the listed definitions must be byte-identical to the frozen source
            src = open(p, encoding="utf-8").read()
            names = list(m.get("differs_only_in") or [])
            ok_ = set(names) <= {"main"} and _outside_sha(src, names) == m["outside_sha256"]
            ast_ok.append({"file": m["shipped"], "ok": ok_, "differs_only_in": names})
        if "json_semantic_sha256" in m:
            o = json.load(open(p, encoding="utf-8"))
            if isinstance(o, dict):
                o = {k: v for k, v in o.items() if k != "source"}
            h = hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()
            json_ok.append({"file": m["shipped"], "ok": h == m["json_semantic_sha256"]})
    ok = all(r["ok"] for r in rows) and all(x["ok"] for x in ast_ok) and all(x["ok"] for x in json_ok)
    return {"ok": ok, "files": len(rows), "sha_ok": sum(r["ok"] for r in rows),
            "byte_identical_to_freeze": sum(not m["changed"] for m in manifest()["files"]),
            "changed_by_public_export": [m["shipped"] for m in manifest()["files"] if m["changed"]],
            "outside_main_identical": ast_ok, "json": json_ok, "e_freeze_digest": manifest().get("e_freeze_digest")}


# ------------------------------------------------------------------------------------------------- conformance
def _dec(v: Any) -> Any:
    if isinstance(v, dict):
        if set(v) == {"__float__"}:
            return float(v["__float__"])
        return {k: _dec(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_dec(x) for x in v]
    return v


def check_conformance(seed: int = 20261105, n_generated: int = 2000) -> dict:
    from ._vendor.gemmaproto.conformance import classify
    from ._vendor.gemmaproto.gen import rand_name, rand_object, rand_string
    from ._vendor.gemmaproto.serializer import render_call, is_representable, values_equal
    from .parse import ParseError, StreamParser, extract, parse_completion
    from .parse.engine import MAX_DEPTH

    def run(text: str) -> dict:
        out = {}
        try:
            pc = parse_completion(text)
            out["completion"] = {"calls": [{"name": c.name, "arguments": c.arguments} for c in pc.calls],
                                 "content": "".join(pc.content) or None}
        except ParseError as e:
            out["completion"] = {"calls": [], "loud": True, "error": e.code}
        ex = extract(text)
        out["extract"] = {"calls": [{"name": c.name, "arguments": c.arguments} for c in ex.calls],
                          "content": ex.content, "loud": bool(ex.errors)}
        sp = StreamParser(mode="per_call")
        calls, content = [], []
        for i in range(0, len(text), 3):
            for ev in sp.feed(text[i:i + 3]):
                calls += [ev[2]] if ev[0] == "call_end" else []
                content += [ev[1]] if ev[0] == "content" else []
        for ev in sp.finish():
            calls += [ev[2]] if ev[0] == "call_end" else []
            content += [ev[1]] if ev[0] == "content" else []
        out["stream"] = {"calls": [{"name": c.name, "arguments": c.arguments} for c in calls],
                         "content": "".join(content) or None, "loud": bool(sp.errors)}
        return out

    per_class: dict[str, dict] = {}
    failures: list[dict] = []
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "conformance_public.jsonl")
    for line in open(path, encoding="utf-8"):
        c = json.loads(line)
        intended = _dec(c["intended"]) if c["intended"] is not None else None
        res = run(c["text"])
        row = per_class.setdefault(c["class"], {"cases": 0, "pass": 0})
        row["cases"] += 1
        ok = True
        for target, r in res.items():
            o = classify({**r, "status": "ok"}, intended)
            want = "EXACT" if c["valid"] else "LOUD"
            if o != want:
                ok = False
                failures.append({"id": c["id"], "target": target, "outcome": o, "expected": want})
        row["pass"] += ok
    # generated checks for the classes whose minimal repros are not public
    r = random.Random(seed)
    gen = {"C6_string_opacity": [0, 0], "C7_termination": [0, 0], "C8_linear_time": [0, 0], "C9_bounded_nesting": [0, 0]}
    for _ in range(n_generated):          # strings with control-token text inside (gemmaproto's TRICKY_FRAGMENTS)
        args = {"a": rand_string(r), "b": rand_object(r, n=2)}
        if not is_representable(args):
            continue
        text = render_call(rand_name(r), args)
        gen["C6_string_opacity"][1] += 1
        try:
            pc = parse_completion(text)
            ex = extract(text)
            good = len(pc.calls) == 1 and values_equal(pc.calls[0].arguments, args) and len(ex.calls) == 1
        except ParseError:
            good = False
        gen["C6_string_opacity"][0] += good
        mut = list(text)                  # random single-character mutations must terminate quickly
        for _ in range(3):
            mut[r.randrange(len(mut))] = r.choice('[]{},:`"<|>')
        t0 = time.perf_counter()
        extract("".join(mut))
        gen["C7_termination"][1] += 1
        gen["C7_termination"][0] += (time.perf_counter() - t0) < 1.0
    times = []
    for k in (2000, 8000):                # many arguments: time must grow ~linearly
        text = render_call("f", {f"k{i}": f"v{i}" for i in range(k)})
        t0 = time.perf_counter()
        parse_completion(text)
        times.append(time.perf_counter() - t0)
    gen["C8_linear_time"] = [int(times[1] < 8 * max(times[0], 1e-3)), 1]
    deep = "<|tool_call>call:f{a:" + "[" * (MAX_DEPTH * 4) + "]" * (MAX_DEPTH * 4) + "}<tool_call|>"
    try:
        parse_completion(deep)
        gen["C9_bounded_nesting"] = [0, 1]
    except ParseError as e:
        gen["C9_bounded_nesting"] = [int(e.code == "TOO_DEEP"), 1]
    except RecursionError:
        gen["C9_bounded_nesting"] = [0, 1]
    ok = not failures and all(k == n for k, n in gen.values())
    return {"ok": ok, "public_repro_classes": per_class, "generated": gen, "failures": failures[:20],
            "linear_time_seconds": {"2000_args": round(times[0], 4), "8000_args": round(times[1], 4)}}


# ------------------------------------------------------------------------------------------------- P1
def synthetic_payloads(n: int = 300, seed: int = 20261105) -> list[dict]:
    """Edit payloads whose strings are full of look-alike closers (the adversarial QuoteStorm idea), generic code."""
    r = random.Random(seed)
    frags = ['`', '"', "'", '```', '"""', '\\"', "`,", '",', "',", "x = `a`", 'print("ok")', "s = 'it''s'",
             "f\"{a}\"", "# `old_string` ", "new_string:", ",filepath:", "\n", "    ", "return {\"k\": v}"]
    out = []
    for i in range(n):
        old = "".join(r.choice(frags) for _ in range(r.randint(1, 12)))
        new = "".join(r.choice(frags) for _ in range(r.randint(1, 12)))
        out.append({"src": "synthetic", "filepath": f"pkg/mod_{i % 17}.py", "old": old, "new": new})
    return out


def check_p1(model_dir: str, *, data: str | None = None, engine: str = "frozen", cfgs: tuple[str, ...] = ("ipd", "fullp"),
             limit: int | None = None, logdir: str | None = None) -> dict:
    """Port of workstream B's P1 acceptance harness (intent_decoding/proxy_equivalence.py, _p1e_worker): E's real
    Proxy.engine_chat with the model replaced by a replay of each valid edit call; the delivered call must carry
    exactly the intended arguments and the proxy's raw text must equal the replayed call."""
    import asyncio
    import collections
    import tempfile
    from ._frozen import load_e
    from .repair.proxy import make_proxy, proxy_args

    payloads = ([json.loads(l) for l in open(data, encoding="utf-8")] if data else synthetic_payloads())
    payloads = [p for p in payloads if isinstance(p.get("old"), str) and isinstance(p.get("new"), str)]
    if limit:
        payloads = payloads[:limit]
    E = load_e(with_proxy=True)
    gp = E.gemma_protocol
    BG = gp.BG
    tools_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tools_edit.json")
    tools = json.load(open(tools_path, encoding="utf-8"))
    tmp = None
    if logdir is None:
        tmp = tempfile.TemporaryDirectory(prefix="slipguard-p1-")
        logdir = tmp.name
    args = proxy_args(backend="http://127.0.0.1:9/v1", served="gemma-4", model_dir=model_dir, logdir=logdir,
                      cpu_workers=1, max_backend_conc=4, call_timeout=60.0)
    px = make_proxy(args, engine=engine)
    eng = px.engine
    tok = eng.tok
    EOS = 106
    msgs = [{"role": "system", "content": "You are a coding agent."}, {"role": "user", "content": "Apply the edit."}]
    _, pids = eng.render_ids(gp.to_conversation(msgs), [dict(t) for t in tools], {"enable_thinking": False}, False)
    cur = {"G": None}

    async def stub_backend(path, body, timeout):
        G = cur["G"]
        ids = body["prompt"]
        sofar = eng.decode(ids[len(pids):])
        if body.get("allowed_token_ids"):
            t = int(body["allowed_token_ids"][0])
            return 200, json.dumps({"choices": [{"logprobs": {"tokens": [f"token_id:{t}"], "token_logprobs": [0.0]}}]})
        ok = G.startswith(sofar)
        if body.get("max_tokens") == 1:
            t = tok.encode(G[len(sofar):len(sofar) + 64], add_special_tokens=False)[0] if (ok and len(sofar) < len(G)) else EOS
            return 200, json.dumps({"choices": [{"token_ids": [t], "text": tok.decode([t])}]})
        if not ok:
            return 200, json.dumps({"choices": [{"text": "", "token_ids": [EOS], "finish_reason": "stop", "stop_reason": None}]})
        rest = G[len(sofar):]
        best = None
        for s_ in body.get("stop") or []:
            i = rest.find(s_)
            if i >= 0 and (best is None or i + len(s_) < best[0]):
                best = (i + len(s_), s_)
        if best is not None:
            ch = rest[:best[0]]
            return 200, json.dumps({"choices": [{"text": ch, "token_ids": tok.encode(ch, add_special_tokens=False),
                                                 "finish_reason": "stop", "stop_reason": best[1]}]})
        return 200, json.dumps({"choices": [{"text": rest, "token_ids": (tok.encode(rest, add_special_tokens=False) if rest else []) + [EOS],
                                             "finish_reason": "stop", "stop_reason": None}]})

    px.backend = stub_backend
    res = {}

    async def run_cfg(cfg_name):
        c = collections.Counter()
        ex = []
        cfg = px.cfgs[cfg_name]
        for p in payloads:
            for order in ("new_first", "old_first"):
                keys = ["filepath", "new_string", "old_string"] if order == "new_first" else ["filepath", "old_string", "new_string"]
                vals = {"filepath": p["filepath"], "new_string": p["new"], "old_string": p["old"]}
                G = gp.TC_START + BG.render_call("edit_file", [(k, vals[k], "str") for k in keys]) + gp.TC_END
                if tok.decode(tok.encode(G, add_special_tokens=False)) != G:
                    c["roundtrip_skipped"] += 1
                    continue
                if not BG.is_valid(G[len(gp.TC_START):-len(gp.TC_END)], BG.schema_from_tools(tools)):
                    c["not_strictly_valid_skipped"] += 1
                    continue
                cur["G"] = G
                body = {"messages": msgs, "tools": tools, "temperature": 0.2, "top_p": 0.95, "seed": 0,
                        "max_tokens": len(tok.encode(G, add_special_tokens=False)) + 64,
                        "chat_template_kwargs": {"enable_thinking": False}}
                rec = {"cfg": cfg_name}
                st, out = await px.engine_chat(body, cfg, rec)
                c["n"] += 1
                tcs = ((out.get("choices") or [{}])[0].get("message", {}).get("tool_calls") or []) if st == 200 else []
                a = json.loads(tcs[0]["function"]["arguments"]) if tcs else None
                raw_same, args_same = rec.get("raw") == G, a == vals
                c["changed"] += not (raw_same and args_same)
                if not (raw_same and args_same) and len(ex) < 5:
                    ex.append({"order": order, "raw_same": raw_same, "args_same": args_same})
        return {"calls": c["n"], "changed": c["changed"], "roundtrip_skipped": c["roundtrip_skipped"],
                "not_strictly_valid_skipped": c["not_strictly_valid_skipped"], "pass": c["changed"] == 0 and c["n"] > 0,
                "examples": ex}

    async def main():
        await px.start(None)
        try:
            for cfg_name in cfgs:
                res[cfg_name] = await run_cfg(cfg_name)
        finally:
            await px.stop(None)
    asyncio.run(main())
    if tmp is not None:
        for f in px.logs.values():
            f.close()
        tmp.cleanup()
    return {"ok": all(v["pass"] for v in res.values()), "engine": engine, "payloads": len(payloads),
            "source": "QuoteStorm payloads file" if data else "built-in synthetic look-alike payloads", "by_cfg": res}
