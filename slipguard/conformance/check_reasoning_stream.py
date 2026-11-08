"""Dev check: through vLLM's own server objects, the plugin's streaming reasoning/content/calls equal the
non-streaming ones on texts with a thought, a prefilled thought, and no thought."""
import json, os, random, sys
sys.argv += []
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gg_targets
from slipguard._vendor.gemmaproto import render_call
from slipguard._vendor.gemmaproto.gen import rand_string
env = gg_targets.GGEnv()
vt = env.vtag
r = random.Random(5)
bad = n = 0
for i in range(300):
    call = render_call("edit_file", {"filepath": "a.py", "old_string": rand_string(r), "new_string": rand_string(r)})
    thought = "plan: " + "".join(r.choice("abc def\n`'\"") for _ in range(r.randint(0, 400)))
    shape = r.choice(["thought", "prefill", "none"])
    text = {"thought": "<|channel>thought\n" + thought + "<channel|>" + call,
            "prefill": thought + "<channel|>" + call, "none": "Sure. " + call}[shape]
    case = {"text": text, "tools": json.load(open(os.path.join(HERE, "..", "src/slipguard/data/tools_edit.json")))}
    a = env.targets[f"gg.{vt}.server"](case)
    b = env.targets[f"gg.{vt}.stream"](case)
    n += 1
    same = (a["calls"] == b["calls"] and (a.get("reasoning") or None) == (b.get("reasoning") or None)
            and ((a.get("content") or "").strip() == (b.get("content") or "").strip()))
    if not same:
        bad += 1
        if bad <= 3:
            print("MISMATCH", shape, {k: (str(a.get(k))[:80], str(b.get(k))[:80]) for k in ("calls", "reasoning", "content")})
print(vt, "cases", n, "mismatches", bad)
