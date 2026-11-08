"""Patched Gemma 4 chat template (unofficial) and a dependency-light renderer.

Files (package data):
  gemma4_july_guarded.jinja   the official July template + two patches (tools/build_template.py):
                              P-a closed empty thought after a tool response when thinking is off;
                              P-b control-token text in tool calls / tool responses made inert (reversible).
  gemma4_july_official.jinja  the unmodified official template (md5 f016bd4b...), shipped for verification.

Use it server-side:  vllm serve <model> --chat-template "$(slipguard template-path)"   (or pass the text as
``chat_template=`` to transformers' ``apply_chat_template``). On every input without those two hazards the output is
byte-identical to the official template (tests T-T1..T-T4).

``render()`` renders with the same Jinja environment transformers uses (sandboxed, trim_blocks, lstrip_blocks,
loopcontrols, tojson without HTML escaping, raise_exception), so no transformers install is needed.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from functools import lru_cache
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
GUARDED = os.path.join(HERE, "gemma4_july_guarded.jinja")
CLOSURE = os.path.join(HERE, "gemma4_july_closure.jinja")      # P-a only
OFFICIAL = os.path.join(HERE, "gemma4_july_official.jinja")
OFFICIAL_MD5 = "f016bd4bc2846e094d596e4ab02644af"


def path(which: str = "guarded") -> str:
    return {"guarded": GUARDED, "closure": CLOSURE, "official": OFFICIAL}[which]


def text(which: str = "guarded") -> str:
    with open(path(which), encoding="utf-8") as f:
        return f.read()


def official_md5() -> str:
    return hashlib.md5(text("official").encode()).hexdigest()


@lru_cache(maxsize=8)
def _compiled(src: str):
    import jinja2
    import jinja2.ext
    from jinja2.sandbox import ImmutableSandboxedEnvironment

    def raise_exception(message):
        raise jinja2.exceptions.TemplateError(message)

    def tojson(x, ensure_ascii=False, indent=None, separators=None, sort_keys=False):
        return json.dumps(x, ensure_ascii=ensure_ascii, indent=indent, separators=separators, sort_keys=sort_keys)

    env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, extensions=[jinja2.ext.loopcontrols])
    env.filters["tojson"] = tojson
    env.globals["raise_exception"] = raise_exception
    env.globals["strftime_now"] = lambda fmt: datetime.now().strftime(fmt)
    return env.from_string(src)


def render(messages: list[dict], tools: list[dict] | None = None, *, add_generation_prompt: bool = True,
           enable_thinking: bool = False, which: str = "guarded", template_text: str | None = None,
           **kwargs: Any) -> str:
    """Render a conversation to the prompt text (special tokens as text), like transformers'
    ``apply_chat_template(..., tokenize=False)``. Needs jinja2 >= 3.1."""
    src = template_text if template_text is not None else text(which)
    return _compiled(src).render(messages=messages, tools=tools, documents=None,
                                 add_generation_prompt=add_generation_prompt, enable_thinking=enable_thinking,
                                 bos_token="<bos>", eos_token="<eos>", **kwargs)
