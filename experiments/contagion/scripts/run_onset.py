"""PREREG_v2.3 'onset transplant' wrapper around the FROZEN scripts/run_injection.py (unchanged): plan pathways
  O0  P's first-edit (B1) state exactly as logged (= A's P0 render of the P context)
  O1  the same state with every historical tool result re-serialized as ADK + LiteLLM do for a tool that returns text:
      google-adk 1.36.1 wraps a non-dict function result as {'result': value} (flows/llm_flows/functions.py:1117,
      __build_response_event) and lite_llm._content_to_message_param sends _safe_json_serialize(response) =
      json.dumps(response, ensure_ascii=False) as the role=tool content (lite_llm.py:546, 803-809); LiteLLM 1.104 and
      vLLM 0.19.1 pass that string to the template unchanged (verified byte-for-byte against experiments/conformance/
      history/pipeline.py, the library-faithful ADK->LiteLLM->vLLM pipeline, by scripts/verify_onset_o1.py)
Both arms use pathway P0 / k 0 internally, the context's own (July) template and thinking ON; per-context seeds are shared
(common random numbers).
usage: run_onset.py <run_injection.py arguments>   (plan lines: {"id", "pathway": "O0"|"O1", "k": 0, ...})"""
import sys, os, copy, json, runpy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import variants as V


def adk_result_content(c):
    """ADK 1.36.1 + LiteLLM: role=tool content for a FunctionTool that returned the string c."""
    return json.dumps({'result': c}, ensure_ascii=False)


def o1_messages(msgs):
    out = copy.deepcopy(msgs)
    for m in out:
        if m.get('role') == 'tool' and isinstance(m.get('content'), str):
            m['content'] = adk_result_content(m['content'])
    return out


_bp = V.build_prompt


def build_prompt(tok, meta, pathway, k, which='old', closer=None, ctx=None):
    if pathway in ('O0', 'O1'):
        msgs, tools = ctx if ctx is not None else V.load_context(meta)
        if pathway == 'O1': msgs = o1_messages(msgs)
        return _bp(tok, meta, 'P0', 0, which=which, ctx=(msgs, tools))
    return _bp(tok, meta, pathway, k, which=which, closer=closer, ctx=ctx)


V.build_prompt = build_prompt
if __name__ == '__main__':
    sys.argv = [os.path.join(HERE, 'run_injection.py')] + sys.argv[1:]
    runpy.run_path(os.path.join(HERE, 'run_injection.py'), run_name='__main__')
