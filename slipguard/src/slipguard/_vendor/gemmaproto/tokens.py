"""Gemma-4 control tokens (text form) and their ids in the Gemma-4 tokenizer (all sizes share the vocabulary).

Every token below is a *single* special token in the tokenizer, and the HF tokenizer is loaded with
``split_special_tokens=False``: the same character sequence appearing inside data (a file, a tool result)
is tokenized as the control token, not as text. See spec/GEMMA4_PROTOCOL_SPEC.md section 8.
"""

BOS = "<bos>"                      # id 2
EOS = "<eos>"                      # id 1
TURN_OPEN = "<|turn>"              # id 105
TURN_CLOSE = "<turn|>"             # id 106
TOOL_DECL_OPEN = "<|tool>"         # id 46
TOOL_DECL_CLOSE = "<tool|>"        # id 47
TOOL_CALL_OPEN = "<|tool_call>"    # id 48
TOOL_CALL_CLOSE = "<tool_call|>"   # id 49
TOOL_RESP_OPEN = "<|tool_response>"   # id 50
TOOL_RESP_CLOSE = "<tool_response|>"  # id 51
STR = '<|"|>'                      # id 52: the ONLY string delimiter; there is no escape mechanism
CHANNEL_OPEN = "<|channel>"        # id 100
CHANNEL_CLOSE = "<channel|>"       # id 101
THINK = "<|think|>"                # id 98

TOKEN_IDS = {
    BOS: 2, EOS: 1, TURN_OPEN: 105, TURN_CLOSE: 106, TOOL_DECL_OPEN: 46, TOOL_DECL_CLOSE: 47,
    TOOL_CALL_OPEN: 48, TOOL_CALL_CLOSE: 49, TOOL_RESP_OPEN: 50, TOOL_RESP_CLOSE: 51, STR: 52,
    CHANNEL_OPEN: 100, CHANNEL_CLOSE: 101, THINK: 98,
}

# Control tokens that must never appear inside a well-formed call outside of string values.
PROTOCOL_TOKENS = (TURN_OPEN, TURN_CLOSE, TOOL_DECL_OPEN, TOOL_DECL_CLOSE, TOOL_CALL_OPEN, TOOL_CALL_CLOSE,
                   TOOL_RESP_OPEN, TOOL_RESP_CLOSE, CHANNEL_OPEN, CHANNEL_CLOSE, THINK, BOS, EOS)

# Look-alike closers observed in real Gemma-4 outputs (a string closed with one of these instead of STR).
# Order matters for longest-match labelling.
LOOKALIKE_CLOSERS = ('\\"\\"\\"', '"""', "'''", '```', '\\"', "\\'", '"', "'", '`', '”', '’')
