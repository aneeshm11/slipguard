#!/usr/bin/env python3
"""Generate slipguard's patched Gemma 4 chat template from the official July template (dev-time tool).

    python tools/build_template.py <official July chat_template.jinja>

Each patch is an exact string replacement asserted to match exactly once; the official file is copied unchanged
next to the patched one (for verification). Patches:
  P-a  thinking-off closure: after a tool response with thinking off, emit the closed empty thought (the mirror of
       the template's own thinking-on prefill branch).
  P-b  control-token neutralization: a macro gg_n(s) (U+2060 after the '<' of every special-token text, reversible;
       slipguard.history.neutralize) applied to string values and keys of tool calls and tool responses and to the
       call / response names. Declarations (escape_keys=True) and system/user/model text are unchanged.
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "src", "slipguard", "template")
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from slipguard.history.neutralize import SPECIAL_TOKENS, WJ  # noqa: E402

JULY_MD5 = "f016bd4bc2846e094d596e4ab02644af"


def macro() -> str:
    chain = "s | string | replace('<" + WJ + "', '<" + WJ + WJ + "')"
    for t in SPECIAL_TOKENS:
        lit = t.replace("\\", "\\\\").replace("'", "\\'")
        chain += " | replace('" + lit + "', '<" + WJ + lit[1:] + "')"
    return ("{#- slipguard P-b: gg_n(s) makes Gemma 4 control-token text inert (U+2060 WORD JOINER after '<'; reversible) -#}\n"
            "{%- macro gg_n(s) -%}{{- " + chain + " -}}{%- endmacro -%}\n")


PATCHES = [
    ("P-a", "    {%- elif ns.prev_message_type == 'tool_response' and enable_thinking -%}\n"
            "        {{- '<|channel>thought\\n' -}}\n"
            "    {%- endif -%}\n",
            "    {%- elif ns.prev_message_type == 'tool_response' and enable_thinking -%}\n"
            "        {{- '<|channel>thought\\n' -}}\n"
            "    {#- slipguard P-a: thinking off after a tool response -> closed empty thought -#}\n"
            "    {%- elif ns.prev_message_type == 'tool_response' and not enable_thinking -%}\n"
            "        {{- '<|channel>thought\\n<channel|>' -}}\n"
            "    {%- endif -%}\n"),
    ("P-b.string", "        {{- '<|\"|>' + argument + '<|\"|>' -}}\n",
                   "        {{- '<|\"|>' + (argument if escape_keys else gg_n(argument)) + '<|\"|>' -}}\n"),
    ("P-b.argkey", "            {%- else -%}\n                {{- key -}}\n            {%- endif -%}\n",
                   "            {%- else -%}\n                {{- gg_n(key) -}}\n            {%- endif -%}\n"),
    ("P-b.respname", "        {{- 'response:' + tool_name + '{' -}}\n", "        {{- 'response:' + gg_n(tool_name) + '{' -}}\n"),
    ("P-b.respkey", "            {{- key -}}:{{- format_argument(value, escape_keys=False) -}}\n            {%- if not loop.last %},{% endif -%}\n",
                    "            {{- gg_n(key) -}}:{{- format_argument(value, escape_keys=False) -}}\n            {%- if not loop.last %},{% endif -%}\n"),
    ("P-b.respvalue", "        {{- 'response:' + tool_name + '{value:' + format_argument(response, escape_keys=False) + '}' -}}\n",
                      "        {{- 'response:' + gg_n(tool_name) + '{value:' + format_argument(response, escape_keys=False) + '}' -}}\n"),
    ("P-b.callname", "                    {{- '<|tool_call>call:' + function['name'] + '{' -}}\n",
                     "                    {{- '<|tool_call>call:' + gg_n(function['name']) + '{' -}}\n"),
    ("P-b.callkey", "                            {{- key -}}:{{- format_argument(value, escape_keys=False) -}}\n",
                    "                            {{- gg_n(key) -}}:{{- format_argument(value, escape_keys=False) -}}\n"),
    ("P-b.macro", "{%- macro strip_thinking(text) -%}\n", None),   # macro definition inserted before this line
]


def build(official: str) -> str:
    s = official
    for pid, old, new in PATCHES:
        n = s.count(old)
        if n != 1:
            raise SystemExit(f"{pid}: expected exactly one match, found {n} (template layout changed?)")
        s = s.replace(old, macro() + old if new is None else new)
    header = ("{#- slipguard: patched Gemma 4 chat template (unofficial). Base: the official template 'Published: "
              "2026-07-09' (md5 " + JULY_MD5 + "). Patches: P-a thinking-off closure after tool responses; P-b "
              "control-token neutralization in tool calls and tool responses. Identical output on every input "
              "without those hazards (slipguard tests T-T1..T-T4). -#}\n")
    return header + s


def main():
    src = sys.argv[1]
    official = open(src, encoding="utf-8").read()
    md5 = hashlib.md5(official.encode()).hexdigest()
    if md5 != JULY_MD5:
        raise SystemExit(f"not the official July template (md5 {md5})")
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "gemma4_july_official.jinja"), "w", encoding="utf-8").write(official)
    patched = build(official)
    open(os.path.join(OUT, "gemma4_july_guarded.jinja"), "w", encoding="utf-8").write(patched)
    # P-a only (for renderers that neutralize at the token level instead, e.g. the proxy's --token-neutralize)
    pid, old, new = PATCHES[0]
    assert pid == "P-a" and official.count(old) == 1
    closure = ("{#- slipguard: Gemma 4 chat template + P-a only (thinking-off closure after tool responses); base md5 "
               + JULY_MD5 + " -#}\n" + official.replace(old, new))
    open(os.path.join(OUT, "gemma4_july_closure.jinja"), "w", encoding="utf-8").write(closure)
    print("written; patched sha256", hashlib.sha256(patched.encode()).hexdigest()[:16])


if __name__ == "__main__":
    main()
