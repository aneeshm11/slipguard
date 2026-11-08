"""slipguard.parse in 30 lines: strict parse, per-call runtime parse, streaming."""
from slipguard.parse import ParseError, StreamParser, extract, parse_completion

D = '<|"|>'
good = "<|tool_call>call:edit_file{filepath:" + D + "a.py" + D + ",new_string:" + D + "x = 1" + D + ",old_string:" + D + "x = 0" + D + "}<tool_call|>"
slip = good.replace("x = 1" + D + ",old", "x = 1`,old")          # the one-token slip: a backtick closes the string

print(parse_completion(good).calls[0].arguments)
try:
    parse_completion(slip)
except ParseError as e:                                            # fail loud: code + position
    print("slip detected:", e.code, "at", e.pos)

ex = extract("Let me edit. " + good + slip)                        # runtime semantics
print(len(ex.calls), "call delivered;", [e.code for e in ex.errors], "; content:", ex.content[:40], "...")

sp = StreamParser(mode="per_call")                                 # streaming: a call arrives whole, at its end
for i in range(0, len(good), 5):
    for ev in sp.feed(good[i:i + 5]):
        if ev[0] == "call_end":
            print("streamed call:", ev[2].name)
sp.finish()
