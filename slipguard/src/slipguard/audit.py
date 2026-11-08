"""`slipguard audit`: scan existing agent transcripts (OpenAI-format message lists) for Gemma 4 protocol hazards.

    slipguard audit transcripts.jsonl [--tools tools.json] [--json]

Input: a JSON file with one conversation, or JSONL with one conversation per line. A conversation is either a list of
messages or an object with ``messages`` (and optionally ``tools``).

The malformed_call check needs the TOOL DECLARATIONS (OpenAI ``tools`` list): from the conversation's own ``tools``,
else from ``--tools`` (a JSON list, or an object with a ``tools`` key, e.g. a PNC context manifest:
``data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json``). A conversation without declarations is NOT checked for
malformed calls: the summary on stderr says so, and the --json line carries
``"malformed_call": "not checked (no tool declarations)"``. ``--require-tools`` turns that into exit status 2.

Findings per conversation (nothing is modified):
  malformed_call        a historical call that workstream E's frozen criterion flags (unknown tool, missing or
                        undeclared keys, leaked look-alike closer, special token in a value) -- what quarantine would fix
  raw_call_in_content   assistant text still carrying raw tool-call markup (a call returned as content)
  control_text          control-token text inside a tool result or a historical call argument
  serialized_result     a tool result that is ADK/LiteLLM's json.dumps({'result': ...}) form
  thinking_off_gap      the conversation ends with a tool result while thinking is off (needs the closed thought)
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable

from .history import transforms as T
from .history.neutralize import has_control_text, value_has_control_text


NOT_CHECKED = "not checked (no tool declarations)"


def audit_messages(messages: list[dict], tools: list[dict] | None = None,
                   enable_thinking: bool | None = None) -> list[dict]:
    """Findings for one conversation. Without ``tools`` the malformed_call check cannot run and is skipped (the CLI
    reports that explicitly; see the module docstring)."""
    out: list[dict] = []
    if tools:
        from ._frozen import load_e
        qr = load_e().quarantine_renderer
        schemas = qr.tool_schemas(tools)
        strict = T.strict_ids(messages)
        for i, m in enumerate(messages):
            for tc in (m.get("tool_calls") or []) if m.get("role") == "assistant" else []:
                f = tc.get("function") or {}
                a = f.get("arguments")
                try:
                    args = json.loads(a) if isinstance(a, str) else (a or {})
                except ValueError:
                    args = None
                cls = qr.classify_args(f.get("name"), args, schemas)
                if not cls["ok"] and tc.get("id") not in strict:
                    out.append({"finding": "malformed_call", "message": i, "id": tc.get("id"), "tool": f.get("name"),
                                "why": cls["why"]})
    for i, m in enumerate(messages):
        role = m.get("role")
        if role == "assistant":
            txt = T._text_of(m.get("content")) or ""
            if T.TOOL_CALL_OPEN in txt:
                out.append({"finding": "raw_call_in_content", "message": i})
            for tc in m.get("tool_calls") or []:
                a = (tc.get("function") or {}).get("arguments")
                if (isinstance(a, str) and has_control_text(a)) or (isinstance(a, (dict, list)) and value_has_control_text(a)):
                    out.append({"finding": "control_text", "message": i, "where": "call arguments", "id": tc.get("id")})
        elif role == "tool":
            txt = T._text_of(m.get("content"))
            if txt is not None and has_control_text(txt):
                out.append({"finding": "control_text", "message": i, "where": "tool result"})
            if isinstance(m.get("content"), str) and T._unwrap_result(m["content"]) is not None:
                out.append({"finding": "serialized_result", "message": i})
    if messages and messages[-1].get("role") == "tool" and not enable_thinking:
        out.append({"finding": "thinking_off_gap", "message": len(messages) - 1})
    return out


def _conversations(path: str) -> Iterable[tuple[list[dict], list[dict] | None]]:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        docs: list[Any] = [json.loads(text)]
    except ValueError:
        docs = [json.loads(line) for line in text.splitlines() if line.strip()]
    for d in docs:
        if isinstance(d, list):
            yield d, None
        elif isinstance(d, dict):
            yield d.get("messages") or [], d.get("tools")


def load_tools(path: str) -> list[dict]:
    """--tools file: a JSON list of tool declarations, or an object with a ``tools`` list (e.g. a PNC context
    manifest.json)."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, dict) and isinstance(d.get("tools"), list):
        d = d["tools"]
    if not isinstance(d, list):
        raise SystemExit(f"slipguard audit: {path}: expected a JSON list of tool declarations or an object with 'tools'")
    return d


def main(argv: list[str] | None = None) -> int:
    epilog = ("input: a JSON file with one conversation, or JSONL with one per line; a conversation is a list of "
              "OpenAI-format messages, or an object {\"messages\": [...], \"tools\": [...]} (tools optional).\n"
              "findings: malformed_call, raw_call_in_content, control_text, serialized_result, thinking_off_gap.\n"
              "exit status: 0 = no malformed_call, raw_call_in_content or control_text finding (serialized_result and "
              "thinking_off_gap are reported but do not fail); 1 = at least one of those three; 2 = --require-tools "
              "and a conversation had no tool declarations, or a usage error.\n"
              "Runs on the CPU with the core install (standard library only).")
    ap = argparse.ArgumentParser(prog="slipguard audit", description=__doc__.split("\n\n")[0], epilog=epilog,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="transcripts: .json (one conversation) or .jsonl (one per line)")
    ap.add_argument("--tools", help="tool declarations for conversations that do not carry their own: a JSON list, or an "
                                    "object with 'tools' (e.g. a PNC context manifest.json). Without declarations the "
                                    "malformed_call check cannot run")
    ap.add_argument("--require-tools", action="store_true",
                    help="exit 2 if any conversation could not be checked for malformed calls (no tool declarations)")
    ap.add_argument("--thinking", action="store_true", help="the conversations ran with thinking on")
    ap.add_argument("--json", action="store_true", help="one JSON line per conversation")
    a = ap.parse_args(argv)
    default_tools = load_tools(a.tools) if a.tools else None
    totals: dict[str, int] = {}
    n = unchecked = 0
    for k, (msgs, tools) in enumerate(_conversations(a.file)):
        n += 1
        decl = tools or default_tools
        unchecked += not decl
        f = audit_messages(msgs, decl, enable_thinking=a.thinking)
        for x in f:
            totals[x["finding"]] = totals.get(x["finding"], 0) + 1
        if a.json:
            print(json.dumps({"conversation": k, "malformed_call": "checked" if decl else NOT_CHECKED, "findings": f},
                             ensure_ascii=False))
        elif f or not decl:
            print(f"conversation {k}: " + "; ".join([f"{x['finding']}@{x['message']}" for x in f]
                                                    + ([] if decl else ["malformed_call " + NOT_CHECKED])))
    if unchecked:
        print(f"slipguard audit: WARNING: malformed_call check SKIPPED for {unchecked} of {n} conversation(s): no tool "
              "declarations. Pass --tools <tools.json> (a JSON list, or e.g. a PNC context manifest.json).",
              file=sys.stderr)
    print(f"{n} conversation(s); findings: {json.dumps(totals) if totals else 'none'}"
          + (f"; malformed_call not checked in {unchecked}" if unchecked else ""), file=sys.stderr)
    if a.require_tools and unchecked:
        return 2
    return 1 if totals.get("malformed_call") or totals.get("raw_call_in_content") or totals.get("control_text") else 0
