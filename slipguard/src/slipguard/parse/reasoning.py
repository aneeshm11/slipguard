"""String-aware split of a Gemma 4 completion into (reasoning, content) -- used by the vLLM reasoning plugin and the
proxy's lite engine. Pure Python."""
from __future__ import annotations

CH_OPEN, CH_CLOSE = "<|channel>", "<channel|>"
TOOL_CALL_OPEN = "<|tool_call>"
_THOUGHT_LABEL = "thought\n"


def split_reasoning(model_output: str) -> tuple[str | None, str | None]:
    """String-aware split of one completion into (reasoning, content).

    * output starts with <|channel>: the reasoning is up to the FIRST <channel|> (label 'thought\\n' stripped);
      unterminated -> everything is reasoning, content None (as vLLM does);
    * else, if a <channel|> occurs before any <|tool_call> and the output has no <|channel> before it: the prompt
      ended inside a thought (JULY template, thinking on, after a tool result) -> reasoning = text before it;
    * else: no reasoning; the whole output is content.
    The content is never split again: later channel tokens stay in the content (the tool parser reports them).
    """
    if model_output.startswith(CH_OPEN):
        j = model_output.find(CH_CLOSE)
        body = model_output[len(CH_OPEN):] if j < 0 else model_output[len(CH_OPEN):j]
        if body.startswith(_THOUGHT_LABEL):
            body = body[len(_THOUGHT_LABEL):]
        if j < 0:
            return body, None
        return body, (model_output[j + len(CH_CLOSE):] or None)
    j = model_output.find(CH_CLOSE)
    if j >= 0:
        k = model_output.find(TOOL_CALL_OPEN)
        o = model_output.find(CH_OPEN)
        if (k < 0 or j < k) and (o < 0 or o > j):
            return model_output[:j], (model_output[j + len(CH_CLOSE):] or None)
    return None, model_output
