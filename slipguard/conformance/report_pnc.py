"""Public-input conformance report: every PNC turn, slipguard vs the built-in parsers, judged with workstream C's rules.

    python conformance/report_pnc.py --suite <C's conformance dir> --cases cases_pnc.jsonl --out <dir> <results.jsonl ...>

Populations (conformance/build_pnc_cases.py):
  valid             strictly valid turns with >= 1 call; intended = the calls the model emitted
  ill_intent_known  ill-formed turns whose malformed call is restated by a later clean retry (retry-derived gold)
  ill_no_intent     every other ill-formed turn (no intent: delivered calls are counted, never scored)
Per target: valid calls exact; ill-formed turns surfaced (C's judge: loud, or returned as text that still carries the
call) / silently delivered / silently lost; on known intent: exact / wrong / surfaced; per input class (first protocol
error) the number of turns on which the target was silent; streaming == non-streaming; hangs and exceptions.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


SUITE = _arg("--suite")
sys.path.insert(0, os.path.join(SUITE, "diff"))
sys.path.insert(0, SUITE)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from analyze_x import judge, input_kind, retained  # noqa: E402
from gemmaproto.conformance import fingerprint  # noqa: E402
from worker import dec  # noqa: E402
from slipguard.parse import extract  # noqa: E402
from slipguard.parse.reasoning import split_reasoning  # noqa: E402

WRONG = {"DROPPED_ARG", "EXTRA_KEY", "CORRUPT_VALUE", "EMPTY_ARGS", "WRONG_NAME", "CALL_COUNT", "TYPE_DIFF"}
LABEL = {"EXPECTED_COLON": "key=value argument drift", "NO_CALL_PREFIX": "call-header drift",
         "EXPECTED_SEP": "look-alike string closer", "INVALID_LITERAL": "bare / foreign literal",
         "UNTERMINATED": "unterminated call", "JSON_STYLE_STRING": "JSON-style string",
         "STRAY_TOKEN": "stray control token"}


def pretty(t):
    if t.startswith("gg."):
        t2 = t[3:]
        if t2.startswith("vllm"):
            v, p = t2.split(".")
            return f"slipguard plugin, vLLM 0.{int(v[4:])} {p}"
        return {"completion": "slipguard parse_completion", "extract": "slipguard extract (per-call)",
                "stream": "slipguard StreamParser", "repair": "slipguard extract(repair=True) [opt-in]"}[t2]
    if t.startswith("vllm"):
        v, p = t.split(".")
        return f"vLLM 0.{int(v[4:])} built-in {p}"
    if t.startswith("hf"):
        return f"transformers {t[2]}.{t[3:5]} parse_response"
    return {"ref": "gemmaproto (reference)"}.get(t, t)


def main():
    cases, kind, code, prefix_fp, rest = {}, {}, {}, {}, {}
    for line in open(_arg("--cases"), encoding="utf-8"):
        c = json.loads(line)
        c["intended"] = dec(c["intended"]) if c.get("intended") is not None else None
        cases[c["id"]] = c
        kind[c["id"]] = input_kind(c["text"])
        if c["subfamily"].startswith("ill"):
            _, ct = split_reasoning(c["text"])
            ex = extract(ct or "")
            code[c["id"]] = ex.errors[0].code if ex.errors else "none"
            if ex.calls and ex.errors:     # per-call semantics: the strictly valid calls before the first error
                prefix_fp[c["id"]] = (len(ex.calls), fingerprint([{"name": k.name, "arguments": k.arguments}
                                                                  for k in ex.calls]))
                rest[c["id"]] = (ct or "")[ex.errors[0].pos:]
    pop = collections.Counter(c["subfamily"] for c in cases.values())
    files = [a for a in sys.argv[1:] if a.endswith(".jsonl") and a != _arg("--cases")]
    seen = set()                          # LATER files win (a re-run of one target overrides an earlier result)
    paths = [f for pat in files for f in sorted(glob.glob(pat))][::-1]
    agg = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    by_code = collections.defaultdict(collections.Counter)
    fps = collections.defaultdict(dict)
    safety = collections.defaultdict(lambda: {"n": 0, "hang": 0, "exception": 0, "max_ms": 0.0})
    examples = collections.defaultdict(list)
    for f in paths:
        if True:
            for line in open(f, encoding="utf-8"):
                r = json.loads(line)
                key = (r["case"], r["target"])
                if key in seen:          # same (case, target) in two files: keep the later file's result
                    continue
                seen.add(key)
                c = cases[r["case"]]
                t, sf = r["target"], c["subfamily"]
                s = safety[t]
                s["n"] += 1
                s["hang"] += r.get("outcome") == "HANG" or r.get("status") in ("timeout", "hard_hang")
                s["exception"] += r.get("status") in ("exception", "crash") and not t.startswith("hf")
                s["max_ms"] = max(s["max_ms"], r.get("ms") or 0)
                bucket, verdict = judge(kind[r["case"]], r, c["intended"], text=c["text"])
                o = r["outcome"]
                a = agg[t][sf]
                a["n"] += 1
                a["outcome:" + o] += 1
                a["verdict:" + verdict] += 1
                if sf.startswith("valid"):
                    a["exact"] += o == "EXACT"
                else:
                    loud = o == "LOUD" or (o == "HANG") or r.get("status") in ("exception",)
                    if verdict == "pass":
                        a["surfaced"] += 1
                    elif r.get("n_calls") and prefix_fp.get(r["case"]) == (r["n_calls"], r.get("fp")) \
                            and retained(rest[r["case"]], r):
                        a["prefix_then_text"] += 1   # valid calls before the first error delivered, the rest as text
                        verdict = "pass"
                    elif r.get("n_calls"):
                        a["delivered"] += 1
                        if sf == "ill_intent_known":
                            a["exact" if o == "EXACT" else "wrong"] += 1
                    else:
                        a["lost"] += 1
                    if verdict != "pass" and not loud:
                        by_code[t][code[r["case"]]] += 1
                        if sf == "ill_intent_known" and o in WRONG and len(examples[t]) < 3:
                            examples[t].append(r["case"])
                if t.endswith((".server", ".stream")):
                    fps[t][r["case"]] = (o, r.get("fp"))
    targets = sorted(agg, key=lambda t: (not t.startswith("gg."), t))
    n_ill = pop["ill_intent_known"] + pop["ill_no_intent"]
    out = {"source": "public PNC corpus: every model turn (raw generation incl. thinking) with its episode's tool schema",
           "populations": dict(pop), "ill_input_classes": dict(collections.Counter(code.values())),
           "no_intent_reasons": dict(collections.Counter(c["meta"].get("no_intent") for c in cases.values()
                                                         if c["subfamily"] == "ill_no_intent")),
           "targets": {}, "stream_vs_server": {}}
    for t in targets:
        v, ik, ni = agg[t]["valid"], agg[t]["ill_intent_known"], agg[t]["ill_no_intent"]
        out["targets"][t] = {
            "label": pretty(t),
            "valid_exact": [v["exact"], v["n"]],
            "ill_surfaced": [ik["surfaced"] + ni["surfaced"], ik["n"] + ni["n"]],
            "ill_prefix_calls_then_text": ik["prefix_then_text"] + ni["prefix_then_text"],
            "ill_silently_delivered": ik["delivered"] + ni["delivered"],
            "ill_silently_lost": ik["lost"] + ni["lost"],
            "intent_known": {"n": ik["n"], "exact": ik["exact"], "wrong": ik["wrong"], "surfaced": ik["surfaced"],
                             "lost": ik["lost"]},
            "no_intent": {"n": ni["n"], "delivered_unscored": ni["delivered"], "surfaced": ni["surfaced"],
                          "lost": ni["lost"]},
            "silent_by_input_class": dict(by_code[t]),
            "outcomes": {sf: {k: n for k, n in agg[t][sf].items() if k.startswith(("outcome:", "verdict:"))}
                         for sf in agg[t]},
            "safety": safety[t], "wrong_examples": examples[t]}
    for t in targets:
        if t.endswith(".server") and t[:-7] + ".stream" in fps:
            a, b = fps[t], fps[t[:-7] + ".stream"]
            common = set(a) & set(b)
            out["stream_vs_server"][t[:-7]] = {"n": len(common), "same": sum(a[k] == b[k] for k in common)}
    od = _arg("--out")
    os.makedirs(od, exist_ok=True)
    json.dump(out, open(os.path.join(od, "RESULTS.json"), "w"), indent=1, ensure_ascii=False)

    def frac(k, n):
        return f"{k:,}/{n:,}"
    L = ["# Conformance on public real inputs (PNC: every model turn)", "",
         f"{sum(pop.values()):,} turns: {pop['valid']:,} strictly valid turns with calls, {pop.get('valid_no_call', 0)} valid "
         f"without a call, {n_ill:,} ill-formed ({pop['ill_intent_known']} with retry-derived intent, "
         f"{pop['ill_no_intent']} without). Judged with workstream C's rules (diff/analyze_x.judge). Built-in = the "
         "parsers vLLM / transformers ship (C's harness); slipguard = this library, the plugin driven through each "
         "vLLM version's own server objects. Streaming = one token per delta, no length cap.", "",
         "Ill-formed input classes (first protocol error): " +
         ", ".join(f"{LABEL.get(k, k)} {n}" for k, n in collections.Counter(code.values()).most_common()) + ".", "",
         "| target | valid calls exact | ill-formed surfaced | of which: valid calls before the error + rest as text | "
         "silently delivered | silently lost | known intent: exact / WRONG / surfaced | no intent: delivered (unscored) "
         "| hang / exc |",
         "|---|---|---|---|---|---|---|---|---|"]
    for t in targets:
        r = out["targets"][t]
        ik, ni, s = r["intent_known"], r["no_intent"], r["safety"]
        L.append(f"| {r['label']} | {frac(*r['valid_exact'])} | {frac(r['ill_surfaced'][0] + r['ill_prefix_calls_then_text'], r['ill_surfaced'][1])} | "
                 f"{r['ill_prefix_calls_then_text']} | {r['ill_silently_delivered']} | {r['ill_silently_lost']} | {ik['exact']} / {ik['wrong']} / "
                 f"{ik['surfaced']} (n={ik['n']}) | {ni['delivered_unscored']} (n={ni['n']}) | {s['hang']} / {s['exception']} |")
    classes = [k for k, _ in collections.Counter(code.values()).most_common()]
    L += ["", "## Silent outcomes per input class (turns where the target neither raised nor kept the call text)", "",
          "| target | " + " | ".join(f"{LABEL.get(k, k)} (n={list(code.values()).count(k)})" for k in classes) + " |",
          "|---|" + "---|" * len(classes)]
    for t in targets:
        L.append(f"| {out['targets'][t]['label']} | " + " | ".join(str(by_code[t].get(k, 0)) for k in classes) + " |")
    L += ["", "## Streaming == non-streaming (same outcome and same calls)", "", "| path | same / n |", "|---|---|"]
    for p, v in out["stream_vs_server"].items():
        L.append(f"| {pretty(p + '.server').replace(' server', '')} | {frac(v['same'], v['n'])} |")
    L += ["", "Definitions. *Surfaced*: C's judge passes the target on ill-formed input (an error, or the turn returned as "
          "text that still carries the call), or -- per-call runtime semantics -- the strictly valid calls BEFORE the "
          "first protocol error are delivered and everything from the error on is returned as text (a server has no "
          "error channel; nothing after the error becomes a call). *Silently delivered*: the target returned a call from ill-formed text without "
          "an error. On turns with known intent the delivered call is scored (exact = what the model meant; WRONG = a "
          "dropped argument, a corrupted value, a wrong name or a wrong number of calls); without intent it is not "
          "scored. *Retry-derived intent*: the malformed call is the turn's last call and a later turn of the same "
          "episode (within 3) restates it as a clean call (strictly valid, not flagged by the frozen quarantine "
          "criterion) whose keys and values all occur in the malformed call text, with a canonical rendering at most "
          "8 characters shorter / 24 characters longer (conformance/build_pnc_cases.py)."]
    note = os.path.join(od, "POSTHOC_NOTE.md")      # a disclosure kept next to the results is appended verbatim
    if os.path.exists(note):
        L += ["", open(note, encoding="utf-8").read().rstrip()]
    open(os.path.join(od, "RESULTS.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
