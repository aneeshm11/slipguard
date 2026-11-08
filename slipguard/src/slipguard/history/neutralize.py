"""Reversible neutralization of Gemma 4 control-token text inside untrusted strings.

The Gemma 4 tokenizer turns the *text* of its 24 special tokens into the special tokens themselves, wherever the text
occurs, including inside tool results and string arguments. The format has no escape mechanism. Neutralization breaks
every such spelling with one U+2060 WORD JOINER (WJ) after the leading ``<``, so the text reaches the model as
ordinary characters:

    N(s)    = s with every "<WJ" replaced by "<WJWJ", then every special-token text "<R" replaced by "<WJ R"
    N^-1(s) = s with every "<WJWJ" replaced by "<WJ" and every "<WJ R" (R a special-token tail) replaced by "<R"

N is injective (no token tail starts with WJ), N^-1(N(s)) == s for every string, and N(s) == s for every string that
contains neither a special-token text nor "<WJ" -- so clean content is never touched.

Prefer token-level protection where you control tokenization (tokenize untrusted spans with special-token parsing
disabled); use this text-level form when the text is rendered by someone else's chat template and tokenizer.
"""
from __future__ import annotations

import re

WJ = "⁠"
# The 24 special tokens of the Gemma 4 tokenizer (all sizes share the vocabulary). Every one starts with '<'.
SPECIAL_TOKENS: tuple[str, ...] = (
    "<pad>", "<eos>", "<bos>", "<unk>", "<mask>", "<|tool>", "<tool|>", "<|tool_call>", "<tool_call|>",
    "<|tool_response>", "<tool_response|>", '<|"|>', "<|think|>", "<|channel>", "<channel|>", "<|turn>", "<turn|>",
    "<|image>", "<|audio>", "<|image|>", "<|audio|>", "<image|>", "<audio|>", "<|video|>",
)
_TAILS = sorted({t[1:] for t in SPECIAL_TOKENS}, key=len, reverse=True)
_TOKEN_RE = re.compile("<(?=" + "|".join(re.escape(t) for t in _TAILS) + ")")
_HAZARD_RE = re.compile("<(?:" + WJ + "|" + "|".join(re.escape(t) for t in _TAILS) + ")")
_INVERSE_RE = re.compile("<" + WJ + "(" + WJ + "|(?=" + "|".join(re.escape(t) for t in _TAILS) + "))")


def has_control_text(s: str) -> bool:
    """True iff ``s`` contains the text of a Gemma 4 special token (or a ``<WJ`` that N must escape)."""
    return bool(_HAZARD_RE.search(s))


def neutralize_text(s: str) -> str:
    """N(s): see the module docstring. Identity on clean strings."""
    if not _HAZARD_RE.search(s):
        return s
    s = s.replace("<" + WJ, "<" + WJ + WJ)
    return _TOKEN_RE.sub("<" + WJ, s)


def unneutralize_text(s: str) -> str:
    """N^-1(s): exact inverse of :func:`neutralize_text`."""
    if ("<" + WJ) not in s:
        return s
    return _INVERSE_RE.sub(lambda m: "<" + (WJ if m.group(1) == WJ else ""), s)


def neutralize_value(v):
    """Apply N to every string (and mapping key) inside a JSON-like value. Returns ``v`` itself when clean."""
    if isinstance(v, str):
        return neutralize_text(v)
    if isinstance(v, list):
        out = [neutralize_value(x) for x in v]
        return v if all(a is b for a, b in zip(out, v)) else out
    if isinstance(v, dict):
        changed = False
        out = {}
        for k, x in v.items():
            nk = neutralize_text(k) if isinstance(k, str) else k
            nx = neutralize_value(x)
            changed = changed or nk is not k or nx is not x
            out[nk] = nx
        return out if changed else v
    return v


def value_has_control_text(v) -> bool:
    if isinstance(v, str):
        return has_control_text(v)
    if isinstance(v, list):
        return any(value_has_control_text(x) for x in v)
    if isinstance(v, dict):
        return any((isinstance(k, str) and has_control_text(k)) or value_has_control_text(x) for k, x in v.items())
    return False
