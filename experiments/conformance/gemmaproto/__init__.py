"""gemmaproto: executable specification of the Gemma-4 tool-call protocol.

    from gemmaproto import render_call, parse_call, ParseError
    text = render_call("edit_file", {"filepath": "a.py", "old_string": "x", "new_string": "y"})
    call = parse_call(text)            # exact inverse on canonical text; raises ParseError otherwise

See spec/GEMMA4_PROTOCOL_SPEC.md for the grammar (EBNF), value types, key rules and template semantics.
"""
from .tokens import *  # noqa: F401,F403
from .serializer import (render_value, render_call, render_args_body, render_tool_response, render_declaration,
                         dictsort_items, is_representable, is_bare_key, values_equal, TemplateError, JULY, JUNE,
                         TEMPLATES)
from .parser import (ParseError, ToolCall, ParsedCompletion, parse_call, parse_completion, parse_value_text,
                     parse_args_body, IncrementalCallParser, find_absorbed, absorbed_arg_pattern, ERROR_CODES)

__version__ = "0.1.0"
